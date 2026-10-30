"""SP-02 发布端：按 V1.2 候选规范发模拟观测，并记录"我发了什么"。

用法示例：
  # 基线：100 条
  python publisher.py --count 100 --out evidence/sent_baseline.jsonl
  # 注入重复：先发 100 条，再把其中 5 条原样重发
  python publisher.py --count 100 --fault dup --out evidence/sent_dup.jsonl
  # 注入乱序：每 10 条打乱顺序
  python publisher.py --count 100 --fault shuffle --out evidence/sent_shuffle.jsonl
  # 注入重启：发到一半断开，换 boot_id、seq 归零再发
  python publisher.py --count 100 --fault restart --out evidence/sent_restart.jsonl

断连行为：Broker 不可用时消息进本地缓冲，重连后补发（对应"Broker 暂停/恢复"场景）。
缓冲期间的消息在 sent 日志里 buffered=true，发送成功后补记 ts_published。

⚠️ 主题命名 `aquaguard/<device_id>/observation` 与 status 通道是**假设**（A-01），
   需由组长/契约线确认；换主题只需改 --topic-prefix。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import deque

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from observation import (  # noqa: E402
    make_flow_value,
    make_observation,
    make_presence_value,
    make_water_value,
    now_iso,
)

CALIBRATION_ID = "SIM-CAL-0"  # 模拟标定，真实标定在 SP-01 产出


def build_observation(sensor_type: str, *, boot_id: str, seq: int, uptime_ms: int, scenario: str) -> dict:
    """按场景造一条观测。未知一律 null，不猜 false。"""
    device_id = DEVICE_ID

    if sensor_type == "flow":
        if scenario == "leak" or scenario == "walkaway":
            pulses, interval_ms, lpm = 60, 1000, 6.0
        else:
            pulses, interval_ms, lpm = 12, 1000, 1.2
        value = make_flow_value(pulses, interval_ms, lpm, CALIBRATION_ID)

    elif sensor_type == "water":
        wet = scenario == "leak"  # 漏水场景才湿
        value = make_water_value(wet)

    else:  # presence
        if scenario == "walkaway":
            value = make_presence_value(present=False, moving=False, still=False)
        elif scenario == "leak":
            value = make_presence_value(present=False, moving=False, still=False)
        else:
            value = make_presence_value(present=True, moving=True, still=False)

    return make_observation(
        device_id=device_id,
        sensor_type=sensor_type,
        value=value,
        boot_id=boot_id,
        seq=seq,
        uptime_ms=uptime_ms,
        time_basis="RECEIVED_FALLBACK",  # 模拟数据没有可信设备时钟 -> event_time 必须 null
        event_time=None,
        quality="valid",
        source="simulation",
    )


DEVICE_ID = "A001"
SENSOR_CYCLE = ("flow", "water", "presence")


class Publisher:
    def __init__(self, args):
        self.args = args
        self.buffer = deque()          # (observation, ts_attempt)
        self.sent_log = []             # 记录发送事实
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sp02-publisher-{random.randint(1000, 9999)}",
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        self.status_topic = f"{args.topic_prefix}/{DEVICE_ID}/status"
        self.obs_topic = f"{args.topic_prefix}/{DEVICE_ID}/observation"
        # 遗嘱：掉线时 Broker 自动发 offline
        self.client.will_set(
            self.status_topic,
            json.dumps({"status": "offline", "device_id": DEVICE_ID}, ensure_ascii=False),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=3)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            print(f"[pub] 连接失败 {reason_code}", flush=True)
            return
        print(f"[pub] 已连接 {self.args.host}:{self.args.port}", flush=True)
        client.publish(
            self.status_topic,
            json.dumps({"status": "online", "device_id": DEVICE_ID}, ensure_ascii=False),
            qos=1,
            retain=True,
        )
        self.flush_buffer()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        print(f"[pub] 连接断开 {reason_code}（之后的消息进缓冲）", flush=True)

    def ensure_connected(self, timeout=10.0):
        if self.client.is_connected():
            return True
        try:
            self.client.connect(self.args.host, self.args.port, keepalive=15)
        except Exception as exc:  # noqa: BLE001
            print(f"[pub] 连接失败：{exc}", flush=True)
            return False
        # 必须启动 paho 的网络线程，否则 publish 只会进队列、永远不会真正发出
        self.client.loop_start()
        deadline = time.time() + timeout
        while time.time() < deadline and not self.client.is_connected():
            time.sleep(0.1)
        if not self.client.is_connected():
            print("[pub] 等了 10 秒仍未连上", flush=True)
            return False
        return True

    def flush_buffer(self):
        if not self.buffer:
            return
        print(f"[pub] 开始补发缓冲 {len(self.buffer)} 条", flush=True)
        while self.buffer:
            obs, ts_attempt = self.buffer.popleft()
            rc = self._publish(obs)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                self.buffer.appendleft((obs, ts_attempt))
                print("[pub] 补发中断，剩余保留", flush=True)
                return
            self._record(obs, ts_attempt=ts_attempt, ts_published=now_iso(), buffered=True)

    def _publish(self, obs: dict) -> int:
        payload = json.dumps(obs, ensure_ascii=False, separators=(",", ":"))
        info = self.client.publish(self.obs_topic, payload, qos=1)
        return info.rc

    def _record(self, obs, *, ts_attempt, ts_published, buffered):
        self.sent_log.append(
            {
                "observation_id": obs["observation_id"],
                "device_id": obs["device_id"],
                "boot_id": obs["boot_id"],
                "seq": obs["seq"],
                "sensor_type": obs["sensor_type"],
                "ts_attempt": ts_attempt,
                "ts_published": ts_published,
                "buffered": buffered,
                "payload": obs,
            }
        )

    def send(self, obs: dict):
        ts_attempt = now_iso()
        if not self.client.is_connected():
            self.buffer.append((obs, ts_attempt))
            print(f"[pub] 离线，缓冲 {obs['sensor_type']} seq={obs['seq']}", flush=True)
            return
        rc = self._publish(obs)
        if rc == mqtt.MQTT_ERR_SUCCESS:
            self._record(obs, ts_attempt=ts_attempt, ts_published=now_iso(), buffered=False)
        else:
            self.buffer.append((obs, ts_attempt))
            print(f"[pub] 发布失败 rc={rc}，缓冲", flush=True)

    def run(self):
        a = self.args
        if not self.ensure_connected():
            raise SystemExit("[pub] Broker 连不上，请先启动 Broker")

        boot_id = f"{random.randint(0, 0xFFFF):04x}"
        start_mono = time.monotonic()
        seq = 0
        made = []

        def uptime_ms():
            return int((time.monotonic() - start_mono) * 1000)

        print(f"[pub] boot_id={boot_id} 场景={a.scenario} 故障模式={a.fault} 条数={a.count}", flush=True)

        batch = []
        for i in range(a.count):
            if a.fault == "restart" and i == a.count // 2:
                print("[pub] === 模拟发布端重启：断开、换 boot_id、seq 归零 ===", flush=True)
                self.client.loop_stop()
                self.client.disconnect()
                time.sleep(1.0)
                self.ensure_connected()
                boot_id = f"{random.randint(0, 0xFFFF):04x}"
                start_mono = time.monotonic()
                seq = 0
                print(f"[pub] 新 boot_id={boot_id}", flush=True)

            seq += 1
            sensor_type = SENSOR_CYCLE[i % len(SENSOR_CYCLE)]
            obs = build_observation(
                sensor_type,
                boot_id=boot_id,
                seq=seq,
                uptime_ms=uptime_ms(),
                scenario=a.scenario,
            )
            made.append(obs)

            if a.fault == "shuffle":
                # 乱序模式：先攒窗口，再打乱顺序整批发出去
                batch.append(obs)
                if len(batch) >= a.shuffle_window:
                    shuffled = batch[:]
                    random.shuffle(shuffled)
                    for o in shuffled:
                        self.send(o)
                    batch = []
            else:
                self.send(obs)

            time.sleep(1.0 / a.rate)

        # 乱序模式：把最后一个不满的窗口发掉
        if a.fault == "shuffle":
            for o in batch:
                self.send(o)

        # 等补发完成
        deadline = time.time() + a.flush_timeout
        while self.buffer and time.time() < deadline:
            time.sleep(0.2)
        if self.buffer:
            print(f"[pub] 警告：仍有 {len(self.buffer)} 条未发出（缓冲超时）", flush=True)

        # 注入重复：原样重发 5 条
        if a.fault == "dup":
            dup_src = made[: min(5, len(made))]
            print(f"[pub] 注入重复：重发 {len(dup_src)} 条（observation_id 与 seq 完全相同）", flush=True)
            for o in dup_src:
                self.client.publish(self.obs_topic, json.dumps(o, ensure_ascii=False, separators=(",", ":")), qos=1)
                full = dict(o)
                self.sent_log.append(
                    {
                        "observation_id": full["observation_id"],
                        "device_id": full["device_id"],
                        "boot_id": full["boot_id"],
                        "seq": full["seq"],
                        "sensor_type": full["sensor_type"],
                        "ts_attempt": now_iso(),
                        "ts_published": now_iso(),
                        "buffered": False,
                        "duplicate_injection": True,
                        "payload": full,
                    }
                )
                time.sleep(0.05)

        time.sleep(0.8)
        self.client.loop_stop()
        self.client.disconnect()

        # 落 sent 日志
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            for rec in self.sent_log:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[pub] 完成：发出记录 {len(self.sent_log)} 条 -> {a.out}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="SP-02 发布端（V1.2 模拟观测）")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18830)
    p.add_argument("--topic-prefix", default="aquaguard")
    p.add_argument("--count", type=int, default=100)
    p.add_argument("--rate", type=float, default=20.0, help="每秒条数")
    p.add_argument("--scenario", default="normal", choices=["normal", "leak", "walkaway"])
    p.add_argument("--fault", default="none", choices=["none", "dup", "shuffle", "restart"])
    p.add_argument("--shuffle-window", type=int, default=10)
    p.add_argument("--flush-timeout", type=float, default=20.0)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    Publisher(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

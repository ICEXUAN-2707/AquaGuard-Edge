"""SP-02 订阅端：把收到的原始消息原样落成 JSONL（证据文件）。

用法：
  python subscriber.py --host 127.0.0.1 --port 18830 --out evidence/raw.jsonl --duration 30

落盘格式（每行一个 JSON）：
  {"_recv_at": "2026-10-30T12:00:00.123+08:00",
   "_topic": "aquaguard/A001/observation",
   "_qos": 1,
   "_retain": false,
   "_payload_raw": "<原始字节解码后的字符串>",
   "_obs": { ...解析后的 DTO，解析失败时为 null... },
   "_parse_error": null}

注意：_recv_at / _topic 等是**证据侧字段**，不是 DTO 字段，不要发出去。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from observation import now_iso  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="SP-02 订阅端：原始消息落 JSONL")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18830)
    p.add_argument("--topic", default="aquaguard/+/observation", help="默认只订观测通道；status 通道另有用途")
    p.add_argument("--out", required=True, help="输出 JSONL 路径")
    p.add_argument("--duration", type=float, default=30, help="运行多少秒后退出")
    args = p.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fh = open(args.out, "w", encoding="utf-8", newline="\n")
    counter = {"n": 0}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            print(f"[sub] 连接失败 {reason_code}", flush=True)
            return
        client.subscribe(args.topic, qos=1)
        print(f"[sub] 已连接 {args.host}:{args.port} 订阅 {args.topic}", flush=True)

    def on_message(client, userdata, msg):
        counter["n"] += 1
        rec = {
            "_recv_at": now_iso(),
            "_topic": msg.topic,
            "_qos": msg.qos,
            "_retain": bool(msg.retain),
            "_payload_raw": msg.payload.decode("utf-8", errors="replace"),
            "_obs": None,
            "_parse_error": None,
        }
        try:
            rec["_obs"] = json.loads(rec["_payload_raw"])
        except Exception as exc:  # noqa: BLE001
            rec["_parse_error"] = f"{type(exc).__name__}: {exc}"
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        obs = rec["_obs"]
        tag = ""
        if isinstance(obs, dict):
            tag = f"{obs.get('sensor_type')} seq={obs.get('seq')}"
        print(f"[sub] #{counter['n']:>4} {msg.topic} {tag}", flush=True)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="sp02-subscriber",
        protocol=mqtt.MQTTv311,
        clean_session=True,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=2)
    client.connect_async(args.host, args.port, keepalive=15)
    client.loop_start()

    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        fh.close()
        print(f"[sub] 结束，收到 {counter['n']} 条 -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

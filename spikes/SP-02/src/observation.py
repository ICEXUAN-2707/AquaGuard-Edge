"""V1.2 候选规范 · SensorObservation 构造与校验（SP-02 用）

设计依据：reference/reference_02/00_Contracts_V1.2_修订候选.md 的 D1 条款。

关键约束（照抄自 D1，不要在这里"优化"）：
  1. 一个对象 = 一个 sensor_type = 一次观测。三种 value 载荷不能互换。
  2. 无法产出观测值的状态心跳走 MQTT status 通道，不伪造成 flow=0。
  3. quality=valid 时 water.wet / presence.present 必须已知；未知写 null，不能猜成 false。
  4. received_at 与非空 event_time 必须是带时区 ISO8601；
     time_basis=RECEIVED_FALLBACK 时 event_time 必须为 null。
  5. source 原始接入只有 hardware / simulation。

⚠️ 本文件的枚举 TIME_BASES 目前只确认了 RECEIVED_FALLBACK 一个值。
   另外两个时间基准的枚举名待契约线（C）确认，确认前代码里只用 RECEIVED_FALLBACK。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

SCHEMA_VERSION = "1.1"

SENSOR_TYPES = ("flow", "water", "presence")
QUALITIES = ("valid", "invalid", "unknown")
SOURCES = ("hardware", "simulation")
TIME_BASES = ("RECEIVED_FALLBACK",)  # 另两个枚举名待确认（见文件头）

# 东八区（比赛现场在 +08:00）
TZ_CN = timezone(timedelta(hours=8))

REQUIRED_KEYS = {
    "schema_version",
    "observation_id",
    "device_id",
    "sensor_type",
    "boot_id",
    "seq",
    "uptime_ms",
    "event_time",
    "received_at",
    "time_basis",
    "value",
    "quality",
    "source",
}

# 每种 sensor_type 的 value 必填子字段
VALUE_KEYS = {
    "flow": {"pulse_count", "interval_ms", "estimated_lpm", "calibration_id"},
    "water": {"wet"},
    "presence": {"present", "moving", "still"},
}


def now_iso() -> str:
    """带时区的当前时间（毫秒精度），用于 received_at。"""
    return datetime.now(TZ_CN).isoformat(timespec="milliseconds")


def parse_iso(value: str) -> datetime:
    """解析 ISO8601；要求必须带时区，否则抛 ValueError。"""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"时间必须带时区偏移：{value!r}")
    return dt


def make_flow_value(pulse_count: int, interval_ms: int, estimated_lpm: float, calibration_id: str) -> dict:
    return {
        "pulse_count": int(pulse_count),
        "interval_ms": int(interval_ms),
        "estimated_lpm": round(float(estimated_lpm), 3),
        "calibration_id": str(calibration_id),
    }


def make_water_value(wet):
    return {"wet": wet}


def make_presence_value(present, moving=None, still=None):
    return {"present": present, "moving": moving, "still": still}


def make_observation(
    *,
    device_id: str,
    sensor_type: str,
    value: dict,
    boot_id: str,
    seq: int,
    uptime_ms: int,
    received_at: str | None = None,
    event_time: str | None = None,
    time_basis: str = "RECEIVED_FALLBACK",
    quality: str = "valid",
    source: str = "simulation",
) -> dict:
    """构造一条符合 D1 的观测，并在返回前自校验。"""
    obs = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": str(uuid.uuid4()),
        "device_id": device_id,
        "sensor_type": sensor_type,
        "boot_id": boot_id,
        "seq": int(seq),
        "uptime_ms": int(uptime_ms),
        "event_time": event_time,
        "received_at": received_at or now_iso(),
        "time_basis": time_basis,
        "value": value,
        "quality": quality,
        "source": source,
    }
    validate(obs)
    return obs


def validate(obs: dict) -> None:
    """严格校验；不通过就抛 AssertionError（测试里直接断言）。"""
    if not isinstance(obs, dict):
        raise AssertionError("观测必须是 dict")

    keys = set(obs)
    missing = REQUIRED_KEYS - keys
    extra = keys - REQUIRED_KEYS
    if missing:
        raise AssertionError(f"缺少必填字段：{sorted(missing)}")
    if extra:
        # 这一条专门防"把 prototype_only 之类的实验标记塞进 DTO"
        raise AssertionError(f"不允许的额外字段：{sorted(extra)}")

    if obs["schema_version"] != SCHEMA_VERSION:
        raise AssertionError(f"schema_version 必须是 {SCHEMA_VERSION!r}，实际 {obs['schema_version']!r}")
    if not isinstance(obs["observation_id"], str) or not obs["observation_id"].strip():
        raise AssertionError("observation_id 必须是非空字符串")
    if not isinstance(obs["device_id"], str) or not obs["device_id"].strip():
        raise AssertionError("device_id 必须是非空字符串")
    if not isinstance(obs["boot_id"], str) or not obs["boot_id"].strip():
        raise AssertionError("boot_id 必须是非空字符串")
    if not isinstance(obs["seq"], int) or obs["seq"] < 0:
        raise AssertionError("seq 必须是 >=0 的 int")
    if not isinstance(obs["uptime_ms"], int) or obs["uptime_ms"] < 0:
        raise AssertionError("uptime_ms 必须是 >=0 的 int")

    if obs["sensor_type"] not in SENSOR_TYPES:
        raise AssertionError(f"sensor_type 只能是 {SENSOR_TYPES}")
    if obs["quality"] not in QUALITIES:
        raise AssertionError(f"quality 只能是 {QUALITIES}（stale/duplicate/late 是后处理标签，不是接入层 quality）")
    if obs["source"] not in SOURCES:
        raise AssertionError(f"source 原始接入只能是 {SOURCES}")
    if obs["time_basis"] not in TIME_BASES:
        raise AssertionError(f"time_basis 目前只接受 {TIME_BASES}，见文件头说明")

    # ---- 时间规则 ----
    if not isinstance(obs["received_at"], str) or not obs["received_at"]:
        raise AssertionError("received_at 必须是非空字符串")
    parse_iso(obs["received_at"])
    if obs["time_basis"] == "RECEIVED_FALLBACK":
        if obs["event_time"] is not None:
            raise AssertionError("time_basis=RECEIVED_FALLBACK 时 event_time 必须为 null")
    else:
        if obs["event_time"] is None:
            raise AssertionError("非 RECEIVED_FALLBACK 时 event_time 必须非空")
        parse_iso(obs["event_time"])

    # ---- value 规则 ----
    value = obs["value"]
    if not isinstance(value, dict):
        raise AssertionError("value 必须是 dict")
    want = VALUE_KEYS[obs["sensor_type"]]
    if set(value) != want:
        raise AssertionError(
            f"sensor_type={obs['sensor_type']} 的 value 必须恰好包含 {sorted(want)}，实际 {sorted(value)}"
        )

    def _is_bool_or_null(x):
        return x is None or isinstance(x, bool)

    if obs["sensor_type"] == "flow":
        pc, im, lpm, cid = value["pulse_count"], value["interval_ms"], value["estimated_lpm"], value["calibration_id"]
        if not isinstance(pc, int) or isinstance(pc, bool) or pc < 0:
            raise AssertionError("flow.pulse_count 必须是 >=0 的 int")
        if not isinstance(im, int) or isinstance(im, bool) or im <= 0:
            raise AssertionError("flow.interval_ms 必须是 >0 的 int")
        if isinstance(lpm, bool) or not isinstance(lpm, (int, float)) or lpm < 0:
            raise AssertionError("flow.estimated_lpm 必须是 >=0 的 number")
        if not isinstance(cid, str) or not cid.strip():
            raise AssertionError("flow.calibration_id 必须是非空字符串")

    elif obs["sensor_type"] == "water":
        if not _is_bool_or_null(value["wet"]):
            raise AssertionError("water.wet 必须是 boolean 或 null")
        if obs["quality"] == "valid" and value["wet"] is None:
            raise AssertionError("quality=valid 时 water.wet 必须已知（未知请写 quality=unknown 且 wet=null）")

    else:  # presence
        for k in ("present", "moving", "still"):
            if not _is_bool_or_null(value[k]):
                raise AssertionError(f"presence.{k} 必须是 boolean 或 null")
        if obs["quality"] == "valid" and value["present"] is None:
            raise AssertionError("quality=valid 时 presence.present 必须已知")


def is_duplicate(a: dict, b: dict) -> bool:
    """D1 定义：同一设备、同一轮启动、同一传感器的同一个序号又收到一次。"""
    return (
        a["device_id"] == b["device_id"]
        and a["boot_id"] == b["boot_id"]
        and a["sensor_type"] == b["sensor_type"]
        and a["seq"] == b["seq"]
    )

"""SP-02 单元测试：V1.2 观测构造与校验（D1 条款）。

跑：python -m pytest spikes/SP-02/tests -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from observation import (  # noqa: E402
    is_duplicate,
    make_flow_value,
    make_observation,
    make_presence_value,
    make_water_value,
    now_iso,
    validate,
)

BASE = dict(device_id="A001", boot_id="ab12", seq=1, uptime_ms=1000)


def flow_obs(**kw):
    args = dict(BASE)
    args.update(kw)
    return make_observation(sensor_type="flow", value=make_flow_value(10, 1000, 1.2, "SIM-CAL-0"), **args)


def test_valid_flow_observation_passes():
    obs = flow_obs()
    validate(obs)
    assert obs["schema_version"] == "1.1"
    assert obs["time_basis"] == "RECEIVED_FALLBACK"
    assert obs["event_time"] is None


def test_valid_water_and_presence_pass():
    validate(make_observation(sensor_type="water", value=make_water_value(False), **BASE))
    validate(make_observation(sensor_type="presence", value=make_presence_value(True, True, False), **BASE))


def test_extra_field_is_rejected():
    """实验标记不能塞进 DTO —— 这是任务单点名的一条。"""
    obs = flow_obs()
    obs["prototype_only"] = True
    with pytest.raises(AssertionError, match="额外字段"):
        validate(obs)


def test_missing_field_is_rejected():
    obs = flow_obs()
    del obs["received_at"]
    with pytest.raises(AssertionError, match="缺少必填字段"):
        validate(obs)


def test_wrong_schema_version_rejected():
    obs = flow_obs()
    obs["schema_version"] = "1.0"
    with pytest.raises(AssertionError, match="schema_version"):
        validate(obs)


def test_received_fallback_must_have_null_event_time():
    with pytest.raises(AssertionError, match="event_time 必须为 null"):
        make_observation(
            sensor_type="water",
            value=make_water_value(True),
            event_time=now_iso(),
            time_basis="RECEIVED_FALLBACK",
            **BASE,
        )


def test_received_at_must_have_timezone():
    with pytest.raises(ValueError):
        make_observation(
            sensor_type="water",
            value=make_water_value(True),
            received_at="2026-10-30T12:00:00",  # 没有时区
            **BASE,
        )


def test_valid_quality_requires_known_values():
    """quality=valid 时不能把未知写成 null。"""
    with pytest.raises(AssertionError, match="wet 必须已知"):
        make_observation(sensor_type="water", value=make_water_value(None), quality="valid", **BASE)
    with pytest.raises(AssertionError, match="present 必须已知"):
        make_observation(sensor_type="presence", value=make_presence_value(None, None, None), quality="valid", **BASE)


def test_unknown_quality_allows_null_but_not_false():
    """未知写 null（允许），不许猜成 false。"""
    obs = make_observation(sensor_type="water", value=make_water_value(None), quality="unknown", **BASE)
    validate(obs)
    obs2 = make_observation(sensor_type="water", value=make_water_value(False), quality="unknown", **BASE)
    validate(obs2)  # 但 false 是"确定是干的"，不是未知；这条只保证校验不崩


def test_value_keys_are_strict_per_sensor_type():
    obs = flow_obs()
    obs["value"]["wet"] = True  # 把 water 字段塞进 flow
    with pytest.raises(AssertionError, match="value 必须恰好包含"):
        validate(obs)


def test_flow_interval_must_be_positive():
    with pytest.raises(AssertionError, match="interval_ms"):
        make_observation(sensor_type="flow", value=make_flow_value(1, 0, 0.1, "CAL"), **BASE)


def test_quality_enum_is_strict():
    obs = flow_obs()
    obs["quality"] = "stale"  # stale 是后处理标签，不是接入层 quality
    with pytest.raises(AssertionError, match="quality"):
        validate(obs)


def test_source_only_hardware_or_simulation():
    obs = flow_obs()
    obs["source"] = "cloud"
    with pytest.raises(AssertionError, match="source"):
        validate(obs)


def test_is_duplicate_uses_d1_key():
    a = make_observation(sensor_type="water", value=make_water_value(True), **BASE)
    b = make_observation(sensor_type="water", value=make_water_value(True), **BASE)  # 同 boot/seq/type
    c = make_observation(
        sensor_type="water", value=make_water_value(True), device_id="A002", boot_id="ab12", seq=1, uptime_ms=1000
    )
    assert a["observation_id"] != b["observation_id"]
    assert is_duplicate(a, b) is True
    assert is_duplicate(a, c) is False

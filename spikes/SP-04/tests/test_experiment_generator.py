"""Deterministic generator and anomaly coverage tests."""

from datetime import datetime

from experiment.generate import generate_trials
from experiment_testlib import MANIFEST, trial


def _received(row: dict) -> datetime:
    return datetime.fromisoformat(row["received_at"])


def _event(row: dict) -> datetime:
    return datetime.fromisoformat(row["event_time"])


def test_same_seed_produces_identical_rows():
    first = generate_trials(MANIFEST, scenario_ids=["async_sources"])[0]
    second = generate_trials(MANIFEST, scenario_ids=["async_sources"])[0]
    assert first.rows == second.rows
    assert first.window_ends == second.window_ends


def test_train_and_eval_seeds_are_independent_trials():
    train = trial("async_sources", "train")
    evaluate = trial("async_sources", "eval")
    assert train.trial_id != evaluate.trial_id
    assert [row["received_at"] for row in train.rows] != [row["received_at"] for row in evaluate.rows]


def test_rows_are_dto_valid_and_never_future_dated():
    from edge.contracts.models import validate_raw_observation

    for item in generate_trials(MANIFEST):
        assert item.rows
        for row in item.rows:
            observation = validate_raw_observation(row)
            assert observation.device_id == MANIFEST["device_id"]
            assert observation.event_time is not None
            assert observation.event_time <= observation.received_at
        received = [_received(row) for row in item.rows]
        assert received == sorted(received)


def test_duplicate_anomaly_retransmits_rows():
    item = trial("duplicates")
    identities = [row["observation_id"] for row in item.rows]
    assert len(identities) > len(set(identities))
    grouped = {}
    for row in item.rows:
        grouped.setdefault(row["observation_id"], []).append(row)
    assert max(len(group) for group in grouped.values()) == 2
    assert sum(1 for group in grouped.values() if len(group) == 2) == len(identities) - len(set(identities))


def test_late_presence_anomaly_delays_only_presence_after_thirty_seconds():
    item = trial("late_presence")
    delayed = [
        row for row in item.rows
        if row["sensor_type"] == "presence" and (_event(row) - _event(item.rows[0])).total_seconds() >= 30
    ]
    assert delayed and all((_received(row) - _event(row)).total_seconds() >= 8 for row in delayed)
    assert all((_received(row) - _event(row)).total_seconds() < 8 for row in item.rows if row["sensor_type"] != "presence")


def test_restart_changes_boot_and_never_publishes_old_boot_state_afterwards():
    item = trial("restart")
    boots = [row["boot_id"] for row in item.rows]
    assert set(boots) == {"a", "b"}
    first_boot_b = next(row for row in item.rows if row["boot_id"] == "b")
    assert (_event(first_boot_b) - _event(item.rows[0])).total_seconds() == 25
    assert all((_event(row) - _event(item.rows[0])).total_seconds() >= 25 for row in item.rows if row["boot_id"] == "b")
    assert all((_event(row) - _event(item.rows[0])).total_seconds() < 25 for row in item.rows if row["boot_id"] == "a")


def test_stop_reporting_and_sampling_change_anomalies():
    flow_stop = trial("flow_stop")
    assert not [row for row in flow_stop.rows if row["sensor_type"] == "flow" and (_event(row) - _event(flow_stop.rows[0])).total_seconds() > 20]
    presence_stop = trial("presence_stop")
    assert not [row for row in presence_stop.rows if row["sensor_type"] == "presence" and (_event(row) - _event(presence_stop.rows[0])).total_seconds() > 15]
    slow = trial("slow_presence")
    offsets = sorted({(_event(row) - _event(slow.rows[0])).total_seconds() for row in slow.rows if row["sensor_type"] == "presence"})
    assert offsets == [0, 5, 10, 15, 20, 35]


def test_presence_miss_reports_absent_while_operation_is_present():
    item = trial("presence_miss")
    presence = [row for row in item.rows if row["sensor_type"] == "presence"]
    assert presence and all(row["value"]["present"] is False for row in presence)


def test_window_ends_match_frozen_manifest():
    for item in generate_trials(MANIFEST):
        origin = _event(item.rows[0])
        offsets = [int((end - origin).total_seconds()) for end in item.window_ends]
        assert offsets == MANIFEST["window_ends_sec"]
        assert item.window_ends_sec == MANIFEST["window_ends_sec"]

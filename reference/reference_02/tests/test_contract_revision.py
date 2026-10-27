"""Contract 1.1 candidate: shape, negative cases, and joined fixture checks."""

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


BASE = Path(__file__).resolve().parents[1] / "contracts"
EXAMPLES = json.loads((BASE / "examples.json").read_text(encoding="utf-8"))
SCENARIO = json.loads((BASE / "scenario_s01.json").read_text(encoding="utf-8"))


def validate(name, payload):
    schema = json.loads((BASE / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


@pytest.mark.parametrize("name", [name for name in EXAMPLES if name != "ApiError"])
def test_old_1_0_dto_is_not_silently_accepted(name):
    payload = copy.deepcopy(EXAMPLES[name])
    payload["schema_version"] = "1.0"
    with pytest.raises(ValidationError):
        validate(name, payload)


@pytest.mark.parametrize("sensor_type,value", [
    ("flow", {"pulse_count": 2, "interval_ms": 1000, "estimated_lpm": 0.5, "calibration_id": "cal-v1"}),
    ("water", {"wet": True}),
    ("presence", {"present": True, "moving": False, "still": True}),
])
def test_three_observation_shapes(sensor_type, value):
    payload = copy.deepcopy(EXAMPLES["SensorObservation"])
    payload.update(sensor_type=sensor_type, value=value)
    validate("SensorObservation", payload)


@pytest.mark.parametrize("sensor_type,value", [
    ("flow", {"wet": True}),
    ("water", {"present": False, "moving": False, "still": False}),
    ("presence", {"pulse_count": 2, "interval_ms": 1000, "estimated_lpm": 0.5, "calibration_id": "cal-v1"}),
])
def test_sensor_type_value_mismatch_rejected(sensor_type, value):
    payload = copy.deepcopy(EXAMPLES["SensorObservation"])
    payload.update(sensor_type=sensor_type, value=value)
    with pytest.raises(ValidationError):
        validate("SensorObservation", payload)


@pytest.mark.parametrize("sensor_type,value", [
    ("water", {"wet": None}),
    ("presence", {"present": None, "moving": None, "still": None}),
])
def test_explicit_unknown_observation_is_representable(sensor_type, value):
    payload = copy.deepcopy(EXAMPLES["SensorObservation"])
    payload.update(sensor_type=sensor_type, value=value, quality="unknown")
    validate("SensorObservation", payload)


def test_all_missing_features_are_representable():
    payload = copy.deepcopy(EXAMPLES["FeatureWindow"])
    payload["missing_mask"] = {"flow": True, "water": True, "presence": True}
    payload["features"] = {
        "flow_mean_lpm": None, "flow_max_lpm": None, "flow_active_ratio": None,
        "flow_streak_sec": None, "flow_change_count": None,
        "water_contact": None, "water_contact_sec": None,
        "presence_state": "unknown", "presence_occupied_ratio": None,
        "presence_transition_count": None, "absence_after_flow_sec": None,
        "data_coverage_ratio": 0,
    }
    validate("FeatureWindow", payload)


def test_three_summaries_required():
    payload = copy.deepcopy(EXAMPLES["AlignedWindow"])
    validate("AlignedWindow", payload)
    del payload["sensor_summary"]["flow"]
    with pytest.raises(ValidationError):
        validate("AlignedWindow", payload)


def test_generic_and_version_errors_have_distinct_details():
    payload = copy.deepcopy(EXAMPLES["ApiError"])
    payload.update(code="NOT_FOUND", details={})
    validate("ApiError", payload)
    payload["details"] = {"expected_version": 1, "actual_version": 2}
    with pytest.raises(ValidationError):
        validate("ApiError", payload)
    payload.update(code="VERSION_CONFLICT", details={})
    with pytest.raises(ValidationError):
        validate("ApiError", payload)


@pytest.mark.parametrize("name,path,value", [
    ("SensorObservation", ("source",), "replay"),
    ("SensorObservation", ("received_at",), "yesterday"),
    ("SafetyEvent", ("lifecycle",), "BANANA"),
    ("FeatureWindow", ("features", "data_coverage_ratio"), 2),
    ("CloudSyncRecord", ("attempts",), -1),
    ("SituationAssessment", ("model_score",), 0.99),
])
def test_semantic_outer_constraints_reject_bad_values(name, path, value):
    payload = copy.deepcopy(EXAMPLES[name])
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        validate(name, payload)


def test_joined_fixture_references_match_type_device_and_origin():
    observations = [EXAMPLES["SensorObservation"], *SCENARIO["additional_observations"]]
    for observation in observations:
        validate("SensorObservation", observation)
    by_id = {item["observation_id"]: item for item in observations}
    assert len(by_id) == len(observations)
    window = EXAMPLES["AlignedWindow"]
    assert set(window["source_observation_ids"]) == set(by_id)
    assert {item["sensor_type"] for item in observations} == {"flow", "water", "presence"}
    signal = EXAMPLES["SafetySignal"]
    assert all(by_id[ref]["sensor_type"] == "water" for ref in signal["observation_refs"])
    assert {item["device_id"] for item in observations} == {window["device_id"]}
    window_end = datetime.fromisoformat(window["window_end"])
    for sensor_type, summary in window["sensor_summary"].items():
        observation = next(item for item in observations if item["sensor_type"] == sensor_type)
        age = (window_end - datetime.fromisoformat(observation["received_at"])).total_seconds()
        assert summary["age_sec"] == age
    assert all(item["source"] == "simulation" for item in observations)
    assert all(EXAMPLES[name]["origin"] == "simulation" for name in (
        "AlignedWindow", "FeatureWindow", "SituationAssessment", "SafetySignal",
        "SafetyEvent", "EventTransition", "CloudSyncRecord",
    ))
    assert EXAMPLES["EventTransition"]["event_id"] == EXAMPLES["SafetyEvent"]["event_id"]
    assert EXAMPLES["CloudSyncRecord"]["transition_id"] == EXAMPLES["EventTransition"]["transition_id"]
    assert signal["observed_at"] == by_id["obs-water-1"]["received_at"]
    assert EXAMPLES["SafetyEvent"]["created_at"] == signal["observed_at"]

"""Candidate DTO behavior that JSON Schema alone cannot establish."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import edge.contracts as dto


BASE = Path(__file__).resolve().parents[2] / "reference" / "reference_02" / "contracts"
EXAMPLES = json.loads((BASE / "examples.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_all_public_examples_validate(name):
    getattr(dto, name).model_validate(EXAMPLES[name])


@pytest.mark.parametrize("change", [
    {"sensor_type": "flow", "value": {"wet": True}},
    {"sensor_type": "water", "value": {"wet": None}, "quality": "valid"},
    {"sensor_type": "presence", "value": {"present": False, "moving": True, "still": False}},
    {"time_basis": "DEVICE_SYNCED", "event_time": None},
    {"time_basis": "RECEIVED_FALLBACK", "event_time": "2026-10-26T14:00:00+08:00"},
    {"received_at": "2026-10-26T14:00:00"},
    {"received_at": "yesterday"},
])
def test_observation_rejects_cross_field_errors(change):
    payload = copy.deepcopy(EXAMPLES["SensorObservation"])
    payload.update(change)
    with pytest.raises(ValidationError):
        dto.SensorObservation.model_validate(payload)


def test_explicit_unknown_is_valid_but_not_false():
    payload = copy.deepcopy(EXAMPLES["SensorObservation"])
    payload.update(sensor_type="presence", value={"present": None, "moving": None, "still": None}, quality="unknown")
    result = dto.SensorObservation.model_validate(payload)
    assert result.value.present is None


def test_raw_ingress_rejects_post_processing_quality():
    payload = copy.deepcopy(EXAMPLES["SensorObservation"])
    dto.validate_raw_observation(payload)
    payload["quality"] = "stale"
    with pytest.raises(ValueError):
        dto.validate_raw_observation(payload)


def test_three_source_silence_is_representable():
    aligned = copy.deepcopy(EXAMPLES["AlignedWindow"])
    aligned["sensor_summary"] = {
        key: {"state": "unknown", "age_sec": None, "coverage_ratio": 0}
        for key in ("flow", "water", "presence")
    }
    aligned["source_observation_ids"] = []
    aligned["origin"] = "unknown"
    dto.AlignedWindow.model_validate(aligned)

    feature = copy.deepcopy(EXAMPLES["FeatureWindow"])
    feature["missing_mask"] = {"flow": True, "water": True, "presence": True}
    feature["features"] = {
        "flow_mean_lpm": None, "flow_max_lpm": None, "flow_active_ratio": None,
        "flow_streak_sec": None, "flow_change_count": None,
        "water_contact": None, "water_contact_sec": None,
        "presence_state": "unknown", "presence_occupied_ratio": None,
        "presence_transition_count": None, "absence_after_flow_sec": None,
        "data_coverage_ratio": 0,
    }
    feature["origin"] = "unknown"
    dto.FeatureWindow.model_validate(feature)


def test_missing_water_cannot_be_reported_as_dry():
    feature = copy.deepcopy(EXAMPLES["FeatureWindow"])
    feature["missing_mask"]["water"] = True
    feature["features"]["water_contact"] = False
    with pytest.raises(ValidationError):
        dto.FeatureWindow.model_validate(feature)


def test_unknown_summary_requires_null_age():
    aligned = copy.deepcopy(EXAMPLES["AlignedWindow"])
    aligned["sensor_summary"]["water"]["state"] = "unknown"
    with pytest.raises(ValidationError):
        dto.AlignedWindow.model_validate(aligned)


def test_rules_score_and_unavailable_assessment_rejected():
    assessment = copy.deepcopy(EXAMPLES["SituationAssessment"])
    assessment["model_score"] = 0.99
    with pytest.raises(ValidationError):
        dto.SituationAssessment.model_validate(assessment)
    assessment["model_score"] = None
    assessment["data_quality"] = "UNAVAILABLE"
    with pytest.raises(ValidationError):
        dto.SituationAssessment.model_validate(assessment)


def test_accepted_sync_requires_transport_receipt():
    sync = copy.deepcopy(EXAMPLES["CloudSyncRecord"])
    sync["sync_status"] = "ACCEPTED"
    with pytest.raises(ValidationError):
        dto.CloudSyncRecord.model_validate(sync)
    sync["transport_receipt"] = {
        "provider": "iotda", "receipt_id": "ack-1", "received_at": "2026-10-26T14:00:11+08:00"
    }
    dto.CloudSyncRecord.model_validate(sync)


def test_retry_wait_requires_next_retry_time():
    sync = copy.deepcopy(EXAMPLES["CloudSyncRecord"])
    sync["sync_status"] = "RETRY_WAIT"
    with pytest.raises(ValidationError):
        dto.CloudSyncRecord.model_validate(sync)


def test_error_details_follow_code():
    error = copy.deepcopy(EXAMPLES["ApiError"])
    error.update(code="NOT_FOUND", details={})
    dto.ApiError.model_validate(error)
    error["details"] = {"expected_version": 2, "actual_version": 3}
    with pytest.raises(ValidationError):
        dto.ApiError.model_validate(error)

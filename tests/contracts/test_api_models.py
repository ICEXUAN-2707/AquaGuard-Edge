"""Machine-readable candidate API request/response contracts."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from edge.contracts import (
    AckRequest, AckResponse, AssessmentResponse, EventDetailResponse,
    EventListResponse, ExperimentResult, LiveSnapshot, SyncStatus,
)


BASE = Path(__file__).resolve().parents[2] / "reference" / "reference_02" / "contracts"
EXAMPLES = json.loads((BASE / "examples.json").read_text(encoding="utf-8"))


def test_seven_route_response_shapes():
    LiveSnapshot.model_validate({
        "schema_version": "1.1", "device_id": "home01",
        "captured_at": "2026-10-26T14:00:32+08:00",
        "sensor_summary": EXAMPLES["AlignedWindow"]["sensor_summary"],
        "data_quality": "VALID", "cloud_status": "OFFLINE", "origin": "simulation",
    })
    AssessmentResponse.model_validate({
        "schema_version": "1.1", "assessment": EXAMPLES["SituationAssessment"],
        "safety_signals": [EXAMPLES["SafetySignal"]],
    })
    EventListResponse.model_validate({
        "schema_version": "1.1", "items": [EXAMPLES["SafetyEvent"]], "next_cursor": None,
    })
    EventDetailResponse.model_validate({
        "schema_version": "1.1", "event": EXAMPLES["SafetyEvent"],
        "transitions": [EXAMPLES["EventTransition"]],
    })
    AckRequest.model_validate({"schema_version": "1.1", "expected_version": 1, "idempotency_key": "ack-1", "ack_type": "ACKNOWLEDGE"})
    AckResponse.model_validate({
        "schema_version": "1.1", "event": EXAMPLES["SafetyEvent"], "transition_id": "tr-1",
    })
    SyncStatus.model_validate({
        "schema_version": "1.1", "device_id": "home01", "pending_count": 1,
        "failed_count": 0, "last_ack_level": "NONE", "last_accepted_at": None,
    })
    ExperimentResult.model_validate({
        "schema_version": "1.1", "trial_id": "trial-1", "source": "simulation",
        "status": "PLANNED", "started_at": None, "ended_at": None, "asset_refs": [],
    })


def test_event_detail_rejects_version_gap_and_origin_mismatch():
    payload = {"schema_version": "1.1", "event": EXAMPLES["SafetyEvent"],
               "transitions": [EXAMPLES["EventTransition"]]}
    payload = copy.deepcopy(payload)
    payload["transitions"][0]["event_version"] = 2
    with pytest.raises(ValidationError):
        EventDetailResponse.model_validate(payload)
    payload["transitions"][0]["event_version"] = 1
    payload["transitions"][0]["origin"] = "hardware"
    with pytest.raises(ValidationError):
        EventDetailResponse.model_validate(payload)


def test_ack_request_rejects_empty_key_and_stale_shape():
    with pytest.raises(ValidationError):
        AckRequest.model_validate({"schema_version": "1.1", "expected_version": 0, "idempotency_key": "", "ack_type": "ACKNOWLEDGE"})
    with pytest.raises(ValidationError):
        AckRequest.model_validate({"schema_version": "1.1", "expected_version": 1, "idempotency_key": "ack-1", "ack_type": "CLOSE"})


def test_sync_status_does_not_invent_ack_time():
    with pytest.raises(ValidationError):
        SyncStatus.model_validate({
            "schema_version": "1.1", "device_id": None, "pending_count": 0,
            "failed_count": 0, "last_ack_level": "TRANSPORT", "last_accepted_at": None,
        })

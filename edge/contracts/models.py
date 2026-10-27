"""Semantic validation for the candidate public DTO contract.

These models validate one object at a time. Identity, lineage, state transitions and
database uniqueness require the integration gates described in the contract spec.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Origin = Literal["hardware", "simulation", "mixed", "unknown"]
OFFSET_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$")


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _aware(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO8601 string")
    if OFFSET_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("timestamp must include seconds and an explicit timezone offset")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


class FlowValue(DTO):
    pulse_count: int = Field(ge=0)
    interval_ms: int = Field(gt=0)
    estimated_lpm: float = Field(ge=0)
    calibration_id: str = Field(min_length=1)


class WaterValue(DTO):
    wet: bool | None


class PresenceValue(DTO):
    present: bool | None
    moving: bool | None
    still: bool | None

    @model_validator(mode="after")
    def consistent(self) -> "PresenceValue":
        if self.present is False and (self.moving is True or self.still is True):
            raise ValueError("moving/still cannot be true when present is false")
        if self.moving is True and self.still is True:
            raise ValueError("moving and still cannot both be true")
        return self


class SensorObservation(DTO):
    schema_version: Literal["1.1"]
    observation_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    sensor_type: Literal["flow", "water", "presence"]
    boot_id: str = Field(min_length=1)
    seq: int = Field(ge=0)
    uptime_ms: int = Field(ge=0)
    event_time: datetime | None
    received_at: datetime
    time_basis: Literal["DEVICE_SYNCED", "EDGE_MAPPED", "RECEIVED_FALLBACK"]
    value: FlowValue | WaterValue | PresenceValue
    quality: Literal["valid", "invalid", "unknown", "stale", "duplicate", "late"]
    source: Literal["hardware", "simulation"]

    @field_validator("event_time", "received_at", mode="before")
    @classmethod
    def aware_times(cls, value: object) -> datetime | None:
        return None if value is None else _aware(value)

    @model_validator(mode="after")
    def consistent(self) -> "SensorObservation":
        expected = {"flow": FlowValue, "water": WaterValue, "presence": PresenceValue}
        if type(self.value) is not expected[self.sensor_type]:
            raise ValueError("sensor_type and value shape disagree")
        if self.time_basis == "RECEIVED_FALLBACK" and self.event_time is not None:
            raise ValueError("fallback observations must have event_time=null")
        if self.time_basis != "RECEIVED_FALLBACK" and self.event_time is None:
            raise ValueError("mapped/synced observations require event_time")
        if self.quality == "valid":
            if isinstance(self.value, WaterValue) and self.value.wet is None:
                raise ValueError("valid water observation requires known wet value")
            if isinstance(self.value, PresenceValue) and self.value.present is None:
                raise ValueError("valid presence observation requires known present value")
        return self


def validate_raw_observation(payload: dict[str, object]) -> SensorObservation:
    """Apply the narrower M2 ingress quality contract before post-processing."""
    observation = SensorObservation.model_validate(payload)
    if observation.quality not in ("valid", "invalid", "unknown"):
        raise ValueError("raw observation quality must be valid, invalid, or unknown")
    return observation


class Summary(DTO):
    state: str
    age_sec: float | None = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def age_matches_state(self) -> "Summary":
        if (self.state == "unknown") != (self.age_sec is None):
            raise ValueError("unknown state requires null age; known state requires age")
        return self


class FlowSummary(Summary):
    state: Literal["active", "inactive", "unknown"]


class WaterSummary(Summary):
    state: Literal["wet", "dry", "unknown"]


class PresenceSummary(Summary):
    state: Literal["present", "absent", "unknown"]


class SensorSummary(DTO):
    flow: FlowSummary
    water: WaterSummary
    presence: PresenceSummary


class AlignedWindow(DTO):
    schema_version: Literal["1.1"]
    window_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    published_at: datetime
    alignment_config_version: str = Field(min_length=1)
    sensor_summary: SensorSummary
    origin: Origin
    quality_flags: list[str]
    source_observation_ids: list[str]

    @field_validator("window_start", "window_end", "published_at", mode="before")
    @classmethod
    def aware_times(cls, value: object) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def ordered(self) -> "AlignedWindow":
        if not self.window_start < self.window_end <= self.published_at:
            raise ValueError("window_start < window_end <= published_at is required")
        if len(set(self.source_observation_ids)) != len(self.source_observation_ids):
            raise ValueError("duplicate source observation ID")
        return self


NullableNonnegative = float | None


class Features(DTO):
    flow_mean_lpm: NullableNonnegative = Field(ge=0)
    flow_max_lpm: NullableNonnegative = Field(ge=0)
    flow_active_ratio: NullableNonnegative = Field(ge=0, le=1)
    flow_streak_sec: NullableNonnegative = Field(ge=0)
    flow_change_count: int | None = Field(ge=0)
    water_contact: bool | None
    water_contact_sec: NullableNonnegative = Field(ge=0)
    presence_state: Literal["present", "absent", "unknown"]
    presence_occupied_ratio: NullableNonnegative = Field(ge=0, le=1)
    presence_transition_count: int | None = Field(ge=0)
    absence_after_flow_sec: NullableNonnegative = Field(ge=0)
    data_coverage_ratio: float = Field(ge=0, le=1)


class MissingMask(DTO):
    flow: bool
    water: bool
    presence: bool


class FeatureWindow(DTO):
    schema_version: Literal["1.1"]
    window_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    features: Features
    missing_mask: MissingMask
    state_checkpoint_ref: str = Field(min_length=1)
    origin: Origin

    @model_validator(mode="after")
    def missing_values(self) -> "FeatureWindow":
        f, m = self.features, self.missing_mask
        if m.flow and any(getattr(f, key) is not None for key in (
            "flow_mean_lpm", "flow_max_lpm", "flow_active_ratio", "flow_streak_sec", "flow_change_count"
        )):
            raise ValueError("missing flow cannot have flow features")
        if m.water and (f.water_contact is not None or f.water_contact_sec is not None):
            raise ValueError("missing water cannot have water features")
        if m.presence and (f.presence_state != "unknown" or f.presence_occupied_ratio is not None or f.presence_transition_count is not None):
            raise ValueError("missing presence cannot have presence features")
        if (m.flow or m.presence) and f.absence_after_flow_sec is not None:
            raise ValueError("absence_after_flow_sec requires flow and presence evidence")
        if m.flow and m.water and m.presence and f.data_coverage_ratio != 0:
            raise ValueError("all sources missing requires zero coverage")
        return self


class SituationAssessment(DTO):
    schema_version: Literal["1.1"]
    assessment_id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    situation: Literal["IDLE", "ATTENDED_FLOW", "POSSIBLE_UNATTENDED_FLOW", "UNKNOWN"]
    inference_mode: Literal["rules", "ml", "fallback"]
    model_version: str = Field(min_length=1)
    model_score: float | None
    data_quality: Literal["VALID", "DEGRADED", "UNAVAILABLE"]
    reason_codes: list[str]
    origin: Origin

    @model_validator(mode="after")
    def quality_rules(self) -> "SituationAssessment":
        if self.inference_mode in ("rules", "fallback") and self.model_score is not None:
            raise ValueError("rules/fallback model_score must be null")
        if self.data_quality == "UNAVAILABLE" and self.situation != "UNKNOWN":
            raise ValueError("unavailable data requires UNKNOWN situation")
        return self


class SafetySignal(DTO):
    schema_version: Literal["1.1"]
    signal_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    signal_type: str = Field(min_length=1)
    observed_at: datetime
    value: bool
    quality: Literal["VALID", "INVALID", "UNKNOWN", "STALE"]
    observation_refs: list[str] = Field(min_length=1)
    origin: Origin

    @field_validator("observed_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime:
        return _aware(value)


class SafetyEvent(DTO):
    schema_version: Literal["1.1"]
    event_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    lifecycle: Literal["OPEN", "RESOLVED", "CLOSED"]
    ack_status: Literal["UNACKNOWLEDGED", "ACKNOWLEDGED"]
    physical_status: Literal["ACTIVE", "CLEARED", "UNKNOWN"]
    escalation_level: Literal["L0", "L1", "L2", "L3"]
    version: int = Field(ge=1)
    created_at: datetime
    origin: Origin

    @field_validator("created_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime:
        return _aware(value)


class EventTransition(DTO):
    schema_version: Literal["1.1"]
    transition_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    event_version: int = Field(ge=1)
    transition_type: str = Field(min_length=1)
    occurred_at: datetime
    actor: str = Field(min_length=1)
    reason_codes: list[str]
    evidence_refs: list[str]
    origin: Origin

    @field_validator("occurred_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime:
        return _aware(value)


class Receipt(DTO):
    provider: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1)
    received_at: datetime

    @field_validator("received_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime:
        return _aware(value)


class CloudSyncRecord(DTO):
    schema_version: Literal["1.1"]
    message_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    destination: Literal["huawei_iotda"]
    sync_status: Literal["PENDING", "SENDING", "RETRY_WAIT", "ACCEPTED", "FAILED"]
    attempts: int = Field(ge=0)
    next_retry_at: datetime | None
    last_error: str | None
    transport_receipt: Receipt | None
    business_receipt: Receipt | None
    origin: Origin

    @field_validator("next_retry_at", mode="before")
    @classmethod
    def aware_retry(cls, value: object) -> datetime | None:
        return None if value is None else _aware(value)

    @model_validator(mode="after")
    def status_rules(self) -> "CloudSyncRecord":
        if self.sync_status == "RETRY_WAIT" and self.next_retry_at is None:
            raise ValueError("RETRY_WAIT requires next_retry_at")
        if self.sync_status == "ACCEPTED" and self.transport_receipt is None:
            raise ValueError("ACCEPTED requires a verified transport receipt")
        return self


class VersionDetails(DTO):
    expected_version: int = Field(ge=0)
    actual_version: int = Field(ge=0)


class ApiError(DTO):
    code: Literal["BAD_REQUEST", "UNAUTHORIZED", "NOT_FOUND", "SERVICE_UNAVAILABLE", "VERSION_CONFLICT", "IDEMPOTENCY_CONFLICT"]
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    details: VersionDetails | dict[str, object]

    @model_validator(mode="after")
    def details_match_code(self) -> "ApiError":
        if self.code == "VERSION_CONFLICT" and not isinstance(self.details, VersionDetails):
            raise ValueError("VERSION_CONFLICT requires version details")
        if self.code != "VERSION_CONFLICT" and self.details != {}:
            raise ValueError("non-version errors require empty details")
        return self

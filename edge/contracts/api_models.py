"""Candidate request and response models for the seven business routes."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .models import (
    DTO, Origin, SensorSummary, SituationAssessment, SafetySignal,
    SafetyEvent, EventTransition, _aware,
)


class LiveSnapshot(DTO):
    schema_version: Literal["1.1"]
    device_id: str = Field(min_length=1)
    captured_at: datetime
    sensor_summary: SensorSummary
    data_quality: Literal["VALID", "DEGRADED", "UNAVAILABLE"]
    cloud_status: Literal["ONLINE", "OFFLINE", "UNKNOWN"]
    origin: Origin

    @field_validator("captured_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime:
        return _aware(value)


class AssessmentResponse(DTO):
    schema_version: Literal["1.1"]
    assessment: SituationAssessment
    safety_signals: list[SafetySignal]


class EventListResponse(DTO):
    schema_version: Literal["1.1"]
    items: list[SafetyEvent]
    next_cursor: str | None

    @model_validator(mode="after")
    def ordered(self) -> "EventListResponse":
        keys = [(item.created_at, item.event_id) for item in self.items]
        if keys != sorted(keys, reverse=True):
            raise ValueError("events must be ordered by (created_at,event_id) descending")
        return self


class EventDetailResponse(DTO):
    schema_version: Literal["1.1"]
    event: SafetyEvent
    transitions: list[EventTransition]

    @model_validator(mode="after")
    def history_is_continuous(self) -> "EventDetailResponse":
        versions = [item.event_version for item in self.transitions]
        if versions != list(range(1, self.event.version + 1)):
            raise ValueError("transition versions must be complete and continuous")
        if any(item.event_id != self.event.event_id or item.origin != self.event.origin for item in self.transitions):
            raise ValueError("transition event identity/origin mismatch")
        return self


class AckRequest(DTO):
    schema_version: Literal["1.1"]
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    ack_type: Literal["ACKNOWLEDGE"]


class AckResponse(DTO):
    schema_version: Literal["1.1"]
    event: SafetyEvent
    transition_id: str = Field(min_length=1)


class SyncStatus(DTO):
    schema_version: Literal["1.1"]
    device_id: str | None
    pending_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    last_ack_level: Literal["NONE", "TRANSPORT", "BUSINESS"]
    last_accepted_at: datetime | None

    @field_validator("last_accepted_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime | None:
        return None if value is None else _aware(value)

    @model_validator(mode="after")
    def ack_time_matches_level(self) -> "SyncStatus":
        if self.last_ack_level == "NONE" and self.last_accepted_at is not None:
            raise ValueError("NONE acknowledgement cannot have accepted timestamp")
        if self.last_ack_level != "NONE" and self.last_accepted_at is None:
            raise ValueError("acknowledgement level requires accepted timestamp")
        return self


class ExperimentResult(DTO):
    schema_version: Literal["1.1"]
    trial_id: str = Field(min_length=1)
    source: Literal["simulation", "hardware"]
    status: Literal["PLANNED", "RUNNING", "COMPLETE", "FAILED"]
    started_at: datetime | None
    ended_at: datetime | None
    asset_refs: list[str]

    @field_validator("started_at", "ended_at", mode="before")
    @classmethod
    def aware_time(cls, value: object) -> datetime | None:
        return None if value is None else _aware(value)

    @model_validator(mode="after")
    def ordered(self) -> "ExperimentResult":
        if self.ended_at is not None and (self.started_at is None or self.ended_at < self.started_at):
            raise ValueError("ended_at requires an earlier started_at")
        return self

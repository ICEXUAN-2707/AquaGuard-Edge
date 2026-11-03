"""prototype_only: deterministic M6 water policy, no storage or notification.

Caller supplies verified lineage and serialized per-device signal order.
Candidate contract review remains outstanding.
"""
from dataclasses import dataclass
from datetime import datetime
import math

from edge.contracts.models import SafetySignal, SafetyEvent


@dataclass(frozen=True)
class Policy:
    ttl_seconds: float
    clear_seconds: float

    def __post_init__(self):
        for value in (self.ttl_seconds, self.clear_seconds):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("TTL and clear duration must be finite and positive")


@dataclass(frozen=True)
class Decision:
    physical_status: str
    dry_since: datetime | None
    create_event: bool
    reason: str


def evaluate(payload, current, *, now, dry_since=None, previous_dry_at=None, policy):
    """Evaluate one trusted ordered signal; UNKNOWN interrupts dry evidence.

    Does not infer origin authorization from DTO fields. Does not implement
    event identity, lifecycle, escalation, ACK, or durable debounce state.
    """
    signal = SafetySignal.model_validate(payload)
    event = None if current is None else SafetyEvent.model_validate(current)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include timezone")
    if signal.signal_type != "WATER_CONTACT":
        raise ValueError("unsupported safety signal type")
    if event and (event.device_id != signal.device_id or event.event_type != signal.signal_type or event.lifecycle != "OPEN"):
        raise ValueError("current event must be the matching OPEN event")
    if dry_since is not None and (dry_since.tzinfo is None or dry_since.utcoffset() is None or dry_since > signal.observed_at):
        raise ValueError("dry_since must be aware and no later than observation")
    age = (now - signal.observed_at).total_seconds()
    if age < 0:
        raise ValueError("future observation")
    if signal.quality != "VALID" or age > policy.ttl_seconds:
        return Decision("UNKNOWN", None, False, "WATER_EVIDENCE_UNAVAILABLE")
    if signal.value:
        return Decision("ACTIVE", None, event is None, "WATER_DETECTED")
    # Dry duration requires a chain of consecutive, non-expired dry evidence.
    if dry_since is not None:
        if previous_dry_at is None or previous_dry_at.tzinfo is None or previous_dry_at.utcoffset() is None:
            raise ValueError("dry chain requires aware previous_dry_at")
        if not dry_since <= previous_dry_at <= signal.observed_at:
            raise ValueError("dry evidence order mismatch")
        if (signal.observed_at - previous_dry_at).total_seconds() > policy.ttl_seconds:
            dry_since = None
    if dry_since is None:
        return Decision("UNKNOWN", signal.observed_at, False, "DRY_CONFIRMATION_PENDING")
    if (signal.observed_at - dry_since).total_seconds() >= policy.clear_seconds:
        return Decision("CLEARED", dry_since, False, "WATER_CLEAR_CANDIDATE")
    return Decision("UNKNOWN", dry_since, False, "DRY_CONFIRMATION_PENDING")


def acknowledge(payload):
    """Only confirmation changes; event version belongs to transaction layer."""
    event = SafetyEvent.model_validate(payload)
    if event.lifecycle != "OPEN":
        raise ValueError("prototype ACK supports OPEN events only")
    result = event.model_dump(mode="json")
    result["ack_status"] = "ACKNOWLEDGED"
    return SafetyEvent.model_validate(result).model_dump(mode="json")

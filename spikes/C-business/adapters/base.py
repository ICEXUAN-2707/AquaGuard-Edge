"""Storage-independent delivery boundary. Results describe transport only."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DeliveryRequest:
    attempt_token: str
    message_id: str
    transition_id: str
    payload: dict
    now: str


@dataclass(frozen=True)
class TransportAccepted:
    transport_receipt: dict


@dataclass(frozen=True)
class RetryableFailure:
    error: str = "MOCK_TEMPORARY_FAILURE"


@dataclass(frozen=True)
class PermanentFailure:
    error: str = "MOCK_PERMANENT_FAILURE"


DeliveryResult = TransportAccepted | RetryableFailure | PermanentFailure


class TemporaryDeliveryError(Exception):
    pass


class PermanentDeliveryError(Exception):
    pass


class DeliveryAdapter(Protocol):
    def send(self, request: DeliveryRequest) -> DeliveryResult: ...
    def close(self) -> None: ...

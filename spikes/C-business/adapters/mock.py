"""Simulation-only adapter. Never performs network IO."""
from adapters.base import (TransportAccepted, RetryableFailure,
                           PermanentFailure, TemporaryDeliveryError)


class MockAdapter:
    def __init__(self, mode="accept"):
        if mode not in ("accept", "temporary", "permanent", "exception"):
            raise ValueError("unsupported Mock mode")
        self.mode = mode

    def send(self, request):
        if (request.payload["event"]["origin"] != "simulation" or
                request.payload["transition"]["origin"] != "simulation"):
            raise ValueError("Mock adapter permits simulation only")
        if self.mode == "exception":
            raise TemporaryDeliveryError("mock injected transport timeout")
        if self.mode == "temporary":
            return RetryableFailure()
        if self.mode == "permanent":
            return PermanentFailure()
        return TransportAccepted(dict(provider="mock", receipt_id=request.message_id,
                                      received_at=request.now))

    def close(self):
        pass

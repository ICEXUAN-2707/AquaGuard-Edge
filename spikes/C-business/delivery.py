"""Claim, send outside SQLite transactions, then finish with the attempt token."""
from copy import deepcopy
from adapters.base import (DeliveryAdapter, DeliveryRequest, TransportAccepted,
                           RetryableFailure, PermanentFailure,
                           TemporaryDeliveryError, PermanentDeliveryError)


class DeliveryService:
    def __init__(self, worker, adapter: DeliveryAdapter, *, finish_clock=None):
        if finish_clock is not None and not callable(finish_clock):raise ValueError('finish_clock must be callable')
        self.worker, self.adapter = worker, adapter
        self.finish_clock=finish_clock

    def step(self, *, now):
        claimed = self.worker.claim(now=now)
        if claimed is None:
            return "IDLE"
        record = claimed["record"]
        if record["origin"] != "simulation":
            raise ValueError("Mock worker permits simulation only")
        request = DeliveryRequest(claimed["token"], record["message_id"],
                                  record["transition_id"], deepcopy(claimed["payload"]), now)
        # claim() has committed and closed its connection before adapter IO.
        try:
            result = self.adapter.send(request)
        except TemporaryDeliveryError:
            result = RetryableFailure()
        except PermanentDeliveryError:
            result = PermanentFailure()
        if isinstance(result, TransportAccepted):
            outcome = dict(status="ACCEPTED", transport_receipt=result.transport_receipt)
        elif isinstance(result, RetryableFailure):
            outcome = dict(status="RETRY_WAIT", error=result.error)
        elif isinstance(result, PermanentFailure):
            outcome = dict(status="FAILED", error=result.error)
        else:
            raise TypeError("invalid adapter result")
        return self.worker.finish(claimed["token"], outcome, now=self.finish_clock() if self.finish_clock else now)

    def close(self):
        self.adapter.close()

import json
from copy import deepcopy
from test_cloud_modules import environment,snapshot
from cloud_config import load_config
from adapters.iotda import IoTDAAdapter
from adapters.base import DeliveryRequest,RetryableFailure

class Transport:
    def __init__(self): self.calls=[]; self.closed=False
    def send(self,payload,**kwargs):
        self.calls.append((payload,kwargs)); return RetryableFailure("OFFLINE")
    def close(self): self.closed=True

def test_wrapper_maps_once_and_preserves_ids(environment,snapshot):
    transport=Transport(); adapter=IoTDAAdapter(load_config(environment),transport)
    original=deepcopy(snapshot)
    request=DeliveryRequest("attempt",snapshot["message_id"],snapshot["transition"]["transition_id"],snapshot,"2026-11-07T00:00:00Z")
    assert adapter.send(request).error=="OFFLINE"
    payload,ids=transport.calls[0]
    assert json.loads(payload)["id"]==request.message_id
    assert ids==dict(message_id=request.message_id,attempt_token="attempt")
    assert snapshot==original
    adapter.close(); assert transport.closed

def test_wrapper_rejects_mismatched_request(environment,snapshot):
    transport=Transport(); adapter=IoTDAAdapter(load_config(environment),transport)
    request=DeliveryRequest("a","wrong","wrong",snapshot,"2026-11-07T00:00:00Z")
    assert adapter.send(request).error=="IOTDA_REQUEST_MISMATCH"
    assert not transport.calls

def test_wrapper_rejects_unauthorized_device(environment,snapshot):
    transport=Transport(); adapter=IoTDAAdapter(load_config(environment),transport)
    snapshot["event"]["device_id"]="other"
    request=DeliveryRequest("a",snapshot["message_id"],snapshot["transition"]["transition_id"],snapshot,"2026-11-07T00:00:00Z")
    assert adapter.send(request).error=="IOTDA_NOT_AUTHORIZED"
    assert not transport.calls

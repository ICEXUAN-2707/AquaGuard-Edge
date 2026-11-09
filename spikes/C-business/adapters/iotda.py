"""Authorized mapping wrapper; injected transport only, no live Paho entry."""
from cloud_mapping import build_payload
from cloud_config import ConfigError
from adapters.base import PermanentFailure


class IoTDAAdapter:
    def __init__(self,config,transport):
        self.config,self.transport=config,transport

    def send(self,request):
        snapshot=request.payload
        if (not isinstance(snapshot,dict) or snapshot.get("message_id")!=request.message_id or
                not isinstance(snapshot.get("transition"),dict) or
                snapshot["transition"].get("transition_id")!=request.transition_id):
            return PermanentFailure("IOTDA_REQUEST_MISMATCH")
        from cloud_mapping import MappingError
        try:
            payload=build_payload(snapshot,self.config)
        except ConfigError:
            return PermanentFailure("IOTDA_NOT_AUTHORIZED")
        except MappingError:
            return PermanentFailure("IOTDA_PAYLOAD_INVALID")
        return self.transport.send(payload,message_id=request.message_id,attempt_token=request.attempt_token)

    def close(self):
        self.transport.close()

"""Pure candidate IoTDA message mapping; no MQTT, SQLite or current-event lookup.

Wire compatibility still requires separate official-protocol verification.
"""
import json
from edge.contracts.models import SafetyEvent, EventTransition
from cloud_config import CloudConfig

MAPPING_VERSION="aquaguard-transition-v1"


class MappingError(ValueError):
    pass


def build_payload(snapshot,config: CloudConfig):
    try:
        if not isinstance(snapshot,dict) or set(snapshot)!={"schema_version","message_id","event","transition"}:
            raise ValueError()
        if snapshot["schema_version"]!="1.1" or not isinstance(snapshot["message_id"],str) or not snapshot["message_id"].strip():
            raise ValueError()
        event=SafetyEvent.model_validate(snapshot["event"]).model_dump(mode="json")
        transition=EventTransition.model_validate(snapshot["transition"]).model_dump(mode="json")
        if (event["event_id"]!=transition["event_id"] or event["version"]!=transition["event_version"] or
                event["origin"]!=transition["origin"]):
            raise ValueError()
    except (ValueError,TypeError,KeyError):
        raise MappingError("invalid immutable Outbox snapshot") from None
    config.authorize(event["device_id"],event["origin"])
    content=dict(schema_version="1.1",mapping_version=MAPPING_VERSION,message_type="EVENT_TRANSITION",
        message_id=snapshot["message_id"],event_id=event["event_id"],transition_id=transition["transition_id"],
        event_version=transition["event_version"],origin=event["origin"],event=event,transition=transition)
    envelope=dict(object_device_id=config.device_id,name="AquaGuard Event Transition",id=snapshot["message_id"],content=content)
    return json.dumps(envelope,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)

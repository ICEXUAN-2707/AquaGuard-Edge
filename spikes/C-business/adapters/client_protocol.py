"""Contract for a future Paho wrapper; no network implementation."""
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol


class ConnectReason(Enum):
    TLS_FAILURE = "tls_failure"
    CONNECT_TIMEOUT = "connect_timeout"
    NETWORK_FAILURE = "network_failure"
    ACCEPTED = "accepted"
    AUTH_REJECTED = "auth_rejected"
    TEMPORARY_FAILURE = "temporary_failure"
    PROTOCOL_REJECTED = "protocol_rejected"


@dataclass(frozen=True)
class ClientBinding:
    endpoint: str
    cloud_device_id: str
    client_id: str
    topic: str
    qos: int = 1
    retain: bool = False

    def __post_init__(self):
        if (not self.endpoint or not self.cloud_device_id or not self.client_id or
                self.topic != f"$oc/devices/{self.cloud_device_id}/sys/messages/up" or
                type(self.qos) is not int or self.qos != 1 or self.retain is not False):
            raise ValueError("invalid MQTT client binding")


class MQTTClient(Protocol):
    """Factory binds identity/TLS/topic before construction.

    start/publish must return promptly. on_connect reports normalized reason;
    on_publish reports MID and success, never business acceptance. Wrapper maps
    VERSION2 ReasonCode explicitly, not using Python truthiness. publish uses
    binding.topic/qos/retain without serializing payload again.

    close owns disconnect, loop termination and confirmed thread exit. It must
    be bounded; failure raises and leaves enough ownership to retry close.
    No auto-reconnect or old in-memory publish after successful close.
    The wrapper must verify client_id was derived for binding.cloud_device_id.
    """
    binding: ClientBinding
    def start(self, on_connect: Callable[[ConnectReason], None],
              on_publish: Callable[[int, bool], None],
              on_disconnect: Callable[[], None]) -> None: ...
    def publish(self, payload: str) -> tuple[int, int]: ...
    def close(self) -> None: ...

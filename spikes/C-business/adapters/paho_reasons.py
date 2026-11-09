"""Pure translation of VERSION2 normalized reason values (not v1 CONNACK)."""
from adapters.client_protocol import ConnectReason


def connect_reason(value):
    if type(value) is not int:
        return ConnectReason.PROTOCOL_REJECTED
    if value==0:
        return ConnectReason.ACCEPTED
    if value in (134,135):
        return ConnectReason.AUTH_REJECTED
    if value in (136,137,151,159):
        return ConnectReason.TEMPORARY_FAILURE
    return ConnectReason.PROTOCOL_REJECTED


def publish_succeeded(value):
    return type(value) is int and value in (0,16)

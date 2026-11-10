"""Bounded incremental IPC decoder experiment; no socket, process or cloud IO.

The owner must use nonblocking IO. A partial frame never initiates another read.
Only one terminal result is allowed on an attempt-specific result channel.
"""
import json
import struct

MAX_FRAME = 4096


class FrameError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FrameError("duplicate field")
        result[key] = value
    return result


class ResultDecoder:
    def __init__(self, *, generation, message_id, attempt_token):
        values = (generation, message_id, attempt_token)
        if any(type(v) is not str or not v or len(v) > 256 for v in values):
            raise FrameError("invalid identity")
        self.identity = dict(generation=generation, message_id=message_id,
                             attempt_token=attempt_token)
        self.buffer = bytearray()
        self.complete = False
        self.failed = False

    def feed(self, data):
        if self.failed or self.complete:
            raise FrameError("terminal decoder")
        try:
            if type(data) is not bytes or len(self.buffer) + len(data) > MAX_FRAME + 4:
                raise FrameError("frame limit")
            self.buffer.extend(data)
            if len(self.buffer) < 4:
                return None
            size = struct.unpack("!I", self.buffer[:4])[0]
            if not 1 <= size <= MAX_FRAME:
                raise FrameError("frame limit")
            if len(self.buffer) < size + 4:
                return None
            if len(self.buffer) != size + 4:
                raise FrameError("trailing frame")
            frame = json.loads(bytes(self.buffer[4:]).decode("utf-8"),
                               object_pairs_hook=_unique)
            expected = {"ipc_version", "status", *self.identity}
            if type(frame) is not dict or set(frame) != expected:
                raise FrameError("invalid fields")
            if type(frame["ipc_version"]) is not int or frame["ipc_version"] != 1:
                raise FrameError("invalid version")
            if type(frame["status"]) is not str or frame["status"] not in {"PUBACK", "UNKNOWN"}:
                raise FrameError("invalid status")
            if any(frame[key] != value for key, value in self.identity.items()):
                raise FrameError("mismatched attempt")
            self.complete = True
            self.buffer.clear()
            return frame
        except Exception:
            self.failed = True
            self.buffer.clear()
            # Never include input data or parser exceptions in diagnostics.
            raise FrameError("invalid IPC result") from None

    def eof(self):
        if not self.complete:
            self.failed = True
            self.buffer.clear()
            raise FrameError("incomplete IPC result")

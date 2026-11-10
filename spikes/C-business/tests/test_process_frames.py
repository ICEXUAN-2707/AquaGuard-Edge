import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.process_frames import ResultDecoder, FrameError, MAX_FRAME


def decoder():
    return ResultDecoder(generation="g", message_id="m", attempt_token="a")


def wire(**changes):
    frame = dict(ipc_version=1, generation="g", message_id="m",
                 attempt_token="a", status="PUBACK")
    frame.update(changes)
    payload = json.dumps(frame).encode()
    return struct.pack("!I", len(payload)) + payload


def test_partial_bytes_never_require_blocking_read():
    d = decoder()
    frame = wire()
    for byte in frame[:-1]:
        assert d.feed(bytes([byte])) is None
    assert d.feed(frame[-1:])["status"] == "PUBACK"
    d.eof()
    with pytest.raises(FrameError):
        d.feed(frame)


@pytest.mark.parametrize("change", [dict(generation="old"), dict(attempt_token="old"),
    dict(message_id="other"), dict(ipc_version=True), dict(status="ACCEPTED"),
    dict(secret="sentinel")])
def test_invalid_identity_or_schema_fails_closed(change):
    d = decoder()
    with pytest.raises(FrameError, match="^invalid IPC result$"):
        d.feed(wire(**change))
    assert d.failed and not d.buffer


@pytest.mark.parametrize("data", [struct.pack("!I", MAX_FRAME + 1),
    struct.pack("!I", 0), b"x" * (MAX_FRAME + 5), wire() + wire(),
    struct.pack("!I", 1) + b"\xff"])
def test_bounds_and_corruption(data):
    with pytest.raises(FrameError):
        decoder().feed(data)


def test_partial_eof_is_unknown_not_success():
    d = decoder()
    assert d.feed(wire()[:-1]) is None
    with pytest.raises(FrameError, match="incomplete"):
        d.eof()
    assert d.failed


def test_duplicate_keys_rejected_without_echo():
    payload = b'{"secret":"sentinel","secret":"sentinel"}'
    with pytest.raises(FrameError) as error:
        decoder().feed(struct.pack("!I", len(payload)) + payload)
    assert "sentinel" not in str(error.value)

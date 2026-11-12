import socket
from time import monotonic

import pytest
from test_process_frames import decoder, wire
from experiments.process_frames import FrameError
from experiments.process_channel import ResultReader, BoundedWriter


def test_partial_frame_returns_without_waiting_for_peer():
    parent, child = socket.socketpair()
    reader = ResultReader(parent, decoder())
    try:
        child.sendall(wire()[:5])
        start = monotonic()
        assert reader.step() is None
        assert reader.step() is None
        assert monotonic() - start < .5
        child.sendall(wire()[5:])
        assert reader.step()["status"] == "PUBACK"
    finally:
        reader.close()
        child.close()
    assert parent.fileno() == -1


def test_partial_frame_peer_death_fails_closed():
    parent, child = socket.socketpair()
    reader = ResultReader(parent, decoder())
    try:
        child.sendall(wire()[:5])
        assert reader.step() is None
        child.close()
        with pytest.raises(FrameError, match="incomplete"):
            reader.step()
    finally:
        child.close()
        reader.close()


def test_real_full_buffer_does_not_block_writer_or_close():
    parent, child = socket.socketpair()
    child.setblocking(False)
    child.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    filled = False
    try:
        for _ in range(4096):
            try:
                child.send(b"x" * 4096)
            except BlockingIOError:
                filled = True
                break
        assert filled, "could not establish backpressure"
        writer = BoundedWriter(child, wire())
        start = monotonic()
        assert writer.step() is False
        writer.close()
        writer.close()
        assert monotonic() - start < .5
        assert child.fileno() == -1 and not writer.pending
    finally:
        parent.close()
        child.close()


def test_writer_to_reader_roundtrip():
    parent, child = socket.socketpair()
    reader = ResultReader(parent, decoder())
    writer = BoundedWriter(child, wire())
    try:
        assert writer.step()
        assert reader.step()["message_id"] == "m"
    finally:
        writer.close()
        reader.close()

import pytest
from experiments.process_probe import ProcessProbe


@pytest.mark.parametrize("mode,accepted", [("result", True), ("partial", False),
    ("crash", False), ("stall", False), ("result_then_stall", True)])
def test_spawn_result_and_verified_cleanup(mode, accepted):
    probe = ProcessProbe(message_id="m", attempt_token="a", mode=mode)
    try:
        probe.start()
        result = probe.wait_result(.8 if mode == "stall" else 4)
        assert (result is not None) is accepted
        probe.close()
        assert probe.state == "REAPED" and probe.exitcode is not None
        assert probe.reader.sock.fileno() == -1
        assert probe.child_socket.fileno() == -1
        assert probe.outcome == result
        deadline = probe.deadline
        probe.close()
        assert probe.deadline == deadline
        with pytest.raises(ValueError):
            probe.process.is_alive()  # Process handle explicitly closed.
    finally:
        probe.close()


def test_unstarted_cleanup_and_no_reuse():
    probe = ProcessProbe(message_id="m", attempt_token="a")
    probe.close()
    assert probe.state == "REAPED"
    with pytest.raises(RuntimeError):
        probe.start()


def test_start_failure_closes_channels(monkeypatch):
    probe = ProcessProbe(message_id="m", attempt_token="a")
    def fail():
        raise OSError("sentinel")
    monkeypatch.setattr(probe.process, "start", fail)
    with pytest.raises(RuntimeError, match="^probe start failed$"):
        probe.start()
    probe.close()
    assert probe.state == "REAPED" and probe.reader.sock.fileno() == -1


def test_unconfirmed_exit_retains_owner_and_original_result():
    probe = ProcessProbe(message_id="m", attempt_token="a")
    original = probe.process
    class Retained:
        def join(self, timeout): pass
        def is_alive(self): return True
        def terminate(self): pass
        def kill(self): pass
    probe.process = Retained()
    probe.started = True
    probe.outcome = {"status": "PUBACK"}
    try:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            probe.close(.01)
        deadline = probe.deadline
        assert probe.state == "CLEANUP_FAILED"
        assert probe.reader.sock.fileno() != -1
        assert probe.outcome == {"status": "PUBACK"}
        with pytest.raises(RuntimeError):
            probe.close()
        assert probe.deadline == deadline
    finally:
        probe.process = original
        probe.started = False
        probe.close()

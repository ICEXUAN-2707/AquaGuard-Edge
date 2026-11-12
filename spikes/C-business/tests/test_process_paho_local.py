import socket
from time import monotonic

from test_process_frames import decoder
from experiments.process_probe import ProcessProbe


def test_real_paho_tls_stall_child_exit_and_peer_eof():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(5)
    probe = ProcessProbe(message_id="m", attempt_token="a", mode="tls_stall",
                         local_port=server.getsockname()[1])
    peer = None
    try:
        probe.start()
        peer, _ = server.accept()
        peer.settimeout(3)
        # Receiving ClientHello proves the child entered real TLS setup.
        assert peer.recv(4096)
        assert probe.wait_result(.05) is None
        assert probe.process.is_alive()
        started = monotonic()
        probe.close(timeout=2)
        assert monotonic() - started < 2.5
        assert probe.state == "REAPED" and probe.exitcode is not None
        assert probe.outcome is None
        try:
            # Buffered ClientHello bytes may remain before EOF.
            while peer.recv(4096):
                pass
        except ConnectionResetError:
            pass  # Reset also demonstrates peer teardown on Windows.
    finally:
        probe.close()
        if peer is not None:
            peer.close()
        server.close()

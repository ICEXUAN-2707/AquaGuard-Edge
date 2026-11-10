"""Spawn/IPC ownership probe, deliberately not a Paho delivery adapter.

Single caller only. start() is synchronous and has no proven OS-call bound.
Parent sentinel watchdog is experimental; OS-enforced containment remains gated.
"""
import json
import math
import multiprocessing
import os
import socket
import struct
import time
import threading
from uuid import uuid4

from experiments.process_channel import ResultReader, BoundedWriter
from experiments.process_frames import ResultDecoder, FrameError


def watch_parent():
    """Fail closed when the spawn parent's sentinel becomes signaled.

    This daemon does no IPC IO and owns no delivery accounting. It requires a
    responsive Python runtime; it is not a Windows Job Object guarantee.
    """
    from multiprocessing.connection import wait
    parent = multiprocessing.parent_process()
    if parent is None:
        raise RuntimeError("spawn parent required")
    sentinel = parent.sentinel

    def monitor():
        try:
            wait([sentinel])
        finally:
            os._exit(72)

    threading.Thread(target=monitor, name="probe-parent-sentinel", daemon=True).start()


def probe_child(sock, identity, mode, local_port):
    """Controlled test behaviors only; synthetic PUBACK is not MQTT evidence."""
    try:
        watch_parent()
        if mode == "tls_stall":
            # Local-only reproduction of Paho blocking setup, no cloud identity.
            import ssl
            import paho.mqtt.client as mqtt
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                 reconnect_on_failure=False)
            client.tls_set_context(ssl.create_default_context())
            client.connect_timeout = .15
            client.connect("127.0.0.1", local_port, 60)
            return
        if mode == "crash":
            os._exit(17)
        if mode == "stall":
            while True:
                time.sleep(.1)
        payload = json.dumps(dict(ipc_version=1, status="PUBACK", **identity)).encode()
        frame = struct.pack("!I", len(payload)) + payload
        if mode == "partial":
            sock.sendall(frame[:5])
            return
        writer = BoundedWriter(sock, frame)
        deadline = time.monotonic() + 2
        while not writer.step():
            if time.monotonic() >= deadline:
                return
            time.sleep(.005)
        if mode == "result_then_stall":
            while True:
                time.sleep(.1)
    finally:
        sock.close()


class ProcessProbe:
    def __init__(self, *, message_id, attempt_token, mode="result", local_port=None):
        if mode not in {"result", "partial", "crash", "stall", "result_then_stall", "tls_stall"}:
            raise ValueError("invalid probe mode")
        if mode == "tls_stall" and (type(local_port) is not int or not 1 <= local_port <= 65535):
            raise ValueError("invalid local port")
        if mode != "tls_stall" and local_port is not None:
            raise ValueError("unexpected local port")
        self.identity = dict(generation=str(uuid4()), message_id=message_id,
                             attempt_token=attempt_token)
        decoder = ResultDecoder(**self.identity)
        parent, child = socket.socketpair()
        self.reader = ResultReader(parent, decoder)
        self.child_socket = child
        self.process = multiprocessing.get_context("spawn").Process(
            target=probe_child, args=(child, self.identity, mode, local_port), daemon=False)
        self.state = "NEW"
        self.started = False
        self.deadline = None
        self.outcome = None
        self.exitcode = None

    def start(self):
        if self.state != "NEW":
            raise RuntimeError("invalid probe state")
        self.state = "STARTING"
        try:
            self.process.start()
            self.started = True
            self.state = "RUNNING"
        except Exception:
            # If start partially created an OS process, retain it for close.
            self.started = self.process.pid is not None
            self.state = "START_FAILED"
            raise RuntimeError("probe start failed") from None
        finally:
            self.child_socket.close()

    def wait_result(self, timeout):
        if self.state != "RUNNING":
            raise RuntimeError("invalid probe state")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid timeout")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = self.reader.step()
            except (FrameError, OSError):
                return None
            if result is not None:
                if time.monotonic() < deadline:
                    self.outcome = result
                return self.outcome
            time.sleep(min(.005, max(0, deadline - time.monotonic())))
        return None

    def close(self, timeout=2):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid timeout")
        if self.state == "REAPED":
            return
        now = time.monotonic()
        if self.deadline is None:
            self.deadline = now + timeout
        remaining = lambda: max(0, self.deadline - time.monotonic())
        self.state = "STOPPING"
        try:
            if self.started:
                self.process.join(min(.05, remaining()))
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(min(.5, remaining()))
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(remaining())
                if self.process.is_alive():
                    raise RuntimeError("probe exit unconfirmed")
                self.exitcode = self.process.exitcode
            self.reader.close()
            self.child_socket.close()
            self.process.close()
            self.state = "REAPED"
        except Exception:
            self.state = "CLEANUP_FAILED"
            raise RuntimeError("probe cleanup failed") from None

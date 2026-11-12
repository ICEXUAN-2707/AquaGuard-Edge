"""Attempt-local nonblocking result channel experiment, not authenticated transport.

No listener, feeder or reader thread. Caller owns scheduling/deadline and close.
Spawn socket transfer and parent-death containment remain separate gates.
"""
from experiments.process_frames import MAX_FRAME, FrameError


class ResultReader:
    def __init__(self, sock, decoder):
        sock.setblocking(False)
        self.sock, self.decoder = sock, decoder
        self.closed = False

    def step(self):
        if self.closed:
            raise FrameError("closed channel")
        try:
            data = self.sock.recv(MAX_FRAME + 5)
        except BlockingIOError:
            return None
        if not data:
            self.decoder.eof()
            return None
        return self.decoder.feed(data)

    def close(self):
        if not self.closed:
            self.sock.close()
            self.closed = True


class BoundedWriter:
    def __init__(self, sock, frame):
        if type(frame) is not bytes or not 4 < len(frame) <= MAX_FRAME + 4:
            raise FrameError("invalid output size")
        sock.setblocking(False)
        self.sock = sock
        self.pending = frame
        self.closed = False

    def step(self):
        if self.closed:
            raise FrameError("closed channel")
        if not self.pending:
            return True
        try:
            count = self.sock.send(self.pending)
        except BlockingIOError:
            return False
        if count == 0:
            raise FrameError("channel disconnected")
        self.pending = self.pending[count:]
        return not self.pending

    def close(self):
        if not self.closed:
            self.sock.close()
            self.closed = True
            self.pending = b""

from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from adapters.iotda_transport import IoTDATransport
from adapters.base import TransportAccepted,RetryableFailure,PermanentFailure

T="2026-11-07T00:00:00Z"

class Fake:
    def __init__(self,mode="accept"):
        self.mode,self.closes=mode,0
    def start(self,connect,publish,disconnect):
        self.callback,self.disconnect=publish,disconnect
        if self.mode!="connack_timeout": connect(self.mode!="reject")
    def publish(self,payload):
        if self.mode=="disconnect": self.disconnect()
        if self.mode=="accept":
            self.callback(7); self.callback(7)  # callback before return, duplicate
        if self.mode=="wrong_mid": self.callback(8)
        return (1 if self.mode=="publish_fail" else 0),7
    def close(self):
        self.closes+=1
        if self.mode=="cleanup_fail": raise OSError("secret")

@pytest.mark.parametrize("mode,kind,error",[
    ("accept",TransportAccepted,None),
    ("reject",PermanentFailure,"IOTDA_CONNECT_REJECTED"),
    ("connack_timeout",RetryableFailure,"IOTDA_CONNACK_TIMEOUT"),
    ("publish_fail",RetryableFailure,"IOTDA_PUBLISH_FAILED"),
    ("disconnect",RetryableFailure,"IOTDA_DISCONNECTED"),
    ("timeout",RetryableFailure,"IOTDA_PUBACK_TIMEOUT"),
    ("wrong_mid",RetryableFailure,"IOTDA_PUBACK_TIMEOUT")])
def test_outcomes(mode,kind,error):
    fake=Fake(mode)
    core=IoTDATransport(lambda:fake,utcnow=lambda:T,connect_timeout=.01,publish_timeout=.01)
    result=core.send("{}",message_id="message",attempt_token="attempt")
    assert isinstance(result,kind)
    if error: assert result.error==error
    else: assert result.transport_receipt["received_at"]==T
    assert fake.closes==1
    core.close(); core.close()
    assert fake.closes==1


def test_late_callback_cannot_complete_next_attempt():
    first,second=Fake(),Fake("timeout")
    queue=iter([first,second])
    core=IoTDATransport(lambda:next(queue),utcnow=lambda:T,publish_timeout=.01)
    assert isinstance(core.send("{}",message_id="m",attempt_token="a"),TransportAccepted)
    old_start=second.start
    def start(*args):
        old_start(*args); first.callback(7)
    second.start=start
    assert isinstance(core.send("{}",message_id="m",attempt_token="b"),RetryableFailure)


def test_cleanup_failure_stops_reuse_and_hides_exception():
    core=IoTDATransport(lambda:Fake("cleanup_fail"),utcnow=lambda:T,publish_timeout=.01)
    with pytest.raises(RuntimeError,match="IOTDA_CLEANUP_FAILED"):
        core.send("{}",message_id="m",attempt_token="a")
    with pytest.raises(RuntimeError,match="UNAVAILABLE"):
        core.send("{}",message_id="m",attempt_token="b")


@pytest.mark.parametrize("duration",[True,False,float("nan"),float("inf"),0,-1])
def test_invalid_durations(duration):
    with pytest.raises(ValueError):
        IoTDATransport(lambda:Fake(),utcnow=lambda:T,connect_timeout=duration)


def test_puback_after_deadline_is_not_success():
    tick=[0.0]
    class Late(Fake):
        def publish(self,payload):
            tick[0]=2.0
            self.callback(7)
            return 0,7
    core=IoTDATransport(lambda:Late(),utcnow=lambda:T,publish_timeout=1,monotonic_clock=lambda:tick[0])
    assert core.send("{}",message_id="m",attempt_token="a").error=="IOTDA_PUBACK_TIMEOUT"


def test_cleanup_preserves_puback_evidence():
    from adapters.iotda_transport import CleanupError
    class AcceptedButBroken(Fake):
        def close(self):
            raise RuntimeError("secret")
    core=IoTDATransport(lambda:AcceptedButBroken(),utcnow=lambda:T)
    with pytest.raises(CleanupError) as error:
        core.send("{}",message_id="m",attempt_token="a")
    assert isinstance(error.value.outcome,TransportAccepted)
    assert "secret" not in str(error.value)
    assert core.client is not None


def test_raw_client_exception_is_sanitized():
    class Broken(Fake):
        def start(self,*args): raise RuntimeError("credential")
    result=IoTDATransport(lambda:Broken(),utcnow=lambda:T).send("{}",message_id="m",attempt_token="a")
    assert result.error=="IOTDA_CLIENT_FAILED"


def test_concurrent_close_wakes_connect_wait():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    started=Event()
    class Waiting(Fake):
        def start(self,*args): started.set()
    core=IoTDATransport(lambda:Waiting(),utcnow=lambda:T,connect_timeout=30)
    with ThreadPoolExecutor(2) as pool:
        sending=pool.submit(core.send,"{}",message_id="m",attempt_token="a")
        assert started.wait(1)
        closing=pool.submit(core.close)
        assert sending.result(timeout=2).error=="IOTDA_DISCONNECTED"
        closing.result(timeout=2)

from types import SimpleNamespace
from datetime import datetime,timezone
from threading import Event
import pytest
from test_cloud_modules import environment
from cloud_config import load_config
from adapters.paho_client import PahoClient
from adapters.client_protocol import ConnectReason

class Backend:
    def __init__(self,**kwargs): self.kwargs=kwargs; self.done=Event(); self.calls=[]
    def username_pw_set(self,*args): self.username=args[0]
    def tls_set_context(self,context): self.tls=context
    def connect(self,*args):
        self.on_connect(self,None,None,SimpleNamespace(value=0),None)
    def loop(self,timeout): self.done.wait(.005); return 0
    def publish(self,topic,payload,**kwargs):
        self.calls.append((topic,payload,kwargs))
        self.on_publish(self,None,7,SimpleNamespace(value=0),None)
        return SimpleNamespace(rc=0,mid=7)
    def disconnect(self): self.done.set()


def test_wrapper_binding_callbacks_and_cleanup(environment):
    client=PahoClient(load_config(environment),client_factory=Backend)
    connected=Event(); outcomes=[]
    client.start(lambda reason:(outcomes.append(reason),connected.set()),lambda *a:outcomes.append(a),lambda:None)
    assert connected.wait(1)
    assert outcomes[0] is ConnectReason.ACCEPTED
    assert client.publish('{"id":"stable"}')==(0,7)
    topic,payload,flags=client.client.calls[0]
    assert topic==client.binding.topic and payload=='{"id":"stable"}'
    assert flags==dict(qos=1,retain=False)
    assert client.client.tls.check_hostname and client.client.username==client.config.device_id
    assert client.thread.daemon is False
    client.close(); client.close()
    assert not client.thread.is_alive()


def test_blocked_connect_reports_retained_thread_then_retry(environment):
    entered,release=Event(),Event()
    class Blocked(Backend):
        def connect(self,*args): entered.set(); release.wait()
    client=PahoClient(load_config(environment),client_factory=Blocked,close_timeout=.01)
    client.start(lambda r:None,lambda *a:None,lambda:None)
    try:
        assert entered.wait(1)
        with pytest.raises(RuntimeError,match="THREAD_EXIT_TIMEOUT"): client.close()
        assert client.thread.is_alive() and client.closed
        with pytest.raises(RuntimeError): client.publish("{}");
    finally:
        release.set(); client.thread.join(3); client.close()
    assert not client.thread.is_alive()


def test_real_paho_construction_without_network(environment):
    import paho.mqtt.client as mqtt
    client=PahoClient(load_config(environment),client_factory=mqtt.Client)
    assert client.client.callback_api_version is mqtt.CallbackAPIVersion.VERSION2
    assert client.thread is None
    client.close()


@pytest.mark.parametrize("kind,expected",[("tls",ConnectReason.TLS_FAILURE),("timeout",ConnectReason.CONNECT_TIMEOUT),("network",ConnectReason.NETWORK_FAILURE)])
def test_background_failures_are_classified(environment,kind,expected):
    import ssl
    class Failed(Backend):
        def connect(self,*args):
            raise {"tls":ssl.SSLError,"timeout":TimeoutError,"network":ConnectionRefusedError}[kind]("secret")
    client=PahoClient(load_config(environment),client_factory=Failed)
    done=Event(); reasons=[]
    client.start(reasons.append,lambda *a:None,done.set)
    assert done.wait(1)
    client.close()
    assert reasons==[expected] and client.failure is expected
    assert not client.thread.is_alive()


def test_concurrent_close_disposes_once(environment):
    from concurrent.futures import ThreadPoolExecutor
    class Counted(Backend):
        count=0
        def disconnect(self): self.count+=1; super().disconnect()
    client=PahoClient(load_config(environment),client_factory=Counted)
    done=Event(); client.start(lambda r:done.set(),lambda *a:None,lambda:None)
    assert done.wait(1)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda _:client.close(),range(3)))
    assert client.disposed and client.client.count==1 and not client.thread.is_alive()


def test_real_paho_stalled_tls_exposes_cleanup_limit(environment):
    import socket
    import threading
    import paho.mqtt.client as mqtt
    from dataclasses import replace
    # Local TCP accepts but intentionally never responds to TLS ClientHello.
    server=socket.socket(); server.bind(("127.0.0.1",0)); server.listen(1); server.settimeout(10)
    port=server.getsockname()[1]
    release=Event(); accepted=Event(); errors=[]
    def stall():
        try:
            conn,_=server.accept()
            with conn:
                accepted.set(); release.wait(10)
        except Exception as error: errors.append(type(error).__name__)
    thread=threading.Thread(target=stall,daemon=False)
    class LocalPaho(mqtt.Client):
        def connect(self,*args): return super().connect("127.0.0.1",port,60)
    client=PahoClient(replace(load_config(environment),connect_timeout=.15),client_factory=LocalPaho,close_timeout=.1)
    disconnected=Event(); reasons=[]
    thread.start()
    try:
        client.start(reasons.append,lambda *a:None,disconnected.set)
        assert accepted.wait(2)
        # Paho uses keepalive for TLS handshake, not connect_timeout.
        with pytest.raises(RuntimeError,match="THREAD_EXIT_TIMEOUT"):
            client.close()
        assert client.thread.is_alive() and client.closed
        release.set()
        assert disconnected.wait(3)
        client.thread.join(3)
        client.close()
        assert reasons in ([ConnectReason.TLS_FAILURE],[ConnectReason.NETWORK_FAILURE])
        assert not client.thread.is_alive()
    finally:
        release.set(); server.close(); thread.join(3)
        client.close()
    assert not thread.is_alive() and not errors


def test_retained_socket_never_reports_disposed(environment):
    class Retained(Backend):
        def socket(self): return object()
    client=PahoClient(load_config(environment),client_factory=Retained)
    ready=Event(); client.start(lambda r:ready.set(),lambda *a:None,lambda:None)
    assert ready.wait(1)
    with pytest.raises(RuntimeError,match="RESOURCES_RETAINED"): client.close()
    assert not client.disposed and not client.thread.is_alive()


def test_close_budget_includes_blocked_publish_lock(environment):
    from concurrent.futures import ThreadPoolExecutor
    entered,release=Event(),Event()
    class BlockingPublish(Backend):
        def publish(self,*args,**kwargs):
            entered.set(); assert release.wait(2)
            return SimpleNamespace(rc=0,mid=7)
    client=PahoClient(load_config(environment),client_factory=BlockingPublish,close_timeout=.05)
    ready=Event(); client.start(lambda r:ready.set(),lambda *a:None,lambda:None)
    assert ready.wait(1)
    with ThreadPoolExecutor(1) as pool:
        sending=pool.submit(client.publish,"{}")
        try:
            assert entered.wait(1)
            with pytest.raises(RuntimeError,match="BUDGET_EXPIRED"): client.close()
            deadline=client.shutdown_deadline
            with pytest.raises(RuntimeError): client.close()
            assert client.shutdown_deadline==deadline and not client.disposed
        finally:
            release.set(); sending.result(timeout=2); client.thread.join(2); client.close()


def test_disconnect_failure_is_not_disposal(environment):
    class FailedDisconnect(Backend):
        def disconnect(self): return 1
    client=PahoClient(load_config(environment),client_factory=FailedDisconnect)
    ready=Event(); client.start(lambda r:ready.set(),lambda *a:None,lambda:None)
    assert ready.wait(1)
    with pytest.raises(RuntimeError,match="RESOURCES_RETAINED"): client.close()
    assert not client.disposed

"""Injected-client transport core. No Paho factory, credentials or network entry.

Client contract: start(on_connect,on_publish,on_disconnect), publish(payload)->(rc,mid),
close(). The future Paho wrapper owns TLS/auth and bounded thread cleanup.
"""
from threading import Event, Lock
from time import monotonic
import math
import ssl
from edge.contracts.models import _aware
from uuid import uuid4
from adapters.client_protocol import ConnectReason
from adapters.base import TransportAccepted, RetryableFailure, PermanentFailure


class CleanupError(RuntimeError):
    def __init__(self, outcome):
        super().__init__("IOTDA_CLEANUP_FAILED")
        self.outcome = outcome


class IoTDATransport:
    def __init__(self,client_factory,*,utcnow,connect_timeout=5,publish_timeout=10, monotonic_clock=monotonic):
        for duration in (connect_timeout,publish_timeout):
            if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
                raise ValueError("invalid transport timeout")
        self.monotonic=monotonic_clock
        self.stop=Event()
        self.wakeup=None
        self.factory,self.utcnow=client_factory,utcnow
        self.connect_timeout,self.publish_timeout=connect_timeout,publish_timeout
        self.lock=Lock()
        self.serial=Lock()
        self.client=None
        self.generation=None
        self.closed=False
        self.broken=False

    def _dispose(self):
        with self.lock:
            client=self.client
            self.generation=None
        if client is not None:
            try:
                client.close()
            except Exception:
                self.broken=True
                raise CleanupError(None) from None
            else:
                self.client=None

    def send(self,payload,*,message_id,attempt_token):
        # This core deliberately does not implement DeliveryAdapter.send(request).
        # Authorization and mapping must precede use in the future wrapper.
        with self.serial:
            if self.closed or self.broken:
                raise RuntimeError("IOTDA_TRANSPORT_UNAVAILABLE")
            connected,published,disconnected=Event(),Event(),Event()
            callbacks={}
            connect_result=[]
            outcome=None
            phase=["connect"]
            self.wakeup=connected
            connect_deadline=self.monotonic()+self.connect_timeout
            generation=str(uuid4())
            with self.lock:
                self.generation=generation
            def on_connect(success):
                with self.lock:
                    if self.generation==generation and phase[0]=="connect" and not connect_result:
                        connect_result.append((ConnectReason.ACCEPTED if success is True else
                            ConnectReason.AUTH_REJECTED if success is False else success,self.monotonic()))
                        connected.set()
            def on_publish(mid,success=True):
                try:
                    stamp=self.utcnow()
                    _aware(stamp)
                    tick=self.monotonic()
                except Exception:
                    on_disconnect()
                    return
                with self.lock:
                    if self.generation==generation and phase[0]=="publish" and type(mid) is int and 1<=mid<=65535:
                        if mid in callbacks or len(callbacks)<16:
                            callbacks.setdefault(mid,(success is True,stamp,tick))
                        published.set()
            def on_disconnect():
                with self.lock:
                    if self.generation==generation:
                        disconnected.set()
                        connected.set()
                        published.set()
            try:
                self.client=self.factory()
                self.client.start(on_connect,on_publish,on_disconnect)
                if not connected.wait(max(0,connect_deadline-self.monotonic())):
                    outcome=RetryableFailure("IOTDA_CONNACK_TIMEOUT")
                    return outcome
                if self.stop.is_set() or disconnected.is_set():
                    outcome=RetryableFailure("IOTDA_DISCONNECTED")
                    return outcome
                if connect_result and connect_result[0][1]>=connect_deadline:
                    outcome=RetryableFailure("IOTDA_CONNACK_TIMEOUT")
                    return outcome
                reason=connect_result[0][0] if connect_result else None
                if reason is not ConnectReason.ACCEPTED:
                    if reason is ConnectReason.TEMPORARY_FAILURE:
                        outcome=RetryableFailure("IOTDA_CONNECT_TEMPORARY")
                    elif reason is ConnectReason.PROTOCOL_REJECTED:
                        outcome=PermanentFailure("IOTDA_PROTOCOL_REJECTED")
                    else:
                        outcome=PermanentFailure("IOTDA_CONNECT_REJECTED")
                    return outcome
                phase[0]="publish"
                self.wakeup=published
                deadline=self.monotonic()+self.publish_timeout
                rc,mid=self.client.publish(payload)
                if type(mid) is not int or not 1<=mid<=65535:
                    outcome=PermanentFailure("IOTDA_INVALID_MID")
                    return outcome
                if rc!=0:
                    outcome=RetryableFailure("IOTDA_PUBLISH_FAILED")
                    return outcome
                # start/publish are required to be nonblocking by client contract.
                while True:
                    with self.lock:
                        result=callbacks.get(mid)
                        published.clear()
                    if result is not None:
                        if result[2]>=deadline:
                            outcome=RetryableFailure("IOTDA_PUBACK_TIMEOUT")
                            return outcome
                        if not result[0]:
                            outcome=PermanentFailure("IOTDA_PUBLISH_REJECTED")
                            return outcome
                        outcome=TransportAccepted(dict(provider="iotda-mqtt-puback",
                            receipt_id=f"{message_id}:{attempt_token}:{generation}:{mid}",received_at=result[1]))
                        return outcome
                    if self.stop.is_set() or disconnected.is_set():
                        outcome=RetryableFailure("IOTDA_DISCONNECTED")
                        return outcome
                    remaining=deadline-self.monotonic()
                    if remaining<=0 or not published.wait(remaining):
                        outcome=RetryableFailure("IOTDA_PUBACK_TIMEOUT")
                        return outcome
            except ssl.SSLError:
                outcome=PermanentFailure("IOTDA_TLS_INVALID")
                return outcome
            except Exception:
                outcome=RetryableFailure("IOTDA_CLIENT_FAILED")
                return outcome
            finally:
                # One client generation per attempt prevents stale in-memory sends.
                try:
                    self._dispose()
                except CleanupError:
                    raise CleanupError(outcome) from None
                finally:
                    self.wakeup=None

    def close(self):
        self.stop.set()
        wakeup=self.wakeup
        if wakeup is not None:
            wakeup.set()
        with self.serial:
            # closed permanently forbids sends; retained resources may be retried.
            self.closed=True
            self._dispose()

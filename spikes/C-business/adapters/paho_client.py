"""Paho VERSION2 wrapper, injection-only until real lifecycle acceptance.

No default live factory: callers must explicitly supply a client factory.
Owned non-daemon thread; close failure retains ownership and reports failure.
"""
from datetime import datetime,timezone
from threading import Event,Lock,Thread,current_thread
import math
import ssl
import paho.mqtt.client as mqtt
from adapters.client_protocol import ClientBinding,ConnectReason
from adapters.iotda_auth import generate_credentials
from adapters.paho_reasons import connect_reason,publish_succeeded


class PahoClient:
    def __init__(self,config,*,client_factory,utcnow=lambda:datetime.now(timezone.utc),close_timeout=2):
        if isinstance(close_timeout,bool) or not isinstance(close_timeout,(int,float)) or not math.isfinite(close_timeout) or close_timeout<=0:
            raise ValueError("invalid close timeout")
        credentials=generate_credentials(config.device_id,config.device_secret,now=utcnow())
        self.binding=ClientBinding(config.endpoint,config.device_id,credentials.client_id,
            f"$oc/devices/{config.device_id}/sys/messages/up")
        self.config=config
        self.client=client_factory(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=credentials.client_id,protocol=mqtt.MQTTv311,reconnect_on_failure=False)
        self.client.username_pw_set(credentials.username,credentials.password)
        self.client.tls_set_context(config.tls_context())
        self.client.connect_timeout=config.connect_timeout
        self.close_timeout=close_timeout
        self.stop=Event()
        self.lock=Lock()
        self.thread=None
        self.closed=False
        self.started=False
        self.cleanup_lock=Lock()
        self.disposed=False
        self.failure=None

    def start(self,on_connect,on_publish,on_disconnect):
        with self.lock:
            if self.closed or self.started:
                raise RuntimeError("IOTDA_CLIENT_STATE")
            self.started=True
            self.client.on_connect=lambda c,u,f,r,p: on_connect(connect_reason(r.value))
            self.client.on_publish=lambda c,u,m,r,p: on_publish(m,publish_succeeded(r.value))
            self.client.on_disconnect=lambda c,u,f,r,p: on_disconnect()
            def run():
                try:
                    self.client.connect(self.config.endpoint,self.config.port,60)
                    while not self.stop.is_set():
                        if self.client.loop(timeout=.1)!=mqtt.MQTT_ERR_SUCCESS:
                            break
                except ssl.SSLError:
                    self.failure=ConnectReason.TLS_FAILURE
                except TimeoutError:
                    self.failure=ConnectReason.CONNECT_TIMEOUT
                except OSError:
                    self.failure=ConnectReason.NETWORK_FAILURE
                except Exception:
                    self.failure=ConnectReason.PROTOCOL_REJECTED
                finally:
                    if self.failure is not None:
                        try:
                            on_connect(self.failure)
                        except Exception:
                            pass
                    try:
                        on_disconnect()
                    except Exception:
                        pass
            self.thread=Thread(target=run,name="aquaguard-paho",daemon=False)
            self.thread.start()

    def publish(self,payload):
        with self.lock:
            if self.closed or not self.started:
                raise RuntimeError("IOTDA_CLIENT_STATE")
            info=self.client.publish(self.binding.topic,payload,qos=1,retain=False)
            return info.rc,info.mid

    def close(self):
        with self.cleanup_lock:
            if not self.disposed:
                self._close_owned()

    def _close_owned(self):
        with self.lock:
            self.closed=True
            self.stop.set()
            thread=self.thread
        # No loop_start/loop_stop and no unbounded join. Connection calls may
        # still block; retained thread is an explicit unreleased-resource fault.
        if thread is not None:
            if thread is current_thread():
                raise RuntimeError("IOTDA_CLOSE_FROM_CALLBACK")
            thread.join(self.close_timeout)
            if thread.is_alive():
                raise RuntimeError("IOTDA_THREAD_EXIT_TIMEOUT")
        try:
            self.client.disconnect()
            self.disposed=True
        except Exception:
            raise RuntimeError("IOTDA_DISCONNECT_FAILED") from None

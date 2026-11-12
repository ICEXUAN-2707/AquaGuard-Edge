"""Offline, test-only IoTDA configuration. No network or database access."""
from dataclasses import dataclass, field
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import ssl


class ConfigError(ValueError):
    """Controlled diagnostics never include configuration values."""


def identity(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]+", value) is not None


@dataclass(frozen=True)
class TestBinding:
    local_device_id: str
    cloud_device_id: str
    authorization_class: str
    allowed_origins: tuple[str, ...]

    def __post_init__(self):
        if not identity(self.local_device_id) or not identity(self.cloud_device_id):
            raise ConfigError("invalid device binding")
        expected = {"test_hardware": ("hardware",), "simulation_test": ("simulation",)}
        if expected.get(self.authorization_class) != self.allowed_origins:
            raise ConfigError("invalid test authorization")


@dataclass(frozen=True)
class CloudConfig:
    endpoint: str
    port: int
    ca_file: Path
    device_id: str
    device_secret: str = field(repr=False)
    connect_timeout: float
    publish_timeout: float
    bindings: tuple[TestBinding, ...]

    def __post_init__(self):
        if not isinstance(self.endpoint,str) or len(self.endpoint)>253:
            raise ConfigError("invalid endpoint")
        labels=self.endpoint.split(".")
        if len(labels)<2 or any(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", x) is None for x in labels):
            raise ConfigError("invalid endpoint")
        try:
            ipaddress.ip_address(self.endpoint)
        except ValueError:
            pass
        else:
            raise ConfigError("endpoint must be a DNS hostname")
        if type(self.port) is not int or not 1<=self.port<=65535:
            raise ConfigError("invalid port")
        if not identity(self.device_id) or not isinstance(self.device_secret,str) or not self.device_secret.strip():
            raise ConfigError("invalid device credentials")
        for duration in (self.connect_timeout,self.publish_timeout):
            if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
                raise ConfigError("invalid timeout")
        if not isinstance(self.bindings,tuple) or not self.bindings or any(not isinstance(b,TestBinding) for b in self.bindings):
            raise ConfigError("test bindings required")
        if len({b.local_device_id for b in self.bindings})!=len(self.bindings) or any(b.cloud_device_id!=self.device_id for b in self.bindings):
            raise ConfigError("conflicting test bindings")
        try:
            if not isinstance(self.ca_file,Path) or not self.ca_file.is_file():
                raise ValueError()
            self.tls_context()
        except (OSError,ValueError,ssl.SSLError):
            raise ConfigError("invalid CA file") from None

    def tls_context(self):
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode=ssl.CERT_REQUIRED
        context.check_hostname=True
        context.load_verify_locations(cafile=str(self.ca_file))
        return context

    def authorize(self,local_device_id,origin):
        if not any(b.local_device_id==local_device_id and origin in b.allowed_origins for b in self.bindings):
            raise ConfigError("device or origin not authorized")

    def redact(self,text):
        return str(text).replace(self.device_secret,"[REDACTED]")


def load_config(environ=None):
    env=os.environ if environ is None else environ
    prefix="AQUAGUARD_IOTDA_"
    def required(key):
        value=env.get(prefix+key)
        if not isinstance(value,str) or not value.strip():
            raise ConfigError("missing "+prefix+key)
        return value
    try:
        data=json.loads(Path(required("BINDINGS_FILE")).read_text(encoding="utf-8"))
        if not isinstance(data,dict) or set(data)!={"environment","bindings"} or data["environment"]!="test":
            raise ValueError()
        bindings=[]
        for item in data["bindings"]:
            if set(item)!={"local_device_id","cloud_device_id","authorization_class","allowed_origins"}:
                raise ValueError()
            bindings.append(TestBinding(item["local_device_id"],item["cloud_device_id"],item["authorization_class"],tuple(item["allowed_origins"])))
        return CloudConfig(endpoint=required("ENDPOINT"),port=int(env.get(prefix+"PORT","8883")),
            ca_file=Path(required("CA_FILE")),device_id=required("DEVICE_ID"),device_secret=required("DEVICE_SECRET"),
            connect_timeout=float(env.get(prefix+"CONNECT_TIMEOUT","5")),
            publish_timeout=float(env.get(prefix+"PUBACK_TIMEOUT","10")),bindings=tuple(bindings))
    except ConfigError:
        raise
    except (ValueError,TypeError,KeyError,OSError):
        raise ConfigError("invalid IoTDA configuration") from None

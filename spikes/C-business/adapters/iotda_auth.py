"""Pure IoTDA secret authentication, no client construction or IO."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
from cloud_config import identity


@dataclass(frozen=True)
class Credentials:
    client_id: str
    username: str
    password: str = field(repr=False)


def generate_credentials(device_id,device_secret,*,now,verify_timestamp=True):
    if (not identity(device_id) or len(device_id)>241 or not isinstance(device_secret,str) or not device_secret.strip() or
            not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None or
            type(verify_timestamp) is not bool):
        raise ValueError("invalid IoTDA authentication input")
    timestamp=now.astimezone(timezone.utc).strftime("%Y%m%d%H")
    signature=hmac.new(timestamp.encode("ascii"),device_secret.encode("utf-8"),hashlib.sha256).hexdigest()
    return Credentials(f"{device_id}_0_{int(verify_timestamp)}_{timestamp}",device_id,signature)

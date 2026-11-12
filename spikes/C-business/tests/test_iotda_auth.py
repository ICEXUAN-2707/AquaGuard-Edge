from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from adapters.iotda_auth import generate_credentials
from adapters.paho_reasons import connect_reason,publish_succeeded
from adapters.client_protocol import ConnectReason


def test_official_hmac_vector_and_secret_repr():
    result=generate_credentials("dummy-device","12345678",now=datetime(2025,4,14,1,tzinfo=timezone.utc))
    assert result.password=="c75150e6cb841417396819e4d2ee4358a416344a03a083e3a8567074ddec820a"
    assert result.client_id=="dummy-device_0_1_2025041401"
    assert result.username=="dummy-device"
    assert result.password not in repr(result) and "12345678" not in repr(result)


def test_utc_conversion_and_unverified_timestamp_mode():
    result=generate_credentials("dummy","secret",now=datetime(2025,4,14,9,tzinfo=timezone(timedelta(hours=8))),verify_timestamp=False)
    assert result.client_id=="dummy_0_0_2025041401"


@pytest.mark.parametrize("device,secret,now",[("bad/topic","s",datetime.now(timezone.utc)),("dummy","",datetime.now(timezone.utc)),("dummy","s",datetime(2025,1,1))])
def test_invalid_auth(device,secret,now):
    with pytest.raises(ValueError): generate_credentials(device,secret,now=now)


@pytest.mark.parametrize("code,expected",[(0,ConnectReason.ACCEPTED),(134,ConnectReason.AUTH_REJECTED),(135,ConnectReason.AUTH_REJECTED),(136,ConnectReason.TEMPORARY_FAILURE),(137,ConnectReason.TEMPORARY_FAILURE),(132,ConnectReason.PROTOCOL_REJECTED),(True,ConnectReason.PROTOCOL_REJECTED)])
def test_reason_mapping(code,expected):
    assert connect_reason(code) is expected


def test_publish_codes():
    assert publish_succeeded(0) and publish_succeeded(16)
    assert not publish_succeeded(128) and not publish_succeeded(True)


def test_disconnect_only_code_is_not_transient_connack():
    assert connect_reason(139) is ConnectReason.PROTOCOL_REJECTED


def test_client_id_platform_length_limit():
    with pytest.raises(ValueError):
        generate_credentials("x"*242,"secret",now=datetime.now(timezone.utc))


def test_real_paho_version2_normalization():
    from paho.mqtt.client import convert_connack_rc_to_reason_code
    for legacy,expected in [(0,ConnectReason.ACCEPTED),(1,ConnectReason.PROTOCOL_REJECTED),
                            (3,ConnectReason.TEMPORARY_FAILURE),(4,ConnectReason.AUTH_REJECTED),(5,ConnectReason.AUTH_REJECTED)]:
        assert connect_reason(convert_connack_rc_to_reason_code(legacy).value) is expected

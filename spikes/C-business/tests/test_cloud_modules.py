"""Offline config/mapping checks; CA bundle is local, no network."""
from copy import deepcopy
import json
from pathlib import Path
import ssl
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from cloud_config import CloudConfig,ConfigError,TestBinding as Binding,load_config
from cloud_mapping import build_payload,MappingError


@pytest.fixture
def environment(tmp_path):
    ca=Path(sys.prefix)/"Lib/site-packages/pip/_vendor/certifi/cacert.pem"
    assert ca.is_file(), "local pip CA fixture missing"
    bindings=tmp_path/"bindings.json"
    bindings.write_text(json.dumps(dict(environment="test",bindings=[dict(local_device_id="demo01",
        cloud_device_id="test-cloud",authorization_class="simulation_test",allowed_origins=["simulation"])])),encoding="utf-8")
    return {"AQUAGUARD_IOTDA_ENDPOINT":"test.example.invalid","AQUAGUARD_IOTDA_CA_FILE":str(ca),
        "AQUAGUARD_IOTDA_DEVICE_ID":"test-cloud","AQUAGUARD_IOTDA_DEVICE_SECRET":"SENTINEL-secret",
        "AQUAGUARD_IOTDA_BINDINGS_FILE":str(bindings)}


@pytest.fixture
def snapshot():
    examples=json.loads((ROOT/"reference/reference_02/contracts/examples.json").read_text(encoding="utf-8"))
    event=deepcopy(examples["SafetyEvent"]); transition=deepcopy(examples["EventTransition"])
    event.update(device_id="demo01",origin="simulation")
    transition.update(event_id=event["event_id"],event_version=event["version"],origin="simulation")
    return dict(schema_version="1.1",message_id="stable-message",event=event,transition=transition)


def test_normal_config_and_tls(environment):
    config=load_config(environment)
    assert config.port==8883 and config.connect_timeout==5 and config.publish_timeout==10
    tls=config.tls_context()
    assert tls.check_hostname and tls.verify_mode==ssl.CERT_REQUIRED


@pytest.mark.parametrize("key",["ENDPOINT","CA_FILE","DEVICE_ID","DEVICE_SECRET","BINDINGS_FILE"])
def test_missing_config(environment,key):
    del environment["AQUAGUARD_IOTDA_"+key]
    with pytest.raises(ConfigError): load_config(environment)


@pytest.mark.parametrize("port",["0","65536","bad","True","1.5"])
def test_bad_port(environment,port):
    environment["AQUAGUARD_IOTDA_PORT"]=port
    with pytest.raises(ConfigError): load_config(environment)


@pytest.mark.parametrize("endpoint",["https://host.example","bad/path","127.0.0.1","-bad.example"])
def test_bad_endpoint(environment,endpoint):
    environment["AQUAGUARD_IOTDA_ENDPOINT"]=endpoint
    with pytest.raises(ConfigError): load_config(environment)


def test_bad_ca(environment,tmp_path):
    environment["AQUAGUARD_IOTDA_CA_FILE"]=str(tmp_path/"missing.pem")
    with pytest.raises(ConfigError): load_config(environment)
    bad=tmp_path/"bad.pem"; bad.write_text("not a CA")
    environment["AQUAGUARD_IOTDA_CA_FILE"]=str(bad)
    with pytest.raises(ConfigError): load_config(environment)


@pytest.mark.parametrize("timeout",["0","-1","nan","inf","bad"])
def test_bad_timeout(environment,timeout):
    environment["AQUAGUARD_IOTDA_PUBACK_TIMEOUT"]=timeout
    with pytest.raises(ConfigError): load_config(environment)


def test_secret_redaction(environment,capsys,caplog):
    config=load_config(environment)
    assert "SENTINEL-secret" not in repr(config)
    assert config.redact("error SENTINEL-secret")=="error [REDACTED]"
    environment["AQUAGUARD_IOTDA_PORT"]="SENTINEL-secret"
    with pytest.raises(ConfigError) as error: load_config(environment)
    assert "SENTINEL-secret" not in str(error.value)
    assert not caplog.text and capsys.readouterr()==("","")


@pytest.mark.parametrize("device,origin",[("other","simulation"),("demo01","hardware"),("demo01","unknown"),("demo01","mixed")])
def test_unauthorized(environment,device,origin):
    with pytest.raises(ConfigError): load_config(environment).authorize(device,origin)


def test_mapping_stable_and_immutable(environment,snapshot):
    original=deepcopy(snapshot); config=load_config(environment)
    first=build_payload(snapshot,config)
    assert first==build_payload(snapshot,config) and snapshot==original
    content=json.loads(first)["content"]
    assert content["message_id"]==snapshot["message_id"]
    assert content["event_id"]==snapshot["event"]["event_id"]
    assert content["transition_id"]==snapshot["transition"]["transition_id"]
    assert content["event_version"]==snapshot["event"]["version"]
    assert content["schema_version"]=="1.1" and content["mapping_version"]=="aquaguard-transition-v1"
    assert "SENTINEL-secret" not in first and "attempt_token" not in content and "mid" not in content


@pytest.mark.parametrize("bad",[None,{},[],{"schema_version":"1.1"}])
def test_invalid_snapshot(environment,bad):
    with pytest.raises(MappingError): build_payload(bad,load_config(environment))


@pytest.mark.parametrize("field,value",[("event",None),("transition",{}),("message_id",""),("schema_version","2")])
def test_invalid_dto(environment,snapshot,field,value):
    snapshot[field]=value
    with pytest.raises(MappingError): build_payload(snapshot,load_config(environment))


def test_lineage_mismatch(environment,snapshot):
    snapshot["transition"]["event_version"]=snapshot["event"]["version"]+1
    with pytest.raises(MappingError): build_payload(snapshot,load_config(environment))


def test_mapping_unauthorized(environment,snapshot):
    snapshot["event"]["device_id"]="other"
    with pytest.raises(ConfigError): build_payload(snapshot,load_config(environment))

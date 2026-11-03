from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import importlib.util

import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from water import WaterService
from policy import Policy
from store import Conflict

T=datetime(2026,11,2,tzinfo=timezone.utc)


def time(second):
    return (T+timedelta(seconds=second)).isoformat()


def observation(second,wet=True,*,boot="b1",seq=None,quality="valid",device="home01",source="simulation"):
    seq=second if seq is None else seq
    return dict(schema_version="1.1",observation_id=f"{device}/{boot}/{seq}",device_id=device,sensor_type="water",
                boot_id=boot,seq=seq,uptime_ms=seq*1000,event_time=None,received_at=time(second),
                time_basis="RECEIVED_FALLBACK",value=dict(wet=wet),quality=quality,source=source)


def ingest(service,second,wet=True,*,now=None,policy=None,version="v1",fault=None,**changes):
    return service.ingest(observation(second,wet,**changes),now=time(second if now is None else now),
                          policy=policy or Policy(10,2),policy_version=version,trusted_device="home01",
                          trusted_source="simulation",escalation_level="L2",fault_at=fault)


def rows(service):
    with service.connection() as db:
        return tuple(db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in
                     ("events","transitions","outbox","water_inputs","water_state","water_boots"))


def test_durable_clear_rewet_and_ack_replay(tmp_path):
    service=WaterService(tmp_path/"db")
    event=ingest(service,0)["event"]
    ack=dict(schema_version="1.1",expected_version=1,idempotency_key="a",ack_type="ACKNOWLEDGE")
    original=service.ack(event["event_id"],ack,now=time(0),authorized=True)
    assert ingest(service,1,False)["event"]["physical_status"]=="UNKNOWN"
    service=WaterService(service.path)
    cleared=ingest(service,3,False)["event"]
    assert cleared["physical_status"]=="CLEARED" and cleared["lifecycle"]=="OPEN"
    wet=ingest(service,4)["event"]
    assert wet["event_id"]==event["event_id"] and wet["physical_status"]=="ACTIVE"
    assert wet["ack_status"]=="ACKNOWLEDGED"
    assert service.ack(event["event_id"],ack,now=time(4),authorized=True)==original
    assert len(service.detail(event["event_id"])["transitions"])==5


def test_duplicate_cannot_refresh_ttl_or_dry_chain(tmp_path):
    service=WaterService(tmp_path/"db")
    event=ingest(service,0)["event"]
    assert ingest(service,0,now=9)["status"]=="DUPLICATE"
    assert service.expire("home01",now=time(10),policy=Policy(10,2),policy_version="v1")["physical_status"]=="ACTIVE"
    expired=service.expire("home01",now=time(11),policy=Policy(10,2),policy_version="v1")
    assert expired["physical_status"]=="UNKNOWN"
    assert service.expire("home01",now=time(12),policy=Policy(10,2),policy_version="v1")==expired
    with pytest.raises(Conflict,match="out-of-order"):
        ingest(service,1,now=12)
    assert ingest(service,12,False)["event"]["physical_status"]=="UNKNOWN"
    assert service.detail(event["event_id"])["event"]["version"]==2


@pytest.mark.parametrize("kind",["boot","config","unknown","gap"])
def test_dry_chain_reset(tmp_path,kind):
    service=WaterService(tmp_path/"db")
    ingest(service,0)
    ingest(service,1,False)
    if kind=="boot":
        result=ingest(service,3,False,boot="b2",seq=0)
    elif kind=="config":
        result=ingest(service,3,False,version="v2")
    elif kind=="unknown":
        ingest(service,2,None,quality="unknown")
        result=ingest(service,3,False)
    else:
        result=ingest(service,12,False)
    assert result["event"]["physical_status"]=="UNKNOWN"


def test_rejects_identity_conflict_retired_boot_and_out_of_order(tmp_path):
    service=WaterService(tmp_path/"db")
    ingest(service,0)
    with pytest.raises(Conflict,match="identity"):
        ingest(service,0,False)
    ingest(service,2)
    with pytest.raises(Conflict,match="out-of-order"):
        ingest(service,1)
    ingest(service,3,boot="b2",seq=0)
    with pytest.raises(Conflict,match="retired"):
        ingest(service,4,boot="b1")
    assert rows(service)==(1,1,1,3,1,2)


@pytest.mark.parametrize("point",["event","transition","outbox","state"])
def test_ingress_rollback_includes_evidence_and_policy_state(tmp_path,point):
    service=WaterService(tmp_path/"db")
    with pytest.raises(RuntimeError):
        ingest(service,0,fault=point)
    assert rows(service)==(0,0,0,0,0,0)
    ingest(service,0)
    before=rows(service)
    with pytest.raises(RuntimeError):
        ingest(service,1,False,fault=point)
    assert rows(service)==before
    assert ingest(service,1,False)["event"]["physical_status"]=="UNKNOWN"


def test_timer_rollback_and_clock(tmp_path):
    service=WaterService(tmp_path/"db")
    ingest(service,0)
    with pytest.raises(RuntimeError):
        service.expire("home01",now=time(11),policy=Policy(10,2),policy_version="v1",fault_at="state")
    assert rows(service)==(1,1,1,1,1,1)
    assert service.expire("home01",now=time(11),policy=Policy(10,2),policy_version="v1")["physical_status"]=="UNKNOWN"
    with pytest.raises(Conflict,match="backwards"):
        service.expire("home01",now=time(10),policy=Policy(10,2),policy_version="v1")
    with pytest.raises(Conflict,match="policy"):
        service.expire("home01",now=time(12),policy=Policy(10,2),policy_version="v2")


def test_source_clock_shape_and_unavailable_never_create(tmp_path):
    service=WaterService(tmp_path/"db")
    assert ingest(service,0,None,quality="unknown")["event"] is None
    with pytest.raises(ValueError,match="trusted"):
        ingest(service,1,source="hardware")
    payload=observation(1)
    payload.update(time_basis="DEVICE_SYNCED",event_time=time(1))
    with pytest.raises(ValueError,match="clock evidence"):
        service.ingest(payload,now=time(1),policy=Policy(10,2),policy_version="v1",
                       trusted_device="home01",trusted_source="simulation",escalation_level="L2")


def test_ack_cannot_move_transition_clock_backwards(tmp_path):
    service=WaterService(tmp_path/"db")
    event=ingest(service,0)["event"]
    event=ingest(service,3,False)["event"]
    with pytest.raises(ValueError,match="backwards"):
        service.ack(event["event_id"],dict(schema_version="1.1",expected_version=2,idempotency_key="x",ack_type="ACKNOWLEDGE"),now=time(1),authorized=True)


def test_pre_event_dry_evidence_cannot_cross_sources(tmp_path):
    service=WaterService(tmp_path/"db")
    ingest(service,0,False)
    with pytest.raises(Conflict,match="source change"):
        service.ingest(observation(2,False,source="hardware"),now=time(2),policy=Policy(10,2),policy_version="v1",
                       trusted_device="home01",trusted_source="hardware",escalation_level="L2")


def test_duplicate_dry_does_not_count_as_new_confirmation(tmp_path):
    service=WaterService(tmp_path/"db")
    ingest(service,0)
    event=ingest(service,1,False)["event"]
    assert ingest(service,1,False,now=3)["status"]=="DUPLICATE"
    assert service.detail(event["event_id"])["event"]["physical_status"]=="UNKNOWN"


def test_a_actual_normalizer_output_crosses_c_boundary(tmp_path):
    spec=importlib.util.spec_from_file_location("a_water_core",ROOT/"spikes/SP-02/src/core.py")
    core=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    import json
    raw=core.sample(0,"water")
    raw["value"]["wet"]=True
    normalized=core.normalize(json.dumps(raw),"prototype01","simulation",received_at=time(0))
    service=WaterService(tmp_path/"db")
    result=service.ingest(normalized,now=time(0),policy=Policy(10,2),policy_version="v1",
                          trusted_device="prototype01",trusted_source="simulation",escalation_level="L2")
    assert result["signal"]["observation_refs"]==[raw["observation_id"]]
    assert result["event"]["origin"]=="simulation"
    assert result["event"]["physical_status"]=="ACTIVE"

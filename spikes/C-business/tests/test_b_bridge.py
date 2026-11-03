import importlib.util
from pathlib import Path
import sys
import copy
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from b_bridge import publish_window
from projections import Projections,Unavailable
from water import WaterService
from policy import Policy


def fixture(root,**kwargs):
    spec=importlib.util.spec_from_file_location("b_rules_cross_fixture",ROOT/"spikes/SP-04/tests/test_rules.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fixture(root,**kwargs)


def test_actual_b_pipeline_is_fresh_idempotent_and_never_clears_wet_event(tmp_path):
    checkpoints=tmp_path/"checkpoints"
    fw=fixture(checkpoints,attended=True,wet=True)
    queries=Projections(tmp_path/"db")
    now="2026-10-29T00:00:32Z"
    result=publish_window(queries,fw,now=now,checkpoint_root=checkpoints)
    assert result["situation"]=="ATTENDED_FLOW"
    assert publish_window(queries,fw,now="2026-10-29T00:00:39Z",checkpoint_root=checkpoints)==result
    service=WaterService(queries.path)
    obs=dict(schema_version="1.1",observation_id="fast-wet-1",device_id="demo",sensor_type="water",boot_id="fast-boot",
             seq=0,uptime_ms=0,event_time=None,received_at=now,time_basis="RECEIVED_FALLBACK",value=dict(wet=True),quality="valid",source="simulation")
    event=service.ingest(obs,now=now,policy=Policy(10,2),policy_version="cross-v1",trusted_device="demo",trusted_source="simulation",escalation_level="L2")["event"]
    publish_window(queries,fw,now="2026-10-29T00:00:40Z",checkpoint_root=checkpoints)
    assert service.detail(event["event_id"])["event"]["physical_status"]=="ACTIVE"
    with pytest.raises(Unavailable):
        queries.read("assessment","demo",now="2026-10-29T00:00:41Z")
    with pytest.raises(ValueError,match="stale"):
        publish_window(queries,fw,now="2026-10-29T00:00:41Z",checkpoint_root=checkpoints)


def test_b_checkpoint_tampering_and_root_escape_rejected(tmp_path):
    checkpoints=tmp_path/"checkpoints"
    fw=fixture(checkpoints)
    queries=Projections(tmp_path/"db")
    bad=copy.deepcopy(fw)
    bad["features"]["flow_mean_lpm"]=999
    with pytest.raises(ValueError):
        publish_window(queries,bad,now="2026-10-29T00:00:32Z",checkpoint_root=checkpoints)
    other=tmp_path/"other"
    other.mkdir()
    with pytest.raises(ValueError,match="outside"):
        publish_window(queries,fw,now="2026-10-29T00:00:32Z",checkpoint_root=other)
    with queries.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM query_projections").fetchone()[0]==0


def test_live_and_assessment_publish_roll_back_together(tmp_path):
    checkpoints=tmp_path/"checkpoints"
    fw=fixture(checkpoints)
    queries=Projections(tmp_path/"db")
    publish_window(queries,fw,now="2026-10-29T00:00:32Z",checkpoint_root=checkpoints)
    with queries.connection() as db:
        db.execute("DELETE FROM query_projections WHERE kind='live'")
        db.execute("UPDATE query_projections SET body='{}' WHERE kind='assessment'")
    with pytest.raises(ValueError,match="conflicting"):
        publish_window(queries,fw,now="2026-10-29T00:00:32Z",checkpoint_root=checkpoints)
    with queries.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM query_projections WHERE kind='live'").fetchone()[0]==0

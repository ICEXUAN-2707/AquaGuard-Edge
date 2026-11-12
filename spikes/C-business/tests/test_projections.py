from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from projections import Projections
from api import create_app
from test_api import http, TOKEN, NOW, EX, setup


def live():
    return dict(schema_version="1.1",device_id="home01",captured_at=NOW.replace("+00:00","Z"),
                sensor_summary=EX["AlignedWindow"]["sensor_summary"],data_quality="VALID",
                cloud_status="OFFLINE",origin="simulation")


def test_four_query_routes_and_persistent_freshness(tmp_path):
    store,app,events=setup(tmp_path)
    queries=Projections(store.path)
    queries.publish("live",live(),captured_at=NOW,ttl_seconds=10)
    response=dict(schema_version="1.1",assessment=EX["SituationAssessment"],safety_signals=[])
    queries.publish("assessment",response,captured_at=NOW,ttl_seconds=10)
    trial=dict(schema_version="1.1",trial_id="trial1",source="simulation",status="PLANNED",
               started_at=None,ended_at=None,asset_refs=[])
    queries.publish("experiment",trial,captured_at=NOW)
    assert http(app,"GET","/api/devices/home01/live")== (200,live())
    assert http(app,"GET","/api/devices/"+response["assessment"]["device_id"]+"/assessment")[0]==200
    assert http(app,"GET","/api/experiments/trial1")== (200,trial)
    assert http(app,"GET","/api/experiments/trial1",auth=False)[0]==401
    status,sync=http(app,"GET","/api/sync/status")
    assert status==200 and sync["pending_count"]==3 and sync["last_ack_level"]=="NONE"
    assert http(app,"GET","/api/sync/status",query=dict(device_id="a"))[1]["pending_count"]==1
    later=(datetime.fromisoformat(NOW)+timedelta(seconds=11)).isoformat()
    reopened=create_app(Projections(store.path),token=TOKEN,cursor_key=b"x"*32,clock=lambda:later)
    assert http(reopened,"GET","/api/devices/home01/live")[0]==503
    assert http(reopened,"GET","/api/devices/"+response["assessment"]["device_id"]+"/assessment")[0]==503
    assert http(reopened,"GET","/api/devices/missing/live")[0]==404


def test_projection_conflicts_do_not_override(tmp_path):
    queries=Projections(tmp_path/"db")
    queries.publish("live",live(),captured_at=NOW,ttl_seconds=10)
    with pytest.raises(ValueError,match="conflicting"):
        queries.publish("live",dict(live(),origin="hardware"),captured_at=NOW,ttl_seconds=10)
    with pytest.raises(ValueError,match="TTL"):
        queries.publish("live",live(),captured_at=NOW)
    response=dict(schema_version="1.1",assessment=EX["SituationAssessment"],
                  safety_signals=[dict(EX["SafetySignal"],device_id="wrong")])
    with pytest.raises(ValueError,match="mismatch"):
        queries.publish("assessment",response,captured_at=NOW,ttl_seconds=10)
    assert queries.read("live","home01",now=NOW)==live()


def test_sync_requires_real_recorded_receipt_level(tmp_path):
    store,app,events=setup(tmp_path)
    with store.connection() as db:
        row=db.execute("SELECT transition_id,body FROM outbox LIMIT 1").fetchone()
        value=json.loads(row[1])
        value.update(sync_status="ACCEPTED",transport_receipt=dict(provider="mock",receipt_id="t1",received_at=NOW))
        db.execute("UPDATE outbox SET body=? WHERE transition_id=?",(json.dumps(value),row[0]))
    status,sync=http(app,"GET","/api/sync/status")
    assert status==200 and sync["last_ack_level"]=="TRANSPORT" and sync["pending_count"]==2
    with store.connection() as db:
        value["business_receipt"]=dict(provider="mock-consumer",receipt_id="b1",received_at=NOW)
        db.execute("UPDATE outbox SET body=? WHERE transition_id=?",(json.dumps(value),row[0]))
    assert http(app,"GET","/api/sync/status")[1]["last_ack_level"]=="BUSINESS"


@pytest.mark.parametrize("path",["/api/devices/home01/live","/api/devices/home01/assessment","/api/sync/status","/api/experiments/trial1"])
def test_query_permissions(tmp_path,path):
    store,app,events=setup(tmp_path)
    assert http(app,"GET",path,auth=False)[0]==401


def test_invalid_sync_receipt_returns_unavailable(tmp_path):
    store,app,events=setup(tmp_path)
    with store.connection() as db:
        row=db.execute("SELECT transition_id,body FROM outbox LIMIT 1").fetchone()
        value=json.loads(row[1])
        value["sync_status"]="ACCEPTED"
        db.execute("UPDATE outbox SET body=? WHERE transition_id=?",(json.dumps(value),row[0]))
    status,error=http(app,"GET","/api/sync/status")
    assert status==503 and error["details"]=={} and error["code"]=="SERVICE_UNAVAILABLE"


def test_all_seven_candidate_paths_exist(tmp_path):
    store,app,events=setup(tmp_path)
    paths=app.openapi()['paths']
    assert {'/api/events','/api/events/{event_id}','/api/events/{event_id}/ack',
            '/api/devices/{device_id}/live','/api/devices/{device_id}/assessment',
            '/api/sync/status','/api/experiments/{trial_id}'} <= paths.keys()
    assert 'post' in paths['/api/events/{event_id}/close']

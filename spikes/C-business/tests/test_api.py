import asyncio
import json
from pathlib import Path
import sys
import pytest
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from api import create_app
from store import Store
from edge.contracts.models import ApiError

TOKEN="prototype-test-token-32-characters"
NOW="2026-11-02T00:00:00+00:00"
EX=json.loads((ROOT/"reference/reference_02/contracts/examples.json").read_text(encoding="utf-8"))


def http(app,method,path,body=None,auth=True,query=None):
    async def run():
        outputs=[]
        sent=False
        async def receive():
            nonlocal sent
            if not sent:
                sent=True
                return dict(type="http.request",body=b"" if body is None else json.dumps(body).encode(),more_body=False)
            await asyncio.Event().wait()
        async def send(message):
            outputs.append(message)
        headers=[(b"content-type",b"application/json")]
        if auth:
            headers.append((b"authorization",("Bearer "+TOKEN).encode()))
        scope=dict(type="http",asgi=dict(version="3.0"),http_version="1.1",method=method,
                   scheme="http",path=path,raw_path=path.encode(),query_string=urlencode(query or {}).encode(),
                   root_path="",headers=headers,client=("127.0.0.1",1),server=("127.0.0.1",8000))
        await app(scope,receive,send)
        status=next(m["status"] for m in outputs if m["type"]=="http.response.start")
        data=b"".join(m.get("body",b"") for m in outputs if m["type"]=="http.response.body")
        return status,json.loads(data)
    return asyncio.run(run())


def setup(tmp_path):
    store=Store(tmp_path/"api.sqlite")
    events=[]
    for device in ("a","b","c"):
        signal=dict(EX["SafetySignal"],device_id=device,observed_at=NOW)
        events.append(store.open_water(signal,now=NOW,escalation_level="L2",ttl_seconds=10))
    return store,create_app(store,token=TOKEN,cursor_key=b"x"*32,clock=lambda: NOW),events


def test_http_ack_replay_conflict_and_auth(tmp_path):
    store,app,events=setup(tmp_path)
    path="/api/events/"+events[0]["event_id"]+"/ack"
    body=dict(schema_version="1.1",expected_version=1,idempotency_key="ack",ack_type="ACKNOWLEDGE")
    status,error=http(app,"POST",path,body,auth=False)
    assert status==401 and ApiError.model_validate(error).code=="UNAUTHORIZED"
    assert store.detail(events[0]["event_id"])["event"]["version"]==1
    status,result=http(app,"POST",path,body)
    assert status==200 and result["event"]["physical_status"]=="ACTIVE"
    assert http(app,"POST",path,body)==(200,result)
    status,error=http(app,"POST",path,dict(body,idempotency_key="new"))
    assert status==409 and error["details"]==dict(expected_version=1,actual_version=2)
    status,error=http(app,"POST",path,dict(body,expected_version=2))
    assert status==409 and error["code"]=="IDEMPOTENCY_CONFLICT"


def test_pagination_tie_filter_and_cursor_integrity(tmp_path):
    store,app,events=setup(tmp_path)
    identifiers=[]
    query=dict(limit=1)
    while True:
        status,page=http(app,"GET","/api/events",query=query)
        assert status==200
        identifiers.extend(e["event_id"] for e in page["items"])
        if not page["next_cursor"]:
            break
        query["cursor"]=page["next_cursor"]
    assert identifiers==sorted((e["event_id"] for e in events),reverse=True)
    _,first=http(app,"GET","/api/events",query=dict(limit=1))
    for query in (dict(cursor="broken"),dict(cursor=first["next_cursor"],device_id="a"),dict(limit=0),dict(lifecycle="WRONG")):
        status,error=http(app,"GET","/api/events",query=query)
        assert status==400
        ApiError.model_validate(error)


def test_detail_missing_and_validation(tmp_path):
    store,app,events=setup(tmp_path)
    assert http(app,"GET","/api/events/"+events[0]["event_id"])[0]==200
    status,error=http(app,"GET","/api/events/missing")
    assert status==404 and error["code"]=="NOT_FOUND"
    status,error=http(app,"POST","/api/events/"+events[0]["event_id"]+"/ack",{})
    assert status==400 and error["code"]=="BAD_REQUEST"


def test_database_failure_is_sanitized(tmp_path):
    store,app,events=setup(tmp_path)
    with store.connection() as db:
        db.execute("DROP TABLE operations")
    body=dict(schema_version="1.1",expected_version=1,idempotency_key="a",ack_type="ACKNOWLEDGE")
    status,error=http(app,"POST","/api/events/"+events[0]["event_id"]+"/ack",body)
    assert status==503 and error["code"]=="SERVICE_UNAVAILABLE"
    assert error["details"]=={} and "SQL" not in json.dumps(error)
    assert store.detail(events[0]["event_id"])["event"]["version"]==1


def test_timezone_order_and_filter(tmp_path):
    store,app,events=setup(tmp_path)
    # 01:00+08 is older than 00:00Z despite lexical timestamp ordering.
    signal=dict(EX["SafetySignal"],device_id="older",observed_at="2026-11-02T01:00:00+08:00")
    old=store.open_water(signal,now=signal["observed_at"],escalation_level="L2",ttl_seconds=10)
    _,page=http(app,"GET","/api/events")
    assert page["items"][-1]["event_id"]==old["event_id"]
    _,page=http(app,"GET","/api/events",query=dict(device_id="older",lifecycle="OPEN"))
    assert len(page["items"])==1
    assert http(app,"GET","/api/events",auth=False)[0]==401


def test_configuration_has_no_implicit_secret(tmp_path):
    store=Store(tmp_path/"db")
    with pytest.raises(ValueError):
        create_app(store,token="",cursor_key=b"x"*32)

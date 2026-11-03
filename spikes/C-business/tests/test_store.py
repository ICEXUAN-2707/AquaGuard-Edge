import importlib.util
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from edge.contracts.models import CloudSyncRecord
spec = importlib.util.spec_from_file_location("c_business_store",ROOT/"spikes/C-business/store.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
EX = json.loads((ROOT/"reference/reference_02/contracts/examples.json").read_text(encoding="utf-8"))
NOW = "2026-11-02T00:00:00+00:00"


def signal(**changes):
    return dict(EX["SafetySignal"], **dict(observed_at=NOW,**changes))


def open_event(store, **kwargs):
    return store.open_water(signal(),now=NOW,escalation_level="L2",ttl_seconds=10,**kwargs)


def request(version=1,key="ack-1"):
    return dict(schema_version="1.1",expected_version=version,idempotency_key=key,ack_type="ACKNOWLEDGE")


def counts(store):
    with store.connection() as db:
        return tuple(db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in ("events","transitions","outbox","operations"))


def test_full_projection_ack_and_replay_survive_reopen(tmp_path):
    store = m.Store(tmp_path/"events.sqlite")
    event = open_event(store)
    result = store.ack(event["event_id"],request(),now=NOW,authorized=True)
    assert result["event"]["version"] == 2
    assert result["event"]["physical_status"] == "ACTIVE"
    assert result["event"]["lifecycle"] == "OPEN"
    reopened = m.Store(store.path)
    assert reopened.ack(event["event_id"],request(),now=NOW,authorized=True) == result
    assert counts(store) == (1,2,2,1)
    detail = store.detail(event["event_id"])
    assert [r["event_version"] for r in detail["transitions"]] == [1,2]
    with store.connection() as db:
        for row in db.execute("SELECT body FROM outbox"):
            sync = CloudSyncRecord.model_validate(json.loads(row[0]))
            assert sync.origin == event["origin"] and sync.sync_status == "PENDING"


def test_conflicts_and_authorization(tmp_path):
    store = m.Store(tmp_path/"db")
    event = open_event(store)
    with pytest.raises(PermissionError):
        store.ack(event["event_id"],request(),now=NOW)
    store.ack(event["event_id"],request(),now=NOW,authorized=True)
    with pytest.raises(m.Conflict,match="idempotency"):
        store.ack(event["event_id"],request(2),now=NOW,authorized=True)
    with pytest.raises(m.VersionConflict):
        store.ack(event["event_id"],request(1,"new"),now=NOW,authorized=True)
    with pytest.raises(m.NotFound):
        store.detail("missing")
    assert counts(store) == (1,2,2,1)


@pytest.mark.parametrize("fault",["event","transition","outbox"])
def test_create_is_atomic(tmp_path,fault):
    store=m.Store(tmp_path/"db")
    with pytest.raises(RuntimeError):
        open_event(store,fault_at=fault)
    assert counts(store)==(0,0,0,0)


@pytest.mark.parametrize("fault",["event","transition","outbox","operation"])
def test_ack_and_operation_are_atomic(tmp_path,fault):
    store=m.Store(tmp_path/"db")
    event=open_event(store)
    with pytest.raises(RuntimeError):
        store.ack(event["event_id"],request(),now=NOW,authorized=True,fault_at=fault)
    assert counts(store)==(1,1,1,0)
    assert store.detail(event["event_id"])["event"]==event


def test_parallel_paths_and_parallel_same_ack(tmp_path):
    store=m.Store(tmp_path/"db")
    barrier=Barrier(2)
    def create(index):
        barrier.wait()
        return store.open_water(signal(signal_id=f"path-{index}"),now=NOW,escalation_level="L2",ttl_seconds=10)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(create,range(2)))
    assert results[0]==results[1]
    assert counts(store)==(1,1,1,0)
    barrier=Barrier(2)
    def ack(_):
        barrier.wait()
        return store.ack(results[0]["event_id"],request(),now=NOW,authorized=True)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(ack,range(2)))
    assert results[0]==results[1]
    assert counts(store)==(1,2,2,1)


def test_origin_change_and_stale_signals_rejected(tmp_path):
    store=m.Store(tmp_path/"db")
    event=open_event(store)
    other="simulation" if event["origin"]!="simulation" else "hardware"
    with pytest.raises(m.Conflict,match="origin"):
        store.open_water(signal(origin=other),now=NOW,escalation_level="L2",ttl_seconds=10)
    with pytest.raises(ValueError,match="stale"):
        store.open_water(signal(),now="2026-11-02T00:01:00+00:00",escalation_level="L2",ttl_seconds=10)
    assert counts(store)==(1,1,1,0)


def test_database_constraint_rejects_second_open_identity(tmp_path):
    store=m.Store(tmp_path/"db")
    event=open_event(store)
    with pytest.raises(m.sqlite3.IntegrityError):
        with store.connection() as db:
            db.execute("INSERT INTO events VALUES(?,?,?,?,?)",("other-id",event["device_id"],event["event_type"],"OPEN",m.canonical(event)))
    assert counts(store)==(1,1,1,0)


def test_second_ack_key_is_noop_and_does_not_enqueue(tmp_path):
    store=m.Store(tmp_path/"db")
    event=open_event(store)
    original=store.ack(event["event_id"],request(),now=NOW,authorized=True)
    second=store.ack(event["event_id"],request(2,"second"),now=NOW,authorized=True)
    assert second==original
    assert counts(store)==(1,2,2,2)

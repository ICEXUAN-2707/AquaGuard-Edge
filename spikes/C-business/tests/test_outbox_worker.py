from pathlib import Path
import sys
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from outbox import Worker
from store import Store, Conflict
from projections import Projections

T="2026-11-03T00:00:00Z"
def at(second):
    return f"2026-11-03T00:00:{second:02d}Z"

def seeded(tmp_path,**kwargs):
    store=Store(tmp_path/"db")
    example=json.loads((ROOT/"reference/reference_02/contracts/examples.json").read_text(encoding="utf-8"))["SafetySignal"]
    example.update(origin="simulation",observed_at=T)
    event=store.open_water(example,now=T,escalation_level="L2",ttl_seconds=10)
    return Worker(store.path,**kwargs),event

def accepted(claim,second=0):
    return dict(status="ACCEPTED",transport_receipt=dict(provider="mock",receipt_id=claim["record"]["message_id"],received_at=at(second)))

def record(worker):
    with worker.connection() as db:
        return json.loads(db.execute("SELECT body FROM outbox ORDER BY rowid LIMIT 1").fetchone()[0])

def test_retry_persists_due_time_and_immutable_snapshot(tmp_path):
    worker,event=seeded(tmp_path)
    original=worker.detail(event["event_id"])
    first=worker.claim(now=T)
    worker.ack(event["event_id"],dict(schema_version="1.1",expected_version=1,idempotency_key="a",ack_type="ACKNOWLEDGE"),now=T,authorized=True)
    assert first["payload"]["event"]["ack_status"]=="UNACKNOWLEDGED"
    worker.finish(first["token"],dict(status="RETRY_WAIT",error="do not persist arbitrary credential text"),now=T)
    row=record(worker)
    assert row["next_retry_at"].endswith("00:00:01Z") and row["last_error"]=="MOCK_TEMPORARY_FAILURE"
    reopened=Worker(worker.path)
    next_claim=reopened.claim(now=at(1))
    assert next_claim["record"]["message_id"]==first["record"]["message_id"]
    assert next_claim["payload"]==first["payload"]
    before=reopened.detail(event["event_id"])
    assert reopened.finish(next_claim["token"],accepted(next_claim,1),now=at(1))=="ACCEPTED"
    assert reopened.detail(event["event_id"])==before
    assert Projections(worker.path).sync()["last_ack_level"]=="TRANSPORT"

def test_backoff_cap_and_maximum(tmp_path):
    worker,event=seeded(tmp_path,base_delay=2,cap_delay=3,max_attempts=3)
    assert worker.step(now=T,mode="temporary")=="RETRY_WAIT"
    assert worker.claim(now=at(1)) is None
    assert worker.step(now=at(2),mode="exception")=="RETRY_WAIT"
    assert record(worker)["next_retry_at"].endswith("00:00:05Z")
    assert worker.step(now=at(5),mode="temporary")=="FAILED"
    assert worker.claim(now=at(50)) is None

def test_expired_attempt_cannot_overwrite_new_result(tmp_path):
    worker,event=seeded(tmp_path,lease_seconds=2)
    first=worker.claim(now=T)
    assert Worker(worker.path,lease_seconds=2).claim(now=at(2)) is None
    assert record(worker)["sync_status"]=="RETRY_WAIT"
    second=worker.claim(now=at(3))
    assert second["record"]["message_id"]==first["record"]["message_id"]
    assert worker.finish(second["token"],accepted(second,3),now=at(3))=="ACCEPTED"
    assert worker.finish(first["token"],accepted(first,4),now=at(4))=="STALE"
    assert record(worker)["attempts"]==2

def test_duplicate_result_and_conflict(tmp_path):
    worker,event=seeded(tmp_path)
    claim=worker.claim(now=T)
    result=accepted(claim)
    assert worker.finish(claim["token"],result,now=T)=="ACCEPTED"
    assert worker.finish(claim["token"],result,now=at(1))=="DUPLICATE"
    with pytest.raises(Conflict):
        worker.finish(claim["token"],dict(status="FAILED"),now=at(1))

def test_two_workers_claim_only_once(tmp_path):
    worker,event=seeded(tmp_path)
    barrier=Barrier(2)
    def claim(_):
        other=Worker(worker.path)
        barrier.wait()
        return other.claim(now=T)
    with ThreadPoolExecutor(2) as pool:
        claims=list(pool.map(claim,range(2)))
    assert sum(c is not None for c in claims)==1

def test_receipt_validation_and_expired_result(tmp_path):
    worker,event=seeded(tmp_path,lease_seconds=1)
    claim=worker.claim(now=T)
    with pytest.raises(ValueError):
        worker.finish(claim["token"],dict(status="ACCEPTED"),now=T)
    assert worker.finish(claim["token"],accepted(claim,1),now=at(1))=="STALE"
    assert record(worker)["sync_status"]=="SENDING"

def test_payload_missing_never_reconstructed_from_latest_event(tmp_path):
    worker,event=seeded(tmp_path)
    with worker.connection() as db:
        db.execute("DELETE FROM outbox_payloads")
    with pytest.raises(ValueError,match="payload missing"):
        worker.claim(now=T)
    assert record(worker)["sync_status"]=="PENDING"

def test_atomic_event_write_rolls_back_payload(tmp_path):
    worker,event=seeded(tmp_path)
    with pytest.raises(RuntimeError):
        worker.ack(event["event_id"],dict(schema_version="1.1",expected_version=1,idempotency_key="a",ack_type="ACKNOWLEDGE"),now=T,authorized=True,fault_at="operation")
    with worker.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM outbox_payloads").fetchone()[0]==1

def test_policy_is_durable_and_no_silent_restart_change(tmp_path):
    worker,event=seeded(tmp_path)
    with pytest.raises(ValueError,match="policy changed"):
        Worker(worker.path,base_delay=2)

def test_non_simulation_is_failed_without_mock_send(tmp_path):
    worker,event=seeded(tmp_path)
    with worker.connection() as db:
        value=record(worker)
        value["origin"]="unknown"
        db.execute("UPDATE outbox SET body=?",(json.dumps(value),))
    assert worker.step(now=T)=="IDLE"
    assert record(worker)["last_error"]=="MOCK_SOURCE_NOT_ALLOWED"
    assert record(worker)["attempts"]==0

def test_permanent_and_exception_do_not_change_event(tmp_path):
    worker,event=seeded(tmp_path)
    before=worker.detail(event["event_id"])
    assert worker.step(now=T,mode="permanent")=="FAILED"
    assert worker.detail(event["event_id"])==before
    assert Projections(worker.path).sync()["failed_count"]==1

def test_business_receipt_is_separate_idempotent_and_never_inferred(tmp_path):
    worker,event=seeded(tmp_path)
    claim=worker.claim(now=T)
    receipt=dict(provider="mock-consumer",receipt_id="business-1",received_at=at(1))
    with pytest.raises(ValueError,match="accepted"):
        worker.business_receipt(claim["record"]["message_id"],receipt,now=at(1))
    worker.finish(claim["token"],accepted(claim),now=T)
    assert Projections(worker.path).sync()["last_ack_level"]=="TRANSPORT"
    assert worker.business_receipt(claim["record"]["message_id"],receipt,now=at(1))=="BUSINESS"
    assert worker.business_receipt(claim["record"]["message_id"],receipt,now=at(2))=="DUPLICATE"
    assert Projections(worker.path).sync()["last_ack_level"]=="BUSINESS"
    with pytest.raises(Conflict):
        worker.business_receipt(claim["record"]["message_id"],dict(receipt,receipt_id="other"),now=at(2))

def test_cli_mock_worker_updates_sync_but_not_event(tmp_path):
    worker,event=seeded(tmp_path)
    before=worker.detail(event["event_id"])
    result=subprocess.run([sys.executable,str(ROOT/"spikes/C-business/run.py"),"worker","--db",worker.path,"--mode","accept","--steps","1"],capture_output=True,text=True,timeout=15)
    assert result.returncode==0, result.stderr
    assert json.loads(result.stdout)["result"]=="ACCEPTED"
    assert Worker(worker.path).detail(event["event_id"])==before
    assert Projections(worker.path).sync()["last_ack_level"]=="TRANSPORT"

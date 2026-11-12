import json
import sqlite3
import pytest
from test_outbox_worker import seeded, record, T, at
from delivery import DeliveryService
from adapters.mock import MockAdapter
from adapters.base import TemporaryDeliveryError, PermanentDeliveryError


@pytest.mark.parametrize("mode,status", [("accept","ACCEPTED"),("temporary","RETRY_WAIT"),
                                         ("permanent","FAILED"),("exception","RETRY_WAIT")])
def test_modes(mode,status,tmp_path):
    worker,event=seeded(tmp_path)
    assert DeliveryService(worker,MockAdapter(mode)).step(now=T)==status
    assert record(worker)["business_receipt"] is None


def test_adapter_io_has_no_write_lock_and_payload_is_isolated(tmp_path):
    worker,event=seeded(tmp_path)
    class Adapter(MockAdapter):
        def send(self,request):
            with sqlite3.connect(worker.path,timeout=0.1) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE io_probe (value TEXT)")
                db.execute("INSERT INTO io_probe VALUES ('outside')")
            request.payload["event"]["ack_status"]="ACKNOWLEDGED"
            return super().send(request)
    DeliveryService(worker,Adapter()).step(now=T)
    with worker.connection() as db:
        payload=json.loads(db.execute("SELECT body FROM outbox_payloads").fetchone()[0])
    assert payload["event"]["ack_status"]=="UNACKNOWLEDGED"


@pytest.mark.parametrize("error,status",[(TemporaryDeliveryError,"RETRY_WAIT"),
                                        (PermanentDeliveryError,"FAILED")])
def test_controlled_exception(error,status,tmp_path):
    worker,event=seeded(tmp_path)
    class Adapter(MockAdapter):
        def send(self,request):
            raise error("secret must not persist")
    assert DeliveryService(worker,Adapter()).step(now=T)==status
    assert "secret" not in record(worker)["last_error"]


def test_unexpected_exception_leaves_recoverable_lease(tmp_path):
    worker,event=seeded(tmp_path,lease_seconds=2)
    class Adapter(MockAdapter):
        def send(self,request):
            raise RuntimeError("programming failure")
    with pytest.raises(RuntimeError):
        DeliveryService(worker,Adapter()).step(now=T)
    assert record(worker)["sync_status"]=="SENDING"
    assert worker.claim(now=at(2)) is None
    assert record(worker)["sync_status"]=="RETRY_WAIT"
    assert worker.claim(now=at(3))["payload"]["event"]["event_id"]==event["event_id"]


def test_non_simulation_never_calls_adapter(tmp_path):
    worker,event=seeded(tmp_path)
    with worker.connection() as db:
        value=record(worker); value["origin"]="hardware"
        db.execute("UPDATE outbox SET body=?",(json.dumps(value),))
    class Adapter(MockAdapter):
        def send(self,request):
            pytest.fail("must not send")
    assert DeliveryService(worker,Adapter()).step(now=T)=="IDLE"


def test_existing_version_order_limitation(tmp_path):
    worker,event=seeded(tmp_path)
    first=worker.claim(now=T)
    worker.ack(event["event_id"],dict(schema_version="1.1",expected_version=1,
               idempotency_key="ack",ack_type="ACKNOWLEDGE"),now=T,authorized=True)
    second=worker.claim(now=T)
    assert first["payload"]["event"]["version"]==1
    assert second["payload"]["event"]["version"]==2


def test_main_worker_database_remains_compatible(tmp_path):
    import subprocess
    import types
    from test_outbox_worker import ROOT
    source=subprocess.run(["git","show","main:spikes/C-business/outbox.py"],
                          cwd=ROOT,capture_output=True,text=True,check=True).stdout
    legacy=types.ModuleType("main_outbox")
    exec(compile(source,"main:outbox.py","exec"),legacy.__dict__)
    worker,event=seeded(tmp_path)
    old=legacy.Worker(worker.path)
    assert old.step(now=T,mode="temporary")=="RETRY_WAIT"
    before=record(worker)
    assert DeliveryService(worker,MockAdapter()).step(now=at(1))=="ACCEPTED"
    assert record(worker)["message_id"]==before["message_id"]
    assert legacy.Worker(worker.path).detail(event["event_id"])["event"]==event


def test_independent_processes_claim_once(tmp_path):
    import subprocess
    import sys
    from test_outbox_worker import ROOT
    worker,event=seeded(tmp_path)
    code="import sys; sys.path.insert(0,sys.argv[1]); from outbox import Worker; import json; print(json.dumps(Worker(sys.argv[2]).claim(now=sys.argv[3])))"
    processes=[subprocess.Popen([sys.executable,"-c",code,str(ROOT/"spikes/C-business"),
                                worker.path,T],cwd=ROOT,stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,text=True) for _ in range(2)]
    claims=[]
    for process in processes:
        stdout,stderr=process.communicate(timeout=15)
        assert process.returncode==0,stderr
        claims.append(json.loads(stdout))
    assert sum(value is not None for value in claims)==1

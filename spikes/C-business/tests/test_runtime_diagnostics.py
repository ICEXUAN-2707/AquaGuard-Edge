from test_api import http, create_app, TOKEN
from test_water import WaterService, time
from runtime_diagnostics import RuntimeDiagnostics, phase
from datetime import datetime, timedelta
from test_projections import live, NOW, Projections
import sqlite3
import threading
import time as timing
from store import begin_immediate


def test_real_database_writer_wait_is_attributed_and_nested_phase_restores(tmp_path):
    service=WaterService(tmp_path/'db')
    monitor=RuntimeDiagnostics();started=threading.Event();errors=[]
    def writer():
        try:
            with monitor.scope(),phase('test_transaction'),service.connection() as db:
                started.set();begin_immediate(db)
        except Exception as exc:errors.append(type(exc).__name__)
    with sqlite3.connect(service.path) as lock:
        lock.execute('BEGIN IMMEDIATE')
        thread=threading.Thread(target=writer);thread.start()
        assert started.wait(2)
        timing.sleep(.15)
        lock.rollback()
    thread.join(3)
    assert not thread.is_alive() and not errors
    assert monitor.value['phases']['sqlite_begin_immediate']['wall_seconds']>=.1
    assert monitor.value['active_phase'] is None
    assert 'sqlite_commit' in monitor.value['phases']

def test_checkpoint_delay_is_attributed_separately_from_other_phases(tmp_path,monkeypatch):
    import online
    original=online.save
    def slow_save(*args,**kwargs):
        timing.sleep(.15)
        return original(*args,**kwargs)
    monkeypatch.setattr(online,'save',slow_save)
    monitor=RuntimeDiagnostics()
    start=datetime.fromisoformat(NOW)
    runtime=online.Simulation(tmp_path/'db',tmp_path/'checkpoints',start)
    with monitor.scope():
        for second in range(33):runtime.step(start+timedelta(seconds=second))
    assert monitor.value['phases']['checkpoint_compute_write_fsync']['wall_seconds']>=.15
    assert 'alignment' in monitor.value['phases'] and 'live_assessment_verify_publish' in monitor.value['phases']
    assert monitor.value['active_phase'] is None

def test_diagnostics_distinguishes_gap_from_work_and_retains_failure():
    monitor=RuntimeDiagnostics()
    first=monitor.begin('2026-11-13T00:00:00Z',0,0)
    monitor.finish(first,end=2,cpu=.2,ended_at='2026-11-13T00:00:02Z',step_seconds=1.5,tick_seconds=.5)
    later=monitor.begin('2026-11-13T00:01:02Z',62,.3)
    record=monitor.finish(later,end=63,cpu=.4,ended_at='2026-11-13T00:01:03Z',step_seconds=None,tick_seconds=None,error_type='ValueError')
    assert record['gap_seconds']==60 and record['advance_seconds']==1
    assert monitor.value['last_success_at']=='2026-11-13T00:00:02Z'
    assert monitor.value['failures']==1 and monitor.value['max_gap_seconds']==60

def test_diagnostics_requires_auth_and_handles_api_only_app(tmp_path):
    service=WaterService(tmp_path/'db')
    app=create_app(service,token=TOKEN,cursor_key=b'x'*32,clock=lambda:time(0))
    assert http(app,'GET','/api/runtime/diagnostics',auth=False)[0]==401
    status,value=http(app,'GET','/api/runtime/diagnostics')
    assert status==200 and value['timing'] is None and value['projections']==[]

def test_expired_snapshot_is_explained_without_extending_ttl_then_recovers(tmp_path):
    service=WaterService(tmp_path/'db')
    current=[NOW]
    app=create_app(service,token=TOKEN,cursor_key=b'x'*32,clock=lambda:current[0])
    queries=Projections(service.path)
    queries.publish('live',live(),captured_at=NOW,ttl_seconds=10)
    assert http(app,'GET','/api/devices/home01/live')[0]==200
    current[0]=(datetime.fromisoformat(NOW)+timedelta(seconds=11)).isoformat()
    assert http(app,'GET','/api/devices/home01/live')[0]==503
    status,value=http(app,'GET','/api/runtime/diagnostics',query={'device_id':'home01'})
    assert status==200 and value['projections'][0]['age_seconds']==11
    assert value['projections'][0]['ttl_seconds']==10
    queries.publish('live',dict(live(),captured_at=current[0]),captured_at=current[0],ttl_seconds=10)
    assert http(app,'GET','/api/devices/home01/live')[0]==200

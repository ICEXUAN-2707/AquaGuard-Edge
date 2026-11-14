import json
from test_cloud_modules import environment
from test_outbox_worker import seeded,record,T,at
from cloud_config import load_config,ConfigError
from offline_cloud_worker import assemble
from delivery import DeliveryService
from adapters.mock import MockAdapter
import pytest
import sqlite3
from pathlib import Path

@pytest.mark.parametrize('kind',['empty_file','empty_sqlite','journal','unrelated','missing_columns','missing_policy','wrong_policy','missing_index','narrow_index'])
def test_wrong_database_is_rejected_without_any_write(tmp_path,environment,kind):
    path=tmp_path/'wrong.sqlite'
    if kind in ('missing_policy','wrong_policy','missing_index','narrow_index'):
        worker,event=seeded(tmp_path);path=Path(worker.path)
        with sqlite3.connect(path) as db:
            if kind=='missing_policy':db.execute('DELETE FROM delivery_policy')
            elif kind=='wrong_policy':db.execute("UPDATE delivery_policy SET body='{}'")
            else:
                db.execute('DROP INDEX unique_open')
                if kind=='narrow_index':db.execute("CREATE UNIQUE INDEX unique_open ON events(device_id,event_type) WHERE lifecycle='OPEN' AND event_type='WATER_CONTACT'")
    elif kind=='empty_file':path.touch()
    else:
        with sqlite3.connect(path) as db:
            if kind=='journal':db.execute('CREATE TABLE observations(id TEXT PRIMARY KEY,body TEXT)')
            elif kind=='unrelated':db.execute('CREATE TABLE unrelated(value TEXT)')
            elif kind=='missing_columns':
                for table in ('events','transitions','outbox','operations','outbox_payloads','delivery_attempts','delivery_policy'):
                    db.execute('CREATE TABLE '+table+'(unrelated TEXT)')
            else:db.execute('PRAGMA user_version=1')
    before=path.read_bytes()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        schema=db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall()
    with pytest.raises(ValueError):assemble(path,load_config(environment))
    assert path.read_bytes()==before
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall()==schema

def test_missing_database_is_not_created(tmp_path,environment):
    path=tmp_path/'absent.sqlite'
    with pytest.raises(ValueError):assemble(path,load_config(environment))
    assert not path.exists()

def test_mapping_worker_is_offline_and_schedules_retry_at_finish(tmp_path,environment):
    worker,event=seeded(tmp_path)
    config=load_config(environment)
    # Fixture binding identity is explicit; match immutable local event identity.
    with worker.connection() as db:
        payload=json.loads(db.execute('SELECT body FROM outbox_payloads').fetchone()[0])
    from dataclasses import replace
    binding=replace(config.bindings[0],local_device_id=payload['event']['device_id'],authorization_class='simulation_test',allowed_origins=('simulation',))
    service=assemble(worker.path,replace(config,bindings=(binding,)),clock=lambda:at(2))
    try:
        assert service.step(now=T)=='RETRY_WAIT'
        assert record(worker)['next_retry_at']==at(3)
        assert record(worker)['transport_receipt'] is None
        assert service.adapter.transport.calls==1
    finally:service.close()
    assert service.adapter.transport.closed

def test_hardware_binding_is_rejected_before_worker_creation(tmp_path,environment):
    worker,event=seeded(tmp_path)
    config=load_config(environment)
    from dataclasses import replace
    binding=replace(config.bindings[0],authorization_class='test_hardware',allowed_origins=('hardware',))
    with pytest.raises(ConfigError):assemble(worker.path,replace(config,bindings=(binding,)))

def test_existing_mock_finish_time_remains_compatible(tmp_path):
    worker,event=seeded(tmp_path)
    assert DeliveryService(worker,MockAdapter('temporary')).step(now=T)=='RETRY_WAIT'
    assert record(worker)['next_retry_at']==at(1)

def test_expired_send_is_stale_and_recovery_keeps_message_identity(tmp_path,environment):
    from dataclasses import replace
    worker,event=seeded(tmp_path)
    config=load_config(environment)
    binding=replace(config.bindings[0],local_device_id=event['device_id'],authorization_class='simulation_test',allowed_origins=('simulation',))
    times=iter([at(10),at(12)])
    service=assemble(worker.path,replace(config,bindings=(binding,)),clock=lambda:next(times))
    original=record(worker)['message_id']
    try:
        assert service.step(now=T)=='STALE'
        assert record(worker)['sync_status']=='SENDING'
        assert worker.claim(now=at(10)) is None
        assert record(worker)['sync_status']=='RETRY_WAIT'
        assert service.step(now=at(11))=='RETRY_WAIT'
        assert record(worker)['message_id']==original
        assert record(worker)['next_retry_at']==at(14)
        assert record(worker)['transport_receipt'] is None
    finally:service.close()

def test_backward_finish_clock_cannot_complete_attempt(tmp_path):
    worker,event=seeded(tmp_path)
    service=DeliveryService(worker,MockAdapter('temporary'),finish_clock=lambda:T)
    with pytest.raises(ValueError,match='precedes claim'):service.step(now=at(1))
    assert record(worker)['sync_status']=='SENDING'
    service.close()

def test_invalid_finish_clock_is_rejected_before_claim(tmp_path):
    worker,event=seeded(tmp_path)
    with pytest.raises(ValueError):DeliveryService(worker,MockAdapter('temporary'),finish_clock='not callable')
    assert record(worker)['attempts']==0

def test_conflicting_persistent_policy_is_not_silently_migrated(tmp_path,environment):
    worker,event=seeded(tmp_path,base_delay=2)
    config=load_config(environment)
    from dataclasses import replace
    binding=replace(config.bindings[0],local_device_id=event['device_id'],authorization_class='simulation_test',allowed_origins=('simulation',))
    with pytest.raises(ValueError,match='policy changed'):assemble(worker.path,replace(config,bindings=(binding,)))
    assert record(worker)['attempts']==0

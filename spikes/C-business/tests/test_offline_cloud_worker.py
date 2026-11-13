import json
from test_cloud_modules import environment
from test_outbox_worker import seeded,record,T,at
from cloud_config import load_config,ConfigError
from offline_cloud_worker import assemble
from delivery import DeliveryService
from adapters.mock import MockAdapter
import pytest

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

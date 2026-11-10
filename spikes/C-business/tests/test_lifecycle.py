import pytest
from test_water import WaterService, ingest, time, rows
from lifecycle import close_event
from store import Conflict, IdempotencyConflict
from test_api import http, create_app, TOKEN


def prepared(tmp_path):
    service=WaterService(tmp_path/'db')
    event=ingest(service,0)['event']
    service.ack(event['event_id'],dict(schema_version='1.1',expected_version=1,
        idempotency_key='ack',ack_type='ACKNOWLEDGE'),now=time(0),authorized=True)
    ingest(service,1,False)
    event=ingest(service,3,False)['event']
    return service,event


def test_close_replay_and_recurrence_create_new_unacknowledged_event(tmp_path):
    service,event=prepared(tmp_path)
    request=dict(schema_version='1.1',expected_version=event['version'],idempotency_key='close')
    result=close_event(service,event['event_id'],request,now=time(3),authorized=True)
    assert result['event']['lifecycle']=='CLOSED'
    service=WaterService(service.path)
    before=rows(service)
    assert close_event(service,event['event_id'],request,now=time(4),authorized=True)==result
    assert rows(service)==before
    old_signal=dict(schema_version='1.1',signal_id='late-slow',device_id='home01',
                    signal_type='WATER_CONTACT',observed_at=time(0),value=True,quality='VALID',
                    observation_refs=['home01/b1/0'],origin='simulation')
    assert service.open_water(old_signal,now=time(4),escalation_level='L2',ttl_seconds=10)['lifecycle']=='CLOSED'
    assert rows(service)==before
    again=ingest(service,4)['event']
    assert again['event_id']!=event['event_id']
    assert again['ack_status']=='UNACKNOWLEDGED' and again['version']==1
    assert rows(service)[0]==2
    assert rows(service)[1]==rows(service)[2]


@pytest.mark.parametrize('kind',['active','stale','unconfirmed'])
def test_close_rejects_unsafe_state_without_writes(tmp_path,kind):
    service,event=prepared(tmp_path)
    if kind=='active': event=ingest(service,4)['event']
    if kind=='unconfirmed':
        service=WaterService(tmp_path/'other')
        ingest(service,0);ingest(service,1,False);event=ingest(service,3,False)['event']
    before=rows(service)
    with pytest.raises(Conflict):
        close_event(service,event['event_id'],dict(schema_version='1.1',expected_version=event['version'],
            idempotency_key='close'),now=time(14 if kind=='stale' else 4),authorized=True)
    assert rows(service)==before


def test_close_http_auth_version_and_operation_key_isolation(tmp_path):
    service,event=prepared(tmp_path)
    app=create_app(service,token=TOKEN,cursor_key=b'x'*32,clock=lambda:time(3))
    route=f"/api/events/{event['event_id']}/close"
    body=dict(schema_version='1.1',expected_version=event['version'],idempotency_key='close')
    assert http(app,'POST',route,body,auth=False)[0]==401
    assert http(app,'POST',route,dict(body,expected_version=1))[0]==409
    assert http(app,'POST',route,dict(body,idempotency_key='ack'))[0]==409
    status,result=http(app,'POST',route,body)
    assert status==200 and result['event']['lifecycle']=='CLOSED'

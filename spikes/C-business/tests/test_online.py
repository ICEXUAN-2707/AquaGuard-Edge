import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from online import Simulation


def test_continuous_windows_and_fast_water_event(tmp_path):
    start=datetime(2026,11,5,tzinfo=timezone.utc)
    demo=Simulation(tmp_path/'db',tmp_path/'checkpoints',start)
    situations=[]
    for i in range(91):
        result=demo.step(start+timedelta(seconds=i))
        if result:
            situations.append(result['situation'])
    assert 'ATTENDED_FLOW' in situations
    assert 'POSSIBLE_UNATTENDED_FLOW' in situations
    with demo.water.connection() as db:
        events=db.execute("SELECT body FROM events").fetchall()
        assert {json.loads(row[0])['event_type'] for row in events}=={'WATER_CONTACT','POSSIBLE_UNATTENDED_FLOW'}
        assert db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]>=1
    live=demo.queries.read('live','demo01',now=(start+timedelta(seconds=90)).isoformat())
    assert live['origin']=='simulation'
    assert len(demo.rows)<=543
    projection=demo.queries.read('assessment','demo01',now=(start+timedelta(seconds=90)).isoformat())
    assert projection['safety_signals'][0]['value'] is True
    from api import create_app
    from test_api import http,TOKEN
    app=create_app(demo.water,token=TOKEN,cursor_key=b'x'*32,
                   clock=lambda:(start+timedelta(seconds=90)).isoformat())
    status,body=http(app,'GET','/api/devices/demo01/assessment')
    assert status==200 and body['safety_signals'][0]['value'] is True
    status,body=http(app,'GET','/api/events')
    assert status==200 and len(body['items'])==2

    # Restart uses durable episode identity; ACK never clears physical evidence.
    event=next(json.loads(row[0]) for row in events if json.loads(row[0])['event_type']=='POSSIBLE_UNATTENDED_FLOW')
    demo.water.ack(event['event_id'],dict(schema_version='1.1',expected_version=event['version'],
        idempotency_key='online-ack',ack_type='ACKNOWLEDGE'),now=(start+timedelta(seconds=90)).isoformat(),authorized=True)
    assert demo.water.detail(event['event_id'])['event']['physical_status']=='ACTIVE'
    demo.context.expire(now=(start+timedelta(seconds=110)).isoformat())
    expired=demo.water.detail(event['event_id'])['event']
    assert expired['physical_status']=='UNKNOWN' and expired['ack_status']=='ACKNOWLEDGED'
    restarted=Simulation(tmp_path/'db',tmp_path/'checkpoints',start+timedelta(seconds=120))
    for i in range(91):
        restarted.step(start+timedelta(seconds=120+i))
    with restarted.water.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE event_type='POSSIBLE_UNATTENDED_FLOW'").fetchone()[0]==1


def test_context_transaction_rollback_and_replay(tmp_path):
    import pytest
    from checkpoint import restore
    from context_events import ContextEvents
    start=datetime(2026,11,5,tzinfo=timezone.utc)
    demo=Simulation(tmp_path/'source',tmp_path/'checkpoints',start)
    for i in range(76):
        demo.step(start+timedelta(seconds=i))
    feature=None
    for path in (tmp_path/'checkpoints').glob('*.json'):
        candidate=restore(path)['feature_window']
        if candidate['features']['absence_after_flow_sec'] is not None and candidate['features']['absence_after_flow_sec']>=20:
            feature=candidate
    assert feature is not None
    from checkpoint import restore as replay
    now=replay(feature['state_checkpoint_ref'])['last_window']['published_at']
    store=ContextEvents(tmp_path/'target')
    with pytest.raises(RuntimeError):
        store.ingest(feature,now=now,checkpoint_root=tmp_path/'checkpoints',fault_at='outbox')
    with store.connection() as db:
        for table in ('events','transitions','outbox','context_state'):
            assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0
    store.ingest(feature,now=now,checkpoint_root=tmp_path/'checkpoints')
    store.ingest(feature,now=now,checkpoint_root=tmp_path/'checkpoints')
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM transitions').fetchone()[0]==1


def test_scheduler_jitter_preserves_flow_terminal_state(tmp_path):
    start=datetime(2026,11,5,tzinfo=timezone.utc)
    demo=Simulation(tmp_path/'jitter',tmp_path/'checkpoints',start)
    result=None
    for i in range(36):
        assessment=demo.step(start+timedelta(seconds=i*1.031))
        if assessment:
            result=assessment
    assert result is not None and result['situation']=='ATTENDED_FLOW'

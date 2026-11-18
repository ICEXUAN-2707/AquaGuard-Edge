import sys
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]/'src'))
from core import Journal, sample
from ingress import process_message, observation_topic


def test_configured_device_preserves_wire_identity_and_dedup(tmp_path):
    journal = Journal(tmp_path/'configured.sqlite')
    row = sample(device_id='demo01')
    msg = message(json.dumps(row).encode())
    msg.topic = observation_topic('demo01')
    acks = []
    first = process_message(msg, journal, lambda *args: acks.append(args), device_id='demo01')
    second = process_message(msg, journal, lambda *args: acks.append(args), device_id='demo01')
    assert first['classification'] == 'new'
    assert second['classification'] == 'duplicate'
    assert first['observation']['observation_id'] == row['observation_id']
    assert journal.export()[0]['device_id'] == 'demo01'
    assert len(acks) == 2
    journal.close()


@pytest.mark.parametrize('change', ['device', 'topic', 'source'])
def test_configured_binding_rejects_spoofed_input(tmp_path, change):
    from core import observation_id
    row = sample(device_id='demo01')
    if change == 'device': row['device_id'] = 'other'
    if change == 'source': row['source'] = 'hardware'
    row['observation_id'] = observation_id(row)
    msg = message(json.dumps(row).encode())
    msg.topic = observation_topic('other' if change == 'topic' else 'demo01')
    journal = Journal(tmp_path/'rejected.sqlite')
    result = process_message(msg, journal, lambda *args: None, device_id='demo01')
    assert result['classification'] == 'invalid'
    assert journal.export() == []
    journal.close()


@pytest.mark.parametrize('device', ['', '#', '+', 'a/b', 'a'*65, None])
def test_invalid_configuration_does_not_ack(device):
    with pytest.raises(ValueError):
        process_message(message(b'{}'), None, lambda *args: pytest.fail('unexpected ACK'), device_id=device)


def message(payload):
    return SimpleNamespace(topic='prototype/aquaguard/prototype01/observation', qos=1, retain=False, mid=12, payload=payload)


@pytest.mark.parametrize('payload', [json.dumps(sample()).encode(), b'not-json'])
def test_ack_after_durable_record(tmp_path, payload):
    journal = Journal(tmp_path/'test.sqlite')
    def ack(mid, qos):
        count = journal.db.execute('SELECT count(*) FROM attempts').fetchone()[0]
        count += journal.db.execute('SELECT count(*) FROM rejected').fetchone()[0]
        assert count == 1
    process_message(message(payload), journal, ack)
    journal.close()


@pytest.mark.parametrize('payload', [json.dumps(sample()).encode(), b'not-json'])
def test_storage_failure_never_acknowledged(payload):
    class Broken:
        def accept(self, row):
            raise OSError('disk unavailable')
        reject = accept
    acknowledgements = []
    with pytest.raises(OSError):
        process_message(message(payload), Broken(), lambda *args: acknowledgements.append(args))
    assert not acknowledgements


def test_actual_sqlite_readonly_failure_does_not_ack(tmp_path):
    journal = Journal(tmp_path/'readonly.sqlite')
    journal.db.execute('PRAGMA query_only=ON')
    acknowledgements = []
    with pytest.raises(sqlite3.OperationalError):
        process_message(message(json.dumps(sample()).encode()), journal, lambda *args: acknowledgements.append(args))
    assert not acknowledgements
    journal.close()


@pytest.mark.parametrize('payload,retained', [(b'\xff',False), (b'{',False), (json.dumps(sample()).encode(),True)])
def test_rejects_are_durable_and_acknowledged(tmp_path,payload,retained):
    journal = Journal(tmp_path/'reject.sqlite')
    msg = message(payload)
    msg.retain = retained
    acknowledgements = []
    result = process_message(msg,journal,lambda *args: acknowledgements.append(args))
    assert result['classification'] == 'invalid'
    assert len(acknowledgements) == 1
    assert journal.db.execute('SELECT count(*) FROM rejected').fetchone()[0] == 1
    assert not journal.export()
    journal.close()


def test_timing_observes_committed_record_before_ack(tmp_path):
    journal=Journal(tmp_path/'timing.sqlite');timing={}
    ticks=iter([10,11,13,14,15])
    def ack(*args):
        with sqlite3.connect(tmp_path/'timing.sqlite') as other:
            assert other.execute('SELECT count(*) FROM attempts').fetchone()[0]==1
        assert timing['commit_returned'] and not timing['ack_submitted']
    process_message(message(json.dumps(sample()).encode()),journal,ack,timing=timing,clock=lambda:next(ticks))
    assert timing['storage_seconds']==2 and timing['receive_to_commit_seconds']==3
    assert timing['commit_to_ack_submit_seconds']==2 and timing['receive_to_ack_submit_seconds']==5
    assert timing['ack_submitted'] and timing['broker_ack_confirmed'] is None
    assert timing['observation_id']==sample()['observation_id']
    journal.close()


@pytest.mark.parametrize('boundary',['storage','after_commit','ack'])
def test_timing_preserves_failure_boundary_without_false_ack(tmp_path,boundary):
    journal=Journal(tmp_path/'failure.sqlite');timing={};acks=[]
    if boundary=='storage':journal.db.execute('PRAGMA query_only=ON')
    def after():
        if boundary=='after_commit':raise OSError('interrupted after commit')
    def ack(*args):
        if boundary=='ack':raise OSError('ack submission failed')
        acks.append(args)
    with pytest.raises((OSError,sqlite3.OperationalError)):
        process_message(message(json.dumps(sample()).encode()),journal,ack,after,timing=timing)
    assert timing['commit_returned']==(boundary!='storage')
    assert not timing['ack_submitted'] and not acks
    journal.close()


def test_timing_is_opt_in_and_does_not_call_clock(tmp_path):
    journal=Journal(tmp_path/'old.sqlite')
    process_message(message(b'not-json'),journal,lambda *args:None,clock=lambda:pytest.fail('clock must remain unused'))
    journal.close()

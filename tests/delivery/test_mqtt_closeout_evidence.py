import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import mqtt_closeout_evidence as module
from mqtt_local_backend import LocalBackend
import mqtt_local_backend as backend_module


@pytest.mark.parametrize('change',['valid','missing','outside','invalid_json'])
def test_checkpoint_inventory_is_read_only_and_fail_closed(tmp_path,change):
    folder=tmp_path/'cp';folder.mkdir();used=folder/'used.json';used.write_text('{}')
    (folder/'other.json').write_text('{}')
    ref=used if change!='outside' else tmp_path/'external.json'
    database=tmp_path/'business'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE state(body TEXT)')
        db.execute('INSERT INTO state VALUES(?)',('{broken' if change=='invalid_json' else json.dumps({'state_checkpoint_ref':str(ref.resolve())}),))
    if change=='missing':used.unlink()
    before=database.read_bytes();value=module.checkpoint_inventory(database,folder)
    assert value['ok']==(change=='valid') and not value['deletion_authorized']
    assert database.read_bytes()==before and (folder/'other.json').exists()


def test_version_lock_tracks_dependency_files_and_binary_without_execution(tmp_path,monkeypatch):
    (tmp_path/'web').mkdir();(tmp_path/'web/package-lock.json').write_text('{}')
    (tmp_path/'requirements-app.lock.txt').write_text('example==1.0\n')
    broker=tmp_path/'broker.exe';broker.write_bytes(b'not an executable')
    monkeypatch.setattr(module.importlib.metadata,'distributions',lambda:[SimpleNamespace(metadata={'Name':'example'},version='1.0')])
    first=module.runtime_lock(tmp_path,broker,'2.0.21')
    broker.write_bytes(b'changed')
    assert module.runtime_lock(tmp_path,broker,'2.0.21')['broker_sha256']!=first['broker_sha256']
    (tmp_path/'requirements-app.lock.txt').write_text('example==2.0\n')
    with pytest.raises(ValueError,match='dependency'):module.runtime_lock(tmp_path,broker,'2.0.21')


@pytest.mark.parametrize('change',['valid','missing_consumer','failed_publish','negative','wrong_scope','invalid'])
def test_latency_join_preserves_missing_or_invalid_evidence(tmp_path,change):
    publisher=tmp_path/'publish.jsonl';consumer=tmp_path/'consume.jsonl'
    sent=dict(scope='publish_attempt',observation_id='id-1',publish_start=10,puback_returned=True)
    received=dict(scope='consumer_cursor_commit',observation_id='id-1',cursor_commit=12)
    if change=='failed_publish':sent['puback_returned']=False
    if change=='negative':received['cursor_commit']=9
    if change=='wrong_scope':received['scope']='cloud_accepted'
    publisher.write_text(json.dumps(sent)+'\n'+(json.dumps(sent)+'\n' if change=='valid' else ''))
    if change!='missing_consumer':consumer.write_text('broken' if change=='invalid' else json.dumps(received)+'\n')
    value=module.consumption_latency([publisher],consumer)
    assert value['status']==('AVAILABLE' if change=='valid' else 'INCOMPLETE')
    assert not value['acceptance_passed']
    if change=='valid':assert value['max_seconds']==2 and value['duplicate_publications']==1 and value['matched_unique']==1


def test_broker_self_report_must_match_locked_version(tmp_path):
    backend=LocalBackend(tmp_path/'broker',18887,8051);backend.output=tmp_path
    backend.runtime_versions={'broker_version':'2.0.99'}
    (tmp_path/'broker-0.log').write_text('Opening ipv4 listen socket on port 18887.\nmosquitto version 2.0.21 running')
    with pytest.raises(ValueError,match='self-reported'):backend.broker_ready()

@pytest.mark.parametrize('change',['outside_asset','relative_asset','broken_checkpoint'])
def test_all_checkpoint_reference_channels_fail_closed(tmp_path,change):
    folder=tmp_path/'cp';folder.mkdir();cp=folder/'used.json';cp.write_text('{broken' if change=='broken_checkpoint' else '{}')
    ref=str((tmp_path/'outside.json').resolve()) if change=='outside_asset' else 'relative.json'
    payload={'state_checkpoint_ref':str(cp.resolve())}
    if change!='broken_checkpoint':payload['asset_refs']=[ref]
    database=tmp_path/'business'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE state(body TEXT)');db.execute('INSERT INTO state VALUES(?)',(json.dumps(payload),))
    result=module.checkpoint_inventory(database,folder)
    assert not result['ok']
    if change=='broken_checkpoint':assert result['invalid_referenced_json']==1
    else:assert result['outside_checkpoint_refs']==1

import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'spikes/SP-02/src'))
from mqtt_local_backend import LocalBackend,database_exit_checks
import mqtt_local_backend as backend_module
from prepare_mqtt_protocol import prepare


def test_manifests_repeat_published_prefix_and_inject_unique_retired_identity(tmp_path,monkeypatch):
    backend=LocalBackend(tmp_path/'broker.exe',18887,8051)
    backend.output=tmp_path;backend.cli=ROOT/'spikes/SP-02/src/cli.py'
    backend.plan=prepare(tmp_path/'plan',revision='a'*40,ttl=10,stop_seconds=18,continuous_seconds=30)
    launched=[]
    monkeypatch.setattr(backend,'launch',lambda *args,**kwargs:launched.append(args))
    stages={row['name']:row for row in backend.plan['stages']}
    def rows(name):return [json.loads(line) for line in (tmp_path/(name+'-publisher')/'manifest.jsonl').read_text().splitlines()]
    backend.publisher(stages['startup']);original=rows('startup')
    backend.publisher(stages['resume_duplicate'],duplicate=True);resumed=rows('resume_duplicate')
    assert resumed[3:6]==original[:3]
    assert resumed[3:6]!=original[-3:]
    backend.publisher(stages['new_boot'],retired=True);new=rows('new_boot')
    assert new[0]['boot_id']!=new[3]['boot_id']
    assert new[3]['boot_id']==resumed[0]['boot_id']
    assert new[3]['observation_id'] not in {row['observation_id'] for row in resumed}
    assert len(launched)==3
    assert all('--interval' in call[1] for call in launched)


def test_cleanup_touches_only_retained_process_objects(tmp_path):
    backend=LocalBackend(tmp_path/'broker',18887,8051);actions=[]
    class Child:
        pid=42;code=None
        def poll(self):return self.code
        def terminate(self):actions.append('owned terminate');self.code=0
        def wait(self,timeout):return self.code
    child=Child();backend.active['publisher']=child;backend.history.append(('publisher',child))
    result=backend.stop()
    assert result['all_exited'] and actions==['owned terminate'] and not backend.active
    assert backend.stop()['all_exited'] and actions==['owned terminate']


@pytest.mark.parametrize('duplicate',[False,True])
def test_exit_checks_read_only_and_detect_duplicate_open(tmp_path,duplicate):
    journal=tmp_path/'journal.sqlite';business=tmp_path/'business.sqlite'
    with sqlite3.connect(journal) as db:
        db.executescript('CREATE TABLE observations(id);CREATE TABLE rejected(id);CREATE TABLE attempts(number,classification);')
    with sqlite3.connect(business) as db:
        db.executescript('CREATE TABLE events(device_id,event_type,lifecycle);CREATE TABLE mqtt_consumer(singleton,journal,cursor);')
        db.execute('INSERT INTO mqtt_consumer VALUES(1,?,0)',(str(journal.resolve()),))
        db.execute("INSERT INTO events VALUES('demo01','WATER_CONTACT','OPEN')")
        if duplicate:db.execute("INSERT INTO events VALUES('demo01','WATER_CONTACT','OPEN')")
    before=(business.read_bytes(),journal.read_bytes())
    value=database_exit_checks(business,journal)
    assert value['ok']==(not duplicate)
    assert value['duplicate_open_groups']==int(duplicate)
    assert (business.read_bytes(),journal.read_bytes())==before


def test_exit_checks_do_not_create_missing_database(tmp_path):
    with pytest.raises(sqlite3.OperationalError):database_exit_checks(tmp_path/'missing',tmp_path/'journal')
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('log',[
    '',
    'mosquitto version 2.0 running',
    'Opening ipv4 listen socket on port 18887.\nmosquitto version 2.0 running\nError: Address already in use',
])
def test_broker_readiness_requires_owned_success_log_before_socket_probe(tmp_path,monkeypatch,log):
    backend=LocalBackend(tmp_path/'broker',18887,8051);backend.output=tmp_path
    (tmp_path/'broker-0.log').write_text(log)
    monkeypatch.setattr(backend_module.socket,'socket',lambda:pytest.fail('must not trust unrelated socket'))
    assert not backend.broker_ready()


def test_broker_ready_checks_loopback_socket_after_owned_log(tmp_path,monkeypatch):
    backend=LocalBackend(tmp_path/'broker',18887,8051);backend.output=tmp_path
    (tmp_path/'broker-0.log').write_text('Opening ipv4 listen socket on port 18887.\nmosquitto version 2.0.21 running')
    class Socket:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def connect_ex(self,address):assert address==('127.0.0.1',18887);return 0
    monkeypatch.setattr(backend_module.socket,'socket',Socket)
    assert backend.broker_ready()


@pytest.mark.parametrize('listening',[True,False])
def test_exit_ports_must_close_without_touching_other_processes(tmp_path,monkeypatch,listening):
    backend=LocalBackend(tmp_path/'broker',18887,8051);backend.output=tmp_path
    monkeypatch.setattr(backend_module,'database_exit_checks',lambda *args:{'ok':True})
    class Probe:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,value):assert value==.5
        def connect_ex(self,address):return 0 if listening else 1
    monkeypatch.setattr(backend_module.socket,'socket',Probe)
    value=backend.exit_checks()
    assert value['ok']==(not listening)
    assert value['ports_closed']=={'mqtt':not listening,'http':not listening}

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from mqtt_phase_evidence import capture,evaluate


def evidence():
    return dict(water_events=[dict(event_id='event-1',origin='simulation',ack_status='UNACKNOWLEDGED',physical_status='ACTIVE')],
                water_transitions=4,boot='old',cursor=10,quarantine=0,duplicates=0)


def scenario(name):
    before=evidence();after=deepcopy(before);after['cursor']=20
    stage=dict(name=name,boot='old')
    if name=='publisher_stop':after['water_events'][0]['physical_status']='UNKNOWN'
    if name=='resume_duplicate':
        before['water_events'][0]['physical_status']='UNKNOWN'
        after.update(duplicates=3,water_transitions=5)
    if name=='new_boot':stage['boot']='new';after.update(boot='new',quarantine=3)
    return stage,before,after,[{'live':{'status':200}}]


@pytest.mark.parametrize('name',['startup','continuous','publisher_stop','resume_duplicate','edge_restart','new_boot','shutdown'])
def test_satisfied_synthetic_phase_evidence_is_local_only(name):
    value=evaluate(*scenario(name))
    assert value['status']=='SATISFIED'
    assert 'acceptance_passed' not in value


@pytest.mark.parametrize('name,change',[
    ('publisher_stop','active'),('resume_duplicate','no_duplicate'),('resume_duplicate','extra_transition'),
    ('edge_restart','identity'),('edge_restart','ack'),('new_boot','no_quarantine'),
    ('new_boot','boot'),('continuous','503'),
])
def test_phase_invariant_regressions_are_not_hidden(name,change):
    stage,before,after,samples=scenario(name)
    if change=='active':after['water_events'][0]['physical_status']='ACTIVE'
    if change=='no_duplicate':after['duplicates']=0
    if change=='extra_transition':after['water_transitions']=6
    if change=='identity':after['water_events'][0]['event_id']='new-event'
    if change=='ack':after['water_events'][0]['ack_status']='ACKNOWLEDGED'
    if change=='no_quarantine':after['quarantine']=0
    if change=='boot':after['boot']='old'
    if change=='503':samples[0]['live']['status']=503
    assert evaluate(stage,before,after,samples)['status']=='VIOLATED'


def test_missing_evidence_is_incomplete():
    stage,before,after,samples=scenario('edge_restart');del after['water_events']
    assert evaluate(stage,before,after,samples)['status']=='INCOMPLETE'


def test_capture_is_read_only_and_preserves_uninitialized_cursor(tmp_path):
    business=tmp_path/'business';journal=tmp_path/'journal'
    with sqlite3.connect(business) as db:
        db.executescript('CREATE TABLE events(event_id,device_id,event_type,lifecycle,body);CREATE TABLE transitions(event_id);CREATE TABLE mqtt_consumer(singleton,boot,cursor);CREATE TABLE mqtt_quarantine(number);')
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)',('event-1','demo01','WATER_CONTACT','OPEN',json.dumps(evidence()['water_events'][0])))
    with sqlite3.connect(journal) as db:
        db.execute('CREATE TABLE attempts(classification)');db.execute("INSERT INTO attempts VALUES('duplicate')")
    original=(business.read_bytes(),journal.read_bytes())
    value=capture(business,journal)
    assert value['cursor']==0 and value['boot'] is None and value['duplicates']==1
    assert (business.read_bytes(),journal.read_bytes())==original


def test_capture_does_not_initialize_database(tmp_path):
    with pytest.raises(sqlite3.OperationalError):capture(tmp_path/'missing',tmp_path/'journal')
    assert not (tmp_path/'missing').exists()

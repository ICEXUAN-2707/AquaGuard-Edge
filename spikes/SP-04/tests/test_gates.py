import sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from gates import gate,DEFAULT
from checkpoint import save
from alignment import align
T=datetime(2026,10,29,tzinfo=timezone.utc)
def fixture(tmp_path,active=True):
    rows=[]
    for i in range(5,31,5):
        rows.append(dict(schema_version='1.1',observation_id=f'f{i}',device_id='demo',sensor_type='flow',boot_id='a',seq=i,uptime_ms=i*1000,event_time=(T+timedelta(seconds=i)).isoformat(),received_at=(T+timedelta(seconds=i)).isoformat(),time_basis='DEVICE_SYNCED',value=dict(pulse_count=1,interval_ms=5000,estimated_lpm=6.0 if active else 0.0,calibration_id='synthetic'),quality='valid',source='simulation'))
    w=align(rows,[T+timedelta(seconds=30)])['windows'][0]
    return save(tmp_path,w,rows,alignment_config={})

def test_missing_presence_gate(tmp_path):
    fw=fixture(tmp_path)
    r=gate(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)
    assert r['status']=='UNKNOWN' and r['reason']=='PRESENCE_UNKNOWN'

def test_idle_does_not_require_presence_but_degrades(tmp_path):
    fw=fixture(tmp_path,False)
    r=gate(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)
    assert r['status']=='READY' and r['idle_sec']==30 and r['data_quality']=='DEGRADED'

def test_stale_boundary_and_future(tmp_path):
    fw=fixture(tmp_path,False)
    assert gate(fw,T+timedelta(seconds=40),checkpoint_root=tmp_path)['status']=='READY'
    assert gate(fw,T+timedelta(seconds=40,microseconds=1),checkpoint_root=tmp_path)['reason']=='WINDOW_STALE'
    with pytest.raises(ValueError,match='time'):gate(fw,T,checkpoint_root=tmp_path)

def test_path_and_forged_input_rejected(tmp_path):
    fw=fixture(tmp_path/'trusted',False)
    other=tmp_path/'other';other.mkdir()
    with pytest.raises(ValueError,match='outside'):gate(fw,T+timedelta(seconds=32),checkpoint_root=other)
    fw['features']['flow_mean_lpm']=5
    with pytest.raises(ValueError,match='mismatch'):gate(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)

def test_rules_mutual_exclusion_exhaustive():
    from itertools import product
    for flow,presence,fc,pc,duration,idle in product(('unknown','active','inactive'),('unknown','present','absent'),(0,0.79,0.8,1),(0,0.79,0.8,1),(None,9.9,10,10.1),(None,4.9,5,5.1)):
        good=flow!='unknown' and fc>=0.8
        pgood=presence!='unknown' and pc>=0.8
        flags=[good and flow=='inactive' and idle is not None and idle>=5,
               good and flow=='active' and pgood and presence=='present',
               good and flow=='active' and pgood and presence=='absent' and duration is not None and duration>=10]
        assert sum(flags)<=1

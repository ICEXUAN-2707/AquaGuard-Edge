import sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from rules import classify
from gates import DEFAULT
from checkpoint import save
from alignment import align
T=datetime(2026,10,29,tzinfo=timezone.utc)
def fixture(root,*,leave=20,attended=False,idle=False,wet=False):
    rows=[]
    for sensor in ('flow','water','presence'):
        times=list(range(0,31,5))
        if sensor=='presence' and leave not in times:times.append(leave)
        for seq,t in enumerate(sorted(times)):
            if sensor=='flow' and t==0:continue
            value=dict(pulse_count=1,interval_ms=5000,estimated_lpm=0.0 if idle else 6.0,calibration_id='synthetic') if sensor=='flow' else dict(wet=wet) if sensor=='water' else dict(present=attended or t<leave,moving=False,still=attended or t<leave)
            rows.append(dict(schema_version='1.1',observation_id=f'{sensor}-{seq}',device_id='demo',sensor_type=sensor,boot_id='a',seq=seq,uptime_ms=int(t*1000),event_time=(T+timedelta(seconds=t)).isoformat(),received_at=(T+timedelta(seconds=t)).isoformat(),time_basis='DEVICE_SYNCED',value=value,quality='valid',source='simulation'))
    w=align(rows,[T+timedelta(seconds=30)])['windows'][0]
    return save(root,w,rows,alignment_config={})

@pytest.mark.parametrize('leave,expected',[(20.1,'UNKNOWN'),(20,'POSSIBLE_UNATTENDED_FLOW'),(19.9,'POSSIBLE_UNATTENDED_FLOW')])
def test_real_pipeline_duration_boundaries(tmp_path,leave,expected):
    fw=fixture(tmp_path,leave=leave)
    r=classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)
    assert r['situation']==expected and r['model_score'] is None
    assert r['reason_codes']==['DURATION_NOT_REACHED' if expected=='UNKNOWN' else 'UNATTENDED_DURATION_REACHED']

@pytest.mark.parametrize('idle,attended,expected',[(True,False,'IDLE'),(False,True,'ATTENDED_FLOW')])
def test_idle_and_attended(tmp_path,idle,attended,expected):
    fw=fixture(tmp_path,idle=idle,attended=attended)
    assert classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)['situation']==expected

def test_water_independence_and_stable_identity(tmp_path):
    fw=fixture(tmp_path,attended=True,wet=True)
    a=classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)
    b=classify(fw,T+timedelta(seconds=40),checkpoint_root=tmp_path)
    assert a==b and a['situation']=='ATTENDED_FLOW'
    stale=classify(fw,T+timedelta(seconds=41),checkpoint_root=tmp_path)
    assert stale['situation']=='UNKNOWN' and stale['assessment_id']!=a['assessment_id']
    assert 'WINDOW_STALE' in stale['reason_codes']

def test_rule_config_changes_identity(tmp_path):
    fw=fixture(tmp_path)
    a=classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)
    cfg=dict(DEFAULT,unattended_sec=11)
    b=classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path,config=cfg)
    assert a['assessment_id']!=b['assessment_id'] and b['situation']=='UNKNOWN'

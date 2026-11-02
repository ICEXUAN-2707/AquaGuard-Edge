import sys
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from rules import classify
from gates import DEFAULT
from checkpoint import restore,save
from alignment import align
from test_rules import fixture,T,timedelta

@pytest.mark.parametrize('drop,idle,situation,quality,reasons',[
    (('flow','water','presence'),False,'UNKNOWN','UNAVAILABLE',['FLOW_MISSING','PRESENCE_EVIDENCE_DEGRADED','WATER_EVIDENCE_DEGRADED']),
    (('flow',),False,'UNKNOWN','UNAVAILABLE',['FLOW_MISSING']),
    (('presence',),False,'UNKNOWN','DEGRADED',['PRESENCE_EVIDENCE_DEGRADED','PRESENCE_UNKNOWN']),
    (('water',),False,'POSSIBLE_UNATTENDED_FLOW','DEGRADED',['UNATTENDED_DURATION_REACHED','WATER_EVIDENCE_DEGRADED']),
    (('presence','water'),True,'IDLE','DEGRADED',['IDLE_CONFIRMED','PRESENCE_EVIDENCE_DEGRADED','WATER_EVIDENCE_DEGRADED']),
    ((),False,'POSSIBLE_UNATTENDED_FLOW','VALID',['UNATTENDED_DURATION_REACHED']),
])
def test_end_to_end_missing_matrix(tmp_path,drop,idle,situation,quality,reasons):
    fw=fixture(tmp_path/'seed',idle=idle)
    seed=restore(fw['state_checkpoint_ref'])
    rows=[r for r in seed['history'] if r['sensor_type'] not in drop]
    w=align(rows,[T+timedelta(seconds=30)])['windows'][0]
    payload=save(tmp_path/'cases',w,rows,alignment_config={})
    result=classify(payload,T+timedelta(seconds=32),checkpoint_root=tmp_path)
    assert (result['situation'],result['data_quality'],result['reason_codes'])==(situation,quality,reasons)
    assert result['origin']==('unknown' if not rows else 'simulation')

@pytest.mark.parametrize('change',[
    {'evaluation_policy':'other'}, {'flow_threshold_policy':'independent'},
    {'rule_version':''}, {'unattended_sec':'10'}, {'unattended_sec':True},
    {'min_flow_coverage':1.1}, {'max_window_age_sec':float('nan')}, {'extra':1},
])
def test_configuration_rejected(tmp_path,change):
    fw=fixture(tmp_path)
    with pytest.raises(ValueError):classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path,config=dict(DEFAULT,**change))

@pytest.mark.parametrize('leave,attended,idle,expected',[
    (20.1,False,False,'UNKNOWN'),(20,False,False,'POSSIBLE_UNATTENDED_FLOW'),
    (5,True,False,'ATTENDED_FLOW'),(5,False,True,'IDLE'),
])
def test_threshold_monotonicity_and_water_independence(tmp_path,leave,attended,idle,expected):
    labels=[]
    for wet in (False,True):
        fw=fixture(tmp_path/str(wet),leave=leave,attended=attended,idle=idle,wet=wet)
        labels.append(classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)['situation'])
    assert labels==[expected,expected]

def test_independent_threshold_reference(tmp_path):
    for duration in (5,9.9,10,10.1,15):
        fw=fixture(tmp_path/str(duration),leave=30-duration)
        for threshold in (5,10,15):
            result=classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path,config=dict(DEFAULT,unattended_sec=threshold))
            expected='POSSIBLE_UNATTENDED_FLOW' if duration>=threshold else 'UNKNOWN'
            assert result['situation']==expected

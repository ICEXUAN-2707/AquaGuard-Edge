import sys
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
sys.path.insert(0,str(BASE.parent/'SP-03/tests'))
from test_alignment import obs,T,timedelta
from continuous import continuous_features

def history():
    rows=[]
    for t in range(0,61,5):
        rows.extend([obs(t,sensor='water',seq=t),obs(t,sensor='presence',seq=t,value=dict(present=False,moving=False,still=False))])
        if t:rows.append(obs(t,sensor='flow',seq=t,value=dict(pulse_count=1,interval_ms=5000,estimated_lpm=6.0,calibration_id='synthetic')))
    return rows

def test_cross_window_no_double_count():
    rows=history()
    for t in (30,35,60):
        result=continuous_features(rows,T+timedelta(seconds=t))
        assert result==dict(flow_streak_sec=float(t),water_contact_sec=float(t),absence_after_flow_sec=float(t))
        assert result==continuous_features(list(reversed(rows)),T+timedelta(seconds=t))

def test_missing_history_only_reports_supported_duration():
    rows=[r for r in history() if (r['sensor_type']=='flow' and r['seq']>30) or (r['sensor_type']!='flow' and r['seq']>=30)]
    assert continuous_features(rows,T+timedelta(seconds=60))['flow_streak_sec']==30

def test_unknown_interrupts_water():
    rows=[obs(20),obs(25,seq=2,quality='unknown',value={'wet':None}),obs(30,seq=3)]
    r=continuous_features(rows,T+timedelta(seconds=35))
    assert r['water_contact_sec']==5
    assert r['flow_streak_sec'] is None and r['absence_after_flow_sec'] is None

def test_ttl_boundary():
    assert continuous_features([obs(20)],T+timedelta(seconds=30))['water_contact_sec'] is None

def test_dry_is_zero():
    assert continuous_features([obs(25,value={'wet':False})],T+timedelta(seconds=30))['water_contact_sec']==0

def test_cross_boot_refused():
    with pytest.raises(ValueError,match='cross-boot'):continuous_features([obs(20),obs(25,boot='b')],T+timedelta(seconds=30))

def test_ttl_gap_restarts_duration():
    rows=[obs(0),obs(20,seq=2)]
    assert continuous_features(rows,T+timedelta(seconds=25))['water_contact_sec']==5

def test_window_tail_without_new_flow_is_unknown():
    r=continuous_features(history(),T+timedelta(seconds=61))
    assert r['flow_streak_sec'] is None and r['absence_after_flow_sec'] is None

def test_nonfinite_config_rejected():
    with pytest.raises(ValueError):continuous_features([],T,threshold=float('nan'))

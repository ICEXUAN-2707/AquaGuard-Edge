import sys,json
from pathlib import Path
from datetime import datetime
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from engine import compute
from alignment import align
from test_continuous import history,T,timedelta,obs

def test_twelve_features_golden():
    rows=history(); end=T+timedelta(seconds=60)
    w=align(rows,[end])['windows'][0]
    r=compute(w,rows,alignment_config={})
    assert r['features']==dict(flow_mean_lpm=6.0,flow_max_lpm=6.0,flow_active_ratio=1.0,flow_streak_sec=60.0,flow_change_count=0,water_contact=True,water_contact_sec=60.0,presence_state='absent',presence_occupied_ratio=0.0,presence_transition_count=0,absence_after_flow_sec=60.0,data_coverage_ratio=1.0)
    assert not any(r['missing_mask'].values())
    assert r==compute(w,list(reversed(rows)),alignment_config={})

def test_all_missing():
    w=align([],[T+timedelta(seconds=30)])['windows'][0]
    r=compute(w,[],alignment_config={})
    assert all(r['missing_mask'].values())
    assert r['features']['data_coverage_ratio']==0
    assert all(v is None for k,v in r['features'].items() if k not in ('presence_state','data_coverage_ratio'))

def test_history_or_config_tampering_rejected():
    rows=[obs(25)];w=align(rows,[T+timedelta(seconds=30)])['windows'][0]
    with pytest.raises(ValueError,match='mismatch'):compute(w,[],alignment_config={})
    with pytest.raises(ValueError,match='mismatch'):compute(w,rows,alignment_config=dict(ttl=20))

def test_source_ttl_reaches_continuous_algorithm():
    rows=[obs(25)]
    config=dict(ttl_by_source=dict(flow=10,water=3,presence=10))
    w=align(rows,[T+timedelta(seconds=30)],**config)['windows'][0]
    assert compute(w,rows,alignment_config=config)['features']['water_contact_sec'] is None

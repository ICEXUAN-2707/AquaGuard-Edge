import sys,json
from pathlib import Path
from datetime import datetime
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from state_features import state_features
from alignment import align
sys.path.insert(0,str(BASE.parent/'SP-03/tests'))
from test_alignment import obs,T,timedelta

def run(rows,**config):
    w=align(rows,[T+timedelta(seconds=30)],**config)['windows'][0]
    return state_features(w,rows,alignment_config=config)

def test_three_source_goldens_and_order():
    case=json.loads((BASE.parent/'SP-03/data/r06_three_source.json').read_text(encoding='utf-8'))
    windows=align(case['observations'],[datetime.fromisoformat(t) for t in case['window_ends']],**case['config'])['windows']
    for w in windows:
        r=state_features(w,case['observations'],alignment_config=case['config'])
        assert r==state_features(w,list(reversed(case['observations'])),alignment_config=case['config'])
        assert r['water_contact'] is True
        assert r['presence_state']=='present'
        assert r['presence_occupied_ratio']==1
        assert r['presence_transition_count']==0
        expected=sum(s['coverage_ratio'] for s in w['sensor_summary'].values())/3
        assert r['data_coverage_ratio']==pytest.approx(expected)

def test_transition_and_unknown_gap():
    def p(t,v,i):
        return obs(t,sensor='presence',seq=i,quality='unknown' if v is None else 'valid',value=dict(present=v,moving=False if v is not None else None,still=v))
    r=run([p(10,True,1),p(20,False,2)],ttl=30)
    assert r['presence_transition_count']==1 and r['presence_occupied_ratio']==0.5
    r=run([p(10,True,1),p(15,None,2),p(20,False,3)],ttl=30)
    assert r['presence_transition_count'] is None
    assert r['presence_occupied_ratio']==pytest.approx(1/3)

def test_missing_and_ttl_boundary():
    r=run([])
    assert r['water_contact'] is None and r['presence_state']=='unknown' and r['data_coverage_ratio']==0
    assert run([obs(20)])['water_contact'] is None

def test_configuration_mismatch():
    rows=[obs(20)]
    w=align(rows,[T+timedelta(seconds=30)])['windows'][0]
    with pytest.raises(ValueError,match='version'): state_features(w,rows,alignment_config=dict(ttl=20))

def test_cross_boot_rejected():
    rows=[obs(20),obs(25,boot='b')]
    with pytest.raises(ValueError,match='cross-boot'): run(rows)

def test_independent_state_reference():
    import random
    rng=random.Random(20261030)
    for _ in range(30):
        values=[rng.choice([True,False]) for i in range(30)]
        rows=[obs(i,sensor='presence',seq=i,value=dict(present=v,moving=False,still=v)) for i,v in enumerate(values)]
        r=run(rows,ttl=2)
        assert r['presence_occupied_ratio']==pytest.approx(sum(values)/30)
        assert r['presence_transition_count']==sum(a!=b for a,b in zip(values,values[1:]))
        assert r['presence_state']==('present' if values[-1] else 'absent')

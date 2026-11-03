import sys
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from transitions import count_transitions
from test_state_features import run
from test_basic_flow import row
from test_state_features import obs

def presence(t,v,seq):
    return obs(t,sensor='presence',seq=seq,quality='unknown' if v is None else 'valid',value=dict(present=v,moving=False if v is not None else None,still=v))

def test_flow_changes_and_gap():
    assert run([row(0,10,6,0),row(10,20,0,1),row(20,30,6,2)])['flow_change_count']==2
    assert run([row(0,10,6,0),row(20,30,0,1)])['flow_change_count'] is None
    assert run([row(0,10,6,0),row(10,30,6,1)])['flow_change_count']==0

def test_presence_right_endpoint():
    assert run([presence(20,True,0),presence(30,False,1)],ttl=20)['presence_transition_count']==1
    assert run([presence(20,True,0),presence(30,True,1)],ttl=20)['presence_transition_count']==0

def test_ttl_and_unknown_do_not_bridge_endpoint():
    assert run([presence(20,True,0),presence(30,False,1)],ttl=10)['presence_transition_count'] is None
    assert run([presence(20,True,0),presence(25,None,1),presence(30,False,2)],ttl=20)['presence_transition_count'] is None

def test_independent_boolean_reference():
    import random
    rng=random.Random(88)
    for _ in range(100):
        values=[rng.choice([True,False]) for i in range(30)]
        intervals=[(i,i+1,v) for i,v in enumerate(values)]
        assert count_transitions(intervals)==sum(values[i]!=values[i-1] for i in range(1,30))

"""R01 hand-authored scenario consistency checks, not a production rule engine."""
import json
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
CONFIG=json.loads((BASE/'data/rules_config.json').read_text(encoding='utf-8-sig'))
CASES=json.loads((BASE/'data/hand_cases.json').read_text(encoding='utf-8-sig'))

def test_approved_config():
    assert CONFIG['unattended_sec']==10
    assert CONFIG['idle_confirm_sec']==5
    assert CONFIG['evaluation_policy']=='fixed_publication_time'

@pytest.mark.parametrize('case',CASES,ids=[c['name'] for c in CASES])
def test_scenario_expected_matches_explicit_preconditions(case):
    # Independent declarative predicates for the handwritten table.
    flow_ok=case['flow']!='unknown' and case['flow_coverage']>=CONFIG['min_flow_coverage']
    presence_ok=case['presence']!='unknown' and case['presence_coverage']>=CONFIG['min_presence_coverage']
    idle=flow_ok and case['flow']=='inactive' and case['idle_sec'] is not None and case['idle_sec']>=CONFIG['idle_confirm_sec']
    attended=flow_ok and case['flow']=='active' and presence_ok and case['presence']=='present'
    unattended=flow_ok and case['flow']=='active' and presence_ok and case['presence']=='absent' and case['absence_sec'] is not None and case['absence_sec']>=CONFIG['unattended_sec']
    expected_flags={'IDLE':idle,'ATTENDED_FLOW':attended,'POSSIBLE_UNATTENDED_FLOW':unattended}
    assert sum(expected_flags.values())<=1
    assert case['expected']==next((k for k,v in expected_flags.items() if v),'UNKNOWN')
    assert case['reason']

def test_boundaries_are_explicit():
    cases={c['name']:c for c in CASES}
    assert cases['absent_9_9']['expected']=='UNKNOWN'
    assert cases['absent_exact_10']['expected']=='POSSIBLE_UNATTENDED_FLOW'
    assert cases['coverage_exact']['expected']=='POSSIBLE_UNATTENDED_FLOW'
    assert cases['wet_attended']['expected']=='ATTENDED_FLOW'

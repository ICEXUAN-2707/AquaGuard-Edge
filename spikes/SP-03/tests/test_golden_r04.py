"""Hand-authored golden cases. Store actual comparisons for group review."""
import json
from pathlib import Path
import pytest
from test_alignment import obs,run,summary
BASE=Path(__file__).resolve().parents[1]
CASES=json.loads((BASE/'data/r04_golden.json').read_text(encoding='utf-8-sig'))
@pytest.mark.parametrize('case',CASES,ids=[c['name'] for c in CASES])
def test_hand_authored_golden(case):
    result=run([obs(case['event'],case['received'])],case['end'])
    actual=summary(result)
    assert actual['state']==case['state']
    assert actual['coverage_ratio']==pytest.approx(case['coverage'])
    assert result['windows'][0]['source_observation_ids']==case['refs']

def test_fallback_keeps_original_null_and_tracks_origin():
    row=obs(25)
    row.update(event_time=None,time_basis='RECEIVED_FALLBACK')
    result=run([row])
    assert row['event_time'] is None
    assert summary(result)['state']=='wet'
    assert 'RECEIVED_FALLBACK' in result['windows'][0]['quality_flags']
    assert result['windows'][0]['origin']=='simulation'

def test_mixed_source_lineage():
    a,b=obs(20),obs(25,seq=2)
    b['source']='hardware'
    assert run([a,b])['windows'][0]['origin']=='mixed'

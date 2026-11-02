"""Independent arithmetic oracle for R01 definitions, not the M4 engine."""
import json
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
CASES=json.loads((BASE/'data/hand_cases.json').read_text(encoding='utf-8-sig'))
@pytest.mark.parametrize('case',CASES,ids=[c['name'] for c in CASES])
def test_hand_arithmetic(case):
    flow=case['flow_segments']; presence=case['presence_segments']
    f=sum(b-a for a,b,q in flow); p=sum(b-a for a,b,v in presence)
    actual=dict(flow_mean_lpm=sum((b-a)*q for a,b,q in flow)/f if f else None,
                flow_max_lpm=max((q for a,b,q in flow),default=None),
                flow_active_ratio=sum(b-a for a,b,q in flow if q>0.1)/f if f else None,
                presence_occupied_ratio=sum(b-a for a,b,v in presence if v)/p if p else None,
                data_coverage_ratio=(f+case['water_valid_sec']+p)/(3*case['window_sec']))
    for key,expected in case['expected'].items():
        assert actual[key] is None if expected is None else actual[key]==pytest.approx(expected)

def test_dictionary_has_exact_candidate_features():
    import csv
    schema=json.loads((BASE.parents[1]/'reference/reference_02/contracts/FeatureWindow.schema.json').read_text(encoding='utf-8'))
    with (BASE/'data/feature_dictionary.csv').open(encoding='utf-8-sig',newline='') as f:
        names=[r['feature'] for r in csv.DictReader(f)]
    assert len(names)==12 and len(set(names))==12
    assert set(names)==set(schema['properties']['features']['required'])

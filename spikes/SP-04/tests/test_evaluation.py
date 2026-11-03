import sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from evaluate import evaluate,metrics

def test_comparison_expected_and_accounting(tmp_path):
    report=evaluate(tmp_path)
    for result in report['metrics'].values():
        assert sum(result[k] for k in ('tp','fp','tn','fn','rejected_positive','rejected_negative'))==8
    b0=report['metrics']['B0_flow'];b1=report['metrics']['B1_instant'];b2=report['metrics']['B2_10s']
    assert (b0['tp'],b0['fp'])==(3,4)
    assert (b1['tp'],b1['fp'],b1['rejected_positive'])==(2,3,1)
    assert (b2['tp'],b2['fp'],b2['rejected_positive'],b2['rejected_negative'])==(2,1,1,2)
    records={r['trial_id']:r for r in report['records']}
    assert records['synthetic-left20']['predictions']==records['synthetic-hidden-person']['predictions']
    assert report['metrics']['B2_15s']['rejected_positive']==2

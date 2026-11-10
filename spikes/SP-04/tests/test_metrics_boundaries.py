import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluate import metrics,evaluate


def row(target,prediction):
    return {'candidate_target':target,'predictions':{'method':prediction}}


def test_empty_set_has_explicit_error():
    with pytest.raises(ValueError,match='at least one'):metrics([],'method')


def test_no_positive_has_undefined_recall_not_zero():
    result=metrics([row(False,False),row(False,None)],'method')
    assert result['positive_recall_all'] is None
    assert result['rejection_rate']==.5
    assert result['tn']==1 and result['rejected_negative']==1


def test_no_negative_and_all_rejected_still_count_positive_denominator():
    result=metrics([row(True,None),row(True,None)],'method')
    assert result['positive_recall_all']==0
    assert result['rejection_rate']==1
    assert result['fn']==0 and result['rejected_positive']==2


@pytest.mark.parametrize('target',[0,1,'true',None])
def test_targets_are_not_truthy_coercions(target):
    with pytest.raises(ValueError,match='target'):metrics([row(target,True)],'method')


@pytest.mark.parametrize('prediction',[0,1,'false',float('nan'),float('inf')])
def test_predictions_are_not_truthy_coercions(prediction):
    with pytest.raises(ValueError,match='prediction'):metrics([row(True,prediction)],'method')


def test_missing_method_is_explicit():
    with pytest.raises(ValueError,match='missing'):metrics([row(True,True)],'other')


def test_original_eight_scene_report_does_not_drift(tmp_path):
    root=Path(__file__).resolve().parents[3]
    frozen=json.loads((root/'deliverables/B-EVAL-001/raw/comparison.json').read_text(encoding='utf-8'))
    assert evaluate(tmp_path)==frozen

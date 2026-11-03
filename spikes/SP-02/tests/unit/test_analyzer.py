import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('sp02analyzer', Path(__file__).parents[2]/'src/analyzer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_set_comparison_detects_equal_count_wrong_identity():
    result = module.analyze([{'observation_id':'a'}], [{'classification':'new','observation':{'observation_id':'b'}}])
    assert result['status'] == 'FAIL'
    assert result['missing'] == ['a']
    assert result['unexpected'] == ['b']


def test_duplicates_do_not_change_unique_count():
    row = {'observation_id':'a'}
    result = module.analyze([row,row], [{'classification':'new','observation':row}, {'classification':'duplicate','observation':row}])
    assert result['status'] == 'PASS'
    assert result['sent_unique'] == 1


def test_empty_run_cannot_pass():
    assert module.analyze([], [])['status'] == 'FAIL'


def test_matching_identity_changed_content_is_failure():
    result = module.analyze([{'observation_id':'a','value':1}],
                            [{'classification':'new','observation':{'observation_id':'a','value':2}}])
    assert result['status']=='FAIL'
    assert result['content_mismatches']==['a']


def test_unknown_classification_cannot_pass():
    row = {'observation_id':'a'}
    assert module.analyze([row],[{'classification':'new','observation':row},{'classification':'mystery'}])['status']=='FAIL'


def test_manifest_content_conflict_cannot_pass():
    row = {'observation_id':'a','value':1}
    assert module.analyze([row,dict(row,value=2)],[{'classification':'new','observation':row}])['status']=='FAIL'

import importlib.util
import json
import sys
from pathlib import Path

spec=importlib.util.spec_from_file_location('supervision',Path(__file__).resolve().parents[2]/'scripts/supervise_endurance.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_atomic_receipt_replaces_prior_state_and_leaves_no_partial_file(tmp_path):
    path=tmp_path/'receipt.json'
    module.atomic_json(path,{'phase':'running'})
    module.atomic_json(path,{'phase':'failed','child_exit_code':1})
    assert json.loads(path.read_text())=={'phase':'failed','child_exit_code':1}
    assert not path.with_suffix('.json.tmp').exists()

def test_failed_child_is_not_mislabeled_completed(tmp_path,monkeypatch):
    output=tmp_path/'new-observation'
    monkeypatch.setattr(sys,'argv',['supervise','--directory',str(output),'--seconds','60'])
    class FailedChild:
        pid=123
        returncode=7
        def wait(self,timeout):return self.returncode
        def poll(self):return self.returncode
    monkeypatch.setattr(module.subprocess,'Popen',lambda *args,**kwargs:FailedChild())
    assert module.main()==1
    receipt=json.loads((tmp_path/'new-observation.supervisor.json').read_text())
    assert receipt['phase']=='failed' and receipt['child_exit_code']==7
    assert receipt['result_exists'] is False and receipt['child_exit_confirmed'] is True

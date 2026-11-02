"""Recovery and fault checks, including classification in a fresh Python process."""
import sys,json,subprocess,hashlib
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from rules import classify
from checkpoint import restore,save,canonical
from alignment import align
from test_rules import fixture,T,timedelta

def test_fresh_process_recovery_and_repeat(tmp_path):
    fw=fixture(tmp_path)
    now=T+timedelta(seconds=32)
    expected=classify(fw,now,checkpoint_root=tmp_path)
    script='import sys,json; from datetime import datetime; sys.path.insert(0,sys.argv[1]); from rules import classify; p=json.load(sys.stdin); print(json.dumps(classify(p,datetime.fromisoformat(sys.argv[3]),checkpoint_root=sys.argv[2]),sort_keys=True))'
    result=subprocess.run([sys.executable,'-c',script,str(BASE/'src'),str(tmp_path),now.isoformat()],input=json.dumps(fw),text=True,capture_output=True,check=True,timeout=30)
    assert json.loads(result.stdout)==expected
    assert classify(fw,now,checkpoint_root=tmp_path)==expected

def test_resume_with_new_observations(tmp_path):
    fw=fixture(tmp_path/'initial');restored=restore(fw['state_checkpoint_ref'])
    extra=[]
    for original in restored['history']:
        if original['event_time'].startswith('2026-10-29T00:00:30'):
            r=json.loads(json.dumps(original));r.update(observation_id=r['observation_id']+'-next',seq=r['seq']+100,uptime_ms=35000,event_time=(T+timedelta(seconds=35)).isoformat(),received_at=(T+timedelta(seconds=35)).isoformat());extra.append(r)
    rows=restored['history']+extra
    w=align(rows,[T+timedelta(seconds=35)])['windows'][0]
    resumed=save(tmp_path/'resumed',w,rows,alignment_config={})
    fresh=save(tmp_path/'fresh',w,list(reversed(rows)),alignment_config={})
    a=classify(resumed,T+timedelta(seconds=37),checkpoint_root=tmp_path)
    b=classify(fresh,T+timedelta(seconds=37),checkpoint_root=tmp_path)
    assert a==b and a['situation']=='POSSIBLE_UNATTENDED_FLOW'

@pytest.mark.parametrize('kind',['missing','corrupt','version'])
def test_checkpoint_fault_rejected(tmp_path,kind):
    fw=fixture(tmp_path);path=Path(fw['state_checkpoint_ref'])
    if kind=='missing':path.unlink()
    elif kind=='corrupt':path.write_bytes(path.read_bytes()+b' ')
    else:
        data=json.loads(path.read_bytes());data['feature_version']='unsupported'
        raw=canonical(data);other=tmp_path/(hashlib.sha256(raw).hexdigest()+'.json');other.write_bytes(raw);fw['state_checkpoint_ref']=str(other.resolve())
    with pytest.raises((ValueError,FileNotFoundError)):
        classify(fw,T+timedelta(seconds=32),checkpoint_root=tmp_path)

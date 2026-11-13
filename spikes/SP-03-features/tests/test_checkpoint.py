import sys,json,hashlib
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from checkpoint import save,restore,canonical
from alignment import align
from engine import compute
from test_continuous import history,T,timedelta,obs

def test_snapshot_idempotence_and_resume(tmp_path):
    rows=history();end=T+timedelta(seconds=60)
    w=align(rows,[end])['windows'][0]
    output=save(tmp_path,w,rows,alignment_config={})
    assert output==save(tmp_path,w,list(reversed(rows)),alignment_config={})
    assert len(list(tmp_path.glob('*.json')))==1
    restored=restore(output['state_checkpoint_ref'],expected_config={})
    assert restored['feature_window']==output
    extra=[obs(65,sensor='water',seq=65),obs(65,sensor='presence',seq=65,value=dict(present=False,moving=False,still=False)),obs(65,sensor='flow',seq=65,value=dict(pulse_count=1,interval_ms=5000,estimated_lpm=6.0,calibration_id='synthetic'))]
    extended=rows+extra
    new_w=align(extended,[T+timedelta(seconds=65)])['windows'][0]
    resumed=compute(new_w,restored['history']+extra,alignment_config=restored['alignment_config'])
    assert resumed==compute(new_w,extended,alignment_config={})
    assert resumed['features']['flow_streak_sec']==65

def test_corruption_and_config(tmp_path):
    rows=history();w=align(rows,[T+timedelta(seconds=60)])['windows'][0]
    output=save(tmp_path,w,rows,alignment_config={});path=Path(output['state_checkpoint_ref'])
    with pytest.raises(ValueError,match='configuration'):restore(path,expected_config=dict(ttl=11))
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='digest'):restore(path)

def test_version_and_result_tamper(tmp_path):
    rows=history();w=align(rows,[T+timedelta(seconds=60)])['windows'][0]
    output=save(tmp_path,w,rows,alignment_config={})
    original=json.loads(Path(output['state_checkpoint_ref']).read_bytes())
    for kind in ('version','result'):
        payload=json.loads(json.dumps(original))
        if kind=='version':payload['feature_version']='unsupported'
        else:payload['result']['features']['flow_mean_lpm']=999
        data=canonical(payload);path=tmp_path/(hashlib.sha256(data).hexdigest()+'.json');path.write_bytes(data)
        with pytest.raises(ValueError,match='version' if kind=='version' else 'replay'):restore(path)

def test_missing_featurewindow_cross_fields(tmp_path):
    w=align([],[T+timedelta(seconds=30)])['windows'][0]
    output=save(tmp_path,w,[],alignment_config={})
    assert all(output['missing_mask'].values())
    assert restore(output['state_checkpoint_ref'])['feature_window']==output

def test_atomic_save_failure_leaves_no_partial_checkpoint(tmp_path,monkeypatch):
    import checkpoint
    rows=history();w=align(rows,[T+timedelta(seconds=60)])['windows'][0]
    def fail(*args):raise OSError('injected replace failure')
    monkeypatch.setattr(checkpoint.os,'replace',fail)
    with pytest.raises(OSError,match='injected'):save(tmp_path,w,rows,alignment_config={})
    assert list(tmp_path.iterdir())==[]

def test_scoped_verification_reuses_compute_but_never_mutable_results_or_path_trust(tmp_path,monkeypatch):
    import checkpoint
    rows=history();w=align(rows,[T+timedelta(seconds=60)])['windows'][0]
    output=save(tmp_path,w,rows,alignment_config={});path=Path(output['state_checkpoint_ref'])
    compute_original=checkpoint.compute;calls=[]
    def counted(*args,**kwargs):
        calls.append(1);return compute_original(*args,**kwargs)
    monkeypatch.setattr(checkpoint,'compute',counted)
    with checkpoint.verification_scope():
        restored=restore(path);restored['history'].clear();restored['last_window'].clear()
        restored['feature_window']['features']['flow_mean_lpm']=999
        assert restore(path)['history'] and restore(path)['last_window']
        assert restore(path)['feature_window']==output
        assert len(calls)==1
        with pytest.raises(ValueError,match='configuration'):restore(path,expected_config={'ttl':99})
        original=path.read_bytes();path.write_bytes(original+b' ')
        with pytest.raises(ValueError,match='digest'):restore(path)
        path.write_bytes(original)
    restore(path)
    assert len(calls)==2  # No reuse across publication lifetimes.

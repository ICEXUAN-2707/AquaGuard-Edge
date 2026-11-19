import json,hashlib,shutil
from pathlib import Path
import pytest
from test_checkpoint import history,T,timedelta,align,save
import checkpoint
import checkpoint_cached_v1 as cached

@pytest.fixture
def saved(tmp_path):
    rows=history();window=align(rows,[T+timedelta(seconds=60)])['windows'][0]
    return Path(save(tmp_path,window,rows,alignment_config={})['state_checkpoint_ref'])

def test_scoped_results_equal_frozen_restore_and_only_compute_once(saved,monkeypatch):
    expected=checkpoint.restore(saved);calls=[];original=checkpoint.compute
    def count(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(checkpoint,'compute',count)
    with cached.verification_scope():
        assert cached.restore(saved)==expected
        assert cached.restore(saved)==expected
    assert len(calls)==1
    cached.restore(saved);cached.restore(saved)
    assert len(calls)==3

def test_cached_output_mutation_cannot_change_subsequent_results(saved):
    expected=checkpoint.restore(saved)
    with cached.verification_scope():
        value=cached.restore(saved);value['history'].clear();value['feature_window']['features']['flow_mean_lpm']=999
        assert cached.restore(saved)==expected

def test_same_content_different_path_keeps_correct_reference(saved,tmp_path):
    other=tmp_path/'copy';other.mkdir();copy=other/saved.name;shutil.copyfile(saved,copy)
    with cached.verification_scope():
        cached.restore(saved)
        assert cached.restore(copy)==checkpoint.restore(copy)

def test_cache_hit_still_rejects_config_and_changed_file(saved):
    with cached.verification_scope():
        cached.restore(saved)
        with pytest.raises(ValueError,match='configuration'):cached.restore(saved,expected_config={'ttl':11})
        saved.write_bytes(saved.read_bytes()+b' ')
        with pytest.raises(ValueError,match='digest'):cached.restore(saved)

@pytest.mark.parametrize('kind',['version','result'])
def test_renamed_tamper_still_gets_independent_verification(saved,tmp_path,kind):
    payload=json.loads(saved.read_bytes())
    if kind=='version':payload['feature_version']='unsupported'
    else:payload['result']['features']['flow_mean_lpm']=999
    data=checkpoint.canonical(payload);path=tmp_path/(hashlib.sha256(data).hexdigest()+'.json');path.write_bytes(data)
    with cached.verification_scope():
        cached.restore(saved)
        with pytest.raises(ValueError):cached.restore(path)

def test_nested_scopes_restore_outer_cache_and_release_on_exception(saved):
    with cached.verification_scope():
        cached.restore(saved);outer=cached._cache.get()
        with pytest.raises(RuntimeError):
            with cached.verification_scope():
                cached.restore(saved);assert cached._cache.get() is not outer
                raise RuntimeError()
        assert cached._cache.get() is outer
    assert cached._cache.get() is None

def test_cache_is_bounded_by_entries(saved,tmp_path):
    with cached.verification_scope():
        for n in range(7):
            payload=json.loads(saved.read_bytes());payload['cache_test_marker']=n
            data=checkpoint.canonical(payload);path=tmp_path/(hashlib.sha256(data).hexdigest()+'.json');path.write_bytes(data)
            assert cached.restore(path)==checkpoint.restore(path)
        assert len(cached._cache.get())==4

import importlib.util
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('mqtt_collector',ROOT/'scripts/observe_mqtt_capacity.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_long_collection_is_opt_in_and_creates_nothing(tmp_path):
    output=tmp_path/'run'
    with pytest.raises(ValueError,match='disabled'):module.collect('unused','unused',output,samples=100)
    assert not output.exists()

def test_failed_inventory_is_incomplete_without_fabricated_acceptance(tmp_path):
    result=module.collect(tmp_path/'absent',tmp_path/'missing',tmp_path/'run')
    assert result['collection_status']=='INCOMPLETE' and result['recorded_samples']==0
    assert result['long_run_acceptance'] is False

def test_single_snapshot_completion_is_not_performance_acceptance(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'snapshot',lambda *args:{'pending_eligible_attempts':3})
    result=module.collect('unused','unused',tmp_path/'run')
    assert result['collection_status']=='COMPLETED' and not result['long_run_acceptance']
    assert result['coverage_status']=='UNKNOWN'


def test_host_gap_is_recorded_without_backfilling_or_suspend_verdict(tmp_path,monkeypatch):
    import json
    clock=[0.0];calls=[0];sleeps=[]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(module.time,'time',lambda:1000+clock[0])
    def sleep(seconds):
        sleeps.append(seconds);clock[0]+=seconds+20
    def snapshot(*args):
        calls[0]+=1
        return {'scope':'test'}
    monkeypatch.setattr(module.time,'sleep',sleep)
    monkeypatch.setattr(module,'snapshot',snapshot)
    result=module.collect('unused','unused',tmp_path/'run',samples=3,interval=1)
    rows=[json.loads(line) for line in (tmp_path/'run/samples.jsonl').read_text().splitlines()]
    assert result['collection_status']=='COMPLETED' and result['coverage_status']=='GAPS'
    assert result['late_samples']==2 and result['max_sample_gap_seconds']==21
    assert calls[0]==3 and sleeps==[1,1]
    assert all(row['estimated_suspend_seconds'] is None for row in rows)
    assert not result['long_run_acceptance']


@pytest.mark.parametrize('interval',[float('nan'),float('inf'),True,'15'])
def test_invalid_interval_is_rejected_without_output(tmp_path,interval):
    with pytest.raises(ValueError):module.collect('unused','unused',tmp_path/'run',interval=interval)
    assert not (tmp_path/'run').exists()

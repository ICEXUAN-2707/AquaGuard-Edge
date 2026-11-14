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

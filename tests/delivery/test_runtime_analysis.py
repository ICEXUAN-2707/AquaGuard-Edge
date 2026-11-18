import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('runtime_analysis',Path(__file__).resolve().parents[2]/'scripts/analyze_runtime_observation.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_missing_diagnostics_preserve_unavailable_sample_instead_of_hiding_it():
    report=module.analyze([{'elapsed_sec':10,'live':{'status':404}},
                           {'elapsed_sec':60,'live':{'status':503}},
                           {'elapsed_sec':65,'live':{'status':200}}])
    assert report['steady_live_status_counts']=={'503':1,'200':1}
    assert report['unavailable_samples'][0]['estimated_suspend_seconds'] is None
    assert report['max_advance_seconds'] is None
    assert report['max_sample_gap_seconds'] is None
    assert report['max_estimated_suspend_seconds'] is None


def test_measured_zero_is_distinct_from_unknown_suspend():
    report=module.analyze([{'elapsed_sec':60,'estimated_suspend_seconds':0,'sample_gap_seconds':15}])
    assert report['max_estimated_suspend_seconds']==0
    assert report['max_sample_gap_seconds']==15

def test_partial_timing_fields_remain_unknown():
    result=module.analyze([{'elapsed_sec':60,'runtime':{'diagnostics':{'timing':{'max_advance_seconds':0}}}}])
    assert result['max_advance_seconds']==0
    assert result['max_runtime_gap_seconds'] is None and result['max_timer_failures'] is None

def test_protocol_samples_use_declared_phase_and_new_elapsed_key():
    report=module.analyze([{'elapsed_seconds':60,'phase':'continuous','live':{'status':200}},
                           {'elapsed_seconds':100,'phase':'publisher_stop','live':{'status':503}},
                           {'elapsed_seconds':120,'phase':'shutdown','live':None}])
    assert report['steady_samples']==1 and report['steady_live_status_counts']=={'200':1}
    assert report['max_advance_seconds'] is None

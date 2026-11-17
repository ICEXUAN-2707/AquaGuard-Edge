from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from mqtt_runtime_observation import assess,validate_thresholds,os_clocks,process_resources


def budgets():
    # Synthetic test budgets, not approved experiment thresholds.
    return dict(max_sample_gap_seconds=16,min_coverage_ratio=1,max_os_excluded_seconds=0,
                max_collection_seconds=1,max_process_rss_bytes=1000)


def clock(elapsed,awake=None):return dict(available=True,source='test',elapsed_seconds=elapsed,awake_seconds=elapsed if awake is None else awake)


def sample(offset):
    return dict(phase_elapsed_seconds=offset,collection_seconds=.1,os_clock=clock(offset),
                resources=[dict(name='edge',pid=1,creation_filetime=100,available=True,rss_bytes=100,cpu_seconds=offset/10)])


def report(samples,**changes):
    config=dict(duration=30,interval=15,thresholds=budgets(),end_clock=clock(30));config.update(changes)
    return assess(samples,**config)


def test_complete_observations_are_local_budget_checks_only():
    value=report([sample(0),sample(15)])
    assert value['status']=='SATISFIED' and value['expected_samples']==2
    assert value['processes'][0]['max_cpu_seconds']==1.5 and value['os_excluded_seconds']==0
    assert 'acceptance_passed' not in value


def test_pause_tail_preserves_original_denominator_and_reports_gap():
    value=report([sample(0)],actual_duration=60,end_clock=clock(60,10))
    assert value['status']=='VIOLATED' and value['expected_samples']==2
    assert value['coverage_ratio']==.5 and value['max_sample_gap_seconds']==60
    assert value['os_excluded_seconds']==50
    assert not value['checks']['gap'] and not value['checks']['os_excluded']


@pytest.mark.parametrize('missing',['clock','resource','malformed_resource','clock_reversed'])
def test_unknown_metrics_never_become_zero_or_satisfied(missing):
    rows=[sample(0),sample(15)];end=clock(30)
    if missing=='clock':rows[0]['os_clock']={'available':False}
    if missing=='resource':rows[0]['resources'][0]={'available':False}
    if missing=='malformed_resource':del rows[0]['resources'][0]['rss_bytes']
    if missing=='clock_reversed':end=clock(-1)
    value=report(rows,end_clock=end)
    assert value['status']=='INCOMPLETE'
    if missing in ('clock','clock_reversed'):assert value['os_excluded_seconds'] is None


def test_pid_reuse_remains_two_process_identities():
    rows=[sample(0),sample(15)];rows[1]['resources'][0]['creation_filetime']=200
    value=report(rows)
    assert len(value['processes'])==2


def test_missing_thresholds_remain_unconfigured():
    assert report([sample(0),sample(15)],thresholds=None)['status']=='UNCONFIGURED'


@pytest.mark.parametrize('change',[{'min_coverage_ratio':2},{'max_os_excluded_seconds':-1},{'max_process_rss_bytes':True},{'max_collection_seconds':float('nan')}])
def test_invalid_budgets_are_rejected(change):
    config=budgets();config.update(change)
    with pytest.raises(ValueError):validate_thresholds(config)


def test_windows_native_clocks_and_owned_short_child():
    if os.name!='nt':pytest.skip('Windows native observations')
    first=os_clocks();assert first['available'],first
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(2)'])
    try:
        value=process_resources(child)
        assert value['available'] and value['rss_bytes']>0 and value['creation_filetime']>0
        second=os_clocks()
        assert second['elapsed_seconds']>=first['elapsed_seconds'] and second['awake_seconds']>=first['awake_seconds']
    finally:child.terminate();child.wait(timeout=5)

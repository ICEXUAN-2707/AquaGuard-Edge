import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alignment_r02', BASE/'src/alignment.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
T=datetime(2026,10,29,tzinfo=timezone.utc)
def obs(t, received=None, sensor='water', seq=1, boot='a', quality='valid', value=None):
    return dict(schema_version='1.1', observation_id=f'{sensor}-{boot}-{seq}', device_id='demo', sensor_type=sensor, boot_id=boot, seq=seq, uptime_ms=max(0,t*1000), event_time=(T+timedelta(seconds=t)).isoformat(), received_at=(T+timedelta(seconds=t if received is None else received)).isoformat(), time_basis='DEVICE_SYNCED', value=value or {'wet':True}, quality=quality, source='simulation')
def run(rows, end=30):
    return m.align(rows,[T+timedelta(seconds=end)])
def summary(result, sensor='water'):
    return result['windows'][0]['sensor_summary'][sensor]
def test_silence_publishes():
    assert all(s['coverage_ratio']==0 and s['state']=='unknown' for s in run([])['windows'][0]['sensor_summary'].values())
def test_predecessor_and_ttl_boundary():
    assert summary(run([obs(-5)]))['coverage_ratio']==pytest.approx(5/30)
    assert summary(run([obs(20)]))['state']=='unknown'
def test_right_boundary_state_without_duration():
    s=summary(run([obs(30,32)]))
    assert s==dict(state='wet',age_sec=0.0,coverage_ratio=0.0)
def test_late_is_per_window():
    row=obs(29,33)
    result=m.align([row],[T+timedelta(seconds=30),T+timedelta(seconds=35)])
    assert result['windows'][0]['sensor_summary']['water']['state']=='unknown'
    assert result['windows'][1]['sensor_summary']['water']['state']=='wet'
    assert len(result['audit'])==1
    assert result['windows'][0]['source_observation_ids']==[]
def test_unknown_interrupts_hold():
    s=summary(run([obs(20),obs(25,seq=2,quality='unknown',value={'wet':None})]))
    assert s['state']=='unknown'
    assert s['coverage_ratio']==pytest.approx(5/30)
def test_boot_sequence_reset_and_order():
    rows=[obs(20),obs(25,seq=1,boot='b')]
    assert run(rows)==run(list(reversed(rows)))
    assert summary(run(rows))['state']=='wet'
def test_duplicate_and_conflict():
    r=obs(20)
    assert run([r,r])['audit'][0]['code']=='DUPLICATE'
    conflict=dict(r,value={'wet':False})
    with pytest.raises(ValueError): run([r,conflict])
def test_future_rejected():
    assert summary(run([obs(25,20)]))['state']=='unknown'
def test_flow_interval_clipping():
    r=obs(5,sensor='flow',value=dict(pulse_count=1,interval_ms=10000,estimated_lpm=1.0,calibration_id='synthetic'))
    assert summary(run([r]),'flow')['coverage_ratio']==pytest.approx(5/30)
def test_invalid_config_and_raw_quality():
    with pytest.raises(ValueError): m.align([],[],ttl=0)
    with pytest.raises(ValueError): run([obs(20,quality='late')])
def test_golden_file():
    case=json.loads((BASE/'data/r02_case.json').read_text(encoding='utf-8-sig'))
    actual=m.align(case['observations'],[datetime.fromisoformat(t) for t in case['window_ends']],**case['config'])
    assert [w['sensor_summary'] for w in actual['windows']]==case['expected_summaries']

def test_unknown_interrupter_retains_lineage():
    result=run([obs(20),obs(25,seq=2,quality='unknown',value={'wet':None})])
    assert result['windows'][0]['source_observation_ids']==['water-a-1','water-a-2']

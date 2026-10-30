import sys,json,random
from pathlib import Path
from datetime import datetime,timedelta,timezone
import pytest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
sys.path.insert(0,str(BASE.parent/'SP-03/src'))
from basic_flow import calculate
from alignment import align
T=datetime(2026,10,29,tzinfo=timezone.utc)
def row(a,b,q,i):
    return dict(schema_version='1.1',observation_id=f'f{i}',device_id='demo',sensor_type='flow',boot_id='a',seq=i,uptime_ms=b*1000,event_time=(T+timedelta(seconds=b)).isoformat(),received_at=(T+timedelta(seconds=b)).isoformat(),time_basis='DEVICE_SYNCED',value=dict(pulse_count=1,interval_ms=(b-a)*1000,estimated_lpm=q,calibration_id='synthetic'),quality='valid',source='simulation')
def window(rows):
    return align(rows,[T+timedelta(seconds=30)])['windows'][0]
@pytest.mark.parametrize('spans,expected',[
    ([(0,10,6)],(6,6,1,1/3)),
    ([(0,10,6),(10,30,0)],(2,6,1/3,1)),
    ([],(None,None,None,0)),
    ([(-5,5,3),(10,20,9)],(7,9,1,0.5)),
])
def test_hand_goldens(spans,expected):
    rows=[row(a,b,q,i) for i,(a,b,q) in enumerate(spans)]
    actual=calculate(window(rows),rows)
    for key,value in zip(('flow_mean_lpm','flow_max_lpm','flow_active_ratio','flow_coverage_ratio'),expected):
        assert actual[key] is None if value is None else actual[key]==pytest.approx(value)

def test_independent_one_second_oracle_and_m3_coverage():
    rng=random.Random(20261029)
    for trial in range(100):
        cells=[rng.choice([None,0.0,0.1,3.0,6.0]) for _ in range(30)]
        rows=[row(i,i+1,q,i) for i,q in enumerate(cells) if q is not None]
        w=window(rows); result=calculate(w,list(reversed(rows)))
        known=[q for q in cells if q is not None]
        assert result['flow_coverage_ratio']==pytest.approx(len(known)/30)
        assert result['flow_coverage_ratio']==pytest.approx(w['sensor_summary']['flow']['coverage_ratio'])
        if known:
            assert result['flow_mean_lpm']==pytest.approx(sum(known)/len(known))
            assert result['flow_max_lpm']==max(known)
            assert result['flow_active_ratio']==pytest.approx(sum(q>0.1 for q in known)/len(known))

def test_three_source_fixture():
    case=json.loads((BASE.parent/'SP-03/data/r06_three_source.json').read_text(encoding='utf-8'))
    windows=align(case['observations'],[datetime.fromisoformat(t) for t in case['window_ends']],**case['config'])['windows']
    for w in windows:
        r=calculate(w,case['observations'])
        assert r['flow_mean_lpm']==6 and r['flow_active_ratio']==1
        assert r['flow_coverage_ratio']==w['sensor_summary']['flow']['coverage_ratio']

def test_overlap_and_reference_failures():
    rows=[row(0,10,6,1),row(5,15,3,2)]
    with pytest.raises(ValueError,match='overlapping'): calculate(window(rows),rows)
    rows=[row(0,10,6,1)]; w=window(rows)
    with pytest.raises(ValueError,match='missing'): calculate(w,[])
    w['origin']='hardware'
    with pytest.raises(ValueError,match='origin'): calculate(w,rows)

def test_split_invariance():
    coarse=[row(0,30,6,0)]
    fine=[row(i,i+5,6,i) for i in range(0,30,5)]
    a,b=calculate(window(coarse),coarse),calculate(window(fine),fine)
    for key in ('flow_mean_lpm','flow_max_lpm','flow_active_ratio','flow_coverage_ratio','valid_flow_sec'):
        assert a[key]==b[key]

def test_subsecond_duration_and_exact_threshold():
    r=row(0,1,0.1,0)
    r['value']['interval_ms']=250
    actual=calculate(window([r]),[r])
    assert actual['valid_flow_sec']==0.25
    assert actual['flow_mean_lpm']==0.1
    assert actual['flow_active_ratio']==0
    assert actual['flow_coverage_ratio']==pytest.approx(0.25/30)

def test_bad_threshold_rejected():
    for value in (-1,float('nan'),float('inf')):
        with pytest.raises(ValueError,match='threshold'): calculate(window([]),[],threshold=value)

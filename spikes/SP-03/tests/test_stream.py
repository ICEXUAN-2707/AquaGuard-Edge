import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stream import Stream
from test_alignment import obs,T,timedelta,m
import pytest

def test_silence_and_batch_equivalence():
    s=Stream('demo',T+timedelta(seconds=30))
    rows=[obs(20),obs(25,seq=2)]
    for r in rows: assert s.push(r)==[]
    actual=s.advance(T+timedelta(seconds=37))
    expected=m.align(rows,[T+timedelta(seconds=30),T+timedelta(seconds=35)])
    assert [p['windows'][0] for p in actual]==expected['windows']

def test_per_source_ttl():
    s=Stream('demo',T+timedelta(seconds=30),ttl_by_source=dict(flow=1,water=3,presence=20))
    s.push(obs(25))
    w=s.advance(T+timedelta(seconds=32))[0]['windows'][0]
    assert w['sensor_summary']['water']['state']=='unknown'
    assert w['sensor_summary']['water']['coverage_ratio']==pytest.approx(3/30)

def test_reboot_clears_other_sensor_state_and_rejects_retired():
    s=Stream('demo',T+timedelta(seconds=30))
    s.push(obs(25))
    s.push(obs(26,sensor='presence',boot='b',value=dict(present=True,moving=False,still=True)))
    assert s.advance(T+timedelta(seconds=32))[0]['windows'][0]['sensor_summary']['water']['state']=='unknown'
    with pytest.raises(ValueError,match='retired'): s.push(obs(33,seq=2))

def test_capacity_fail_closed_and_expiry():
    s=Stream('demo',T+timedelta(seconds=30),capacity=1)
    s.push(obs(20))
    with pytest.raises(OverflowError): s.push(obs(21,seq=2))
    assert len(s.rows)==1
    s.advance(T+timedelta(seconds=102))
    assert len(s.rows)==0

def test_deadline_arrival_then_explicit_timer():
    s=Stream('demo',T+timedelta(seconds=30))
    assert s.push(obs(30,32))==[]
    assert s.advance(T+timedelta(seconds=32))[0]['windows'][0]['sensor_summary']['water']['state']=='wet'
    with pytest.raises(ValueError): s.advance(T)

def test_boot_history_bounded():
    s=Stream('demo',T+timedelta(seconds=30),max_boots=1)
    s.push(obs(1));s.push(obs(2,boot='b'))
    with pytest.raises(OverflowError): s.push(obs(3,boot='c'))

def test_silent_device_identity():
    s=Stream('home01',T+timedelta(seconds=30))
    assert s.advance(T+timedelta(seconds=32))[0]['windows'][0]['device_id']=='home01'

def test_caller_mutation_does_not_change_buffer():
    s=Stream('demo',T+timedelta(seconds=30))
    row=obs(25)
    s.push(row)
    row['value']['wet']=False
    assert s.advance(T+timedelta(seconds=32))[0]['windows'][0]['sensor_summary']['water']['state']=='wet'

def test_boot_reset_is_audited():
    s=Stream('demo',T+timedelta(seconds=30))
    s.push(obs(1))
    packets=s.push(obs(2,boot='b'))
    assert packets[-1]['audit'][0]['code']=='BOOT_RESET'

def test_late_arrival_audited_without_rewriting_published_window():
    s=Stream('demo',T+timedelta(seconds=30))
    published=s.advance(T+timedelta(seconds=32))[0]['windows'][0]
    packets=s.push(obs(29,33))
    assert packets[-1]['audit'][0]['code']=='ARRIVED_AFTER_PUBLICATION'
    assert published['sensor_summary']['water']['state']=='unknown'
    assert s.advance(T+timedelta(seconds=37))[0]['windows'][0]['sensor_summary']['water']['state']=='wet'

def test_audit_configuration_cannot_be_mutated_by_caller():
    ttls=dict(flow=1,water=3,presence=20)
    s=Stream('demo',T+timedelta(seconds=30),ttl_by_source=ttls)
    s.push(obs(1))
    packet=s.push(obs(2,boot='b'))[-1]
    packet['config']['ttl_by_source']['water']=999
    assert s.config['ttl_by_source']['water']==3

def test_expired_full_buffer_recovers_on_push():
    s=Stream('demo',T+timedelta(seconds=30),capacity=1)
    s.push(obs(1))
    packets=s.push(obs(100,seq=2))
    assert len(s.rows)==1 and len(packets)>0
    assert s.rows[0]['seq']==2

def test_invalid_new_boot_preserves_state():
    s=Stream('demo',T+timedelta(seconds=30))
    s.push(obs(25))
    with pytest.raises(ValueError,match='future'): s.push(obs(100,26,boot='b'))
    assert s.boot=='a' and not s.retired and len(s.rows)==1

def test_capacity_failure_is_atomic():
    s=Stream('demo',T+timedelta(seconds=30),capacity=1)
    s.push(obs(25))
    before=(s.now,s.next_end,list(s.rows))
    with pytest.raises(OverflowError): s.push(obs(26,seq=2))
    assert (s.now,s.next_end,s.rows)==before

def test_bounded_catchup_then_retry():
    s=Stream('demo',T+timedelta(seconds=30),max_windows=2)
    s.push(obs(1))
    with pytest.raises(OverflowError,match='catch-up'): s.push(obs(100,seq=2))
    assert s.next_end==T+timedelta(seconds=30)
    windows=[]
    while s.next_end+timedelta(seconds=2)<T+timedelta(seconds=100):
        batch=s.advance(T+timedelta(seconds=100),inclusive=False)
        assert len(batch)<=2
        windows.extend(p['windows'][0]['window_end'] for p in batch)
    assert len(windows)==len(set(windows))==14
    s.push(obs(100,seq=2))

def test_unknown_new_boot_rejected():
    s=Stream('demo',T+timedelta(seconds=30))
    s.push(obs(1))
    with pytest.raises(ValueError,match='valid event-time'): s.push(obs(2,boot='b',quality='unknown',value={'wet':None}))
    assert s.boot=='a'

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mqtt_journal import JournalRuntime


def journal(path):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE attempts(number INTEGER PRIMARY KEY,classification TEXT,body TEXT)')


def append(path, start, second, *, boot='mqtt-boot', source='simulation'):
    values={'flow':dict(pulse_count=8,interval_ms=1000,estimated_lpm=1.,calibration_id='simulation-only'),
            'water':dict(wet=second>=35),'presence':dict(present=True,moving=True,still=False)}
    with sqlite3.connect(path) as db:
        for sensor,value in values.items():
            row=dict(schema_version='1.1',observation_id=f'{boot}:{sensor}:{second}',device_id='demo01',
                sensor_type=sensor,boot_id=boot,seq=second,uptime_ms=second*1000,event_time=None,
                received_at=(start+timedelta(seconds=second)).isoformat(),time_basis='RECEIVED_FALLBACK',
                value=value,quality='valid',source=source)
            db.execute("INSERT INTO attempts(classification,body) VALUES('new',?)",(json.dumps(row),))


def test_journal_drives_live_events_and_restart(tmp_path):
    start=datetime(2026,11,10,tzinfo=timezone.utc)
    source=tmp_path/'journal.sqlite'; journal(source)
    runtime=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',start,source)
    for i in range(46):
        append(source,start,i)
        runtime.step(start+timedelta(seconds=i))
    now=start+timedelta(seconds=45)
    live=runtime.queries.read('live','demo01',now=now.isoformat())
    assert live['origin']=='simulation'
    assert live['sensor_summary']['water']['state']=='wet'
    with runtime.water.connection() as db:
        before=db.execute('SELECT count(*) FROM transitions').fetchone()[0]
        assert db.execute('SELECT count(*) FROM outbox').fetchone()[0]>0
    restored=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',now,source)
    restored.step(now)
    with restored.water.connection() as db:
        assert db.execute('SELECT count(*) FROM transitions').fetchone()[0]==before
    assert restored.cursor==138
    assert restored.rows[-1]['observation_id']=='mqtt-boot:presence:45'


def test_stale_backlog_cannot_refresh_state(tmp_path):
    start=datetime(2026,11,10,tzinfo=timezone.utc)
    source=tmp_path/'journal'; journal(source); append(source,start,40)
    now=start+timedelta(seconds=100)
    runtime=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',now,source)
    assert runtime.step(now) is None
    with runtime.water.connection() as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0]==0
        assert db.execute('SELECT reason FROM mqtt_water_dispositions').fetchone()[0]=='STALE_BACKLOG'


def test_late_water_is_recorded_without_blocking_consumer_restart(tmp_path):
    start=datetime(2026,11,10,tzinfo=timezone.utc)
    source=tmp_path/'journal'; journal(source)
    runtime=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',start,source)
    append(source,start,35)
    runtime.step(start+timedelta(seconds=35))
    runtime.water.expire('demo01',now=(start+timedelta(seconds=37)).isoformat(),
                         policy=__import__('policy').Policy(10,2),policy_version='g1-simulation-v1')
    append(source,start,36)
    runtime.step(start+timedelta(seconds=38))
    assert runtime.cursor==6
    with runtime.water.connection() as db:
        assert db.execute('SELECT reason FROM mqtt_water_dispositions').fetchone()[0]=='BEHIND_WATER_WATERMARK'
        assert db.execute('SELECT count(*) FROM events').fetchone()[0]==1
    restored=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',start+timedelta(seconds=38),source)
    restored.step(start+timedelta(seconds=38))
    assert restored.cursor==6


def test_batch_receipts_and_concurrent_future_commit(tmp_path):
    start=datetime(2026,11,10,tzinfo=timezone.utc)
    source=tmp_path/'journal'; journal(source)
    runtime=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',start,source)
    for i in (0,1,2): append(source,start,i)
    runtime.step(start+timedelta(seconds=1))
    assert runtime.cursor==6  # Future commit is deferred, not discarded.
    runtime.step(start+timedelta(seconds=3))
    assert runtime.cursor==9
    assert [r['received_at'] for r in runtime.rows][-1]==(start+timedelta(seconds=2)).isoformat()


@pytest.mark.parametrize('change',['boot','source'])
def test_unapproved_boot_and_source_fail_closed(tmp_path,change):
    start=datetime(2026,11,10,tzinfo=timezone.utc)
    source=tmp_path/'journal'; journal(source); append(source,start,0)
    runtime=JournalRuntime(tmp_path/'business',tmp_path/'checkpoints',start,source)
    runtime.step(start)
    append(source,start,1,boot='other' if change=='boot' else 'mqtt-boot',source='hardware' if change=='source' else 'simulation')
    with pytest.raises(ValueError): runtime.step(start+timedelta(seconds=1))
    assert runtime.cursor==3

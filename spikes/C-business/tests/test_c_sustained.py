"""Bounded accelerated simulation, not an overnight wall-clock soak."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from online import Simulation


def test_six_minute_simulated_run_stays_bounded_and_reopens(tmp_path):
    start=datetime(2026,11,10,tzinfo=timezone.utc)
    runtime=Simulation(tmp_path/'business',tmp_path/'checkpoints',start)
    windows=0
    for second in range(361):
        if runtime.step(start+timedelta(seconds=second)):
            windows+=1
        assert len(runtime.rows)<=543
    assert windows>=60
    with runtime.water.connection() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT count(*) FROM transitions').fetchone()[0]==db.execute('SELECT count(*) FROM outbox').fetchone()[0]
        assert not db.execute("SELECT device_id,event_type FROM events WHERE lifecycle='OPEN' GROUP BY device_id,event_type HAVING count(*)>1").fetchall()
    from checkpoint import restore
    last=runtime.queries.read('experiment','demo-trial',now=(start+timedelta(seconds=360)).isoformat())
    assert restore(last['asset_refs'][0])['feature_window']
    restarted=Simulation(tmp_path/'business',tmp_path/'checkpoints',start+timedelta(seconds=361))
    restarted.step(start+timedelta(seconds=361))
    with restarted.water.connection() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

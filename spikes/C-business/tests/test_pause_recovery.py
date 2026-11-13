from test_c_sustained import Simulation, datetime, timedelta, timezone
from projections import Unavailable
import pytest


def test_long_pause_expires_snapshot_and_resume_does_not_backfill(tmp_path):
    start=datetime(2026,11,13,tzinfo=timezone.utc)
    runtime=Simulation(tmp_path/'db',tmp_path/'checkpoints',start)
    for second in range(41):runtime.step(start+timedelta(seconds=second))
    runtime.queries.read('live','demo01',now=(start+timedelta(seconds=40)).isoformat())
    resumed=start+timedelta(seconds=300)
    with pytest.raises(Unavailable):runtime.queries.read('live','demo01',now=resumed.isoformat())
    before=runtime.sequence
    runtime.step(resumed)
    assert runtime.sequence==before+1
    assert not [row for row in runtime.rows if start+timedelta(seconds=40)<datetime.fromisoformat(row['received_at'])<resumed]
    for second in range(301,336):runtime.step(start+timedelta(seconds=second))
    live=runtime.queries.read('live','demo01',now=(start+timedelta(seconds=335)).isoformat())
    assert datetime.fromisoformat(live['captured_at'].replace('Z','+00:00'))>=resumed

def test_one_publication_computes_saved_and_verified_features_only_once_each(tmp_path,monkeypatch):
    import checkpoint
    original=checkpoint.compute;calls=[]
    def counted(*args,**kwargs):
        calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(checkpoint,'compute',counted)
    start=datetime(2026,11,13,tzinfo=timezone.utc)
    runtime=Simulation(tmp_path/'db',tmp_path/'checkpoints',start)
    for second in range(33):runtime.step(start+timedelta(seconds=second))
    assert len(calls)==2  # save plus independent replay verification; later gates reuse verified content.

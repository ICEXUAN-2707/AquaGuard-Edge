"""Real SQLite SQLITE_FULL using a per-connection page quota, not filling disk."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'spikes/C-business/tests'))
from test_water import WaterService, ingest, rows


def test_sqlite_full_rolls_back_event_evidence_and_recovers(tmp_path,monkeypatch):
    service=WaterService(tmp_path/'full.sqlite')
    with service.connection() as db:
        db.execute('CREATE TABLE quota_probe(body BLOB)')
        db.execute('CREATE TRIGGER exhaust_quota AFTER INSERT ON water_inputs BEGIN INSERT INTO quota_probe VALUES(zeroblob(1048576)); END')
        pages=db.execute('PRAGMA page_count').fetchone()[0]
    connection=service.connection
    @contextmanager
    def limited():
        with connection() as db:
            db.execute(f'PRAGMA max_page_count={pages+4}')
            yield db
    before=rows(service)
    with monkeypatch.context() as patch:
        patch.setattr(service,'connection',limited)
        with pytest.raises(sqlite3.OperationalError) as caught:
            ingest(service,0)
        assert caught.value.sqlite_errorcode==sqlite3.SQLITE_FULL
    assert rows(service)==before
    with connection() as db:
        db.execute('DROP TRIGGER exhaust_quota')
    assert ingest(service,0)['event']['version']==1
    assert rows(service)[:4]==(1,1,1,1)

import importlib.util
from pathlib import Path
import sqlite3
import pytest
spec=importlib.util.spec_from_file_location('mqtt_status',Path(__file__).resolve().parents[2]/'scripts/mqtt_capacity_snapshot.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_missing_database_is_not_created(tmp_path):
    with pytest.raises(sqlite3.OperationalError):module.snapshot(tmp_path/'journal',tmp_path/'business')
    assert not (tmp_path/'business').exists()

def test_backlog_counts_only_unconsumed_eligible_attempts(tmp_path):
    journal=tmp_path/'journal';business=tmp_path/'business'
    with sqlite3.connect(journal) as db:
        db.executescript('CREATE TABLE observations(id);CREATE TABLE rejected(id);CREATE TABLE attempts(number,classification);')
        db.executemany('INSERT INTO attempts VALUES (?,?)',[(1,'new'),(2,'duplicate'),(3,'new'),(4,'out_of_order')])
    with sqlite3.connect(business) as db:
        db.execute('CREATE TABLE mqtt_consumer(singleton,journal,cursor)')
        db.execute('INSERT INTO mqtt_consumer VALUES (1,?,1)',(str(journal.resolve()),))
    assert module.snapshot(journal,business)['pending_eligible_attempts']==2
    with sqlite3.connect(business) as db:db.execute('UPDATE mqtt_consumer SET cursor=100')
    with pytest.raises(ValueError,match='outside journal inventory'):module.snapshot(journal,business)


def test_sidecar_inventory_preserves_main_and_sidecar_bytes(tmp_path):
    path=tmp_path/'database.sqlite';path.write_bytes(b'main')
    Path(str(path)+'-wal').write_bytes(b'wal-bytes')
    before=path.read_bytes()
    assert module.file_inventory(path)=={'main':4,'wal':9,'shm':0}
    assert path.read_bytes()==before

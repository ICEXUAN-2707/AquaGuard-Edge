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

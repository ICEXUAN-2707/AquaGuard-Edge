import importlib.util
from pathlib import Path
import sqlite3
import pytest

spec=importlib.util.spec_from_file_location('endurance',Path(__file__).resolve().parents[2]/'scripts/runtime_endurance.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_read_only_database_snapshot_preserves_missing_and_detects_corruption(tmp_path):
    path=tmp_path/'business.sqlite'
    assert module.database_snapshot(path)=={'available':False}
    assert not path.exists()
    path.write_bytes(b'not a sqlite file')
    with pytest.raises(sqlite3.DatabaseError):module.database_snapshot(path,True)

def test_growth_ignores_unavailable_memory_and_uses_actual_elapsed():
    assert module.growth([{'elapsed_sec':0,'rss_bytes':None}],'rss_bytes') is None
    assert module.growth([{'elapsed_sec':10,'rss_bytes':100},{'elapsed_sec':70,'rss_bytes':200}],'rss_bytes')==6000

def test_host_suspend_is_not_confused_with_awake_scheduling_gap():
    before={'uptime_seconds':100,'awake_seconds':80}
    assert module.suspend_delta(before,{'uptime_seconds':160,'awake_seconds':140})==0
    assert module.suspend_delta(before,{'uptime_seconds':160,'awake_seconds':90})==50
    assert module.suspend_delta(None,before) is None

def test_process_tree_memory_does_not_hide_unavailable_child(monkeypatch):
    monkeypatch.setattr(module,'process_tree',lambda pid:[10,11])
    monkeypatch.setattr(module,'memory_bytes',lambda pid:100 if pid==10 else None)
    assert module.tree_memory(10)=={'rss_bytes':None,'process_count':2}
    monkeypatch.setattr(module,'memory_bytes',lambda pid:100)
    assert module.tree_memory(10)=={'rss_bytes':200,'process_count':2}

def test_storage_includes_wal_and_checkpoints_not_logs(tmp_path):
    (tmp_path/'business.sqlite').write_bytes(b'a'*10)
    (tmp_path/'business.sqlite-wal').write_bytes(b'a'*5)
    folder=tmp_path/'business.sqlite.checkpoints';folder.mkdir()
    (folder/'snapshot.json').write_bytes(b'a'*7)
    (tmp_path/'service.log').write_bytes(b'a'*100)
    assert module.storage_snapshot(tmp_path)=={'sqlite_bytes':15,'checkpoint_bytes':7,'checkpoint_files':1}

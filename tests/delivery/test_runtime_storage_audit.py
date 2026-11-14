import importlib.util
import json
from pathlib import Path
import sqlite3
import pytest

spec=importlib.util.spec_from_file_location('storage_audit',Path(__file__).resolve().parents[2]/'scripts/audit_runtime_storage.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_inventory_protects_explicit_refs_and_never_authorizes_deletion(tmp_path):
    folder=tmp_path/'checkpoints';folder.mkdir()
    used=folder/'used.json';used.write_text('{}')
    unused=folder/'other.json';unused.write_text('{}')
    missing=folder/'missing.json'
    path=tmp_path/'business.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE "odd table" (body TEXT)')
        db.execute('INSERT INTO "odd table" VALUES (?)',(json.dumps({'nested':{'asset_refs':[str(used),str(missing),'relative.json']}}),))
    before=path.read_bytes()
    result=module.audit(path,folder)
    assert result['referenced_present']==1 and result['referenced_missing']==1
    assert result['no_reference_observed']==1 and result['outside_or_relative_references']==1
    assert result['deletion_authorized'] is False
    assert path.read_bytes()==before and unused.exists() and used.exists()

def test_missing_database_is_not_created(tmp_path):
    path=tmp_path/'missing.sqlite'
    with pytest.raises(sqlite3.OperationalError):module.audit(path,tmp_path)
    assert not path.exists()

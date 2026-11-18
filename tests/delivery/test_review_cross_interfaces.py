import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]

def test_supervisor_runs_read_only_inventory_without_promoting_acceptance(tmp_path):
    db=tmp_path/'business.sqlite';cp=tmp_path/'checkpoints';cp.mkdir()
    connection=sqlite3.connect(db)
    connection.execute('CREATE TABLE state(body TEXT)');connection.execute('INSERT INTO state VALUES(?)',(json.dumps({'state_checkpoint_ref':str((cp/'one.json').resolve())}),));connection.commit();connection.close()
    (cp/'one.json').write_text('{}');before=db.read_bytes()
    output=tmp_path/'owned'
    command=[sys.executable,str(ROOT/'scripts/supervise_endurance.py'),'--directory',str(output),'--script',str(ROOT/'scripts/audit_runtime_storage.py'),'--seconds','10','--','--db',str(db),'--checkpoints',str(cp)]
    value=subprocess.run(command,capture_output=True,text=True,timeout=20)
    assert value.returncode==0,value.stderr
    receipt=json.loads(Path(str(output)+'.supervisor.json').read_text())
    inventory=json.loads(Path(str(output)+'.supervisor.log').read_text())
    assert not receipt['acceptance_passed'] and not inventory['deletion_authorized']
    assert inventory['referenced_present']==1 and db.read_bytes()==before

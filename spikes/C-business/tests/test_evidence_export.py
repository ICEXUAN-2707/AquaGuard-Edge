import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_evidence import export


def test_export_omits_secrets_and_preserves_existing_package(tmp_path):
    source=tmp_path/'run';source.mkdir()
    (source/'cleanup.json').write_text(json.dumps([dict(exit_confirmed=True)]))
    (source/'result.json').write_text('{"status":"PASS"}')
    (source/'.env').write_text('private-test-value')
    (source/'edge.log').write_text('private-test-value')
    target=tmp_path/'evidence.zip'
    export(source,target)
    before=target.read_bytes()
    with ZipFile(target) as archive:
        assert '.env' not in archive.namelist() and 'edge.log' not in archive.namelist()
        assert 'EXPORT_MANIFEST.json' in archive.namelist()
    with pytest.raises(FileExistsError):
        export(source,target)
    assert target.read_bytes()==before


def test_export_rejects_unconfirmed_ownership(tmp_path):
    (tmp_path/'cleanup.json').write_text(json.dumps([dict(exit_confirmed=False)]))
    with pytest.raises(ValueError,match='cleanup required'):
        export(tmp_path,tmp_path/'bad.zip')
    assert not (tmp_path/'bad.zip').exists()

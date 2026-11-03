import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
from import_b import import_artifacts,prepare
from projections import Projections,Unavailable


def artifacts():
    def read(path):
        return json.loads((ROOT/path).read_text(encoding="utf-8"))
    return (read("spikes/SP-03/evidence/r06_windows.json")["windows"],
            read("spikes/SP-03-features/evidence/r07_feature_windows.json"),
            read("spikes/SP-04/evidence/r03_assessments.json"))


def test_actual_b_artifacts_preserve_historical_time_and_do_not_create_events(tmp_path):
    windows,features,assessments=artifacts()
    path=tmp_path/"b.sqlite"
    assert import_artifacts(path,windows,features,assessments,ttl_seconds=30)==2
    queries=Projections(path)
    latest=max(windows,key=lambda w:w["window_end"])
    value=queries.read("assessment","demo",now=latest["published_at"])
    assert value["assessment"]["window_id"]==latest["window_id"]
    assert value["safety_signals"]==[]
    with pytest.raises(Unavailable):
        queries.read("assessment","demo",now="2026-11-03T00:00:00Z")
    with queries.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==0
    with pytest.raises(FileExistsError):
        import_artifacts(path,windows,features,assessments,ttl_seconds=30)


def test_b_wrong_device_rejected_before_creating_database(tmp_path):
    windows,features,assessments=artifacts()
    assessments[0]["device_id"]="wrong"
    path=tmp_path/"b.sqlite"
    with pytest.raises(ValueError,match="device"):
        import_artifacts(path,windows,features,assessments,ttl_seconds=30)
    assert not path.exists()


def test_b_missing_window_rejected():
    windows,features,assessments=artifacts()
    with pytest.raises(ValueError,match="sets"):
        prepare(windows[:-1],features,assessments)

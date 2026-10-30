import importlib.util
from pathlib import Path
import json
import pytest
from pydantic import ValidationError

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sp03_replay", BASE / "src/replay.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rows():
    return [json.loads(s) for s in (BASE / "data/synthetic.jsonl").read_text(encoding="utf-8-sig").splitlines()]


def test_expected_order_and_time_degradation():
    result = module.replay(rows())
    expected = json.loads((BASE / "data/expected.json").read_text(encoding="utf-8-sig"))
    assert [r["observation"]["observation_id"] for r in result] == expected["arrival_order"]
    assert [r["observation"]["observation_id"] for r in result if r["degraded_time"]] == expected["degraded_ids"]
    assert result[-1]["observation"]["event_time"] is None
    assert result[-1]["effective_time"] == result[-1]["virtual_time"]


def test_input_permutation_is_reproducible():
    assert module.replay(rows()) == module.replay(list(reversed(rows())))


def test_unknown_is_preserved():
    result = module.replay(rows())
    assert result[-1]["observation"]["value"]["present"] is None


def test_invalid_payload_rejected():
    data = rows()
    data[0]["value"] = {"wet": False}
    with pytest.raises(ValidationError):
        module.replay(data)


def test_duplicate_identity_rejected():
    data = rows()
    with pytest.raises(ValueError, match="duplicate"):
        module.replay(data + [data[0]])

def test_postprocessed_quality_rejected_at_replay_ingress():
    data=rows()
    data[0]['quality']='late'
    with pytest.raises(ValueError,match='raw observation quality'):
        module.replay(data)

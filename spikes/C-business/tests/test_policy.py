import importlib.util
import json
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("c_business_policy", ROOT / "spikes/C-business/policy.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
EX = json.loads((ROOT / "reference/reference_02/contracts/examples.json").read_text(encoding="utf-8"))
T = datetime(2026, 11, 2, tzinfo=timezone.utc)


def signal(**changes):
    row = dict(EX["SafetySignal"])
    row.update(observed_at=T.isoformat(), **changes)
    return row


def run(row, current=None, **kwargs):
    if kwargs.get("dry_since") is not None:
        kwargs.setdefault("previous_dry_at", kwargs["dry_since"])
    return m.evaluate(row, current, now=T, policy=m.Policy(10, 2), **kwargs)


def test_wet_creates_candidate_immediately_and_ack_preserves_physical_state():
    assert run(signal(value=True)).create_event
    event = dict(EX["SafetyEvent"], physical_status="ACTIVE", lifecycle="OPEN")
    result = m.acknowledge(event)
    assert result["physical_status"] == "ACTIVE"
    assert result["lifecycle"] == "OPEN"
    assert result["ack_status"] == "ACKNOWLEDGED"
    assert not run(signal(value=True), event).create_event


@pytest.mark.parametrize("quality", ["UNKNOWN", "INVALID", "STALE"])
def test_unavailable_false_cannot_clear(quality):
    result = run(signal(value=False, quality=quality), dry_since=T-timedelta(seconds=5))
    assert result.physical_status == "UNKNOWN" and result.dry_since is None


def test_stale_and_future():
    row = signal(value=False)
    row["observed_at"] = (T-timedelta(seconds=11)).isoformat()
    assert run(row).physical_status == "UNKNOWN"
    row["observed_at"] = (T+timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match="future"):
        run(row)


def test_explicit_dry_confirmation_boundary():
    assert run(signal(value=False)).physical_status == "UNKNOWN"
    assert run(signal(value=False), dry_since=T-timedelta(seconds=1)).physical_status == "UNKNOWN"
    assert run(signal(value=False), dry_since=T-timedelta(seconds=2)).physical_status == "CLEARED"


def test_device_and_signal_type_are_checked():
    with pytest.raises(ValueError, match="matching"):
        run(signal(device_id="different"), EX["SafetyEvent"])
    with pytest.raises(ValueError, match="unsupported"):
        run(signal(signal_type="OTHER"))


def test_dry_gap_restarts_confirmation():
    result = run(signal(value=False), dry_since=T-timedelta(seconds=20))
    assert result.physical_status == "UNKNOWN"
    assert result.dry_since == T


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True])
def test_bad_policy(value):
    with pytest.raises(ValueError):
        m.Policy(value, 2)

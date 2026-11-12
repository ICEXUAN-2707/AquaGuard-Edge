"""The frozen manifest must carry operation-based labels and stay frozen."""

from pathlib import Path

import pytest

from experiment.manifest import (
    expand_trials,
    load_manifest,
    manifest_sha256,
    read_frozen_digest,
    validate_manifest,
)

from experiment_testlib import manifest_copy, scenario

DIGEST = Path(__file__).resolve().parents[1] / "experiment" / "scenarios_v1.sha256"


def test_frozen_digest_matches_checked_in_manifest():
    manifest = load_manifest()
    assert read_frozen_digest(DIGEST) == manifest_sha256(manifest)


def test_scenario_and_trial_counts_and_disjoint_split():
    manifest = load_manifest()
    trials = expand_trials(manifest)
    assert len(manifest["scenarios"]) == 17
    assert len(trials) == 34
    train = {trial["trial_id"] for trial in trials if trial["split"] == "train"}
    evaluate = {trial["trial_id"] for trial in trials if trial["split"] == "eval"}
    assert len(train) == len(evaluate) == 17
    assert train.isdisjoint(evaluate)


def test_labels_follow_declared_operation_timeline():
    """Recompute every expectation from the operation, without the rule engine."""
    manifest = load_manifest()
    decision = manifest["decision_window_end_sec"]
    threshold = manifest["window"]["flow_threshold"]
    for item in manifest["scenarios"]:
        presence = item["operation"]["presence"]
        present = _value_at(presence, "present", decision)
        flow = _value_at(item["operation"]["flow"], "lpm", decision)
        if item["expected"] == "candidate":
            assert present is False, item["scenario_id"]
            assert flow > threshold, item["scenario_id"]
            assert item["onset_sec"] == _absence_start(presence, decision), item["scenario_id"]
        elif item["expected"] == "no_candidate":
            assert present is True or flow <= threshold, item["scenario_id"]
        else:
            assert item["anomaly"] != "none", item["scenario_id"]


def test_required_scenario_families_are_present():
    manifest = load_manifest()
    ids = {item["scenario_id"] for item in manifest["scenarios"]}
    assert {
        "presence_miss",
        "attended_wet",
        "static_present",
        "transient_brief",
        "intermittent_flow",
        "presence_stop",
        "flow_stop",
        "invalid_presence",
        "slow_presence",
        "late_presence",
        "restart",
        "async_sources",
        "duplicates",
    } <= ids
    wet = scenario(manifest, "attended_wet")["operation"]["water"]
    assert any(segment["wet"] is True for segment in wet)


def test_manifest_rejects_regex_derived_or_contradictory_labels():
    spec = manifest_copy()
    item = scenario(spec, "attended")
    item["truth"] = "positive"
    item["expected"] = "candidate"
    item["onset_sec"] = 10
    with pytest.raises(ValueError):
        validate_manifest(spec)


def test_manifest_rejects_onset_that_does_not_match_operation():
    spec = manifest_copy()
    scenario(spec, "left_10")["onset_sec"] = 25
    with pytest.raises(ValueError):
        validate_manifest(spec)


def test_manifest_rejects_unknown_expectation_without_documented_limitation():
    spec = manifest_copy()
    item = scenario(spec, "idle")
    item["truth"] = "negative"
    item["expected"] = "unknown"
    item["anomaly"] = "none"
    with pytest.raises(ValueError):
        validate_manifest(spec)


def test_manifest_rejects_duplicate_scenario_id():
    spec = manifest_copy()
    spec["scenarios"].append(dict(spec["scenarios"][0]))
    with pytest.raises(ValueError):
        validate_manifest(spec)


def test_manifest_keys_are_frozen():
    spec = manifest_copy()
    spec["unexpected"] = 1
    with pytest.raises(ValueError):
        validate_manifest(spec)


def _value_at(segments: list[dict], key: str, instant: float):
    for segment in segments:
        if segment["from"] <= instant < segment["to"]:
            return segment[key]
    if instant == segments[-1]["to"]:
        return segments[-1][key]
    raise AssertionError(f"operation does not cover {instant}")


def _absence_start(segments: list[dict], instant: float) -> float | None:
    for index in range(len(segments) - 1, -1, -1):
        segment = segments[index]
        if not segment["from"] <= instant < segment["to"]:
            continue
        if segment["present"] is not False:
            return None
        start = segment["from"]
        previous = index - 1
        while previous >= 0 and segments[previous]["present"] is False:
            start = segments[previous]["from"]
            previous -= 1
        return start
    raise AssertionError(f"operation does not cover {instant}")

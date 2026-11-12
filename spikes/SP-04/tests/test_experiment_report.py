"""End-to-end report artifacts and their stable handoff fields."""

import json
import hashlib

import pytest

from experiment.ml import load_model
from experiment.report import safety_section
from experiment.run import run_experiment


def test_full_report_artifacts_and_contract(tmp_path):
    output = tmp_path / "out"
    workdir = tmp_path / "work"
    report = run_experiment(output=output, workdir=workdir)

    for name in ("report.json", "trial_index.json", "metrics.md", "model_card.md", "reproduce.txt", "scenarios_v1.json"):
        assert (output / name).is_file(), name
    assert (output / "model" / "c3-model.json").is_file()

    assert hashlib.sha256((output / "model" / "c3-model.json").read_bytes()).hexdigest() == report["model"]["sha256"]

    assert report["scope"] == "synthetic_prototype_only"
    assert report["manifest"]["trials"] == 34
    assert len(report["trials"]) == 34
    split = report["dataset"]["split"]
    assert len(split["train"]) == len(split["eval"]) == 17
    assert set(split["train"]).isdisjoint(split["eval"])

    assert report["online_offline"]["windows_compared"] == 136
    assert report["online_offline"]["mismatches"] == []
    assert report["online_offline"]["windows_equal"] == 136

    assert report["fallback_check"]["missing_model"]["matches_c2"] == 17
    assert report["fallback_check"]["version_mismatch"]["matches_c2"] == 17

    safety = report["safety_independence"]
    assert safety["model_excludes_water"] is True
    assert safety["water_contact_trials"]
    assert all(case["water_contact"] is True for case in safety["water_contact_trials"])

    for record in report["trials"]:
        assert record["windows"]
        for window in record["windows"]:
            assert set(window["methods"]) == {
                "C0_threshold_flow",
                "C1_instant_multisource",
                "C2_temporal_rules",
                "C3_lightweight_ml_shadow",
            }
            assert window["online_offline"]["window_equal"] is True

    assert report["indistinguishable"]
    assert all(case["scenario_id"] == "presence_miss" for case in report["indistinguishable"])
    assert any(case["tag"] == "FALSE_POSITIVE" for case in report["failures"])
    assert any(case["tag"] == "DECIDED_WITHOUT_EVIDENCE" for case in report["failures"])

    model = load_model(output / "model" / "c3-model.json")
    assert model["model_version"] == report["model"]["model_version"]
    assert report["model"]["training"]["samples"] == 10
    assert set(report["metric_definitions"]) >= {"tp", "fp", "recall", "rejection_rate", "detection_delay_sec"}

    index = json.loads((output / "trial_index.json").read_text(encoding="utf-8"))
    assert len(index) == 34
    assert all("method_outputs" in item for item in index)


def test_report_is_deterministic_across_runs(tmp_path):
    output = tmp_path / "out"
    first = run_experiment(output=output, workdir=tmp_path / "work1")
    first_bytes = (output / "report.json").read_bytes()
    second = run_experiment(output=output, workdir=tmp_path / "work2")
    assert first == second
    assert (output / "report.json").read_bytes() == first_bytes


def test_report_can_run_on_a_scenario_subset(tmp_path):
    report = run_experiment(
        output=tmp_path / "out",
        workdir=tmp_path / "work",
        scenario_ids=["idle", "attended", "left_10", "left_20"],
    )
    assert len(report["trials"]) == 8
    assert report["dataset"]["split"]["train"] and report["dataset"]["split"]["eval"]


def test_report_rejects_unknown_scenario(tmp_path):
    with pytest.raises(ValueError):
        run_experiment(output=tmp_path / "out", workdir=tmp_path / "work", scenario_ids=["does-not-exist"])


def test_safety_section_requires_decision_window_flag():
    record = {
        "trial_id": "x",
        "split": "train",
        "decision_window_end_sec": 35,
        "windows": [
            {
                "window_end_sec": 30,
                "features": {"water_contact": True, "water_contact_sec": 5.0},
                "c2_assessment": {"situation": "ATTENDED_FLOW"},
            }
        ],
        "methods": {},
    }
    # No window at the decision point means the trial is not a safety sample yet.
    assert safety_section([record], {"feature_names": [], "excluded_features": []})["water_contact_trials"] == []

"""C0-C3 adapters, aggregation and the fallback contract."""

from datetime import datetime, timedelta

import pytest

from experiment import methods, ml
from experiment.config import MODEL_FEATURE_NAMES
from experiment_testlib import comparison, window_at


def _now(window: dict) -> datetime:
    return datetime.fromisoformat(window["window_end"].replace("Z", "+00:00")) + timedelta(seconds=2)


def _samples():
    base = {name: 0.0 for name in MODEL_FEATURE_NAMES}
    rows = []
    labels = []
    for occupied, absence, label in ((1.0, 0.0, 0), (0.9, 0.0, 0), (0.5, 15.0, 1), (0.2, 25.0, 1)):
        item = dict(base, presence_occupied_ratio=occupied, absence_after_flow_sec=absence, data_coverage_ratio=1.0)
        rows.append(item)
        labels.append(label)
    return rows, labels


def _model():
    samples, labels = _samples()
    return ml.train(samples, labels, metadata={"source": "unit-test", "samples": len(samples), "positives": sum(labels), "trial_ids": [], "manifest_sha256": "test", "feature_version": ml.FEATURE_VERSION, "decision_window_end_sec": 35})


def test_threshold_and_instant_baselines_on_the_same_window(tmp_path):
    _, attended = comparison("attended", tmp_path)
    window = window_at(attended, 35)["window"]
    assert methods.c0_threshold(window, min_flow_coverage=0.8)["value"] is True
    assert methods.c1_instant(window, min_flow_coverage=0.8, min_presence_coverage=0.8)["value"] is False


def test_temporal_rule_rejects_transient_absence_while_instant_rule_fires(tmp_path):
    _, transient = comparison("transient_brief", tmp_path)
    window = window_at(transient, 30)
    c1 = methods.c1_instant(window["window"], min_flow_coverage=0.8, min_presence_coverage=0.8)
    c2 = methods.c2_rules(window["assessment"])
    assert c1["value"] is True
    assert c2["value"] is None
    decision = methods.aggregate([c1, methods.c2_rules(window_at(transient, 35)["assessment"])], [30, 35], 35)
    assert decision["value"] is True


def test_c1_abstains_when_presence_is_unknown(tmp_path):
    _, stopped = comparison("presence_stop", tmp_path)
    window = window_at(stopped, 35)["window"]
    prediction = methods.c1_instant(window, min_flow_coverage=0.8, min_presence_coverage=0.8)
    assert prediction["value"] is None
    assert prediction["reason"] in {"PRESENCE_COVERAGE_LOW", "PRESENCE_UNKNOWN"}


def test_aggregation_requires_a_real_decision():
    assert methods.aggregate([{"value": None}, {"value": None}], [30, 35], 35)["value"] is None
    assert methods.aggregate([{"value": False}, {"value": None}], [30, 35], 35)["value"] is False
    assert methods.aggregate([{"value": None}, {"value": True}], [30, 35], 35)["first_end_sec"] == 35
    with pytest.raises(ValueError):
        methods.aggregate([{"value": True}], [40], 35)


def test_c3_missing_model_falls_back_to_rules(tmp_path):
    _, left = comparison("left_10", tmp_path)
    window = window_at(left, 35)
    c2 = methods.c2_rules(window["assessment"])
    result = methods.c3_shadow(
        window["feature_window"],
        checkpoint_root=left["checkpoint_root"],
        now=_now(window["window"]),
        rules_prediction=c2,
        model_path=None,
    )
    assert result["fallback"] is True and result["mode"] == "fallback"
    assert result["value"] == c2["value"]
    assert result["reason"] == "FALLBACK_MODEL_MISSING"


def test_c3_shadow_never_touches_water_contact(tmp_path):
    model = _model()
    path = tmp_path / "model.json"
    ml.write_model(path, model)
    _, wet = comparison("attended_wet", tmp_path)
    window = window_at(wet, 35)
    c2 = methods.c2_rules(window["assessment"])
    result = methods.c3_shadow(
        window["feature_window"],
        checkpoint_root=wet["checkpoint_root"],
        now=_now(window["window"]),
        rules_prediction=c2,
        model_path=path,
    )
    assert result["shadow"] is True and result["mode"] == "ml"
    assert result["model_version"] == model["model_version"]
    assert result["observed_safety"]["water_contact"] is True
    assert "water_contact" not in model["feature_names"]
    assert window["features"]["water_contact"] is True


def test_c3_abstains_on_degraded_evidence_instead_of_guessing(tmp_path):
    model = _model()
    path = tmp_path / "model.json"
    ml.write_model(path, model)
    _, slow = comparison("slow_presence", tmp_path)
    window = window_at(slow, 35)
    result = methods.c3_shadow(
        window["feature_window"],
        checkpoint_root=slow["checkpoint_root"],
        now=_now(window["window"]),
        rules_prediction=methods.c2_rules(window["assessment"]),
        model_path=path,
    )
    assert result["value"] is None
    assert result["reason"] == "GATE_QUALITY_DEGRADED"

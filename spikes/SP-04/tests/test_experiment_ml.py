"""C3 model: training, persistence, loading and fallback error codes."""

import json

import pytest

from experiment import ml
from experiment.config import EXCLUDED_MODEL_FEATURES, MODEL_FEATURE_NAMES


def _sample(**overrides):
    base = {name: 0.0 for name in MODEL_FEATURE_NAMES}
    base.update({"presence_occupied_ratio": 1.0, "data_coverage_ratio": 1.0})
    base.update(overrides)
    return base


def _train():
    samples = [
        _sample(presence_occupied_ratio=1.0, absence_after_flow_sec=0.0),
        _sample(presence_occupied_ratio=0.9, absence_after_flow_sec=0.0),
        _sample(presence_occupied_ratio=0.4, absence_after_flow_sec=15.0),
        _sample(presence_occupied_ratio=0.2, absence_after_flow_sec=25.0),
    ]
    labels = [0, 0, 1, 1]
    return ml.train(
        samples,
        labels,
        metadata={
            "manifest_sha256": "unit-test",
            "trial_ids": ["a", "b", "c", "d"],
            "samples": 4,
            "positives": 2,
            "feature_version": ml.FEATURE_VERSION,
            "decision_window_end_sec": 35,
            "source": "unit-test",
        },
    )


def _depth(node):
    return 1 if node["leaf"] else 1 + max(_depth(node["left"]), _depth(node["right"]))


def test_tree_trains_predicts_and_respects_depth():
    model = _train()
    assert model["model_version"].startswith("c3-decision-tree-v1-")
    assert model["model_version"].endswith(model["content_sha256"][:12])
    assert _depth(model["tree"]) <= 2
    value, score, reason = ml.predict(model, _sample(presence_occupied_ratio=0.3, absence_after_flow_sec=20.0))
    assert (value, reason) == (True, "ML_INFERENCE")
    assert 0 <= score <= 1
    assert ml.predict(model, _sample())[0] is False


def test_training_is_deterministic():
    first = _train()
    second = _train()
    assert first["model_version"] == second["model_version"]
    assert first["tree"] == second["tree"]


def test_write_and_load_roundtrip(tmp_path):
    model = _train()
    path = tmp_path / "model.json"
    digest = ml.write_model(path, model)
    assert len(digest) == 64
    loaded = ml.load_model(path)
    assert loaded["model_version"] == model["model_version"]
    assert ml.predict(loaded, _sample(presence_occupied_ratio=0.3, absence_after_flow_sec=20.0))[0] is True


def test_missing_model_reports_missing(tmp_path):
    with pytest.raises(ml.ModelUnavailable) as error:
        ml.load_model(tmp_path / "absent.json")
    assert error.value.code == "MODEL_MISSING"
    with pytest.raises(ml.ModelUnavailable) as error:
        ml.load_model(None)
    assert error.value.code == "MODEL_MISSING"


def test_feature_version_mismatch_reports_version_mismatch(tmp_path):
    model = _train()
    model["feature_version"] = "other-feature-version"
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model), encoding="utf-8")
    with pytest.raises(ml.ModelUnavailable) as error:
        ml.load_model(path)
    assert error.value.code == "MODEL_VERSION_MISMATCH"


def test_corrupted_model_content_is_rejected(tmp_path):
    model = _train()
    model["tree"]["threshold"] = 0.5
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model), encoding="utf-8")
    with pytest.raises(ml.ModelUnavailable) as error:
        ml.load_model(path)
    assert error.value.code == "MODEL_CORRUPT"


def test_model_must_not_use_water_contact():
    features = _sample(water_contact=True, water_contact_sec=15.0)
    assert set(MODEL_FEATURE_NAMES).isdisjoint(EXCLUDED_MODEL_FEATURES)
    with pytest.raises(ValueError):
        ml.feature_vector(features, names=tuple(MODEL_FEATURE_NAMES) + ("water_contact",))


def test_incomplete_feature_vector_abstains():
    features = _sample()
    features["absence_after_flow_sec"] = None
    assert ml.feature_vector(features) is None


def test_training_rejects_too_few_or_inconsistent_samples():
    with pytest.raises(ValueError):
        ml.train([_sample(), _sample()], [0, 1], metadata={})
    with pytest.raises(ValueError):
        ml.train([_sample(), _sample(), _sample(), _sample()], [0, 1, 2, 1], metadata={})

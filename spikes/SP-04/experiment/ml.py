"""Minimal C3 decision tree: train, persist, load and shadow inference.

This is deliberately a small, dependency-free CART tree. It is not meant to
beat the rules; it exists so the experiment can actually execute a trainable,
loadable and auditable model. The feature list excludes water contact so the
model can never learn to mask the fast water-contact safety signal.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from checkpoint import FEATURE_VERSION

from experiment.config import (
    EXCLUDED_MODEL_FEATURES,
    MODEL_FAMILY,
    MODEL_FEATURE_NAMES,
    MODEL_FORMAT,
)
from experiment.manifest import canonical, sha256_bytes

DEFAULT_HYPERPARAMETERS = {
    "max_depth": 2,
    "min_samples_leaf": 2,
    "criterion": "gini",
    "tie_break": "positive",
}


class ModelUnavailable(Exception):
    """Raised when a shadow model cannot be used and the caller must fall back."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def feature_vector(features: dict, names: tuple[str, ...] = MODEL_FEATURE_NAMES) -> dict | None:
    """Project the DTO feature dictionary onto the model input vector.

    Returns ``None`` when a needed feature is missing; the caller must then
    abstain instead of imputing a value.
    """
    if set(names) & set(EXCLUDED_MODEL_FEATURES):
        raise ValueError("model features must not include water contact")
    vector: dict[str, float] = {}
    for name in names:
        value = features.get(name)
        if value is None:
            return None
        if isinstance(value, bool):
            value = float(value)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        vector[name] = float(value)
    return vector


def _gini(positives: int, total: int) -> float:
    if total <= 0:
        return 0.0
    positive = positives / total
    return 2.0 * positive * (1.0 - positive)


def _leaf(labels: list[int], indices: list[int]) -> dict:
    positives = sum(labels[index] for index in indices)
    total = len(indices)
    return {
        "leaf": True,
        "samples": total,
        "positives": positives,
        "score": positives / total,
        "value": 1 if positives * 2 >= total else 0,
    }


def _best_split(
    samples: list[dict],
    labels: list[int],
    indices: list[int],
    feature_names: tuple[str, ...],
    min_samples_leaf: int,
) -> dict | None:
    total = len(indices)
    positives = sum(labels[index] for index in indices)
    best = None
    for feature in feature_names:
        values = sorted({samples[index][feature] for index in indices})
        for left, right in zip(values, values[1:]):
            threshold = (left + right) / 2.0
            left_indices = [index for index in indices if samples[index][feature] <= threshold]
            right_indices = [index for index in indices if samples[index][feature] > threshold]
            if len(left_indices) < min_samples_leaf or len(right_indices) < min_samples_leaf:
                continue
            left_positives = sum(labels[index] for index in left_indices)
            right_positives = positives - left_positives
            impurity = (
                len(left_indices) / total * _gini(left_positives, len(left_indices))
                + len(right_indices) / total * _gini(right_positives, len(right_indices))
            )
            if best is None or impurity < best["impurity"] - 1e-12:
                best = {
                    "feature": feature,
                    "threshold": threshold,
                    "left": left_indices,
                    "right": right_indices,
                    "impurity": impurity,
                }
    return best


def _build(
    samples: list[dict],
    labels: list[int],
    indices: list[int],
    feature_names: tuple[str, ...],
    *,
    depth: int,
    max_depth: int,
    min_samples_leaf: int,
) -> dict:
    positives = sum(labels[index] for index in indices)
    if depth >= max_depth or len(indices) < 2 * min_samples_leaf or positives in (0, len(indices)):
        return _leaf(labels, indices)
    split = _best_split(samples, labels, indices, feature_names, min_samples_leaf)
    if split is None:
        return _leaf(labels, indices)
    node = {
        "leaf": False,
        "feature": split["feature"],
        "threshold": split["threshold"],
        "samples": len(indices),
        "impurity": round(split["impurity"], 12),
    }
    node["left"] = _build(
        samples, labels, split["left"], feature_names,
        depth=depth + 1, max_depth=max_depth, min_samples_leaf=min_samples_leaf,
    )
    node["right"] = _build(
        samples, labels, split["right"], feature_names,
        depth=depth + 1, max_depth=max_depth, min_samples_leaf=min_samples_leaf,
    )
    return node


def train(
    samples: list[dict],
    labels: list[int],
    *,
    metadata: dict,
    hyperparameters: dict | None = None,
) -> dict:
    """Fit the tree and return the complete, content-addressed model payload."""
    hyperparameters = dict(DEFAULT_HYPERPARAMETERS if hyperparameters is None else hyperparameters)
    if set(hyperparameters) != set(DEFAULT_HYPERPARAMETERS):
        raise ValueError("hyperparameter keys mismatch")
    max_depth, min_leaf = hyperparameters["max_depth"], hyperparameters["min_samples_leaf"]
    if isinstance(max_depth, bool) or not 1 <= max_depth <= 10:
        raise ValueError("max_depth must be 1..10")
    if isinstance(min_leaf, bool) or not 1 <= min_leaf <= 100:
        raise ValueError("min_samples_leaf must be 1..100")
    if len(samples) != len(labels) or not samples:
        raise ValueError("samples and labels must be non-empty and aligned")
    if len(samples) < 2 * min_leaf:
        raise ValueError("not enough training samples for the requested tree")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must be binary")
    vectors = [feature_vector(sample) for sample in samples]
    if any(vector is None for vector in vectors):
        raise ValueError("training samples must be complete feature vectors")
    indices = list(range(len(vectors)))
    tree = _build(
        vectors, list(labels), indices, MODEL_FEATURE_NAMES,
        depth=0, max_depth=max_depth, min_samples_leaf=min_leaf,
    )
    body = {
        "format": MODEL_FORMAT,
        "family": MODEL_FAMILY,
        "feature_version": FEATURE_VERSION,
        "feature_names": list(MODEL_FEATURE_NAMES),
        "excluded_features": list(EXCLUDED_MODEL_FEATURES),
        "hyperparameters": hyperparameters,
        "training": metadata,
        "tree": tree,
    }
    content = sha256_bytes(canonical(body))
    payload = dict(body, model_version=f"c3-{MODEL_FAMILY}-v1-{content[:12]}", content_sha256=content)
    _validate_payload(payload)
    return payload


def predict(model: dict, features: dict) -> tuple[bool | None, float | None, str]:
    vector = feature_vector(features)
    if vector is None:
        return None, None, "ML_FEATURES_INCOMPLETE"
    node = model["tree"]
    while not node["leaf"]:
        node = node["left"] if vector[node["feature"]] <= node["threshold"] else node["right"]
    return bool(node["value"]), float(node["score"]), "ML_INFERENCE"


def write_model(path: str | Path, model: dict) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(data, encoding="utf-8")
    return sha256_bytes(data.encode("utf-8"))


def _expected_content(payload: dict) -> str:
    body = {key: value for key, value in payload.items() if key not in ("model_version", "content_sha256")}
    return sha256_bytes(canonical(body))


def _validate_tree(node: object) -> None:
    if not isinstance(node, dict) or "leaf" not in node:
        raise ModelUnavailable("MODEL_CORRUPT", "tree node is malformed")
    if node["leaf"]:
        if node["value"] not in (0, 1) or not 0 <= node["score"] <= 1:
            raise ModelUnavailable("MODEL_CORRUPT", "leaf value is invalid")
        return
    if node["feature"] not in MODEL_FEATURE_NAMES:
        raise ModelUnavailable("MODEL_CORRUPT", "tree uses an unknown feature")
    if not isinstance(node["threshold"], (int, float)) or not math.isfinite(node["threshold"]):
        raise ModelUnavailable("MODEL_CORRUPT", "tree threshold is invalid")
    _validate_tree(node["left"])
    _validate_tree(node["right"])


def _validate_payload(payload: dict) -> None:
    if payload.get("format") != MODEL_FORMAT:
        raise ModelUnavailable("MODEL_UNSUPPORTED", "unsupported model format")
    if payload.get("feature_version") != FEATURE_VERSION:
        raise ModelUnavailable("MODEL_VERSION_MISMATCH", "model feature version does not match runtime")
    if list(payload.get("feature_names", [])) != list(MODEL_FEATURE_NAMES):
        raise ModelUnavailable("MODEL_VERSION_MISMATCH", "model feature list does not match runtime")
    if list(payload.get("excluded_features", [])) != list(EXCLUDED_MODEL_FEATURES):
        raise ModelUnavailable("MODEL_VERSION_MISMATCH", "model exclusion list does not match runtime")
    if not isinstance(payload.get("content_sha256"), str):
        raise ModelUnavailable("MODEL_CORRUPT", "model content digest is missing")
    if _expected_content(payload) != payload["content_sha256"]:
        raise ModelUnavailable("MODEL_CORRUPT", "model content digest mismatch")
    if payload.get("model_version") != f"c3-{MODEL_FAMILY}-v1-{payload['content_sha256'][:12]}":
        raise ModelUnavailable("MODEL_CORRUPT", "model version does not match content")
    try:
        _validate_tree(payload.get("tree"))
    except (KeyError, TypeError) as error:
        raise ModelUnavailable("MODEL_CORRUPT", f"tree structure is invalid: {error}") from error


def load_model(path: str | Path | None) -> dict:
    if path is None:
        raise ModelUnavailable("MODEL_MISSING", "no shadow model path was provided")
    path = Path(path)
    if not path.is_file():
        raise ModelUnavailable("MODEL_MISSING", f"shadow model not found: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelUnavailable("MODEL_CORRUPT", f"shadow model is not readable JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ModelUnavailable("MODEL_CORRUPT", "shadow model root must be an object")
    _validate_payload(payload)
    return payload

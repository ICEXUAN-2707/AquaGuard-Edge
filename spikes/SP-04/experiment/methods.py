"""C0, C1, C2 and shadow C3 adapters over one shared window dataset.

Every method consumes the same aligned window, the same feature window and the
same decision time. A ``None`` value always means "cannot decide from the
available evidence", never "no flow" or "nobody present".
"""

from __future__ import annotations

from experiment import ml
from experiment.config import EXPERIMENT_VERSION
from gates import gate

C0 = "C0_threshold_flow"
C1 = "C1_instant_multisource"
C2 = "C2_temporal_rules"
C3 = "C3_lightweight_ml_shadow"

METHOD_TITLES = {
    C0: "C0 流量阈值基线",
    C1: "C1 即时多源规则",
    C2: "C2 时序/上下文规则",
    C3: "C3 轻量 ML 影子推断",
}


def _prediction(value: bool | None, reason: str, **extra) -> dict:
    return dict({"value": value, "reason": reason}, **extra)


def c0_threshold(window: dict, *, min_flow_coverage: float) -> dict:
    flow = window["sensor_summary"]["flow"]
    if flow["state"] == "unknown":
        return _prediction(None, "FLOW_UNKNOWN")
    if flow["coverage_ratio"] < min_flow_coverage:
        return _prediction(None, "FLOW_COVERAGE_LOW", coverage_ratio=flow["coverage_ratio"])
    return _prediction(flow["state"] == "active", "FLOW_ACTIVE" if flow["state"] == "active" else "FLOW_INACTIVE")


def c1_instant(
    window: dict, *, min_flow_coverage: float, min_presence_coverage: float
) -> dict:
    flow = window["sensor_summary"]["flow"]
    presence = window["sensor_summary"]["presence"]
    if flow["state"] == "unknown":
        return _prediction(None, "FLOW_UNKNOWN")
    if flow["coverage_ratio"] < min_flow_coverage:
        return _prediction(None, "FLOW_COVERAGE_LOW", coverage_ratio=flow["coverage_ratio"])
    if presence["state"] == "unknown":
        return _prediction(None, "PRESENCE_UNKNOWN")
    if presence["coverage_ratio"] < min_presence_coverage:
        return _prediction(None, "PRESENCE_COVERAGE_LOW", coverage_ratio=presence["coverage_ratio"])
    if flow["state"] != "active":
        return _prediction(False, "FLOW_INACTIVE")
    return _prediction(presence["state"] == "absent", "PRESENCE_ABSENT" if presence["state"] == "absent" else "PRESENCE_PRESENT")


def c2_rules(assessment: dict) -> dict:
    situation = assessment["situation"]
    if situation == "UNKNOWN":
        return _prediction(None, assessment["reason_codes"][0] if assessment["reason_codes"] else "UNKNOWN")
    return _prediction(
        situation == "POSSIBLE_UNATTENDED_FLOW",
        situation,
        data_quality=assessment["data_quality"],
        reason_codes=assessment["reason_codes"],
    )


def c3_shadow(
    feature_window: dict,
    *,
    checkpoint_root,
    now,
    rules_prediction: dict,
    model_path,
    rule_config: dict | None = None,
) -> dict:
    try:
        model = ml.load_model(model_path)
    except ml.ModelUnavailable as error:
        # Requirement: missing or incompatible model must fall back to the rule
        # result instead of inventing an ML answer.
        return _prediction(
            rules_prediction["value"],
            f"FALLBACK_{error.code}",
            mode="fallback",
            fallback=True,
            model_version=None,
            score=None,
            shadow=True,
        )
    context = gate(feature_window, now, checkpoint_root=checkpoint_root, config=rule_config)
    if context["status"] != "READY":
        return _prediction(
            None,
            f"GATE_{context['reason']}",
            mode="ml",
            fallback=False,
            model_version=model["model_version"],
            score=None,
            shadow=True,
        )
    if context["data_quality"] != "VALID":
        # UNKNOWN-first: degraded coverage or quality never becomes an ML certainty.
        return _prediction(
            None,
            "GATE_QUALITY_DEGRADED",
            mode="ml",
            fallback=False,
            model_version=model["model_version"],
            score=None,
            shadow=True,
        )
    value, score, reason = ml.predict(model, feature_window["features"])
    return _prediction(
        value,
        reason,
        mode="ml",
        fallback=False,
        model_version=model["model_version"],
        score=score,
        shadow=True,
        observed_safety={
            "water_contact": feature_window["features"].get("water_contact"),
            "water_contact_sec": feature_window["features"].get("water_contact_sec"),
            "model_excludes_water": True,
        },
    )


def aggregate(predictions: list[dict], window_ends_sec: list[int], decision_end_sec: int) -> dict:
    """Alarm-level aggregation: any candidate up to the decision window wins."""
    selected = [
        (prediction, end)
        for prediction, end in zip(predictions, window_ends_sec)
        if end <= decision_end_sec
    ]
    if not selected:
        raise ValueError("no window at or before the decision point")
    for prediction, end in selected:
        if prediction["value"] is True:
            return {"value": True, "first_end_sec": end, "evidence": prediction.get("reason", "CANDIDATE")}
    if any(prediction["value"] is False for prediction, _ in selected):
        return {"value": False, "first_end_sec": None, "evidence": "NO_CANDIDATE"}
    return {"value": None, "first_end_sec": None, "evidence": "ALL_WINDOWS_UNKNOWN"}


def method_definitions(manifest: dict) -> dict:
    return {
        C0: {
            "definition": "窗尾 flow.state=active 即候选；flow 未知或覆盖不足输出 UNKNOWN。",
            "inputs": ["AlignedWindow.sensor_summary.flow"],
            "threshold": manifest["window"]["flow_threshold"],
            "min_flow_coverage": manifest["min_flow_coverage"],
        },
        C1: {
            "definition": "同一窗口 flow.state=active 且 presence.state=absent 才候选；任一源未知或覆盖不足输出 UNKNOWN。",
            "inputs": ["AlignedWindow.sensor_summary.flow", "AlignedWindow.sensor_summary.presence"],
            "min_flow_coverage": manifest["min_flow_coverage"],
            "min_presence_coverage": manifest["min_presence_coverage"],
        },
        C2: {
            "definition": "现有 M5 阈值/时效/覆盖门控与时序规则；absence_after_flow_sec 达到阈值才候选，其余情况保留 UNKNOWN。",
            "inputs": ["FeatureWindow", "本地内容寻址检查点"],
            "unattended_sec": 10,
        },
        C3: {
            "definition": "在 C2 的门控和特征之上运行的轻量决策树影子推断；只记录，不替代规则结论。",
            "inputs": ["FeatureWindow.features"],
            "shadow_only": True,
            "excluded_features": list(ml.EXCLUDED_MODEL_FEATURES),
            "experiment_version": EXPERIMENT_VERSION,
        },
    }

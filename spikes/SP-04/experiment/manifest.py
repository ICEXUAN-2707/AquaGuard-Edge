"""Frozen scenario manifest: loading, structural validation and trial expansion.

Labels and expectations are written as human operation timelines. This module
never imports the rule engine, the feature engine or any classifier, so a
manifest cannot derive its own ground truth from the system under evaluation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

from experiment.config import DEFAULT_MANIFEST, MANIFEST_VERSION, GENERATOR_VERSION

SCENARIO_ID = re.compile(r"^[a-z][a-z0-9_]*$")
TRIAL_ID = re.compile(r"^[a-z][a-z0-9_]*-[a-z0-9]+-(train|eval)-[0-9]+$")
TRUTHS = {"positive", "negative", "indistinguishable"}
EXPECTATIONS = {"candidate", "no_candidate", "unknown"}
ANOMALIES = {
    "none",
    "async_sources",
    "duplicates",
    "late_presence",
    "presence_stop",
    "flow_stop",
    "invalid_presence",
    "restart",
    "slow_presence",
    "presence_miss",
}
REQUIRED_TOP = {
    "manifest_version",
    "generator_version",
    "description",
    "time_origin",
    "device_id",
    "stream_duration_sec",
    "window",
    "min_flow_coverage",
    "min_presence_coverage",
    "window_ends_sec",
    "decision_window_end_sec",
    "scenarios",
}
REQUIRED_SCENARIO = {
    "scenario_id",
    "title",
    "truth",
    "expected",
    "onset_sec",
    "anomaly",
    "presence_motion",
    "operation",
    "seeds",
    "notes",
}


def canonical(value: object) -> bytes:
    """Stable JSON bytes used for every manifest and model digest."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_sha256(manifest: dict) -> str:
    return sha256_bytes(canonical(manifest))


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict:
    path = Path(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    missing = REQUIRED_TOP - set(manifest)
    extra = set(manifest) - REQUIRED_TOP
    if missing or extra:
        raise ValueError(f"manifest keys mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    if manifest["manifest_version"] != MANIFEST_VERSION:
        raise ValueError("unsupported manifest version")
    if manifest["generator_version"] != GENERATOR_VERSION:
        raise ValueError("unsupported generator version")
    if not isinstance(manifest["description"], str) or not manifest["description"].strip():
        raise ValueError("manifest description is required")
    origin = manifest["time_origin"]
    if not isinstance(origin, str) or datetime.fromisoformat(origin).tzinfo is None:
        raise ValueError("time_origin must be an ISO timestamp with timezone")
    if not isinstance(manifest["device_id"], str) or not manifest["device_id"]:
        raise ValueError("device_id is required")

    duration = manifest["stream_duration_sec"]
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
        raise ValueError("stream_duration_sec must be a positive integer")
    window = manifest["window"]
    if not isinstance(window, dict) or set(window) != {
        "width", "step", "lateness", "ttl", "flow_threshold"
    }:
        raise ValueError("window configuration keys mismatch")
    for key in ("width", "step", "ttl", "flow_threshold"):
        value = window[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"invalid window parameter: {key}")
    lateness = window["lateness"]
    if isinstance(lateness, bool) or not isinstance(lateness, (int, float)) or not math.isfinite(lateness) or lateness < 0:
        raise ValueError("invalid window parameter: lateness")
    for key in ("min_flow_coverage", "min_presence_coverage"):
        value = manifest[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise ValueError(f"invalid coverage threshold: {key}")

    ends = manifest["window_ends_sec"]
    if not isinstance(ends, list) or not ends or any(
        isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in ends
    ):
        raise ValueError("window_ends_sec must be positive integers")
    if ends != sorted(set(ends)):
        raise ValueError("window_ends_sec must be strictly ascending")
    if ends[-1] > duration:
        raise ValueError("window_ends_sec must not exceed stream duration")
    decision = manifest["decision_window_end_sec"]
    if decision not in ends:
        raise ValueError("decision window must be one of window_ends_sec")

    scenarios = manifest["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be a non-empty list")
    seen = set()
    for scenario in scenarios:
        _validate_scenario(scenario, manifest)
        if scenario["scenario_id"] in seen:
            raise ValueError(f"duplicate scenario_id: {scenario['scenario_id']}")
        seen.add(scenario["scenario_id"])

    trials = expand_trials(manifest)
    if len({trial["trial_id"] for trial in trials}) != len(trials):
        raise ValueError("duplicate trial_id")
    if {trial["split"] for trial in trials} != {"train", "eval"}:
        raise ValueError("both train and eval trials are required")


def _validate_scenario(scenario: object, manifest: dict) -> None:
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be a JSON object")
    missing = REQUIRED_SCENARIO - set(scenario)
    extra = set(scenario) - REQUIRED_SCENARIO
    if missing or extra:
        raise ValueError(f"scenario keys mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    scenario_id = scenario["scenario_id"]
    if not isinstance(scenario_id, str) or not SCENARIO_ID.fullmatch(scenario_id):
        raise ValueError(f"invalid scenario_id: {scenario_id!r}")
    if not isinstance(scenario["title"], str) or not scenario["title"].strip():
        raise ValueError(f"{scenario_id}: title is required")
    if not isinstance(scenario["notes"], str) or not scenario["notes"].strip():
        raise ValueError(f"{scenario_id}: notes are required")
    truth, expected = scenario["truth"], scenario["expected"]
    if truth not in TRUTHS or expected not in EXPECTATIONS:
        raise ValueError(f"{scenario_id}: invalid truth/expected")
    if expected == "candidate" and truth != "positive":
        raise ValueError(f"{scenario_id}: candidate expectation requires positive truth")
    if expected == "no_candidate" and truth != "negative":
        raise ValueError(f"{scenario_id}: no_candidate expectation requires negative truth")
    if truth == "indistinguishable" and expected != "unknown":
        raise ValueError(f"{scenario_id}: indistinguishable trials must expect UNKNOWN")
    anomaly = scenario["anomaly"]
    if anomaly not in ANOMALIES:
        raise ValueError(f"{scenario_id}: unknown anomaly {anomaly!r}")
    if expected == "unknown" and anomaly == "none":
        raise ValueError(f"{scenario_id}: UNKNOWN expectation needs a documented evidence limitation")
    if scenario["presence_motion"] not in {"moving", "still"}:
        raise ValueError(f"{scenario_id}: presence_motion must be moving or still")

    duration = manifest["stream_duration_sec"]
    operation = scenario["operation"]
    if not isinstance(operation, dict) or set(operation) != {"flow", "water", "presence"}:
        raise ValueError(f"{scenario_id}: operation keys mismatch")
    for sensor, key, allowed in (
        ("flow", "lpm", lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0),
        ("water", "wet", lambda v: isinstance(v, bool)),
        ("presence", "present", lambda v: isinstance(v, bool)),
    ):
        segments = operation[sensor]
        if not isinstance(segments, list) or not segments:
            raise ValueError(f"{scenario_id}: {sensor} operation is required")
        cursor = 0
        for segment in segments:
            if not isinstance(segment, dict) or set(segment) != {"from", "to", key}:
                raise ValueError(f"{scenario_id}: invalid {sensor} segment")
            start, stop = segment["from"], segment["to"]
            if isinstance(start, bool) or isinstance(stop, bool) or not isinstance(start, (int, float)) or not isinstance(stop, (int, float)):
                raise ValueError(f"{scenario_id}: invalid {sensor} interval")
            if not math.isfinite(start) or not math.isfinite(stop) or start != cursor or stop <= start:
                raise ValueError(f"{scenario_id}: {sensor} segments must cover [0,{duration}] in order")
            if not allowed(segment[key]):
                raise ValueError(f"{scenario_id}: invalid {sensor} value")
            cursor = stop
        if cursor != duration:
            raise ValueError(f"{scenario_id}: {sensor} segments must end at stream duration")

    seeds = scenario["seeds"]
    if not isinstance(seeds, dict) or set(seeds) != {"train", "eval"}:
        raise ValueError(f"{scenario_id}: seeds must declare train and eval")
    for split, seed in seeds.items():
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 < seed < 2**63:
            raise ValueError(f"{scenario_id}: invalid {split} seed")
    if seeds["train"] == seeds["eval"]:
        raise ValueError(f"{scenario_id}: train and eval seeds must differ")

    decision = manifest["decision_window_end_sec"]
    flow = _value_at(operation["flow"], "lpm", decision, scenario_id)
    present = _value_at(operation["presence"], "present", decision, scenario_id)
    onset = scenario["onset_sec"]
    if expected == "candidate":
        if present or flow <= manifest["window"]["flow_threshold"]:
            raise ValueError(f"{scenario_id}: positive label needs absent presence and active flow at decision")
        if onset is None or onset != _absence_start(operation["presence"]):
            raise ValueError(f"{scenario_id}: onset_sec must equal the final absence start")
    elif expected == "no_candidate":
        if not present and flow > manifest["window"]["flow_threshold"]:
            raise ValueError(f"{scenario_id}: negative label cannot be unattended flow at decision")
        if onset is not None:
            raise ValueError(f"{scenario_id}: negative scenario must not declare onset_sec")
    if truth == "indistinguishable" and present is not True:
        raise ValueError(f"{scenario_id}: indistinguishable miss needs a physically present person")


def _value_at(segments: list[dict], key: str, instant: float, scenario_id: str):
    for segment in segments:
        if segment["from"] <= instant < segment["to"]:
            return segment[key]
    raise ValueError(f"{scenario_id}: operation does not cover t={instant}")


def _absence_start(segments: list[dict]) -> float | None:
    """Start of the last continuous absence segment (independent of any rule)."""
    last_absent = None
    for segment in segments:
        if segment["present"] is False:
            if last_absent is None or segment["from"] != last_absent["to"]:
                last_absent = dict(segment)
            else:
                last_absent["to"] = segment["to"]
        else:
            last_absent = None
    return None if last_absent is None else last_absent["from"]


def expand_trials(manifest: dict) -> list[dict]:
    """Expand the frozen scenario list into independent trials.

    One scenario contributes exactly one train trial and one eval trial. Both
    use different frozen seeds, so the split is by trial rather than by window.
    """
    trials = []
    for index, scenario in enumerate(manifest["scenarios"]):
        for split in ("train", "eval"):
            seed = scenario["seeds"][split]
            trials.append(
                {
                    "trial_id": f"{scenario['scenario_id']}-{split}-{seed}",
                    "scenario_id": scenario["scenario_id"],
                    "split": split,
                    "seed": seed,
                    "offset_sec": index * 3600,
                }
            )
    return trials


def split_of(manifest: dict) -> dict[str, list[str]]:
    splits: dict[str, list[str]] = {"train": [], "eval": []}
    for trial in expand_trials(manifest):
        splits[trial["split"]].append(trial["trial_id"])
    return splits


def write_frozen_digest(manifest: dict, path: str | Path) -> str:
    digest = manifest_sha256(manifest)
    Path(path).write_text(f"{digest}  scenarios_v1.json\n", encoding="utf-8")
    return digest


def read_frozen_digest(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    return text.split()[0]

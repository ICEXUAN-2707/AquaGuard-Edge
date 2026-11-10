"""Online stream and offline replay over the exact same observations.

The online side drives the existing injected-clock ``Stream``; the offline side
recomputes each window from the arrival-ordered history with ``align``. Both
sides then rebuild the same checkpoint, feature window and C2 assessment, which
is the evidence requested for "窗口、特征和结论可比对".
"""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import groupby
from pathlib import Path

from alignment import ALGORITHM_VERSION, align
from checkpoint import FEATURE_VERSION, save
from rules import SEMANTIC_VERSION, classify
from stream import Stream

from experiment.config import ALIGNMENT_KEYS
from experiment.generate import TrialData
from experiment.manifest import canonical, sha256_bytes


def alignment_config(manifest: dict) -> dict:
    """Full window configuration; ``align``/``save`` receive the filtered subset."""
    return dict(manifest["window"])


def _align_config(config: dict) -> dict:
    return {key: config[key] for key in ALIGNMENT_KEYS if key in config}


def config_digest(config: dict) -> str:
    return sha256_bytes(canonical(_align_config(config)))[:12]


def version_block(config: dict) -> dict:
    return {
        "alignment": f"{ALGORITHM_VERSION}-{config_digest(config)}",
        "feature": FEATURE_VERSION,
        "rules": SEMANTIC_VERSION,
        "alignment_config": _align_config(config),
    }


def _history_for_end(rows: list[dict], end: datetime, config: dict) -> list[dict]:
    """Arrival-ordered history visible at publication, including boot resets.

    Retransmitted observations are collapsed by ``observation_id`` exactly as
    the alignment stage does, because the feature engine rejects a duplicate
    identity in its history argument.
    """
    deadline = end + timedelta(seconds=config["lateness"])
    history: list[dict] = []
    seen: set[str] = set()
    boot: str | None = None
    for row in rows:
        received = datetime.fromisoformat(row["received_at"])
        if received > deadline:
            break
        if boot is not None and row["boot_id"] != boot:
            history = []
            seen = set()
        boot = row["boot_id"]
        if row["observation_id"] in seen:
            continue
        seen.add(row["observation_id"])
        history.append(row)
    return history


def online_windows(trial: TrialData, config: dict) -> tuple[dict[str, dict], list[dict]]:
    """Drive the production-shaped stream and collect published windows."""
    stream = Stream(
        trial.rows[0]["device_id"],
        trial.window_ends[0],
        step=config["step"],
        width=config["width"],
        lateness=config["lateness"],
        ttl=config["ttl"],
        flow_threshold=config["flow_threshold"],
    )
    packets: list[dict] = []
    for timestamp, group in groupby(trial.rows, key=lambda row: row["received_at"]):
        for row in group:
            packets.extend(stream.push(row))
        packets.extend(stream.advance(datetime.fromisoformat(timestamp)))
    last_received = datetime.fromisoformat(trial.rows[-1]["received_at"])
    flush = max(last_received, trial.window_ends[-1] + timedelta(seconds=config["lateness"]))
    packets.extend(stream.advance(flush))

    windows: dict[datetime, dict] = {}
    audits: list[dict] = []
    for packet in packets:
        for window in packet["windows"]:
            windows[_parse(window["window_end"])] = window
        audits.extend(packet["audit"])
    return windows, audits


def offline_windows(trial: TrialData, config: dict) -> dict[datetime, dict]:
    windows = {}
    for end in trial.window_ends:
        history = _history_for_end(trial.rows, end, config)
        window = align(history, [end], **_align_config(config))["windows"][0]
        windows[_parse(window["window_end"])] = window
    return windows


def compare_trial(trial: TrialData, config: dict, workdir: str | Path) -> dict:
    root = Path(workdir) / trial.trial_id
    online, audits = online_windows(trial, config)
    offline = offline_windows(trial, config)
    records = []
    mismatches = []
    for end, end_sec in zip(trial.window_ends, trial.window_ends_sec):
        history = _history_for_end(trial.rows, end, config)
        online_window = online.get(end)
        offline_window = offline.get(end)
        key = online_window["window_end"] if online_window else end.isoformat()
        if online_window is None or offline_window is None:
            mismatches.append({"window_end": key, "reason": "MISSING_WINDOW"})
            continue
        window_equal = online_window == offline_window
        if not window_equal:
            mismatches.append({"window_end": key, "reason": "WINDOW_MISMATCH"})

        now = end + timedelta(seconds=config["lateness"])
        online_features = save(root / "online", online_window, history, alignment_config=_align_config(config))
        offline_features = save(root / "offline", offline_window, history, alignment_config=_align_config(config))
        features_equal = (
            online_features["features"] == offline_features["features"]
            and online_features["missing_mask"] == offline_features["missing_mask"]
            and online_features["origin"] == offline_features["origin"]
        )
        if not features_equal:
            mismatches.append({"window_end": key, "reason": "FEATURE_MISMATCH"})

        online_assessment = classify(online_features, now, checkpoint_root=root / "online")
        offline_assessment = classify(offline_features, now, checkpoint_root=root / "offline")
        assessment_equal = online_assessment == offline_assessment
        if not assessment_equal:
            mismatches.append({"window_end": key, "reason": "ASSESSMENT_MISMATCH"})

        records.append(
            {
                "window_end": key,
                "window_end_sec": end_sec,
                "window": online_window,
                "feature_window": online_features,
                "features": online_features["features"],
                "missing_mask": online_features["missing_mask"],
                "origin": online_features["origin"],
                "assessment": online_assessment,
                "online_offline": {
                    "window_equal": window_equal,
                    "features_equal": features_equal,
                    "assessment_equal": assessment_equal,
                },
            }
        )
    audit_counts: dict[str, int] = {}
    for audit in audits:
        audit_counts[audit["code"]] = audit_counts.get(audit["code"], 0) + 1
    return {
        "trial_id": trial.trial_id,
        "rows": len(trial.rows),
        "audits": audit_counts,
        "audit_details": audits,
        "windows": records,
        "mismatches": mismatches,
        "equal": not mismatches,
    }


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def consistency_summary(results: list[dict]) -> dict:
    windows = [window for result in results for window in result["windows"]]
    codes: dict[str, int] = {}
    for result in results:
        for code, count in result["audits"].items():
            codes[code] = codes.get(code, 0) + count
    return {
        "trials": len(results),
        "windows_compared": len(windows),
        "windows_equal": sum(1 for window in windows if window["online_offline"]["window_equal"]),
        "features_equal": sum(1 for window in windows if window["online_offline"]["features_equal"]),
        "assessments_equal": sum(1 for window in windows if window["online_offline"]["assessment_equal"]),
        "audit_counts": codes,
        "mismatches": [mismatch for result in results for mismatch in result["mismatches"]],
    }

"""Shared helpers for the B experiment tests (not collected by pytest)."""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from experiment.generate import generate_trials
from experiment.manifest import expand_trials, load_manifest
from experiment.replay import alignment_config, compare_trial

MANIFEST = load_manifest()
CONFIG = alignment_config(MANIFEST)


def trials(scenario_ids: list[str] | None = None):
    return generate_trials(MANIFEST, scenario_ids=scenario_ids)


def trial(scenario_id: str, split: str = "train"):
    for item in generate_trials(MANIFEST, scenario_ids=[scenario_id]):
        if item.split == split:
            return item
    raise KeyError(f"{scenario_id}:{split}")


def comparison(scenario_id: str, workdir: Path, split: str = "train"):
    item = trial(scenario_id, split)
    result = compare_trial(item, CONFIG, workdir)
    result["checkpoint_root"] = str((Path(workdir) / item.trial_id / "online").resolve())
    return item, result


def window_at(result: dict, end_sec: int) -> dict:
    for window in result["windows"]:
        if window["window_end_sec"] == end_sec:
            return window
    raise KeyError(end_sec)


def scenario(spec: dict, scenario_id: str) -> dict:
    for item in spec["scenarios"]:
        if item["scenario_id"] == scenario_id:
            return item
    raise KeyError(scenario_id)


def manifest_copy() -> dict:
    import copy

    return copy.deepcopy(MANIFEST)


def split_ids() -> dict:
    result = {"train": [], "eval": []}
    for item in expand_trials(MANIFEST):
        result[item["split"]].append(item["trial_id"])
    return result

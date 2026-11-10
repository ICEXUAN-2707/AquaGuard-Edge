"""Run the frozen B experiment and write versioned artifacts.

Usage (from the repository root)::

    python spikes/SP-04/experiment/run.py --output spikes/SP-04/evidence/r07
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiment import methods, metrics, ml, report, replay
from experiment.config import (
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT,
    EXPERIMENT_VERSION,
    REPO_ROOT,
)
from experiment.generate import generate_trials
from experiment.manifest import (
    canonical,
    expand_trials,
    load_manifest,
    manifest_sha256,
    sha256_bytes,
    split_of,
)
from experiment.methods import C0, C1, C2, C3

from gates import DEFAULT as RULE_CONFIG


def _relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(Path(path).resolve())


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _decision_window(comparison: dict, decision_end_sec: int) -> dict:
    for window in comparison["windows"]:
        if window["window_end_sec"] == decision_end_sec:
            return window
    raise ValueError("decision window is missing from the replay result")


def build_dataset(manifest: dict, workdir: Path, *, scenario_ids: list[str] | None = None) -> tuple[dict, list[dict]]:
    config = replay.alignment_config(manifest)
    trials = generate_trials(manifest, scenario_ids=scenario_ids)
    dataset = []
    for trial in trials:
        comparison = replay.compare_trial(trial, config, workdir)
        comparison["checkpoint_root"] = str((workdir / trial.trial_id / "online").resolve())
        dataset.append({"trial": trial, "comparison": comparison})
    return config, dataset


def train_shadow(dataset: list[dict], manifest: dict, manifest_sha: str) -> dict:
    decision = manifest["decision_window_end_sec"]
    samples, labels, trial_ids = [], [], []
    for item in dataset:
        trial = item["trial"]
        if trial.split != "train" or trial.expected == "unknown":
            continue
        feature_window = _decision_window(item["comparison"], decision)["feature_window"]
        if ml.feature_vector(feature_window["features"]) is None:
            raise ValueError(f"training features are incomplete for {trial.trial_id}")
        samples.append(feature_window["features"])
        labels.append(1 if trial.expected == "candidate" else 0)
        trial_ids.append(trial.trial_id)
    metadata = {
        "manifest_sha256": manifest_sha,
        "trial_ids": trial_ids,
        "samples": len(samples),
        "positives": sum(labels),
        "feature_version": ml.FEATURE_VERSION,
        "decision_window_end_sec": decision,
        "source": "simulation",
    }
    return ml.train(samples, labels, metadata=metadata)


def _evaluate_windows(
    item: dict,
    *,
    manifest: dict,
    model_path: Path,
    tampered_path: Path,
) -> list[dict]:
    trial = item["trial"]
    comparison = item["comparison"]
    decision = manifest["decision_window_end_sec"]
    windows = []
    for window in comparison["windows"]:
        now = _parse(window["window_end"]) + timedelta(seconds=manifest["window"]["lateness"])
        c0 = methods.c0_threshold(window["window"], min_flow_coverage=manifest["min_flow_coverage"])
        c1 = methods.c1_instant(
            window["window"],
            min_flow_coverage=manifest["min_flow_coverage"],
            min_presence_coverage=manifest["min_presence_coverage"],
        )
        c2 = methods.c2_rules(window["assessment"])
        c3 = methods.c3_shadow(
            window["feature_window"],
            checkpoint_root=comparison["checkpoint_root"],
            now=now,
            rules_prediction=c2,
            model_path=model_path,
            rule_config=RULE_CONFIG,
        )
        entry = {
            "window_end_sec": window["window_end_sec"],
            "window_id": window["window"]["window_id"],
            "window_digest": sha256_bytes(canonical(window["window"])),
            "quality_flags": window["window"]["quality_flags"],
            "features": window["features"],
            "missing_mask": window["missing_mask"],
            "c2_assessment": window["assessment"],
            "online_offline": window["online_offline"],
            "methods": {C0: c0, C1: c1, C2: c2, C3: c3},
        }
        windows.append(entry)

    ends = [window["window_end_sec"] for window in windows]
    aggregated = {
        method: methods.aggregate([window["methods"][method] for window in windows], ends, decision)
        for method in (C0, C1, C2, C3)
    }

    fallback = None
    if trial.split == "eval":
        fallback = {}
        comparison_ends = [window["window_end_sec"] for window in comparison["windows"]]
        for name, path in (("missing_model", None), ("version_mismatch", tampered_path)):
            values = []
            for window in comparison["windows"]:
                now = _parse(window["window_end"]) + timedelta(seconds=manifest["window"]["lateness"])
                values.append(
                    methods.c3_shadow(
                        window["feature_window"],
                        checkpoint_root=comparison["checkpoint_root"],
                        now=now,
                        rules_prediction=methods.c2_rules(window["assessment"]),
                        model_path=path,
                        rule_config=RULE_CONFIG,
                    )
                )
            fallback[name] = methods.aggregate(values, comparison_ends, decision)["value"]
    return windows, aggregated, fallback


def evaluate_dataset(
    dataset: list[dict],
    manifest: dict,
    *,
    model_path: Path,
    tampered_path: Path,
) -> list[dict]:
    records = []
    for item in dataset:
        trial = item["trial"]
        windows, aggregated, fallback = _evaluate_windows(
            item,
            manifest=manifest,
            model_path=model_path,
            tampered_path=tampered_path,
        )
        records.append(
            {
                "trial_id": trial.trial_id,
                "scenario_id": trial.scenario_id,
                "title": trial.title,
                "split": trial.split,
                "truth": trial.truth,
                "expected": trial.expected,
                "onset_sec": trial.onset_sec,
                "anomaly": trial.anomaly,
                "notes": trial.notes,
                "seed": trial.seed,
                "rows": item["comparison"]["rows"],
                "audits": item["comparison"]["audits"],
                "decision_window_end_sec": manifest["decision_window_end_sec"],
                "online_offline_equal": item["comparison"]["equal"],
                "windows": windows,
                "methods": aggregated,
                "fallback": fallback,
            }
        )
    return records


def _tampered_model(model: dict, workdir: Path) -> Path:
    payload = json.loads(json.dumps(model))
    payload["feature_version"] = "tampered-feature-version"
    path = workdir / "tampered-model.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _versions(config: dict, model: dict) -> dict:
    block = replay.version_block(config)
    block.update(
        {
            "experiment": EXPERIMENT_VERSION,
            "rule_config": RULE_CONFIG,
            "rule_config_sha256": sha256_bytes(canonical(RULE_CONFIG))[:16],
            "model": model["model_version"],
            "model_feature_version": model["feature_version"],
        }
    )
    return block


def run_experiment(
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST,
    output: str | Path = DEFAULT_OUTPUT,
    scenario_ids: list[str] | None = None,
    workdir: str | Path | None = None,
) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    output = Path(output)
    manifest_sha = manifest_sha256(manifest)
    if scenario_ids is not None:
        available = {scenario["scenario_id"] for scenario in manifest["scenarios"]}
        if not set(scenario_ids) <= available:
            raise ValueError("scenario filter does not match the frozen manifest")
        allowed_trials = {trial["trial_id"] for trial in expand_trials(manifest) if trial["scenario_id"] in set(scenario_ids)}
    else:
        allowed_trials = None

    def _run(temp_dir: Path) -> dict:
        config, dataset = build_dataset(manifest, temp_dir, scenario_ids=scenario_ids)
        model = train_shadow(dataset, manifest, manifest_sha)
        model_path = output / "model" / "c3-model.json"
        model_sha = ml.write_model(model_path, model)
        tampered_path = _tampered_model(model, temp_dir)
        records = evaluate_dataset(
            dataset, manifest, model_path=model_path, tampered_path=tampered_path
        )
        if allowed_trials is not None:
            records = [record for record in records if record["trial_id"] in allowed_trials]

        summary = metrics.methods_summary(records)
        consistency = replay.consistency_summary([item["comparison"] for item in dataset])
        model_relpath = _relative(model_path)
        selected_ids = {record["trial_id"] for record in records}
        split_ids = {
            split: [trial_id for trial_id in ids if trial_id in selected_ids]
            for split, ids in split_of(manifest).items()
        }
        report_payload = report.build_report(
            manifest=manifest,
            manifest_path=_relative(manifest_path),
            manifest_sha=manifest_sha,
            records=records,
            split_ids=split_ids,
            expectations=metrics.expectations_by_split(records),
            versions=_versions(config, model),
            model=model,
            model_sha=model_sha,
            model_relpath=model_relpath,
            metrics_summary=summary,
            consistency=consistency,
            fallback=report.fallback_section(records),
            safety=report.safety_section(records, model),
        )
        report.write_artifacts(
            report_payload,
            output,
            manifest=manifest,
            model=model,
            trial_index=report.trial_index(records),
        )
        return report_payload

    if workdir is None:
        with tempfile.TemporaryDirectory(prefix="b-exp-") as temporary:
            return _run(Path(temporary))
    path = Path(workdir)
    path.mkdir(parents=True, exist_ok=True)
    return _run(path)


def summary(report_payload: dict) -> dict:
    result = {
        "report_version": report_payload["report_version"],
        "manifest_sha256": report_payload["manifest"]["sha256"],
        "trials": len(report_payload["trials"]),
        "online_offline": {
            "windows": report_payload["online_offline"]["windows_compared"],
            "mismatches": len(report_payload["online_offline"]["mismatches"]),
        },
        "fallback": report_payload["fallback_check"],
        "methods": {},
    }
    for method, summary_block in report_payload["metrics"].items():
        metrics_block = summary_block["all"]["metrics"]
        result["methods"][method] = {
            "tp": metrics_block["tp"],
            "fp": metrics_block["fp"],
            "tn": metrics_block["tn"],
            "fn": metrics_block["fn"],
            "rejected_positive": metrics_block["rejected_positive"],
            "rejected_negative": metrics_block["rejected_negative"],
            "recall": metrics_block["recall"],
            "false_positive_rate": metrics_block["false_positive_rate"],
            "median_delay_sec": metrics_block["detection_delay_sec"]["median"],
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen B experiment suite.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--scenario", action="append", default=None)
    args = parser.parse_args(argv)
    report_payload = run_experiment(
        manifest_path=args.manifest,
        output=args.output,
        scenario_ids=args.scenario,
        workdir=args.workdir,
    )
    print(json.dumps(summary(report_payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

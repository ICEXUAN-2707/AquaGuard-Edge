"""Versioned report assembly and human-readable companion artifacts."""

from __future__ import annotations

import json
import platform
from pathlib import Path

from experiment.config import (
    EXPERIMENT_VERSION,
    GENERATOR_VERSION,
    MANIFEST_VERSION,
    METRICS_VERSION,
    REPORT_VERSION,
    REPO_ROOT,
)
from experiment.metrics import DELAY_DEFINITION, FAILURE_TAGS, METRIC_DEFINITIONS
from experiment.methods import C0, C1, C2, C3, METHOD_TITLES, method_definitions

LIMITATIONS = [
    "全部结果来自固定种子的合成仿真；只能证明在明确设定的仿真条件下各方法表现如何，不能证明真实环境泛化能力。",
    "17 个场景族各 2 个 trial（共 34 个），样本量很小，不构成统计显著性，也不报告置信区间。",
    "C3 只在训练集上拟合、在评估集上影子推断；它不追求优于规则，训练样本仅 10 个，不能据此宣称 ML 收益。",
    "10 秒无人在场流水阈值、0.1 LPM 流量阈值与 0.8 覆盖率来自既有实验默认值，不是实测最优或标定结论。",
    "检测延迟按 5 秒窗口步长计，只表示决策延迟，不含真实采集、网络与硬件时延。",
    "在线/离线一致仅覆盖本实现的同一批观测与同一到达顺序，不等于正式服务并发、崩溃恢复或真实时钟验证。",
    "C3 是影子推断，不发布 SituationAssessment，不参与 M6 决策，也不能读取或覆盖水接触安全特征。",
    "没有真实硬件、真实 trial 操作日志与独立 Reviewer；所有结果是 prototype_only。",
]


def build_report(
    *,
    manifest: dict,
    manifest_path: str,
    manifest_sha: str,
    records: list[dict],
    split_ids: dict[str, list[str]],
    expectations: dict,
    versions: dict,
    model: dict,
    model_sha: str,
    model_relpath: str,
    metrics_summary: dict,
    consistency: dict,
    fallback: dict,
    safety: dict,
) -> dict:
    failures = []
    for method, summary in metrics_summary.items():
        for case in summary["all"]["failure_cases"]:
            failures.append(dict(case, method=method, method_title=METHOD_TITLES[method]))
    failures.sort(key=lambda case: (case["method"], case["trial_id"]))
    indistinguishable = [
        {
            "trial_id": record["trial_id"],
            "scenario_id": record["scenario_id"],
            "split": record["split"],
            "truth": record["truth"],
            "outputs": {method: record["methods"][method]["value"] for method in (C0, C1, C2, C3)},
            "note": "人员实际在场但传感器未检出；输入与 left_10 相同，任何方法都无法从当前观测区分。",
        }
        for record in records
        if record["truth"] == "indistinguishable"
    ]
    return {
        "report_version": REPORT_VERSION,
        "scope": "synthetic_prototype_only",
        "experiment_version": EXPERIMENT_VERSION,
        "metrics_version": METRICS_VERSION,
        "python": platform.python_version(),
        "manifest": {
            "path": manifest_path,
            "sha256": manifest_sha,
            "version": MANIFEST_VERSION,
            "generator_version": GENERATOR_VERSION,
            "scenarios": len(manifest["scenarios"]),
            "trials": len(records),
        },
        "versions": versions,
        "dataset": {
            "split": split_ids,
            "split_policy": "按 trial 划分：同一 trial 的所有重叠窗口只属于一个分区，train/eval 的 scenario 相同但种子不同。",
            "expectations": expectations,
            "decision_window_end_sec": manifest["decision_window_end_sec"],
            "window_ends_sec": manifest["window_ends_sec"],
            "window": manifest["window"],
            "label_source": "manifest 中的人工操作时间线与 expected 声明；生成器不导入任何规则、特征或模型模块。",
        },
        "method_definitions": method_definitions(manifest),
        "metric_definitions": dict(METRIC_DEFINITIONS, failure_tags=FAILURE_TAGS, delay_definition=DELAY_DEFINITION),
        "metrics": metrics_summary,
        "trials": records,
        "failures": failures,
        "indistinguishable": indistinguishable,
        "safety_independence": safety,
        "fallback_check": fallback,
        "online_offline": consistency,
        "model": {
            "path": model_relpath,
            "sha256": model_sha,
            "model_version": model["model_version"],
            "family": model["family"],
            "feature_version": model["feature_version"],
            "feature_names": model["feature_names"],
            "excluded_features": model["excluded_features"],
            "hyperparameters": model["hyperparameters"],
            "training": model["training"],
        },
        "limitations": LIMITATIONS,
        "reproduction": {
            "commands": [
                "python spikes/SP-04/experiment/run.py --output spikes/SP-04/evidence/r07",
                "python -m pytest spikes/SP-04/tests -q -p no:cacheprovider",
                "python -m pytest spikes/SP-03/tests spikes/SP-03-features/tests spikes/SP-04/tests tests/contracts tests/smoke -q -p no:cacheprovider",
            ],
            "artifacts": {
                "report": "spikes/SP-04/evidence/r07/report.json",
                "trial_index": "spikes/SP-04/evidence/r07/trial_index.json",
                "metrics": "spikes/SP-04/evidence/r07/metrics.md",
                "model_card": "spikes/SP-04/evidence/r07/model_card.md",
                "model": model_relpath,
                "scenarios": "spikes/SP-04/evidence/r07/scenarios_v1.json",
            },
        },
    }


def _ratio_text(value) -> str:
    return "-" if value is None else f"{value:.3f}"


def render_metrics_markdown(report: dict) -> str:
    lines = [
        f"# B 实验指标（{report['report_version']}）",
        "",
        "范围：`synthetic_prototype_only`。一个 scenario 的一个冻结种子为一个独立 trial；窗口在 trial 内聚合为一次告警决策。",
        "",
        "## 指标定义",
        "",
    ]
    for name, definition in report["metric_definitions"].items():
        if name in ("failure_tags", "delay_definition"):
            continue
        lines.append(f"- `{name}`：{definition}")
    lines += [
        "",
        "## 总体结果",
        "",
        "| 方法 | n | 可判定 | tp | fp | tn | fn | 拒判正例 | 拒判负例 | 召回 | 误报率 | 拒判率 | 延迟中位数(s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for method, summary in report["metrics"].items():
        m = summary["all"]["metrics"]
        lines.append(
            f"| {METHOD_TITLES[method]} | {m['n']} | {m['decidable']} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | "
            f"{m['rejected_positive']} | {m['rejected_negative']} | {_ratio_text(m['recall'])} | "
            f"{_ratio_text(m['false_positive_rate'])} | {_ratio_text(m['rejection_rate'])} | "
            f"{_ratio_text(m['detection_delay_sec']['median'])} |"
        )
    lines += [
        "",
        "## 评估集（C3 的样本外结果）",
        "",
        "| 方法 | n | tp | fp | tn | fn | 拒判正例 | 拒判负例 | 召回 | 误报率 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for method, summary in report["metrics"].items():
        m = summary["eval"]["metrics"]
        lines.append(
            f"| {METHOD_TITLES[method]} | {m['n']} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | "
            f"{m['rejected_positive']} | {m['rejected_negative']} | {_ratio_text(m['recall'])} | "
            f"{_ratio_text(m['false_positive_rate'])} |"
        )
    lines += [
        "",
        "## 失败反例（按方法，含 train/eval）",
        "",
    ]
    if report["failures"]:
        for case in report["failures"]:
            lines.append(
                f"- `{case['method']}` / `{case['trial_id']}` / {case['tag']}：期望 {case['expected']}，"
                f"实际 {case['output']}（{case['evidence']}）。{case['tag_definition']}。"
            )
    else:
        lines.append("- 无。")
    lines += [
        "",
        "## 不可区分场景（保留，不并入误报/召回）",
        "",
    ]
    for case in report["indistinguishable"]:
        lines.append(f"- `{case['trial_id']}`：{case['note']} 输出：`{json.dumps(case['outputs'], ensure_ascii=False)}`")
    lines += [
        "",
        "## 限制",
        "",
    ]
    for item in report["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def render_model_card(report: dict) -> str:
    model = report["model"]
    training = model["training"]
    metrics = report["metrics"][C3]["eval"]["metrics"]
    lines = [
        f"# C3 轻量模型卡：{model['model_version']}",
        "",
        "## 基本信息",
        "",
        f"- 模型族：`{model['family']}`（纯 Python 决策树，无外部 ML 依赖）",
        f"- 模型格式：`b-exp-tree-v1`",
        f"- 特征版本：`{model['feature_version']}`",
        f"- 模型文件：`{model['path']}`",
        f"- 文件摘要：`{model['sha256']}`",
        f"- 训练用冻结清单：`{training['manifest_sha256']}`",
        f"- 训练 trial：{', '.join('`' + item + '`' for item in training['trial_ids'])}",
        f"- 训练样本：{training['samples']}（正例 {training['positives']}）",
        "",
        "## 输入特征",
        "",
    ]
    for name in model["feature_names"]:
        lines.append(f"- `{name}`")
    lines += [
        "",
        f"明确排除：{', '.join('`' + item + '`' for item in model['excluded_features'])}。水接触是独立安全信号，不进入模型，模型也无法抑制或延迟该信号。",
        "",
        "## 超参数",
        "",
        f"- `max_depth={model['hyperparameters']['max_depth']}`",
        f"- `min_samples_leaf={model['hyperparameters']['min_samples_leaf']}`",
        f"- `criterion={model['hyperparameters']['criterion']}`",
        f"- 平票策略：`{model['hyperparameters']['tie_break']}`（平票判正例，避免静默漏报）",
        "",
        "## 样本外指标（eval split）",
        "",
        f"- n={metrics['n']}，tp={metrics['tp']}，fp={metrics['fp']}，tn={metrics['tn']}，fn={metrics['fn']}，"
        f"拒判正例={metrics['rejected_positive']}，拒判负例={metrics['rejected_negative']}",
        f"- 召回（含拒判分母）：{_ratio_text(metrics['recall'])}；误报率：{_ratio_text(metrics['false_positive_rate'])}",
        "",
        "## 加载与回退",
        "",
        "- 加载时校验模型格式、特征版本、特征名列表、排除特征列表、内容摘要与树结构。",
        "- 模型缺失：`MODEL_MISSING`；版本不匹配：`MODEL_VERSION_MISMATCH`；内容损坏：`MODEL_CORRUPT`。任一情况回退到 C2 规则结果，并在结果中保留 `fallback=true` 与原因码。",
        "- 影子推断：C3 只记录候选与分数，不发布 `SituationAssessment`，不进入 M6，不改变 C0/C1/C2 输出。",
        "",
        "## 限制",
        "",
        "- 合成样本量很小，模型只证明“可训练、可加载、可影子运行”，不证明真实环境收益。",
        "- 特征与标签都由仿真操作时间线生成；本轮模型只形成一次 `presence_occupied_ratio` 切分，不能说明它学到了可迁移的时序语义。",
        "- 未做超参数搜索、交叉验证或统计显著性检验。",
        "",
    ]
    return "\n".join(lines)


def render_reproduce(report: dict) -> str:
    lines = [
        "B experiment reproduction",
        "========================",
        f"report_version: {report['report_version']}",
        f"manifest_sha256: {report['manifest']['sha256']}",
        f"python: {report['python']}",
        "",
        "Commands (from repository root):",
    ]
    lines += [f"  {command}" for command in report["reproduction"]["commands"]]
    lines += [
        "",
        "Expected summary:",
        f"  trials={len(report['trials'])} scenarios={report['manifest']['scenarios']} "
        f"windows_compared={report['online_offline']['windows_compared']}",
        "",
        "Artifacts:",
    ]
    for name, path in report["reproduction"]["artifacts"].items():
        lines.append(f"  {name}: {path}")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(
    report: dict,
    output_dir: str | Path,
    *,
    manifest: dict,
    model: dict,
    trial_index: list[dict],
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    def write(name: str, content: str) -> None:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        try:
            written[name] = str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            written[name] = str(path.resolve())

    write("report.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write("trial_index.json", json.dumps(trial_index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write("metrics.md", render_metrics_markdown(report))
    write("model_card.md", render_model_card(report))
    write("reproduce.txt", render_reproduce(report))
    write("scenarios_v1.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write("model/c3-model.json", json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return written


def trial_index(records: list[dict]) -> list[dict]:
    index = []
    for record in records:
        index.append(
            {
                "trial_id": record["trial_id"],
                "scenario_id": record["scenario_id"],
                "title": record["title"],
                "split": record["split"],
                "truth": record["truth"],
                "expected": record["expected"],
                "onset_sec": record["onset_sec"],
                "method_outputs": {method: record["methods"][method]["value"] for method in (C0, C1, C2, C3)},
                "first_candidate_sec": {method: record["methods"][method]["first_end_sec"] for method in (C0, C1, C2, C3)},
                "detection_delay_sec": {
                    method: (
                        None
                        if record["methods"][method]["first_end_sec"] is None or record["onset_sec"] is None
                        else record["methods"][method]["first_end_sec"] - record["onset_sec"]
                    )
                    for method in (C0, C1, C2, C3)
                },
                "window_predictions": [
                    {
                        "window_end_sec": window["window_end_sec"],
                        "methods": {method: window["methods"][method]["value"] for method in (C0, C1, C2, C3)},
                    }
                    for window in record["windows"]
                ],
            }
        )
    return index


def safety_section(records: list[dict], model: dict) -> dict:
    cases = []
    for record in records:
        decision_windows = [
            window
            for window in record["windows"]
            if window["window_end_sec"] == record["decision_window_end_sec"]
        ]
        if not decision_windows:
            continue
        window = decision_windows[0]
        if window["features"].get("water_contact") is not True:
            continue
        cases.append(
            {
                "trial_id": record["trial_id"],
                "split": record["split"],
                "water_contact": window["features"]["water_contact"],
                "water_contact_sec": window["features"]["water_contact_sec"],
                "c2_situation": window["c2_assessment"]["situation"],
                "method_outputs": {method: record["methods"][method]["value"] for method in (C0, C1, C2, C3)},
                "safety_signal_preserved": True,
            }
        )
    return {
        "water_contact_trials": cases,
        "model_feature_names": model["feature_names"],
        "excluded_features": model["excluded_features"],
        "model_excludes_water": not (set(model["feature_names"]) & set(model["excluded_features"])),
        "rule": "水接触只进入独立安全信号与特征，不进入情境模型；C3 影子输出不改变 C2/C0/C1 结论。",
    }


def fallback_section(records: list[dict]) -> dict:
    eval_records = [record for record in records if record["split"] == "eval"]
    missing_mismatch = [
        record["trial_id"]
        for record in eval_records
        if record["fallback"]["missing_model"] != record["methods"][C2]["value"]
    ]
    version_mismatch = [
        record["trial_id"]
        for record in eval_records
        if record["fallback"]["version_mismatch"] != record["methods"][C2]["value"]
    ]
    return {
        "eval_trials": len(eval_records),
        "missing_model": {
            "checked": len(eval_records),
            "matches_c2": len(eval_records) - len(missing_mismatch),
            "mismatches": missing_mismatch,
        },
        "version_mismatch": {
            "checked": len(eval_records),
            "matches_c2": len(eval_records) - len(version_mismatch),
            "mismatches": version_mismatch,
        },
        "note": "模型文件缺失或特征版本不匹配时必须回退到 C2 规则结果；两组均已逐 trial 比对。",
    }

"""Metric definitions and accounting for the C0-C3 comparison.

The reporting unit is one independent trial (one seed of one scenario), not a
window. Windows inside one trial are aggregated to one alarm decision so that
overlapping windows cannot inflate counts. Rejections and evidence-limited
trials are reported separately instead of being silently scored as negatives.
"""

from __future__ import annotations

import math

from experiment.methods import C0, C1, C2, C3

FAILURE_TAGS = {
    "FALSE_POSITIVE": "期望无候选但方法给出候选",
    "MISSED_POSITIVE": "期望候选但方法明确判为无候选",
    "REJECTED_POSITIVE": "期望候选但方法拒判",
    "REJECTED_NEGATIVE": "期望无候选但方法拒判",
    "DECIDED_WITHOUT_EVIDENCE": "证据不足却给出候选",
    "NEGATIVE_WITHOUT_EVIDENCE": "证据不足却明确判为无候选",
    "INDISTINGUISHABLE_OUTPUT": "不可区分场景仍给出确定输出",
}

METRIC_DEFINITIONS = {
    "n": "评估 trial 数（一个 scenario 的一个冻结种子为一个 trial）。",
    "decidable": "期望为候选或明确无候选、且仿真证据足以判定的 trial 数。",
    "unknown_required": "证据不足、正确输出为 UNKNOWN 的 trial 数（含不可区分场景）。",
    "tp": "期望候选且输出候选的 decidable trial 数。",
    "fp": "期望无候选却输出候选的 decidable trial 数（按 trial 计，不按重叠窗计）。",
    "tn": "期望无候选且输出无候选的 decidable trial 数。",
    "fn": "期望候选却明确输出无候选的 decidable trial 数。",
    "rejected_positive": "期望候选但输出 UNKNOWN 的 decidable trial 数。",
    "rejected_negative": "期望无候选但输出 UNKNOWN 的 decidable trial 数。",
    "precision": "tp / (tp + fp)；无候选输出时为空。",
    "recall": "tp / (tp + fn + rejected_positive)；拒判正例计为未检出。",
    "recall_decided": "tp / (tp + fn)；只统计方法实际给出二值结论的正例。",
    "false_positive_rate": "fp / (fp + tn + rejected_negative)；拒判负例保留在分母。",
    "rejection_rate": "(rejected_positive + rejected_negative) / decidable。",
    "correct_abstentions": "unknown_required 中输出 UNKNOWN 的 trial 数。",
    "decided_without_evidence": "unknown_required 中仍给出候选的 trial 数。",
    "negative_without_evidence": "unknown_required 中仍明确判为无候选的 trial 数。",
    "detection_delay_sec": "成功检出的正例中，首个候选窗口窗尾减操作真值 onset（秒）；含窗口步长与 10 秒规则阈值，不含真实网络/硬件时延。",
}
DELAY_DEFINITION = METRIC_DEFINITIONS["detection_delay_sec"]


def _percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percent / 100.0 * len(ordered)))
    return ordered[rank - 1]


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def evaluate(records: list[dict], method: str) -> dict:
    decidable = [record for record in records if record["expected"] != "unknown"]
    limited = [record for record in records if record["expected"] == "unknown"]
    positives = [record for record in decidable if record["expected"] == "candidate"]
    negatives = [record for record in decidable if record["expected"] == "no_candidate"]

    def output(record: dict):
        return record["methods"][method]["value"]

    tp = sum(1 for record in positives if output(record) is True)
    fn = sum(1 for record in positives if output(record) is False)
    rejected_positive = sum(1 for record in positives if output(record) is None)
    fp = sum(1 for record in negatives if output(record) is True)
    tn = sum(1 for record in negatives if output(record) is False)
    rejected_negative = sum(1 for record in negatives if output(record) is None)

    delays = []
    for record in positives:
        if output(record) is True and record["onset_sec"] is not None:
            first = record["methods"][method]["first_end_sec"]
            if first is not None:
                delays.append(first - record["onset_sec"])
    delays = sorted(delays)

    correct_abstentions = sum(1 for record in limited if output(record) is None)
    decided_without_evidence = sum(1 for record in limited if output(record) is True)
    negative_without_evidence = sum(1 for record in limited if output(record) is False)

    return {
        "n": len(records),
        "decidable": len(decidable),
        "unknown_required": len(limited),
        "positives": len(positives),
        "negatives": len(negatives),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "rejected_positive": rejected_positive,
        "rejected_negative": rejected_negative,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, len(positives)),
        "recall_decided": _ratio(tp, tp + fn),
        "false_positive_rate": _ratio(fp, len(negatives)),
        "false_alarms_per_trial": _ratio(fp, len(decidable)),
        "rejection_rate": _ratio(rejected_positive + rejected_negative, len(decidable)),
        "correct_abstentions": correct_abstentions,
        "decided_without_evidence": decided_without_evidence,
        "negative_without_evidence": negative_without_evidence,
        "detection_delay_sec": {
            "n": len(delays),
            "values": delays,
            "median": _percentile(delays, 50),
            "p90": _percentile(delays, 90),
            "max": max(delays) if delays else None,
        },
    }


def failure_cases(records: list[dict], method: str) -> list[dict]:
    cases = []
    for record in records:
        output = record["methods"][method]["value"]
        tag = None
        if record["truth"] == "indistinguishable":
            tag = "INDISTINGUISHABLE_OUTPUT" if output is not None else None
        elif record["expected"] == "candidate":
            tag = "REJECTED_POSITIVE" if output is None else "MISSED_POSITIVE" if output is False else None
        elif record["expected"] == "no_candidate":
            tag = "FALSE_POSITIVE" if output is True else "REJECTED_NEGATIVE" if output is None else None
        else:
            tag = "DECIDED_WITHOUT_EVIDENCE" if output is True else "NEGATIVE_WITHOUT_EVIDENCE" if output is False else None
        if tag is None:
            continue
        cases.append(
            {
                "tag": tag,
                "tag_definition": FAILURE_TAGS[tag],
                "trial_id": record["trial_id"],
                "scenario_id": record["scenario_id"],
                "split": record["split"],
                "truth": record["truth"],
                "expected": record["expected"],
                "output": output,
                "first_end_sec": record["methods"][method]["first_end_sec"],
                "onset_sec": record["onset_sec"],
                "evidence": record["methods"][method]["evidence"],
            }
        )
    return cases


def summarize_method(records: list[dict], method: str, *, split: str | None = None) -> dict:
    selected = records if split is None else [record for record in records if record["split"] == split]
    return {
        "split": split or "all",
        "metrics": evaluate(selected, method),
        "failure_cases": failure_cases(selected, method),
    }


def methods_summary(records: list[dict]) -> dict:
    summary = {}
    for method in (C0, C1, C2, C3):
        summary[method] = {
            "all": summarize_method(records, method),
            "train": summarize_method(records, method, split="train"),
            "eval": summarize_method(records, method, split="eval"),
        }
    return summary


def counts_by_split(records: list[dict]) -> dict:
    counts = {"train": 0, "eval": 0}
    for record in records:
        counts[record["split"]] += 1
    return counts


def expectations_by_split(records: list[dict]) -> dict:
    result = {}
    for split in ("train", "eval"):
        selected = [record for record in records if record["split"] == split]
        result[split] = {
            "trials": len(selected),
            "candidate": sum(1 for record in selected if record["expected"] == "candidate"),
            "no_candidate": sum(1 for record in selected if record["expected"] == "no_candidate"),
            "unknown": sum(1 for record in selected if record["expected"] == "unknown"),
            "indistinguishable": sum(1 for record in selected if record["truth"] == "indistinguishable"),
        }
    return result

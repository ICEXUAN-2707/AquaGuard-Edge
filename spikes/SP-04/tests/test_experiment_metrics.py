"""Metric accounting: trial-level counting, rejection and delay definitions."""

from experiment.methods import C0, C1, C2, C3
from experiment.metrics import evaluate, failure_cases

METHOD = C2


def record(trial_id, expected, truth, split, value, *, onset=None, first=None):
    return {
        "trial_id": trial_id,
        "scenario_id": trial_id,
        "split": split,
        "truth": truth,
        "expected": expected,
        "onset_sec": onset,
        "methods": {
            C0: {"value": value, "first_end_sec": first, "evidence": "test"},
            C1: {"value": value, "first_end_sec": first, "evidence": "test"},
            C2: {"value": value, "first_end_sec": first, "evidence": "test"},
            C3: {"value": value, "first_end_sec": first, "evidence": "test"},
        },
    }


def records():
    return [
        record("pos-hit", "candidate", "positive", "train", True, onset=20, first=30),
        record("pos-rejected", "candidate", "positive", "train", None, onset=20),
        record("pos-missed", "candidate", "positive", "eval", False, onset=20),
        record("neg-fp", "no_candidate", "negative", "train", True),
        record("neg-rejected", "no_candidate", "negative", "eval", None),
        record("neg-tn", "no_candidate", "negative", "eval", False),
        record("unknown-decided", "unknown", "positive", "eval", True),
        record("unknown-abstain", "unknown", "positive", "eval", None),
        record("indistinguishable-decided", "unknown", "indistinguishable", "eval", True),
    ]


def test_counts_and_denominators():
    result = evaluate(records(), METHOD)
    assert result["n"] == 9
    assert result["decidable"] == 6
    assert result["unknown_required"] == 3
    assert (result["tp"], result["fp"], result["tn"], result["fn"]) == (1, 1, 1, 1)
    assert (result["rejected_positive"], result["rejected_negative"]) == (1, 1)
    total = sum(result[key] for key in ("tp", "fp", "tn", "fn", "rejected_positive", "rejected_negative"))
    assert total == result["decidable"]
    assert result["recall"] == 1 / 3
    assert result["recall_decided"] == 1 / 2
    assert result["false_positive_rate"] == 1 / 3
    assert result["rejection_rate"] == 2 / 6
    assert result["correct_abstentions"] == 1
    assert result["decided_without_evidence"] == 2


def test_detection_delay_is_window_aligned_from_operation_onset():
    result = evaluate(records(), METHOD)
    assert result["detection_delay_sec"]["values"] == [10]
    assert result["detection_delay_sec"]["median"] == 10
    assert result["detection_delay_sec"]["max"] == 10


def test_failure_cases_are_explicit_and_indistinguishable_is_separate():
    cases = failure_cases(records(), METHOD)
    tags = {case["trial_id"]: case["tag"] for case in cases}
    assert tags["pos-rejected"] == "REJECTED_POSITIVE"
    assert tags["pos-missed"] == "MISSED_POSITIVE"
    assert tags["neg-fp"] == "FALSE_POSITIVE"
    assert tags["neg-rejected"] == "REJECTED_NEGATIVE"
    assert tags["unknown-decided"] == "DECIDED_WITHOUT_EVIDENCE"
    assert tags["indistinguishable-decided"] == "INDISTINGUISHABLE_OUTPUT"
    assert "unknown-abstain" not in tags


def test_abstention_on_indistinguishable_is_not_a_failure():
    items = [record("indistinguishable-abstain", "unknown", "indistinguishable", "eval", None)]
    assert failure_cases(items, METHOD) == []


def test_split_filter_keeps_trials_grouped():
    result = evaluate([item for item in records() if item["split"] == "eval"], METHOD)
    assert result["n"] == 6
    assert result["decidable"] == 3
    assert result["tp"] == 0

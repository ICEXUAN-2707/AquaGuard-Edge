"""Online stream and offline replay must produce the same windows and conclusions."""

from experiment.replay import compare_trial, consistency_summary
from experiment_testlib import CONFIG, comparison, trials, window_at


def test_full_dataset_online_offline_equality(tmp_path):
    results = [compare_trial(item, CONFIG, tmp_path) for item in trials()]
    summary = consistency_summary(results)
    assert summary["mismatches"] == []
    assert summary["windows_compared"] == 136
    assert summary["windows_equal"] == summary["features_equal"] == summary["assessments_equal"] == 136
    assert summary["audit_counts"]["ARRIVED_AFTER_PUBLICATION"] == 8
    assert summary["audit_counts"]["BOOT_RESET"] == 2


def test_late_data_is_audited_and_never_rewrites_published_window(tmp_path):
    result = [item for item in trials(["late_presence"]) if item.split == "train"][0]
    compared = compare_trial(result, CONFIG, tmp_path)
    assert compared["audits"].get("ARRIVED_AFTER_PUBLICATION") == 4
    window = window_at(compared, 30)
    assert window["assessment"]["situation"] == "UNKNOWN"


def test_restart_is_audited_and_post_reset_window_has_no_old_state(tmp_path):
    result = [item for item in trials(["restart"]) if item.split == "train"][0]
    compared = compare_trial(result, CONFIG, tmp_path)
    assert compared["audits"].get("BOOT_RESET") == 1
    window = window_at(compared, 30)
    assert window["assessment"]["situation"] == "UNKNOWN"
    assert "FLOW_COVERAGE_LOW" in window["assessment"]["reason_codes"]


def test_decision_window_semantics_for_key_scenarios(tmp_path):
    _, left = comparison("left_10", tmp_path)
    assert window_at(left, 30)["features"]["absence_after_flow_sec"] == 10
    assert window_at(left, 35)["assessment"]["situation"] == "POSSIBLE_UNATTENDED_FLOW"

    _, transient = comparison("transient_brief", tmp_path)
    assert window_at(transient, 30)["assessment"]["situation"] == "UNKNOWN"
    assert window_at(transient, 35)["assessment"]["situation"] == "ATTENDED_FLOW"

    _, presence_stop = comparison("presence_stop", tmp_path)
    assert all(window["assessment"]["situation"] == "UNKNOWN" for window in presence_stop["windows"])

    _, idle = comparison("idle", tmp_path)
    assert window_at(idle, 35)["assessment"]["situation"] == "IDLE"

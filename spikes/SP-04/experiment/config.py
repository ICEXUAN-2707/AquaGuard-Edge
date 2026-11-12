"""Shared constants and import bootstrap for the B experiment package."""

from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_VERSION = "b-exp-r07-v1"
MANIFEST_VERSION = "b-exp-manifest-v1"
GENERATOR_VERSION = "b-exp-generator-v1"
METRICS_VERSION = "b-exp-metrics-v1"
REPORT_VERSION = "b-exp-report-v1"
MODEL_FORMAT = "b-exp-tree-v1"
MODEL_FAMILY = "decision-tree"

EXPERIMENT_DIR = Path(__file__).resolve().parent
SPIKE_DIR = EXPERIMENT_DIR.parent
SPIKES_DIR = SPIKE_DIR.parent
REPO_ROOT = SPIKES_DIR.parent

DEFAULT_MANIFEST = EXPERIMENT_DIR / "scenarios_v1.json"
DEFAULT_OUTPUT = SPIKE_DIR / "evidence" / "r07"
RULE_CONFIG_PATH = SPIKE_DIR / "data" / "rules_config.json"

# The existing spikes are plain script directories, not installable packages.
for _path in (
    REPO_ROOT,
    SPIKES_DIR / "SP-03" / "src",
    SPIKES_DIR / "SP-03-features" / "src",
    SPIKE_DIR / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Features consumed by C3. Water contact is intentionally absent: the ML
# shadow must never be able to mask or delay the fast water-contact signal.
MODEL_FEATURE_NAMES = (
    "flow_mean_lpm",
    "flow_max_lpm",
    "flow_active_ratio",
    "flow_streak_sec",
    "flow_change_count",
    "presence_occupied_ratio",
    "presence_transition_count",
    "absence_after_flow_sec",
    "data_coverage_ratio",
)
EXCLUDED_MODEL_FEATURES = ("water_contact", "water_contact_sec")

ALIGNMENT_KEYS = ("width", "lateness", "ttl", "flow_threshold", "ttl_by_source")

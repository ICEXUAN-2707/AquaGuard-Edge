"""B experiment package: frozen synthetic trials and C0-C3 value proof.

The package deliberately contains no new inference algorithm. It wires the
existing M3 alignment, M4 features, M5 rules and checkpoints into one
repeatable experiment and adds only the comparison pieces requested for B:
frozen operation labels, online/offline replay equality, C0-C2 baselines,
a minimal C3 decision tree and a versioned report.
"""

from .config import EXPERIMENT_VERSION

__all__ = ["EXPERIMENT_VERSION"]

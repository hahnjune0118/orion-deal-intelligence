"""Offline, leakage-aware evaluation. Authored fixtures are not model results."""

from .metrics import Metric, compute_metrics
from .runner import audit_model_inputs, run_evaluation

__all__ = ["Metric", "compute_metrics", "audit_model_inputs", "run_evaluation"]

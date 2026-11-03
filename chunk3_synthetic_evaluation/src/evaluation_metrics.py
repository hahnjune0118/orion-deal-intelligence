"""Compatibility import; avoids a second, divergent metric implementation."""
from orion.evaluation.metrics import (Metric, aggregate, compute_metrics,
                                      deterministic_test_pass_rate, event_metrics,
                                      ndcg_at_k, numeric_error)

__all__ = ["Metric", "aggregate", "compute_metrics", "deterministic_test_pass_rate",
           "event_metrics", "ndcg_at_k", "numeric_error"]

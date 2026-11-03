"""Compatibility import; canonical evaluation contracts live in orion."""
from orion.evaluation.models import (Citation, EvaluationGold, PredictedClaim,
                                     QuestionAnnotation, SystemOutput)

__all__ = ["Citation", "EvaluationGold", "PredictedClaim", "QuestionAnnotation", "SystemOutput"]

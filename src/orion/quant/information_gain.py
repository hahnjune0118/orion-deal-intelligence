"""Binary-hypothesis entropy and exhaustive answer-distribution EIG, in bits."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Annotated, Sequence

from pydantic import Field, field_validator

from orion.domain.models import StrictContract
from .bayes import posterior, probability


def entropy(p: float) -> float:
    p = probability(p)
    if p in (0.0, 1.0):
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


class AnswerLikelihood(StrictContract):
    answer: Annotated[str, Field(min_length=1)]
    likelihood_h: float
    likelihood_not_h: float

    @field_validator("likelihood_h", "likelihood_not_h", mode="before")
    @classmethod
    def validate_probability(cls, value):
        return probability(value)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value):
        if not value.strip():
            raise ValueError("answer cannot be whitespace")
        return value


@dataclass(frozen=True)
class AnswerPosterior:
    answer: str
    probability: float
    posterior: float | None
    entropy_bits: float | None


@dataclass(frozen=True)
class EIGResult:
    prior: float
    prior_entropy_bits: float
    expected_posterior_entropy_bits: float
    eig_bits: float
    answers: tuple[AnswerPosterior, ...]
    assumption_source: str
    interpretation: str = "synthetic_scenario_not_empirical"


def expected_information_gain(
    prior: float | None,
    answers: Sequence[AnswerLikelihood] | None,
    assumption_source: str | None,
) -> EIGResult | None:
    """Return null when inputs/provenance are missing; reject invalid inputs.

    Answers must be mutually exclusive and exhaustive conditional on H and on
    not-H. Zero-mass answers are retained with a null posterior and contribute
    zero expected entropy. Duplicate labels or sums other than one are invalid.
    """
    if assumption_source is not None and not isinstance(assumption_source, str):
        raise ValueError("assumption_source must be text or null")
    if prior is None or answers is None or not assumption_source or not assumption_source.strip():
        return None
    p = probability(prior, "prior")
    if isinstance(answers, (str, bytes)) or not answers:
        raise ValueError("At least one exhaustive answer is required")
    validated = tuple(AnswerLikelihood.model_validate(item.model_dump(mode="json")) for item in answers)
    if len({item.answer for item in validated}) != len(validated):
        raise ValueError("Answer labels must be unique")
    for label in ("likelihood_h", "likelihood_not_h"):
        if not math.isclose(math.fsum(getattr(item, label) for item in validated), 1.0, abs_tol=1e-12, rel_tol=0):
            raise ValueError(f"Conditional answer probabilities {label} must sum to one")
    results = []
    expected_entropy_terms = []
    for answer in validated:
        mass = p * answer.likelihood_h + (1.0 - p) * answer.likelihood_not_h
        post = posterior(p, answer.likelihood_h, answer.likelihood_not_h) if mass else None
        bits = entropy(post) if post is not None else None
        results.append(AnswerPosterior(answer.answer, mass, post, bits))
        expected_entropy_terms.append(mass * bits if bits is not None else 0.0)
    prior_entropy = entropy(p)
    expected_entropy = math.fsum(expected_entropy_terms)
    eig = prior_entropy - expected_entropy
    if eig < -1e-12 or eig > prior_entropy + 1e-12:
        raise ArithmeticError("EIG is outside its binary-entropy bounds")
    # Floating-point noise only; never use abs(EIG), which can hide a bug.
    eig = max(0.0, min(prior_entropy, eig))
    return EIGResult(p, prior_entropy, expected_entropy, eig, tuple(results), assumption_source)


def binary_eig(
    prior: float | None, sensitivity: float | None, false_positive: float | None,
    assumption_source: str | None,
) -> EIGResult | None:
    if prior is None or sensitivity is None or false_positive is None:
        return None
    p = probability(prior, "prior")
    a = probability(sensitivity, "sensitivity")
    b = probability(false_positive, "false_positive")
    return expected_information_gain(p, [
        AnswerLikelihood(answer="positive", likelihood_h=a, likelihood_not_h=b),
        AnswerLikelihood(answer="negative", likelihood_h=1.0 - a, likelihood_not_h=1.0 - b),
    ], assumption_source)


def eig_sensitivity(
    priors: Sequence[float], sensitivity: float, false_positive: float,
    assumption_source: str,
) -> list[dict]:
    """Transparent prior sensitivity; no values are generated or calibrated."""
    if not assumption_source or not assumption_source.strip():
        raise ValueError("An acknowledged assumption source is required")
    results = []
    for prior in priors:
        result = binary_eig(prior, sensitivity, false_positive, assumption_source)
        results.append({"prior": result.prior, "eig_bits": result.eig_bits,
                        "positive_posterior": result.answers[0].posterior,
                        "negative_posterior": result.answers[1].posterior})
    return results

"""Optional research ranking; never replaces scoring contract 1.0.0.

This weighted information/materiality heuristic is not EVSI. Production rank
remains ``orion.domain.scoring.rank_state``. A caller must explicitly choose
this experiment and publish the policy and assumption source with its output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Annotated, Literal, Sequence

from pydantic import Field, field_validator, model_validator

from orion.domain.models import StrictContract
from .bayes import probability

POLICY_VERSION = "research-priority-1.0.0"


class ResearchQuestion(StrictContract):
    question_id: Annotated[str, Field(min_length=1)]
    materiality: float | None
    gap: float
    obtainability: float | None
    eig_bits: float | None = None
    eig_assumption_source: str | None = None
    days: float | None = None
    external_cost_minor: Annotated[int, Field(ge=0)] | None = None
    obtainability_includes_cost_time: bool = False
    evidence_overlap: float = 0.0
    review_status: Literal["draft", "approved", "rejected"] = "draft"
    resolved: bool = False

    @field_validator("materiality", "gap", "obtainability", mode="before")
    @classmethod
    def score(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Scores must be numeric in [0, 5]")
        if not math.isfinite(value) or not 0 <= value <= 5:
            raise ValueError("Scores must be finite in [0, 5]")
        return float(value)

    @field_validator("eig_bits", "evidence_overlap", mode="before")
    @classmethod
    def bit_range(cls, value):
        return None if value is None else probability(value)

    @field_validator("days", mode="before")
    @classmethod
    def days_range(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("days must be finite and nonnegative")
        return float(value)

    @model_validator(mode="after")
    def require_eig_provenance(self):
        if self.eig_bits is not None and (not self.eig_assumption_source or not self.eig_assumption_source.strip()):
            raise ValueError("Numerical EIG requires an explicit assumption source")
        return self


class ResearchPriorityPolicy(StrictContract):
    policy_version: Literal["research-priority-1.0.0"] = POLICY_VERSION
    label: Annotated[str, Field(min_length=1)] = "balanced"
    materiality_weight: float = 0.30
    gap_weight: float = 0.25
    eig_weight: float = 0.20
    obtainability_weight: float = 0.15
    time_cost_weight: float = 0.10
    time_scale_days: float = 10.0
    cost_scale_minor: Annotated[int, Field(ge=1)] = 100000
    use_eig: bool = True

    @field_validator("materiality_weight", "gap_weight", "eig_weight", "obtainability_weight", "time_cost_weight", mode="before")
    @classmethod
    def weights(cls, value):
        return probability(value, "weight")

    @field_validator("time_scale_days", mode="before")
    @classmethod
    def positive_time_scale(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("time_scale_days must be finite and positive")
        return float(value)

    @model_validator(mode="after")
    def sum_weights(self):
        total = sum((self.materiality_weight, self.gap_weight, self.eig_weight,
                     self.obtainability_weight, self.time_cost_weight))
        if not math.isclose(total, 1.0, abs_tol=1e-12, rel_tol=0.0):
            raise ValueError("Research priority weights must sum to one")
        return self


@dataclass(frozen=True)
class ResearchPriority:
    question_id: str
    rank: int
    score: float
    components: dict[str, float | None]
    effective_weights: dict[str, float]
    novelty_multiplier: float
    provisional: bool
    reasons: tuple[str, ...]
    policy_version: str = POLICY_VERSION


def rank_research(
    questions: Sequence[ResearchQuestion],
    policy: ResearchPriorityPolicy | None = None,
) -> list[ResearchPriority]:
    """Rank only approved, unresolved questions under an explicit experiment.

    Missing materiality/obtainability use the existing core defaults 3/2 and
    set a provisional flag. Missing EIG or time/cost is omitted with disclosed
    weight renormalization. Time/cost is omitted when already included in an
    obtainability estimate, avoiding double counting that burden.
    """
    selected = ResearchPriorityPolicy.model_validate((policy or ResearchPriorityPolicy()).model_dump())
    parsed = [ResearchQuestion.model_validate(q.model_dump()) for q in questions]
    if len({q.question_id for q in parsed}) != len(parsed):
        raise ValueError("question_id values must be unique")
    raw_rows = []
    base_weights = {
        "materiality": selected.materiality_weight, "gap": selected.gap_weight,
        "eig": selected.eig_weight, "obtainability": selected.obtainability_weight,
        "time_cost": selected.time_cost_weight,
    }
    for question in parsed:
        if question.review_status != "approved" or question.resolved:
            continue
        reasons = []
        materiality = 3.0 if question.materiality is None else question.materiality
        obtainability = 2.0 if question.obtainability is None else question.obtainability
        if question.materiality is None:
            reasons.append("MATERIALITY_DEFAULT_3")
        if question.obtainability is None:
            reasons.append("OBTAINABILITY_DEFAULT_2")
        eig = question.eig_bits if selected.use_eig else None
        if eig is None:
            reasons.append("EIG_DISABLED" if not selected.use_eig else "EIG_MISSING_QUALITATIVE_FALLBACK")
        if question.obtainability_includes_cost_time:
            time_cost = None
            reasons.append("TIME_COST_ALREADY_IN_OBTAINABILITY")
        elif question.days is None or question.external_cost_minor is None:
            time_cost = None
            reasons.append("TIME_COST_MISSING")
        else:
            time_cost = 1.0 / (1.0 + question.days / selected.time_scale_days
                               + question.external_cost_minor / selected.cost_scale_minor)
        components = {"materiality": materiality / 5, "gap": question.gap / 5,
                      "eig": eig, "obtainability": obtainability / 5,
                      "time_cost": time_cost}
        active_total = sum(weight for name, weight in base_weights.items() if components[name] is not None)
        if active_total <= 0:
            raise ValueError("The policy has no positive weight on available components")
        effective = {name: (weight / active_total if components[name] is not None else 0.0)
                     for name, weight in base_weights.items()}
        novelty = 1.0 - question.evidence_overlap
        if question.evidence_overlap:
            reasons.append("EXPLICIT_EVIDENCE_OVERLAP_DISCOUNT")
        score_value = 100.0 * novelty * math.fsum(
            effective[name] * value for name, value in components.items() if value is not None
        )
        provisional = question.materiality is None or question.obtainability is None or (
            selected.use_eig and question.eig_bits is None
        ) or (time_cost is None and not question.obtainability_includes_cost_time)
        raw_rows.append((question, score_value, components, effective, novelty, provisional, tuple(reasons)))
    raw_rows.sort(key=lambda row: (-row[1], -row[2]["materiality"], -row[2]["gap"], row[0].question_id))
    return [ResearchPriority(row[0].question_id, index, row[1], row[2], row[3], row[4], row[5], row[6])
            for index, row in enumerate(raw_rows, start=1)]


def sensitivity_analysis(
    questions: Sequence[ResearchQuestion], policies: Sequence[ResearchPriorityPolicy] | None = None,
) -> dict:
    """Report alternative assumptions without choosing an 'optimal' policy."""
    variants = list(policies) if policies is not None else [
        ResearchPriorityPolicy(),
        ResearchPriorityPolicy(label="financial_materiality", materiality_weight=0.45,
                               gap_weight=0.20, eig_weight=0.15, obtainability_weight=0.10,
                               time_cost_weight=0.10),
        ResearchPriorityPolicy(label="information_first", materiality_weight=0.20,
                               gap_weight=0.20, eig_weight=0.40, obtainability_weight=0.10,
                               time_cost_weight=0.10),
        ResearchPriorityPolicy(label="no_bayesian_eig", use_eig=False),
    ]
    if not variants or len({p.label for p in variants}) != len(variants):
        raise ValueError("Sensitivity policies must be nonempty with unique labels")
    reports = []
    initial_order = None
    for policy in variants:
        ranking = rank_research(questions, policy)
        order = [row.question_id for row in ranking]
        if initial_order is None:
            initial_order = order
        old_ranks = {identifier: rank for rank, identifier in enumerate(initial_order, 1)}
        reports.append({
            "policy": policy.model_dump(), "ranking": [asdict(row) for row in ranking],
            "top3": order[:3], "rank_delta_from_first": {
                row.question_id: old_ranks[row.question_id] - row.rank for row in ranking
            },
        })
    return {"policy_version": POLICY_VERSION, "scope": "optional_research_heuristic_not_EVSI",
            "production_scoring_version": "1.0.0_unchanged", "variants": reports}

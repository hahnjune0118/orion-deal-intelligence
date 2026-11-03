"""Evaluation annotations extend, and never replace, Orion domain contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Citation(EvaluationRecord):
    document_id: str
    document_version: int = Field(ge=1)
    locator: dict[str, Any]
    quote: str = Field(min_length=1)


class PredictedClaim(EvaluationRecord):
    prediction_id: str
    matched_claim_id: str | None = None
    text: str
    factual: bool = True
    citations: list[Citation] = Field(default_factory=list)
    # Human-authored annotation, not a claim that exact quote matching proves truth.
    entailment_supported: bool | None = None


class QuestionAnnotation(EvaluationRecord):
    output_id: str
    text: str
    family_id: str | None = None
    match_reviewed: bool = False
    reviewer: str | None = None
    match_rationale: str | None = None
    target_present: bool | None = None
    artifact_present: bool | None = None
    period_present: bool | None = None
    criterion_present: bool | None = None
    financial_relevance: bool | None = None

    @model_validator(mode="after")
    def reviewed_match_has_audit(self):
        if self.match_reviewed and (not self.reviewer or not self.match_rationale):
            raise ValueError("Reviewed family mapping requires reviewer and rationale")
        return self


class SystemOutput(EvaluationRecord):
    provenance: Literal["authored-fixture", "deterministic-engine", "model-generated", "not_run"]
    status: Literal["completed", "failed", "abstained", "not_run"] = "completed"
    claims: list[PredictedClaim] = Field(default_factory=list)
    retrieved_evidence_ids: list[str] = Field(default_factory=list)
    relationships: list[tuple[str, str, str]] = Field(default_factory=list)
    contradiction_groups: list[str] = Field(default_factory=list)
    questions: list[QuestionAnnotation] = Field(default_factory=list)
    hypothesis_statuses: dict[str, str] = Field(default_factory=dict)
    posterior: dict[str, float] = Field(default_factory=dict)
    eig: dict[str, float] = Field(default_factory=dict)
    # The evaluator records, but never feeds, these audit observations to a model.
    final_approvals_without_review: int = Field(default=0, ge=0)


class EvaluationGold(EvaluationRecord):
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    relationships: list[tuple[str, str, str]] = Field(default_factory=list)
    contradiction_groups: list[str] = Field(default_factory=list)
    critical_families: list[str] = Field(default_factory=list)
    relevance: dict[str, float] = Field(default_factory=dict)
    hypothesis_statuses: dict[str, str] = Field(default_factory=dict)
    resolved_question_families: list[str] = Field(default_factory=list)
    posterior: dict[str, float] = Field(default_factory=dict)
    eig: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_gold(self):
        for key in ("claim_ids", "evidence_ids", "relationships", "contradiction_groups", "critical_families", "resolved_question_families"):
            values = getattr(self, key)
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate gold label in {key}")
        if len(self.critical_families) > 3:
            raise ValueError("A state has at most three critical families; preserve a meaningful Top-3 denominator")
        if any(value < 0 for value in self.relevance.values()):
            raise ValueError("NDCG relevance is nonnegative")
        return self

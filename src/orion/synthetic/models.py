"""Additive dataset metadata around the unchanged Orion 1.0.0 contracts.

Hypothesis and ClaimEvidence are views of binary Claim / Evidence.claim_id.
These wrappers never create a competing persistence model or alter core enums.
"""
from typing import Literal
from pydantic import Field, model_validator
from orion.domain.models import StrictContract, Document, SourceSpan, Claim, Evidence, DDQuestion

class DatasetDocument(StrictContract):
    record: Document
    title: str
    date: str
    reporting_period: str
    document_type: str
    synthetic: Literal[True] = True
    available_stage: int = Field(ge=0)
    elements: list[SourceSpan]

class Hypothesis(StrictContract):
    hypothesis_id: str
    claim: Claim
    threshold: str
    financial_driver: str
    interpretation: Literal['synthetic_scenario_not_investment_probability'] = 'synthetic_scenario_not_investment_probability'
    @model_validator(mode='after')
    def binary(self):
        if self.claim.claim_kind != 'binary_hypothesis':
            raise ValueError('Hypothesis must wrap an existing binary Claim')
        return self

class EvidenceLabel(StrictContract):
    record: Evidence
    evidence_type: str
    evidence_group_id: str
    contradiction_group: str | None
    exact_source_excerpt: str
    available_stage: int = Field(ge=0)
    world_truth_status: str
    document_visible_status: str
    rationale: str

class QuestionLabel(StrictContract):
    record: DDQuestion
    hypothesis_id: str
    question_text: str
    unresolved_assumption: str
    requested_artifact: str
    verification_criterion: str
    business_impact: str
    linked_evidence_ids: list[str]
    expected_priority: int = Field(ge=1)
    information_gain: float | None
    expected_update_behavior: str
    acceptable_question_family: str
    acceptable_alternatives: list[str]

# Canonical quantitative snapshot; do not introduce a competing belief schema.
from orion.quant.bayes import BeliefSnapshot

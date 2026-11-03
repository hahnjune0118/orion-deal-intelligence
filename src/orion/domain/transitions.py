"""Pure, versioned evidence-review transitions for contract/scoring 1.0.0.

An approval decision is supplied by the application service's trusted actor
context. This module never obtains roles from client input, performs I/O, or
claims that an exact source quotation proves the underlying assertion true.
The caller appends the audit event and persists the returned state atomically.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from .grounding import SourceResolver, ValidationMode, validate_grounding
from .models import (
    AnalystDecision, Claim, DealState, Requirement, StagedEvidenceUpdate,
    StrictContract, TransitionRow,
)
from .scoring import (
    active_evidence, build_snapshot, evaluate_requirements, rank_state,
    ranking_input_digest,
)


class TransitionError(ValueError):
    """Stable service-safe error without source text or client payloads."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


T = TypeVar("T", bound=StrictContract)


def _replace(records: Iterable[T], additions: Iterable[T]) -> list[T]:
    """Keep one current entity version; repositories retain the older versions."""
    current = {record.id: record for record in records}
    current.update({record.id: record for record in additions})
    return sorted(current.values(), key=lambda record: (record.id, record.entity_version))


def _claim_requirements(state: DealState, claim: Claim) -> list[Requirement]:
    policies = {
        requirement.key: requirement
        for question in state.dd_questions if question.claim_id == claim.id
        for requirement in question.requirements
    }
    return [policies[key] for key in claim.required_criterion_keys]


def derive_statuses(state: DealState) -> DealState:
    """Derive claim support/truth and approved-question workflow on a fresh copy.

    This helper expects referentially validated input. It does not approve drafts
    or add review decisions. Any changed persisted entity advances one version.
    """
    result = state.model_copy(deep=True)
    eligible = active_evidence(result)
    for claim in result.claims:
        requirements = _claim_requirements(result, claim)
        assessment = evaluate_requirements(result, claim.id, requirements)
        if assessment.conflict_keys:
            support = "contradicted"
        elif len(assessment.credited_keys) == len(requirements):
            support = "supported"
        elif assessment.credited_keys:
            support = "partial"
        else:
            support = "missing"

        if claim.claim_kind == "analyst_assumption":
            truth = "not_checked"
        elif assessment.conflict_keys:
            truth = "disputed"
        else:
            independent_requirements = [
                item.model_copy(update={"require_independent": True})
                for item in requirements
            ]
            independent = evaluate_requirements(result, claim.id, independent_requirements)
            explicit_verification = any(
                decision.actor_role == "reviewer" and decision.action == "approve"
                and decision.target_type == "claim" and decision.target_id == claim.id
                and decision.target_version == claim.entity_version
                for decision in result.analyst_decisions
            )
            # Evidence-update approval never substitutes for the separate,
            # version-bound claim-verification judgment.
            if (claim.truth_status == "independently_verified" and independent.resolved
                    and explicit_verification and support == claim.support_status):
                truth = "independently_verified"
            elif claim.source_span_ids or any(item.claim_id == claim.id for item in eligible):
                truth = "document_only"
            else:
                truth = "not_checked"
        if (claim.support_status, claim.truth_status) != (support, truth):
            claim.support_status = support
            claim.truth_status = truth
            claim.entity_version += 1

    for question in result.dd_questions:
        if question.review_status != "approved" or question.workflow_status in {"duplicate", "rejected"}:
            continue
        assessment = evaluate_requirements(result, question.claim_id, question.requirements)
        workflow = "resolved" if assessment.resolved else "open"
        if question.workflow_status != workflow:
            question.workflow_status = workflow
            question.entity_version += 1
    return result


def assert_current_state(
    state: DealState, *, mode: ValidationMode = "contract",
    source_resolver: SourceResolver | None = None,
) -> None:
    """Reject stale derived statuses, rank data or approval-input digests."""
    validate_grounding(state, mode=mode, source_resolver=source_resolver).raise_for_errors()
    current = derive_statuses(state)
    old_claims = {item.id: (item.support_status, item.truth_status) for item in state.claims}
    old_questions = {item.id: item.workflow_status for item in state.dd_questions}
    if (any(old_claims[item.id] != (item.support_status, item.truth_status) for item in current.claims)
            or any(old_questions[item.id] != item.workflow_status for item in current.dd_questions)):
        raise TransitionError("STALE_STATE", "Stored derived statuses do not match approved evidence.")
    snapshot = next(item for item in state.ranking_snapshots if item.id == state.head_snapshot_id)
    if snapshot.input_digest != ranking_input_digest(state):
        raise TransitionError("STALE_STATE", "Head snapshot is not bound to the current approved inputs.")
    expected = rank_state(state, mode=mode, source_resolver=source_resolver)
    # Reason wording is explanatory, while these are the reproducible values.
    def values(rows):
        return [row.model_dump(exclude={"reason_codes"}) for row in rows]
    if values(snapshot.rows) != values(expected):
        raise TransitionError("STALE_STATE", "Head snapshot ranking differs from its approved inputs.")


def apply_approved_update(
    state: DealState,
    event: StagedEvidenceUpdate,
    *,
    decision: AnalystDecision,
    snapshot_id: str,
    now: str,
    mode: ValidationMode = "contract",
    source_resolver: SourceResolver | None = None,
) -> DealState:
    """Apply one immutable reviewed update without mutating any supplied object.

    Decision/snapshot are included in the return value. Audit append and storage
    are the service's responsibility and must share the same transaction. New
    staged entities keep version one; edits carry exactly old version plus one.
    """
    state = DealState.model_validate(state.model_dump(mode="json"))
    event = StagedEvidenceUpdate.model_validate(event.model_dump(mode="json"))
    decision = AnalystDecision.model_validate(decision.model_dump(mode="json"))
    if event.base_revision != state.state_revision:
        raise TransitionError("REVISION_CONFLICT", "Approval is based on a stale revision.")
    if event.validation_status != "validated":
        raise TransitionError("SOURCE_MISMATCH", "Only validated staged updates may be approved.")
    if any(item.review_status != "draft" for item in [*event.evidence, *event.evidence_relations]):
        raise TransitionError("APPROVAL_REQUIRED", "The immutable staged update must contain reviewable draft atoms.")
    if not (
        decision.deal_id == state.deal.id == event.deal_id
        and decision.actor_role == "reviewer" and decision.action == "approve"
        and decision.target_type == "evidence_update" and decision.target_id == event.id
        and decision.target_version == 1 and decision.base_revision == state.state_revision
        and decision.decided_at == now
    ):
        raise TransitionError("APPROVAL_REQUIRED", "A matching server reviewer decision is required.")
    if any(item.target_type == "evidence_update" and item.target_id == event.id
           and item.action in {"approve", "reject"} for item in state.analyst_decisions):
        raise TransitionError("DUPLICATE_EVENT", "This immutable event was already decided.")
    assert_current_state(state, mode=mode, source_resolver=source_resolver)
    validate_grounding(state, event, mode=mode, source_resolver=source_resolver).raise_for_errors()

    existing_evidence = {item.id: item for item in state.evidence}
    for incoming in event.evidence:
        previous = existing_evidence.get(incoming.id)
        if (previous is not None and previous.review_status == "approved"
                and previous.lifecycle == "active" and previous.stance == "refutes"):
            conflict_fields = ("claim_id", "stance", "criterion_keys", "source_reliability",
                               "source_span_ids", "lifecycle")
            if any(getattr(previous, key) != getattr(incoming, key) for key in conflict_fields):
                raise TransitionError(
                    "REFERENCE_INVALID",
                    "Replacing an active refutation requires a new atom and explicit full supersession.",
                )

    result = state.model_copy(deep=True)
    for name in ("documents", "source_spans"):
        setattr(result, name, _replace(getattr(result, name), getattr(event, name)))
    result.evidence = _replace(result.evidence, [
        item.model_copy(update={"review_status": "approved"}, deep=True) for item in event.evidence
    ])
    result.evidence_relations = _replace(result.evidence_relations, [
        item.model_copy(update={"review_status": "approved"}, deep=True) for item in event.evidence_relations
    ])
    evidence_by_id = {item.id: item for item in result.evidence}
    staged_evidence_ids = {item.id for item in event.evidence}
    for relation in event.evidence_relations:
        if relation.relation_type != "supersedes":
            continue
        target = evidence_by_id[relation.to_evidence_id]
        if set(relation.scope_criterion_keys) != set(target.criterion_keys):
            raise TransitionError("REFERENCE_INVALID", "Partial replacement requires separate evidence atoms first.")
        if target.lifecycle != "superseded":
            target.lifecycle = "superseded"
            if target.id not in staged_evidence_ids:
                target.entity_version += 1

    # Preflight already checked the candidate sources/references. Derive before
    # the full promoted-state validator so a formerly verified claim can become
    # disputed when a refutation arrives. Invalid promoted spans still fail the
    # full validation below before any snapshot or storage operation.
    result = derive_statuses(result)
    validate_grounding(result, mode=mode, source_resolver=source_resolver).raise_for_errors()
    snapshot = build_snapshot(
        result, snapshot_id, now, trigger_event_id=event.id,
        mode=mode, source_resolver=source_resolver,
    )
    result.state_revision += 1
    snapshot.state_revision = result.state_revision
    result.ranking_snapshots.append(snapshot)
    result.head_snapshot_id = snapshot.id
    result.analyst_decisions.append(decision)
    validate_grounding(result, mode=mode, source_resolver=source_resolver).raise_for_errors()
    return result


def question_changes(before: DealState, after: DealState) -> list[TransitionRow]:
    """Explain actual snapshot changes, including relative moves at equal scores."""
    old_snapshot = next(item for item in before.ranking_snapshots if item.id == before.head_snapshot_id)
    new_snapshot = next(item for item in after.ranking_snapshots if item.id == after.head_snapshot_id)
    old_rows = {item.question_id: item for item in old_snapshot.rows}
    new_rows = {item.question_id: item for item in new_snapshot.rows}
    old_questions = {item.id: item for item in before.dd_questions}
    changes = []
    for question in sorted(after.dd_questions, key=lambda item: item.id):
        old_question = old_questions.get(question.id)
        old_row, new_row = old_rows.get(question.id), new_rows.get(question.id)
        before_status = old_question.workflow_status if old_question else "absent"
        if question.workflow_status == "resolved" and before_status != "resolved":
            reason = "CRITERIA_SATISFIED"
        elif before_status == "resolved" and question.workflow_status == "open":
            assessment = evaluate_requirements(after, question.claim_id, question.requirements)
            reason = "CONFLICT_REOPENED" if assessment.conflict_keys else "EVIDENCE_GAP_REOPENED"
        elif old_row and new_row and old_row.score == new_row.score and new_row.rank < old_row.rank:
            reason = "RESIDUAL_PROMOTED"
        elif old_row and new_row and old_row.score == new_row.score and new_row.rank > old_row.rank:
            reason = "RELATIVE_DEMOTED"
        elif old_row and new_row and old_row.score != new_row.score:
            reason = "SCORE_CHANGED"
        elif bool(old_row) != bool(new_row):
            reason = "RANKING_ELIGIBILITY_CHANGED"
        else:
            reason = "UNCHANGED"
        changes.append(TransitionRow(
            question_id=question.id,
            before_rank=old_row.rank if old_row else None,
            after_rank=new_row.rank if new_row else None,
            before_score=old_row.score if old_row else None,
            after_score=new_row.score if new_row else None,
            before_status=before_status, after_status=question.workflow_status, reason=reason,
        ))
    return changes

"""Independent product transitions against immutable handoff expectations."""
from pathlib import Path
import json

import pytest

from orion.demo import prepare_replay
from orion.domain.grounding import GroundingError, validate_grounding
from orion.domain.models import AnalystDecision, EvidenceRelation, StagedEvidenceUpdate
from orion.domain.scoring import build_snapshot, rank_state
from orion.domain.transitions import (
    TransitionError, apply_approved_update, assert_current_state,
    derive_statuses, question_changes,
)

pytestmark = pytest.mark.transitions
NOW = "2026-11-04T00:01:00Z"
ROOT = Path(__file__).resolve().parents[2]


def pack(case):
    prepared = prepare_replay({"case_id": case, "actions": []})
    return prepared.state, prepared.staged_event


def approve(state, event, *, suffix="test"):
    decision = AnalystDecision(
        id=f"decision_{suffix}", entity_version=1, deal_id=state.deal.id,
        actor_id="actor_server_reviewer", actor_role="reviewer",
        target_type="evidence_update", target_id=event.id, target_version=1,
        selection_digest=None, action="approve", reason="Reviewed exact synthetic scope.",
        base_revision=state.state_revision, decided_at=NOW,
    )
    return apply_approved_update(state, event, decision=decision, snapshot_id=f"snap_{suffix}", now=NOW)


def rows(state):
    return [(item.question_id, item.rank, item.gap, item.score) for item in rank_state(state)]


def reseed_for_test(state):
    """Create a coherent test seed; never used by application code."""
    state = derive_statuses(state)
    head = next(s for s in state.ranking_snapshots if s.id == state.head_snapshot_id)
    replacement = build_snapshot(state, head.id, head.created_at, trigger_event_id=head.trigger_event_id)
    state.ranking_snapshots = [replacement if item.id == head.id else item for item in state.ranking_snapshots]
    return state


@pytest.mark.parametrize("case,before_scores,after_scores", [
    ("ns", [100, 97, 89], [97, 89, 86]),
    ("cd", [100, 94, 89], [94, 89, 86]),
    ("lm", [92, 89, 84], [97, 92, 89]),
])
def test_exact_transitions_from_immutable_expected_contract(case, before_scores, after_scores):
    state, event = pack(case)
    original_state, original_event = state.model_dump(), event.model_dump()
    before_snapshot = next(item for item in state.ranking_snapshots if item.id == state.head_snapshot_id)
    base = ROOT / "spec" / ("EXAMPLES" if case == "ns" else f"DATASET_SPECS/{case}")
    expected = json.loads((base / "expected_top3_transition.json").read_text())
    result = approve(state, event)
    snapshot = result.ranking_snapshots[-1]
    assert [row.score for row in before_snapshot.rows[:3]] == before_scores
    assert [row.score for row in snapshot.rows[:3]] == after_scores
    assert snapshot.top3 == expected["after_top3"]
    assert result.state_revision == state.state_revision + 1
    actual_changes = {item.question_id: item.model_dump() for item in question_changes(state, result)}
    assert actual_changes == {item["question_id"]: item for item in expected["question_changes"]}
    actual_claims = {item.id: item for item in result.claims}
    for item in expected["claim_after"]:
        assert actual_claims[item["claim_id"]].support_status == item["support_status"]
        assert actual_claims[item["claim_id"]].truth_status == item["truth_status"]
    assert result.ranking_snapshots[0] == before_snapshot
    assert result.audit_events == state.audit_events
    assert state.model_dump() == original_state
    assert event.model_dump() == original_event
    assert_current_state(result)


def test_northstar_contract_is_not_acceptance_collection_birch_or_truth_verification():
    state, event = pack("ns")
    result = approve(state, event)
    questions = {q.id: q for q in result.dd_questions}
    assert questions["q_ns_contract_a"].workflow_status == "resolved"
    for key in ["q_ns_contract_b", "q_ns_accept_collect", "q_ns_concentration"]:
        assert questions[key].workflow_status == "open"
    assert result.claims[0].support_status == "partial"
    assert result.claims[0].truth_status == "document_only"
    assert all(e.verification_level == "document_only" for e in result.evidence)


def test_lumen_refutation_reopens_and_preserves_both_sources():
    state, event = pack("lm")
    result = approve(state, event)
    assert next(q for q in result.dd_questions if q.id == "q_lm_renewal").workflow_status == "open"
    assert {e.id: e.lifecycle for e in result.evidence} == {
        "ev_lm_initial": "active", "ev_lm_update": "active",
    }
    assert result.evidence_relations[0].relation_type == "contradicts"
    assert result.evidence_relations[0].review_status == "approved"
    assert result.claims[0].truth_status == "disputed"


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
@pytest.mark.parametrize("review", ["draft", "rejected"])
def test_unapproved_and_rejected_atoms_never_change_rank(case, review):
    state, event = pack(case)
    state.documents.extend(event.documents)
    state.source_spans.extend(event.source_spans)
    state.evidence.extend([item.model_copy(update={"review_status": review}) for item in event.evidence])
    state.evidence_relations.extend([item.model_copy(update={"review_status": review}) for item in event.evidence_relations])
    initial, _ = pack(case)
    assert rows(state) == rows(initial)
    assert derive_statuses(state).dd_questions == state.dd_questions


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_duplicate_origin_is_a_noop_on_rank(case):
    state, template = pack(case)
    event = template.model_copy(deep=True)
    event.documents = []
    event.source_spans = []
    event.evidence_relations = []
    duplicate = state.evidence[0].model_copy(deep=True)
    duplicate.id = f"ev_{case}_duplicate"
    duplicate.review_status = "draft"
    event.evidence = [duplicate]
    result = approve(state, event)
    assert rows(result) == rows(state)
    assert all(change.reason == "UNCHANGED" for change in question_changes(state, result))


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_unrelated_context_approval_does_not_change_rank(case):
    state, event = pack(case)
    event.evidence[0].stance = "context"
    event.evidence[0].criterion_keys = []
    event.evidence_relations = []
    result = approve(state, event)
    assert rows(result) == rows(state)


@pytest.mark.parametrize("status", ["invalid", "unverified"])
def test_locator_status_blocks_promotion(status):
    state, event = pack("ns")
    event.source_spans[0].locator_status = status
    with pytest.raises(GroundingError) as error:
        approve(state, event)
    assert error.value.code == "SOURCE_MISMATCH"
    assert state.state_revision == 1


@pytest.mark.parametrize("kind", ["self", "cycle", "different_claim"])
def test_invalid_relations_block_the_entire_transition(kind):
    state, event = pack("lm")
    relation = event.evidence_relations[0]
    if kind == "self":
        relation.to_evidence_id = relation.from_evidence_id
    elif kind == "cycle":
        relation.relation_type = "supersedes"
        reverse = relation.model_copy(deep=True)
        reverse.id = "rel_reverse"
        reverse.from_evidence_id, reverse.to_evidence_id = relation.to_evidence_id, relation.from_evidence_id
        event.evidence_relations.append(reverse)
    else:
        relation.scope_criterion_keys = ["labor"]
    with pytest.raises(GroundingError):
        approve(state, event)
    assert state.state_revision == 1
    assert state.claims[0].truth_status == "document_only"


def test_partial_supersession_requires_atomic_split():
    state, event = pack("lm")
    state.evidence[0].criterion_keys = ["renewal", "labor"]
    state = reseed_for_test(state)
    event.evidence_relations[0].relation_type = "supersedes"
    with pytest.raises(TransitionError) as error:
        approve(state, event)
    assert error.value.code == "REFERENCE_INVALID"
    assert state.evidence[0].lifecycle == "active"


def test_explicit_complete_supersession_can_resolve_conflict_without_deleting_history():
    state, event = pack("lm")
    conflicted = approve(state, event, suffix="conflict")
    replacement = event.model_copy(deep=True)
    replacement.id = "update_restore"
    replacement.base_revision = conflicted.state_revision
    replacement.idempotency_key = "restore_renewal"
    replacement.documents = []
    replacement.source_spans = []
    replacement.evidence = [state.evidence[0].model_copy(deep=True)]
    replacement.evidence[0].id = "ev_restore"
    replacement.evidence[0].review_status = "draft"
    replacement.evidence_relations = [EvidenceRelation(
        id="rel_restore", entity_version=1, deal_id=state.deal.id,
        from_evidence_id="ev_restore", to_evidence_id="ev_lm_update",
        relation_type="supersedes", scope_criterion_keys=["renewal"],
        review_status="draft", rationale="Reviewer approved complete atom replacement.",
    )]
    result = approve(conflicted, replacement, suffix="restore")
    assert next(q for q in result.dd_questions if q.id == "q_lm_renewal").workflow_status == "resolved"
    assert next(e for e in result.evidence if e.id == "ev_lm_update").lifecycle == "superseded"
    assert next(e for e in result.evidence if e.id == "ev_lm_update").entity_version == 2
    assert len(result.evidence_relations) == 2
    assert result.ranking_snapshots[:2] == conflicted.ranking_snapshots
    assert result.claims[0].truth_status == "document_only"
    assert_current_state(result)


def test_exact_quote_and_independent_origin_do_not_produce_verified_truth():
    state, event = pack("cd")
    event.evidence[0].criterion_keys = list(state.claims[0].required_criterion_keys)
    event.evidence[0].provenance = "independent_source"
    event.evidence[0].verification_level = "independent_check"
    event.evidence[0].independent_check_reference = "synthetic independent check reference"
    event.documents[0].source_origin = "independent"
    result = approve(state, event)
    assert result.claims[0].support_status == "supported"
    assert result.claims[0].truth_status == "document_only"
    assert result.ranking_snapshots[-1].top3 == []


@pytest.mark.parametrize("tamper", ["support", "workflow", "digest", "score"])
def test_stale_derived_state_is_rejected_instead_of_silently_repaired(tamper):
    state, event = pack("ns")
    if tamper == "support":
        state.claims[0].support_status = "supported"
    elif tamper == "workflow":
        state.dd_questions[0].workflow_status = "resolved"
    elif tamper == "digest":
        state.ranking_snapshots[0].input_digest = "0" * 64
    else:
        state.ranking_snapshots[0].rows[0].score = 99
    with pytest.raises(TransitionError) as error:
        approve(state, event)
    assert error.value.code == "STALE_STATE"


def test_stale_and_wrong_deal_decisions_are_blocked():
    state, event = pack("ns")
    event.base_revision += 1
    with pytest.raises(TransitionError) as error:
        approve(state, event)
    assert error.value.code == "REVISION_CONFLICT"
    event.base_revision -= 1
    event.deal_id = "deal_other"
    with pytest.raises(TransitionError) as error:
        approve(state, event)
    assert error.value.code == "APPROVAL_REQUIRED"


def test_current_approved_atoms_cannot_be_resubmitted_as_staged_approval():
    state, event = pack("ns")
    event.evidence[0].review_status = "approved"
    with pytest.raises(TransitionError) as error:
        approve(state, event)
    assert error.value.code == "APPROVAL_REQUIRED"


def test_refutation_of_independently_verified_claim_derives_disputed_before_validation():
    state, event = pack("lm")
    evidence = state.evidence[0]
    evidence.criterion_keys = list(state.claims[0].required_criterion_keys)
    evidence.verification_level = "independent_check"
    evidence.independent_check_reference = "synthetic independent confirmations for every criterion"
    state = derive_statuses(state)
    claim = state.claims[0]
    claim.truth_status = "independently_verified"
    claim.entity_version += 1
    state.analyst_decisions.append(AnalystDecision(
        id="decision_verified", entity_version=1, deal_id=state.deal.id,
        actor_id="actor_server_reviewer", actor_role="reviewer", target_type="claim",
        target_id=claim.id, target_version=claim.entity_version, selection_digest=None,
        action="approve", reason="Explicit reviewer verification of all synthetic conditions.",
        base_revision=state.state_revision, decided_at=NOW,
    ))
    state = reseed_for_test(state)
    assert_current_state(state)
    assert state.claims[0].truth_status == "independently_verified"
    result = approve(state, event)
    assert result.claims[0].truth_status == "disputed"
    assert result.claims[0].support_status == "contradicted"
    assert result.claims[0].entity_version == claim.entity_version + 1
    assert next(q for q in result.dd_questions if q.id == "q_lm_renewal").workflow_status == "open"
    assert_current_state(result)


@pytest.mark.parametrize("field,value", [
    ("stance", "context"), ("criterion_keys", []), ("source_reliability", None),
])
def test_active_refutation_cannot_be_erased_by_an_inplace_edit(field, value):
    state, event = pack("lm")
    event.evidence_relations = []  # Refutation itself is sufficient to preserve conflict.
    state = approve(state, event, suffix="first")
    revision = event.model_copy(deep=True)
    revision.id = "update_revise"
    revision.base_revision = state.state_revision
    revision.documents = []
    revision.source_spans = []
    revision.evidence_relations = []
    revision.evidence[0].entity_version = 2
    setattr(revision.evidence[0], field, value)
    with pytest.raises(TransitionError) as error:
        approve(state, revision, suffix="revision")
    assert error.value.code == "REFERENCE_INVALID"
    assert state.claims[0].truth_status == "disputed"


def test_active_refutation_cannot_be_rehomed_to_another_claim():
    state, event = pack("lm")
    event.evidence_relations = []
    state = approve(state, event, suffix="first")
    other = state.claims[0].model_copy(deep=True)
    other.id = "claim_other"
    other.entity_version = 1
    state.claims.append(other)
    state.theses[0].claim_ids.append(other.id)
    for question in list(state.dd_questions):
        new_question = question.model_copy(deep=True)
        new_question.id += "_other"
        new_question.claim_id = other.id
        new_question.entity_version = 1
        state.dd_questions.append(new_question)
    state = reseed_for_test(state)
    revision = event.model_copy(deep=True)
    revision.id = "update_rehome"
    revision.base_revision = state.state_revision
    revision.documents = []
    revision.source_spans = []
    revision.evidence[0].entity_version += 1
    revision.evidence[0].claim_id = other.id
    with pytest.raises(TransitionError) as error:
        approve(state, revision, suffix="rehome")
    assert error.value.code == "REFERENCE_INVALID"
    assert next(c for c in state.claims if c.id == "claim_lm").truth_status == "disputed"

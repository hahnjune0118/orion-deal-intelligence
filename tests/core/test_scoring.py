"""Independent specification examples and boundary tests for ranking.

Expected arithmetic here is chosen by hand from the published rubric. The
package QA arithmetic implementation is neither imported nor copied.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_UP, localcontext
import json
from pathlib import Path
import random

import pytest

from orion.domain.models import DealState
from orion.domain.scoring import (
    build_snapshot,
    display_decimal,
    evaluate_requirements,
    rank_state,
    ranking_input_digest,
)


ROOT = Path(__file__).resolve().parents[2]


def raw_case(case="ns"):
    return json.loads((ROOT / "src/orion/resources/demo" / case / "initial_state.json").read_text())


def state_of(raw):
    return DealState.model_validate(raw)


def row_for(state, question_id):
    return next(row for row in rank_state(state) if row.question_id == question_id)


def add_evidence(raw, key, *, review="approved", reliability=3, stance="supports",
                 independent=False, evidence_id="ev_test", origin="test_origin"):
    item = deepcopy(raw["evidence"][0])
    item.update(id=evidence_id, criterion_keys=[key], stance=stance,
                source_reliability=reliability, review_status=review,
                origin_key=origin, lifecycle="active",
                verification_level="independent_check" if independent else "document_only",
                independent_check_reference="Independent test confirmation" if independent else None)
    raw["evidence"].append(item)
    return item


def custom_questions(definitions):
    """Retain valid historical IDs while adding independently controlled inputs.

    Each tuple supplies id, requirement count, credited count, M, O, canonical
    key. Old questions remain defined for claim coverage and history integrity.
    """
    raw = raw_case()
    template = deepcopy(raw["dd_questions"][0])
    for question in raw["dd_questions"]:
        question.update(review_status="draft", workflow_status="awaiting_review")
    for qid, count, credited, materiality, obtainability, canonical in definitions:
        keys = [f"{qid}_criterion_{i}" for i in range(count)]
        question = deepcopy(template)
        question.update(id=qid, canonical_key=canonical,
                        requirements=[dict(key=key, label=key, min_reliability=3,
                                           require_independent=False) for key in keys])
        question["materiality"]["score"] = materiality
        question["obtainability"]["score"] = obtainability
        raw["dd_questions"].append(question)
        raw["claims"][0]["required_criterion_keys"].extend(keys)
        if credited:
            evidence = add_evidence(raw, keys[0], evidence_id=f"ev_{qid}", origin=f"origin_{qid}")
            evidence["criterion_keys"] = keys[:credited]
    return state_of(raw)


@pytest.mark.parametrize("case,ids,scores", [
    ("ns", ["q_ns_contract_a", "q_ns_contract_b", "q_ns_accept_collect"], [100, 97, 89]),
    ("cd", ["q_cd_cutoff", "q_cd_warranty", "q_cd_inventory"], [100, 94, 89]),
    ("lm", ["q_lm_labor", "q_lm_margin", "q_lm_cash"], [92, 89, 84]),
])
def test_three_initial_rankings(case, ids, scores):
    rows = rank_state(state_of(raw_case(case)))
    assert [row.question_id for row in rows[:3]] == ids
    assert [row.score for row in rows[:3]] == scores
    assert [row.rank for row in rows] == list(range(1, len(rows) + 1))


@pytest.mark.parametrize("materiality,obtainability,expected,provisional", [
    (None, None, 75, True),
    (None, 0, 69, True),
    (0, None, 51, True),
    (0, 0, 45, False),
    (5, 5, 100, False),
])
def test_null_defaults_are_distinct_from_real_zero(materiality, obtainability, expected, provisional):
    raw = raw_case()
    question = raw["dd_questions"][0]
    question["materiality"].update(score=materiality, basis="unknown" if materiality is None else "analyst_rubric")
    question["obtainability"].update(score=obtainability, basis="unknown" if obtainability is None else "analyst_estimate")
    row = row_for(state_of(raw), question["id"])
    assert row.score == expected
    assert row.provisional is provisional
    assert row.materiality == (3 if materiality is None else materiality)
    assert row.obtainability == (2 if obtainability is None else obtainability)


def test_fractional_gap_has_no_integer_truncation():
    state = custom_questions([("q_fraction", 4, 1, 4, 4, "fraction")])
    row = rank_state(state)[0]
    assert row.gap == 3.75
    assert row.score == 77.75
    q = state.dd_questions[-1]
    result = evaluate_requirements(state, q.claim_id, q.requirements)
    assert result.gap == Decimal("3.75")
    assert result.total == 4
    assert len(result.credited_keys) == 1
    assert not result.resolved


def test_raw_score_controls_order_when_displayed_scores_tie():
    # 45*(99/100)=44.55; 45*(100/101)=44.554455... . Both display 44.55.
    state = custom_questions([
        ("q_low", 100, 1, 0, 0, "a_first_alphabetically"),
        ("q_high", 101, 1, 0, 0, "z_last_alphabetically"),
    ])
    rows = rank_state(state)
    assert [row.question_id for row in rows] == ["q_high", "q_low"]
    assert rows[0].score > rows[1].score
    assert [display_decimal(row.score) for row in rows] == ["44.55", "44.55"]


def test_exact_tie_uses_materiality_before_gap():
    state = custom_questions([
        ("q_high_gap", 1, 0, 2, 0, "a"),  # 45 + 16 = 61
        ("q_high_materiality", 5, 3, 5, 1, "z"),  # 18 + 40 + 3 = 61
    ])
    rows = rank_state(state)
    assert [row.score for row in rows] == [61, 61]
    assert [row.question_id for row in rows] == ["q_high_materiality", "q_high_gap"]


def test_rational_exact_tie_does_not_depend_on_intermediate_gap_rounding():
    state = custom_questions([
        ("q_high_materiality", 9, 8, 5, 0, "z"),  # 45/9 + 40 = 45
        ("q_low_materiality", 15, 8, 3, 0, "a"),  # 45*7/15 + 24 = 45
    ])
    rows = rank_state(state)
    assert [row.score for row in rows] == [45, 45]
    assert [row.question_id for row in rows] == ["q_high_materiality", "q_low_materiality"]


def test_exact_tie_uses_gap_before_obtainability():
    state = custom_questions([
        ("q_high_obtainability", 5, 1, 0, 3, "a"),  # 36 + 9 = 45
        ("q_high_gap", 1, 0, 0, 0, "z"),  # 45
    ])
    rows = rank_state(state)
    assert [row.score for row in rows] == [45, 45]
    assert [row.question_id for row in rows] == ["q_high_gap", "q_high_obtainability"]


def test_exact_tie_uses_canonical_key_then_question_id():
    state = custom_questions([
        ("q_z", 1, 0, 0, 0, "A"),
        ("q_a", 1, 0, 0, 0, "A"),
        ("q_first_id", 1, 0, 0, 0, "a"),
    ])
    assert [r.question_id for r in rank_state(state)] == ["q_a", "q_z", "q_first_id"]


def test_resolved_question_is_excluded_before_high_materiality():
    state = custom_questions([
        ("q_resolved", 1, 1, 5, 5, "a"),
        ("q_remaining", 1, 0, 0, 0, "z"),
    ])
    assert [r.question_id for r in rank_state(state)] == ["q_remaining"]


def test_all_resolved_is_empty_and_never_pads_top_three():
    state = custom_questions([("q_resolved", 1, 1, 5, 5, "a")])
    snapshot = build_snapshot(state, "snap_test", "2026-11-03T02:00:00Z")
    assert snapshot.rows == []
    assert snapshot.top3 == []


@pytest.mark.parametrize("review,workflow", [
    ("draft", "awaiting_review"), ("rejected", "rejected"), ("approved", "duplicate"),
])
def test_draft_rejected_and_duplicate_questions_are_excluded(review, workflow):
    raw = raw_case()
    before = rank_state(state_of(raw))
    question = deepcopy(raw["dd_questions"][0])
    question.update(id="q_excluded", review_status=review, workflow_status=workflow,
                    duplicate_of=raw["dd_questions"][0]["id"] if workflow == "duplicate" else None)
    raw["dd_questions"].append(question)
    assert rank_state(state_of(raw)) == before


@pytest.mark.parametrize("stance", ["supports", "refutes"])
def test_unknown_reliability_neither_credits_nor_creates_conflict(stance):
    raw = raw_case()
    add_evidence(raw, "contract_a", reliability=None, stance=stance)
    state = state_of(raw)
    question = state.dd_questions[0]
    result = evaluate_requirements(state, question.claim_id, question.requirements)
    assert result.credited_keys == frozenset()
    assert result.conflict_keys == frozenset()
    assert row_for(state, question.id).score == 100


@pytest.mark.parametrize("review", ["draft", "rejected"])
@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_unapproved_evidence_does_not_change_rank_or_digest(case, review):
    raw = raw_case(case)
    before = state_of(raw)
    key = raw["dd_questions"][0]["requirements"][0]["key"]
    add_evidence(raw, key, review=review, stance="refutes")
    after = state_of(raw)
    assert rank_state(after) == rank_state(before)
    assert ranking_input_digest(after) == ranking_input_digest(before)


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_context_evidence_is_not_requirement_credit(case):
    raw = raw_case(case)
    before = rank_state(state_of(raw))
    item = add_evidence(raw, raw["claims"][0]["required_criterion_keys"][0], stance="context")
    item["criterion_keys"] = []
    assert rank_state(state_of(raw)) == before


def test_duplicate_origin_cannot_count_one_requirement_twice():
    raw = raw_case()
    add_evidence(raw, "accept_a", origin="same_original")
    first = state_of(raw)
    add_evidence(raw, "accept_a", origin="same_original", evidence_id="ev_duplicate")
    second = state_of(raw)
    assert rank_state(first) == rank_state(second)
    assert row_for(second, "q_ns_accept_collect").gap == 3.75


@pytest.mark.parametrize("case", ["cd", "lm"])
def test_approved_duplicate_origin_does_not_change_rank_in_other_packs(case):
    raw = raw_case(case)
    key = raw["dd_questions"][0]["requirements"][0]["key"]
    add_evidence(raw, key, origin="same_original")
    first = rank_state(state_of(raw))
    add_evidence(raw, key, origin="same_original", evidence_id="ev_duplicate")
    assert rank_state(state_of(raw)) == first


def test_independent_requirement_needs_check_but_refutation_does_not():
    raw = raw_case()
    add_evidence(raw, "independence")
    state = state_of(raw)
    q = next(q for q in state.dd_questions if q.id == "q_ns_concentration")
    result = evaluate_requirements(state, q.claim_id, q.requirements)
    assert not result.credited_keys
    raw["evidence"][-1]["stance"] = "refutes"
    result = evaluate_requirements(state_of(raw), q.claim_id, q.requirements)
    assert result.conflict_keys == frozenset({"independence"})
    assert result.gap == 5


def test_independent_check_can_credit_required_scope_without_truth_promotion():
    raw = raw_case()
    add_evidence(raw, "independence", independent=True)
    state = state_of(raw)
    assert "q_ns_concentration" not in [row.question_id for row in rank_state(state)]
    assert state.claims[0].truth_status == "document_only"


def test_conflict_forces_full_gap_even_when_every_requirement_has_support():
    raw = custom_questions([("q_conflict", 1, 1, 5, 4, "conflict")]).model_dump(mode="json")
    add_evidence(raw, "q_conflict_criterion_0", stance="refutes", evidence_id="ev_counter")
    state = state_of(raw)
    row = rank_state(state)[0]
    assert row.question_id == "q_conflict"
    assert row.gap == 5
    assert row.score == 97


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_entity_collection_permutations_are_identical_for_one_hundred_replays(case):
    raw = raw_case(case)
    expected = rank_state(state_of(raw))
    expected_digest = ranking_input_digest(state_of(raw))
    rng = random.Random(4731)
    # Do not reorder ordered lists inside records such as heading_path.
    collections = ("documents", "source_spans", "theses", "claims", "evidence",
                   "evidence_relations", "dd_questions", "ranking_snapshots",
                   "analyst_decisions", "analysis_runs")
    for _ in range(100):
        shuffled = deepcopy(raw)
        for name in collections:
            rng.shuffle(shuffled[name])
        state = state_of(shuffled)
        assert rank_state(state) == expected
        assert ranking_input_digest(state) == expected_digest


def test_digest_ignores_snapshot_clock_but_retains_source_metadata():
    raw = raw_case()
    digest = ranking_input_digest(state_of(raw))
    raw["ranking_snapshots"][0]["created_at"] = "2026-11-03T03:00:00Z"
    assert ranking_input_digest(state_of(raw)) == digest
    raw["documents"][0]["created_at"] = "2026-11-03T03:00:00Z"
    assert ranking_input_digest(state_of(raw)) != digest


@pytest.mark.parametrize("value,expected", [
    (Decimal("1.005"), "1.01"), (Decimal("1.0049"), "1.00"),
    (Decimal("0"), "0.00"), (Decimal("100"), "100.00"),
])
def test_display_uses_half_up_two_places(value, expected):
    assert display_decimal(value) == expected


def test_ambient_decimal_context_cannot_change_raw_sort_or_display():
    state = custom_questions([
        ("q_low", 100, 1, 0, 0, "a"),
        ("q_high", 101, 1, 0, 0, "z"),
    ])
    expected = rank_state(state)
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        assert rank_state(state) == expected
        assert display_decimal(Decimal("1.005")) == "1.01"


def test_materiality_bin_is_not_changed_by_ambient_decimal_rounding():
    raw = raw_case()
    raw["dd_questions"][0]["materiality"].update(
        basis="objective_ratio", exposure_minor=299, denominator_minor=10000,
        score=1, source_span_ids=[raw["source_spans"][0]["id"]],
    )
    state = state_of(raw)
    expected = rank_state(state)
    # 2.99% stays below 3%; a low precision ratio must not round across the bin.
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        assert rank_state(state) == expected

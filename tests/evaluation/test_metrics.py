import math

import pytest

from orion.evaluation.metrics import (
    aggregate, citation_flags, compute_metrics, deterministic_test_pass_rate,
    event_metrics, ndcg_at_k, numeric_error, ratio, wilson_interval, review_correction_rate, reproducibility,
)
from orion.evaluation.models import Citation, EvaluationGold, PredictedClaim, QuestionAnnotation, SystemOutput

pytestmark = pytest.mark.evaluation


def question(identifier, family=None, **updates):
    data = dict(output_id=identifier, text="Provide customer contract for FY2025 and match fee and signatures.",
                family_id=family or identifier, match_reviewed=True, reviewer="reviewer-test",
                match_rationale="Same target, period, artifact and criterion.", target_present=True,
                artifact_present=True, period_present=True, criterion_present=True, financial_relevance=True)
    data.update(updates)
    return QuestionAnnotation(**data)


def output(*questions, **updates):
    return SystemOutput(provenance="authored-fixture", questions=list(questions), **updates)


def test_empty_output_never_looks_like_a_success():
    result = compute_metrics(output(), EvaluationGold(claim_ids=["c1"], critical_families=["q1"], resolved_question_families=["old"]))
    assert result["claim_precision"]["value"] == 0
    assert result["claim_recall"]["value"] == 0
    assert result["top3_critical_dd_coverage"]["value"] == 0
    assert result["citation_precision"]["value"] is None
    assert result["duplicate_question_rate"]["value"] is None
    assert result["actionability"]["value"] == 0
    assert result["resolved_question_removal_accuracy"]["value"] == 0
    assert result["generation_failure"]["value"] is True


def test_duplicate_questions_cannot_inflate_coverage():
    result = compute_metrics(output(question("a", "critical"), question("b", "critical"), question("c", "critical")),
                             EvaluationGold(critical_families=["critical", "other", "third"]))
    assert result["top3_critical_dd_coverage"]["value"] == pytest.approx(1 / 3)
    assert result["duplicate_question_rate"]["value"] == pytest.approx(2 / 3)
    assert result["critical_dd_precision"]["value"] == pytest.approx(1 / 3)


def test_quantity_spam_does_not_improve_top3_or_precision():
    base = [question(f"wrong{i}") for i in range(3)]
    result = compute_metrics(output(*base, question("q1"), question("q2")),
                             EvaluationGold(critical_families=["q1", "q2"]))
    assert result["critical_dd_coverage"]["value"] == 1
    assert result["critical_dd_precision"]["value"] == 0.4
    assert result["top3_critical_dd_coverage"]["value"] == 0


def test_unreviewed_semantic_match_abstains_and_cannot_get_credit():
    result = compute_metrics(output(question("q1", match_reviewed=False)), EvaluationGold(critical_families=["q1"]))
    assert result["top3_critical_dd_coverage"]["value"] == 0
    assert result["question_match_review_coverage"]["value"] == 0
    assert result["duplicate_question_rate"]["value"] is None
    assert result["duplicate_question_rate"]["status"] == "not_reviewed"


def test_review_annotation_requires_a_reviewer_and_reason():
    with pytest.raises(ValueError):
        QuestionAnnotation(output_id="q", text="Question", family_id="a", match_reviewed=True)


def test_duplicate_prediction_ids_rejected():
    with pytest.raises(ValueError, match="IDs"):
        compute_metrics(output(question("q1"), question("q1")), EvaluationGold(critical_families=["q1"]))


def test_claim_metrics_unique_tp_and_duplicates_are_false_positives():
    result = compute_metrics(output(claims=[PredictedClaim(prediction_id="p1", matched_claim_id="c1", text="One"),
                                           PredictedClaim(prediction_id="p2", matched_claim_id="c1", text="One")]),
                             EvaluationGold(claim_ids=["c1", "c2"]))
    assert result["claim_precision"]["value"] == 0.5
    assert result["claim_recall"]["value"] == 0.5
    assert result["claim_f1"]["value"] == 0.5


@pytest.mark.parametrize("change", ["document", "version", "locator", "quote"])
def test_citation_requires_exact_document_version_locator_and_quote(change):
    source = {"document_id": "doc", "document_version": 1, "locator": {"kind": "pdf", "page": 1, "block_index": 0}, "normalized_text": "Revenue is 120."}
    data = dict(document_id="doc", document_version=1, locator=source["locator"], quote="Revenue is 120.")
    if change == "document": data["document_id"] = "forged"
    if change == "version": data["document_version"] = 2
    if change == "locator": data["locator"] = {"kind": "pdf", "page": 2, "block_index": 0}
    if change == "quote": data["quote"] = "Revenue is 999."
    located, valid = citation_flags(Citation(**data), [source])
    assert not valid
    assert located == (change == "quote")


def test_valid_quote_does_not_establish_entailment_or_truth():
    source = {"document_id": "doc", "document_version": 1, "locator": {"kind": "pdf", "page": 1, "block_index": 0}, "normalized_text": "Management claims two customers."}
    citation = Citation(document_id="doc", document_version=1, locator=source["locator"], quote=source["normalized_text"])
    claim = PredictedClaim(prediction_id="p", text="Two independently verified customers.", citations=[citation], entailment_supported=False)
    result = compute_metrics(output(claims=[claim]), EvaluationGold(), [source])
    assert result["citation_precision"]["value"] == 1
    assert result["entailment_accuracy"]["value"] == 0
    assert result["unsupported_claim_rate"]["value"] == 1


def test_missing_entailment_annotation_is_not_assumed_correct():
    source = {"document_id": "doc", "document_version": 1, "locator": {"kind": "pdf", "page": 1, "block_index": 0}, "normalized_text": "Management report."}
    citation = Citation(document_id="doc", document_version=1, locator=source["locator"], quote=source["normalized_text"])
    result = compute_metrics(output(claims=[PredictedClaim(prediction_id="p", text="Claim", citations=[citation])]), EvaluationGold(), [source])
    assert result["entailment_accuracy"]["status"] == "not_reviewed"
    assert result["unsupported_claim_rate"]["value"] is None


def test_ambiguous_source_locator_rejected():
    source = {"document_id": "d", "document_version": 1, "locator": {"kind": "pdf", "page": 1}, "text": "A"}
    citation = Citation(document_id="d", document_version=1, locator=source["locator"], quote="A")
    assert citation_flags(citation, [source, source]) == (False, False)


def test_whitespace_only_quote_not_valid_even_when_source_contains_spaces():
    source = {"document_id": "d", "document_version": 1, "locator": {"kind": "pdf", "page": 1}, "text": "A   B"}
    citation = Citation(document_id="d", document_version=1, locator=source["locator"], quote="   ")
    assert citation_flags(citation, [source]) == (True, False)


@pytest.mark.parametrize("status", ["failed", "abstained"])
def test_nonempty_failed_generation_never_gets_partial_success_credit(status):
    result = compute_metrics(output(question("q1"), status=status), EvaluationGold(critical_families=["q1"]))
    assert result["top3_critical_dd_coverage"]["value"] == 0
    assert result["actionability"]["value"] == 0
    assert result["generation_failure"]["value"]


def test_ndcg_independent_hand_calculation_and_repeats():
    ideal = 7 + 3 / math.log2(3) + 1 / 2
    actual = 1 + 7 / math.log2(3) + 3 / 2
    assert ndcg_at_k(["c", "a", "b"], {"a": 3, "b": 2, "c": 1}).value == pytest.approx(actual / ideal)
    assert ndcg_at_k(["a", "a", "a"], {"a": 3, "b": 2, "c": 1}).value == pytest.approx(7 / ideal)
    assert ndcg_at_k([], {}).value is None


def test_numeric_missing_outputs_cannot_improve_error():
    result = numeric_error({"one": 0.1}, {"one": 0.1, "two": 0.9})
    assert result["error"].status == "incomplete"
    assert result["error"].value is None
    assert result["coverage"].value == 0.5
    assert numeric_error({"one": 0.2}, {"one": 0.1})["error"].value == pytest.approx(0.1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_numerics_rejected(bad):
    with pytest.raises(ValueError):
        numeric_error({"a": bad}, {"a": 0.1})


def test_partial_actionability_review_is_na_not_selected_denominator():
    result = compute_metrics(output(question("q1"), question("q2", criterion_present=None)), EvaluationGold())
    assert result["actionability"]["denominator"] == 2
    assert result["actionability"]["status"] == "not_reviewed"
    assert result["actionability"]["value"] is None


def test_event_no_change_and_double_count_denominators():
    result = event_metrics([{"expected_change": False, "before": [1], "after": [2], "transition_pass": False,
                             "repeated_group_attempts": 2, "repeated_group_updates": 1},
                            {"expected_change": True, "before": [1], "after": [2], "transition_pass": True}])
    assert result["unnecessary_ranking_change_rate"]["value"] == 1
    assert result["evidence_double_counting_rate"]["value"] == 0.5
    assert result["transition_exact_match"]["value"] == 0.5


def test_skipped_tests_not_counted_as_success():
    assert deterministic_test_pass_rate(passed=9, failed=0, errors=0, skipped=1)["value"] == 0.9


def test_aggregation_preserves_unmeasured_rows_and_micro_macro():
    rows = [{"m": ratio(1, 1).as_dict()}, {"m": ratio(0, 9).as_dict()}, {"m": ratio(0, 0).as_dict()}]
    result = aggregate(rows, "m")
    assert result["macro"] == 0.5
    assert result["micro"] == 0.1
    assert result["unmeasured_rows"] == 1


def test_wilson_empty_and_boundary():
    assert wilson_interval(0, 0) is None
    lower, upper = wilson_interval(15, 15)
    assert 0.79 < lower < 0.80
    assert upper == 1


def test_review_and_reproducibility_use_honest_denominators():
    assert review_correction_rate(corrected=1, total_drafts=4)["value"] == 0.25
    reference = {"rows": [["q1", 100]], "input_digest": "abc"}
    assert reproducibility(reference, [reference, {"rows": [["q2", 90]], "input_digest": "abc"}])["value"] == 0.5
    assert reproducibility(reference, [])["value"] is None


@pytest.mark.parametrize("n,d", [(-1, 3), (4, 3), (0, -1), (float("nan"), 1)])
def test_invalid_ratio_counts_fail(n, d):
    with pytest.raises(ValueError): ratio(n, d)

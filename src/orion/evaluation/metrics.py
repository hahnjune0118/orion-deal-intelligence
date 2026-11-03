"""Transparent metrics with explicit denominators and abstention accounting.

Semantic equivalence is supplied as an audited one-to-one family annotation.
No keyword matcher, LLM judge, or gold-dependent prediction is used here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, log2, sqrt
from typing import Any, Iterable, Mapping, Sequence

from .models import Citation, EvaluationGold, SystemOutput


@dataclass(frozen=True)
class Metric:
    numerator: float | int
    denominator: float | int
    value: float | None
    status: str = "measured"
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def ratio(numerator: float, denominator: float, *, empty: float | None = None,
          note: str = "", status: str = "measured") -> Metric:
    if not isfinite(numerator) or not isfinite(denominator) or numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError("Ratio counts must be finite and satisfy 0 <= numerator <= denominator")
    if denominator == 0:
        return Metric(numerator, denominator, empty, "not_applicable" if empty is None else status, note)
    return Metric(numerator, denominator, numerator / denominator, status, note)


def wilson_interval(successes: int, total: int) -> list[float] | None:
    """Descriptive interval only: within-deal observations are not independent."""
    ratio(successes, total)
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    width = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - width), min(1.0, center + width)]


def citation_flags(citation: Citation, sources: Sequence[Mapping[str, Any]]) -> tuple[bool, bool]:
    """Return (native locator match, exact quote match), independently of entailment.

    Sources are trusted indexed elements, not candidate citation objects. A unit
    requires document ID + version + exact structured locator. Normalization is
    the core text-v1 normalization; no fuzzy quote correction is performed.
    """
    from orion.domain.grounding import normalize_text
    units = [unit for unit in sources if unit.get("document_id") == citation.document_id
             and unit.get("document_version") == citation.document_version
             and unit.get("locator") == citation.locator]
    if len(units) != 1:
        return False, False
    text = normalize_text(units[0].get("normalized_text", units[0].get("text", "")))
    quote = normalize_text(citation.quote)
    return True, bool(quote.strip()) and quote in text


def reviewed_families(output: SystemOutput) -> list[str | None]:
    """One predicted item maps to one family. Repeat families remain duplicates."""
    if len({q.output_id for q in output.questions}) != len(output.questions):
        raise ValueError("Output question IDs must be unique; duplicated content uses distinct IDs")
    return [q.family_id if q.match_reviewed else None for q in output.questions]


def ndcg_at_k(ranked: Sequence[str | None], relevance: Mapping[str, float], k: int = 3) -> Metric:
    if type(k) is not int or k < 1 or any(not isfinite(v) or v < 0 for v in relevance.values()):
        raise ValueError("NDCG requires positive k and finite nonnegative relevance")
    seen: set[str] = set()
    score = 0.0
    for position, family in enumerate(ranked[:k], 1):
        gain = relevance.get(family, 0.0) if family is not None and family not in seen else 0.0
        score += (2 ** gain - 1) / log2(position + 1)
        if family is not None:
            seen.add(family)
    ideal = sum((2 ** gain - 1) / log2(i + 2) for i, gain in enumerate(sorted(relevance.values(), reverse=True)[:k]))
    return Metric(score, ideal, None if not ideal else score / ideal,
                  "not_applicable" if not ideal else "measured", "Duplicate families have zero gain after first occurrence.")


def numeric_error(predicted: Mapping[str, float], expected: Mapping[str, float]) -> dict[str, Metric]:
    if any(not isfinite(value) for value in (*predicted.values(), *expected.values())):
        raise ValueError("Numeric metrics reject NaN/infinity")
    present = set(predicted) & set(expected)
    error = sum(abs(predicted[key] - expected[key]) for key in present)
    complete = len(present) == len(expected)
    return {
        "error": Metric(error, len(expected), error / len(expected) if expected and complete else None,
                        "measured" if expected and complete else "incomplete" if expected else "not_applicable",
                        "MAE is withheld if any required output is missing; see numeric coverage."),
        "coverage": ratio(len(present), len(expected)),
    }


def _annotation_metric(values: list[bool | None], name: str, failed: bool) -> Metric:
    # Complete-output annotation is required. Cherry-picking reviewed items is not a denominator.
    if any(value is None for value in values):
        return Metric(sum(value is True for value in values), len(values), None, "not_reviewed",
                      f"{name}: unresolved human annotations are retained in the denominator.")
    return ratio(sum(values), len(values), empty=0.0 if failed else None)


def compute_metrics(output: SystemOutput, gold: EvaluationGold,
                    source_elements: Sequence[Mapping[str, Any]] = ()) -> dict[str, dict]:
    """Compute a state×arm row. Absence of generation cannot count as success."""
    output = SystemOutput.model_validate(output.model_dump())
    gold = EvaluationGold.model_validate(gold.model_dump())
    failed = output.status in {"failed", "abstained", "not_run"} or not output.questions
    claim_ids = [claim.matched_claim_id for claim in output.claims]
    true_claims = set(claim_ids) & set(gold.claim_ids)
    tp = len(true_claims)
    precision = ratio(tp, len(output.claims), empty=0.0 if gold.claim_ids else None)
    recall = ratio(tp, len(gold.claim_ids))
    f1_denominator = len(output.claims) + len(gold.claim_ids)
    metrics: dict[str, Metric] = {
        "claim_precision": precision,
        "claim_recall": recall,
        "claim_f1": ratio(2 * tp, f1_denominator),
        "evidence_retrieval_recall": ratio(len(set(output.retrieved_evidence_ids) & set(gold.evidence_ids)), len(gold.evidence_ids)),
        "evidence_relationship_accuracy": ratio(len(set(output.relationships) & set(gold.relationships)), len(output.relationships)),
        "evidence_relationship_recall": ratio(len(set(output.relationships) & set(gold.relationships)), len(gold.relationships)),
        "contradiction_detection_recall": ratio(len(set(output.contradiction_groups) & set(gold.contradiction_groups)), len(gold.contradiction_groups)),
    }
    citations = [citation for claim in output.claims for citation in claim.citations]
    checks = [citation_flags(citation, source_elements) for citation in citations]
    n_valid = sum(exact for _, exact in checks)
    n_locator = sum(locator for locator, _ in checks)
    metrics.update({
        "citation_precision": ratio(n_valid, len(citations), note="Exact source support only; independent truth/entailment is separate."),
        "locator_accuracy": ratio(n_locator, len(citations)),
        "hallucinated_citation_rate": ratio(len(citations) - n_valid, len(citations)),
        "fabricated_citations": Metric(len(citations) - n_valid, 1, float(len(citations) - n_valid), note="Absolute count, not a population guarantee."),
    })
    factual = [claim for claim in output.claims if claim.factual]
    cited = [claim for claim in factual if claim.citations]
    metrics["citation_completeness"] = ratio(sum(any(citation_flags(c, source_elements)[1] for c in claim.citations) for claim in factual), len(factual))
    metrics["entailment_accuracy"] = _annotation_metric([claim.entailment_supported for claim in cited], "Entailment", failed)
    unsupported = []
    for claim in factual:
        valid_citation = any(citation_flags(c, source_elements)[1] for c in claim.citations)
        unsupported.append(True if not valid_citation else None if claim.entailment_supported is None else not claim.entailment_supported)
    metrics["unsupported_claim_rate"] = _annotation_metric(unsupported, "Unsupported claim", failed=False)

    families = reviewed_families(output)
    critical = set(gold.critical_families)
    all_hits = len(set(families) & critical)
    top_hits = len(set(families[:3]) & critical)
    matched = [family for family in families if family is not None]
    metrics.update({
        "critical_dd_coverage": ratio(all_hits, len(critical)),
        "critical_dd_precision": ratio(all_hits, len(families), empty=0.0 if critical else None),
        "top3_critical_dd_coverage": ratio(top_hits, len(critical)),
        "top3_precision": ratio(top_hits, len(families[:3]), empty=0.0 if critical else None),
        "topk_priority_hit_rate": ratio(top_hits, min(3, len(critical))),
        "duplicate_question_rate": ratio(len(matched) - len(set(matched)), len(families), note="Unreviewed family matches require review; do not certify zero semantic duplicates."),
        "question_match_review_coverage": ratio(sum(q.match_reviewed for q in output.questions), len(output.questions)),
        "ndcg_at_3": ndcg_at_k(families, gold.relevance or {q: 1.0 for q in critical}),
        "hypothesis_update_consistency": ratio(sum(output.hypothesis_statuses.get(k) == v for k, v in gold.hypothesis_statuses.items()), len(gold.hypothesis_statuses)),
        "resolved_question_removal_accuracy": ratio(len(set(gold.resolved_question_families) - set(families)), len(gold.resolved_question_families)),
        "final_approvals_without_hitl": Metric(output.final_approvals_without_review, 1, float(output.final_approvals_without_review)),
    })
    if any(not question.match_reviewed or question.family_id is None for question in output.questions):
        metrics["duplicate_question_rate"] = Metric(len(matched) - len(set(matched)), len(families), None,
                                                   "not_reviewed", "Semantic duplicate rate requires complete family annotation.")
    if failed and gold.resolved_question_families:
        metrics["resolved_question_removal_accuracy"] = ratio(0, len(gold.resolved_question_families),
                                                              note="Failed or empty generation cannot count as correct removal.")
    actionability: list[bool | None] = []
    for question in output.questions:
        flags = [question.target_present, question.artifact_present, question.period_present, question.criterion_present]
        actionability.append(None if any(x is None for x in flags) else all(flags))
    metrics["actionability"] = _annotation_metric(actionability, "Actionability", failed)
    metrics["verification_criterion_completeness"] = _annotation_metric([q.criterion_present for q in output.questions], "Verification", failed)
    metrics["financial_relevance"] = _annotation_metric([q.financial_relevance for q in output.questions], "Financial relevance", failed)
    for name, attr in (("bayesian_posterior", "posterior"), ("eig_calculation", "eig")):
        result = numeric_error(getattr(output, attr), getattr(gold, attr))
        metrics[f"{name}_error"] = result["error"]
        metrics[f"{name}_coverage"] = result["coverage"]
    if output.status in {"failed", "abstained", "not_run"}:
        # A partial record from a failed generation is not a successful delivered
        # answer. Keep its size in denominators, but give no generation credit.
        zero_credit = {
            "claim_precision", "claim_recall", "claim_f1", "evidence_retrieval_recall",
            "evidence_relationship_accuracy", "evidence_relationship_recall", "contradiction_detection_recall",
            "citation_completeness", "entailment_accuracy", "critical_dd_coverage", "critical_dd_precision",
            "top3_critical_dd_coverage", "top3_precision", "topk_priority_hit_rate", "ndcg_at_3",
            "hypothesis_update_consistency", "resolved_question_removal_accuracy", "actionability",
            "verification_criterion_completeness", "financial_relevance", "bayesian_posterior_coverage", "eig_calculation_coverage",
        }
        for name in zero_credit:
            metric = metrics[name]
            metrics[name] = Metric(0, metric.denominator, 0.0 if metric.denominator or name in {"actionability", "top3_precision"} else None,
                                   "measured" if metric.denominator or name in {"actionability", "top3_precision"} else "not_applicable",
                                   "Failed/abstained generation earns no task credit, even when a partial payload is present.")
        for name in ("citation_precision", "locator_accuracy", "hallucinated_citation_rate", "unsupported_claim_rate", "duplicate_question_rate"):
            metric = metrics[name]
            metrics[name] = Metric(metric.numerator, metric.denominator, metric.value, "partial_output_diagnostic", metric.note)
        for name in ("bayesian_posterior_error", "eig_calculation_error"):
            metric = metrics[name]
            metrics[name] = Metric(metric.numerator, metric.denominator, None, "failed_generation", "No delivered numeric answer.")
    result = {name: metric.as_dict() for name, metric in metrics.items()}
    result["generation_failure"] = {"value": failed, "status": output.status}
    return result


def event_metrics(events: Sequence[Mapping[str, Any]]) -> dict[str, dict]:
    """Each event specifies expected_change, before/after and optional applied groups."""
    null_events = [event for event in events if not event["expected_change"]]
    unnecessary = sum(event["before"] != event["after"] for event in null_events)
    repeat_attempts = sum(event.get("repeated_group_attempts", 0) for event in events)
    extra_updates = sum(event.get("repeated_group_updates", 0) for event in events)
    return {
        "unnecessary_ranking_change_rate": ratio(unnecessary, len(null_events)).as_dict(),
        "evidence_double_counting_rate": ratio(extra_updates, repeat_attempts).as_dict(),
        "transition_exact_match": ratio(sum(bool(event.get("transition_pass")) for event in events), len(events)).as_dict(),
    }


def deterministic_test_pass_rate(*, passed: int, failed: int, errors: int, skipped: int = 0) -> dict:
    if any(type(n) is not int or n < 0 for n in (passed, failed, errors, skipped)):
        raise ValueError("Test counts must be nonnegative integers")
    return ratio(passed, passed + failed + errors + skipped,
                 note="Skipped/not-executed declared cases cannot count as passed.").as_dict()


def review_correction_rate(*, corrected: int, total_drafts: int) -> dict:
    return ratio(corrected, total_drafts, note="Substantive source/meaning/criterion changes; identity fixture conversion is not an actual analyst review.").as_dict()


def reproducibility(reference: Mapping[str, Any], reruns: Sequence[Mapping[str, Any]]) -> dict:
    """Inputs contain ordered rows and canonical input digest, not wall clocks."""
    from orion.domain.grounding import canonical_hash
    required = {"rows", "input_digest"}
    if set(reference) != required or any(set(run) != required for run in reruns):
        raise ValueError("Reproducibility requires only rows and input_digest")
    expected = canonical_hash(reference)
    return ratio(sum(canonical_hash(run) == expected for run in reruns), len(reruns),
                 note="Same approved state/policy; audit timestamps intentionally excluded.").as_dict()


def aggregate(rows: Iterable[Mapping[str, Any]], metric_name: str) -> dict:
    values = [row[metric_name] for row in rows]
    measured = [row for row in values if row.get("status") == "measured" and row.get("value") is not None]
    numerator = sum(row["numerator"] for row in measured)
    denominator = sum(row["denominator"] for row in measured)
    return {"macro": sum(row["value"] for row in measured) / len(measured) if measured else None,
            "micro": numerator / denominator if denominator else None,
            "numerator": numerator, "denominator": denominator,
            "measured_rows": len(measured), "unmeasured_rows": len(values) - len(measured),
            "minimum": min((row["value"] for row in measured), default=None)}

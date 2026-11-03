"""Reproducible quantitative demonstration, explicitly not a model benchmark.

Run ``python -m orion.quant.report --output PATH``. The independent illustrative
candidate set is disclosed in full; it is not an extracted company DD output.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from .bayes import BayesianLedger, ConditionalLikelihoodModel, ProbabilityAssumptions, binary_posteriors
from .information_gain import binary_eig
from .priority import ResearchQuestion, rank_research, sensitivity_analysis


def _questions(commercial_prior=.3, commercial_sensitivity=.9, commercial_false_positive=.1,
               *, missing_commercial_eig=False):
    assumptions = [
        ("example_commercial_confirmation", 4, 4, commercial_prior, commercial_sensitivity, commercial_false_positive),
        ("example_margin_reconciliation", 5, 4, .65, .6, .4),
        ("example_capacity_delivery", 3, 3, .5, .8, .2),
    ]
    inputs = []
    questions = []
    for identifier, materiality, gap, prior, sensitivity, false_positive in assumptions:
        source = (
            f"Independent synthetic research example: {identifier}; analyst-authored "
            f"p={prior}, P(positive|H)={sensitivity}, P(positive|not H)={false_positive}; not empirical."
        )
        if identifier == "example_commercial_confirmation" and missing_commercial_eig:
            information = binary_eig(prior, None, false_positive, source)
        else:
            information = binary_eig(prior, sensitivity, false_positive, source)
        questions.append(ResearchQuestion(
            question_id=identifier, materiality=materiality, gap=gap, obtainability=4,
            eig_bits=information.eig_bits if information else None,
            eig_assumption_source=source if information else None,
            days=5, external_cost_minor=50000, evidence_overlap=0,
            review_status="approved",
        ))
        inputs.append({
            "question_id": identifier, "prior": prior,
            "likelihood_positive_h": None if identifier == "example_commercial_confirmation" and missing_commercial_eig else sensitivity,
            "likelihood_positive_not_h": false_positive,
            "assumption_source": source, "assumption_author": "synthetic-research-author",
            "assumption_date": "2026-11-03", "eig": asdict(information) if information else None,
        })
    return questions, inputs


def _conditional_example():
    ledger = BayesianLedger()
    assumptions1 = ProbabilityAssumptions(
        assumption_id="worked_contract_v1", assumption_source="Synthetic first contract example .3/.8/.2",
        author_id="synthetic-analyst", as_of="2026-11-03", prior=.3, likelihood_h=.8, likelihood_not_h=.2,
    )
    first = ledger.update(
        hypothesis_id="worked_h1", evidence_id="worked_contract", evidence_group_id="worked_customer_a",
        source_fingerprint=sha256(b"Synthetic contract A").hexdigest(), assumptions=assumptions1, approved=True,
    )
    assumptions2 = ProbabilityAssumptions(
        assumption_id="worked_execution_v1",
        assumption_source="Explicit conditional P(execution|H,contract)=.75 and P(execution|not H,contract)=.30",
        author_id="synthetic-analyst", as_of="2026-11-03", prior=first.posterior, likelihood_h=.75, likelihood_not_h=.30,
    )
    blocked = ledger.update(
        hypothesis_id="worked_h1", evidence_id="worked_execution", evidence_group_id="worked_customer_a",
        source_fingerprint=sha256(b"Distinct synthetic acceptance and collection A").hexdigest(),
        assumptions=assumptions2, approved=True,
    )
    model = ConditionalLikelihoodModel(
        model_id="worked_joint_model_v1", hypothesis_id="worked_h1", evidence_id="worked_execution",
        assumption_id="worked_execution_v1", conditioning_evidence_ids=["worked_contract"],
        likelihood_h=.75, likelihood_not_h=.30,
        conditioning_group_ids=["worked_customer_a"],
        assumption_source="Reviewed synthetic chain-rule joint scenario, not independence multiplication",
        reviewer_id="synthetic-reviewer", reviewed_at="2026-11-03", review_status="approved",
    )
    second = ledger.update(
        hypothesis_id="worked_h1", evidence_id="worked_execution", evidence_group_id="worked_customer_a",
        source_fingerprint=sha256(b"Distinct synthetic acceptance and collection A").hexdigest(),
        assumptions=assumptions2, approved=True, conditional_model=model,
    )
    return {"unreviewed_joint_model_result": asdict(blocked), "reviewed_joint_model_result": asdict(second),
            "assumptions": [assumptions1.model_dump(), assumptions2.model_dump()],
            "conditional_model": model.model_dump(), "ledger": ledger.snapshot()}


def build_quantitative_report() -> dict:
    """Execute calculations and unchanged-core checks; no gold or LLM input."""
    from orion.demo import prepare_replay
    from orion.domain.scoring import rank_state, ranking_input_digest

    questions, inputs = _questions()
    sensitivity = sensitivity_analysis(questions)
    variants = []
    for label, prior, a, b in [
        ("base", .3, .9, .1), ("lower_prior", .1, .9, .1), ("higher_prior", .5, .9, .1),
        ("moderate_discrimination", .3, .8, .2), ("weak_discrimination", .3, .7, .3),
    ]:
        candidates, assumptions = _questions(prior, a, b)
        ranking = rank_research(candidates)
        variants.append({"label": label, "assumptions": assumptions,
                         "ranking": [asdict(row) for row in ranking],
                         "top3": [row.question_id for row in ranking[:3]]})
    fallback_questions, fallback_inputs = _questions(missing_commercial_eig=True)
    fallback_rows = rank_research(fallback_questions)
    invariants = []
    for case in ("ns", "cd", "lm"):
        state = prepare_replay({"case_id": case, "actions": []}).state
        original = state.model_dump(mode="json")
        before_rows = [row.model_dump() for row in rank_state(state)]
        before_digest = ranking_input_digest(state)
        # Execute optional side-panel/research calculations; none receives a
        # mutable DealState or rewrites production scoring inputs.
        binary_eig(.3, .8, .2, "Optional side panel; explicitly synthetic")
        sensitivity_analysis(questions)
        after_rows = [row.model_dump() for row in rank_state(state)]
        invariants.append({"case": case, "panel_disabled_rank": before_rows,
                           "panel_enabled_rank": after_rows,
                           "unchanged": before_rows == after_rows and original == state.model_dump(mode="json"),
                           "before_digest": before_digest, "after_digest": ranking_input_digest(state)})
    blueprint = binary_eig(.3, .8, .2, "Blueprint explicit illustrative hypothetical scenario")
    return {
        "report_version": "1.0.0", "result_kind": "executed_deterministic_fixture_calculations",
        "model_benchmark": "not_run", "live_api_calls": 0,
        "candidate_scope": "independent illustrative candidates, not extracted Northstar benchmark outputs",
        "production_policy": {"scoring_version": "1.0.0", "formula": "9*gap + 8*materiality + 3*obtainability",
                              "normalized_weights": {"gap": .45, "materiality": .40, "obtainability": .15},
                              "bayesian_panel_affects_rank": False},
        "research_policy": {"version": "research-priority-1.0.0", "type": "weighted_heuristic_not_EVSI",
                            "weights": sensitivity["variants"][0]["policy"],
                            "formula": "100*(1-overlap)*sum(effective_weight*normalized_component)",
                            "missing_policy": "Null EIG is excluded and weights renormalized; never invent probability",
                            "cost_scale_minor": 100000, "time_scale_days": 10},
        "blueprint_binary": binary_posteriors(.3, .8, .2), "blueprint_eig": asdict(blueprint),
        "candidate_inputs": [q.model_dump() for q in questions], "probability_assumptions": inputs,
        "weight_sensitivity": sensitivity,
        "prior_likelihood_sensitivity": variants,
        "ranking_changes_observed": len({tuple(row["top3"]) for row in variants}) > 1,
        "null_eig_fallback": {"assumptions": fallback_inputs, "ranking": [asdict(row) for row in fallback_rows]},
        "production_no_bayes_invariance": invariants,
        "conditional_joint_example": _conditional_example(),
        "limitations": [
            "All probabilities and review decisions are explicitly authored synthetic assumptions.",
            "Rank changes establish sensitivity to the disclosed policy, not optimal investment decisions.",
            "The original production ranking policy is unchanged; research no-EIG ablation is a distinct experiment.",
            "Dependence groups require a trusted source registry/analyst; content hashes cannot detect every semantic paraphrase.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_quantitative_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "result_kind": report["result_kind"],
                      "ranking_changes_observed": report["ranking_changes_observed"],
                      "production_invariant": all(row["unchanged"] for row in report["production_no_bayes_invariance"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

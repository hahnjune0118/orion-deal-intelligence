"""Independent arithmetic and failure-boundary checks; no network/model calls."""
from dataclasses import asdict
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import math

import pytest

from orion.quant.bayes import (BayesianLedger, ConditionalLikelihoodModel,
                              ProbabilityAssumptions, binary_posteriors, posterior)


def assumptions(prior=.3, likelihood_h=.8, likelihood_not_h=.2, **kwargs):
    return ProbabilityAssumptions(
        assumption_id="test-explicit-v1", assumption_source="Independent hypothetical binary test",
        author_id="synthetic-analyst", as_of="2026-11-03", prior=prior,
        likelihood_h=likelihood_h, likelihood_not_h=likelihood_not_h, **kwargs,
    )


def observe(ledger, *, hypothesis="h1", evidence="e1", group="g1", content=None,
            params=None, approved=True, dependencies=(), conditional=None):
    return ledger.update(hypothesis_id=hypothesis, evidence_id=evidence,
                         evidence_group_id=group, source_fingerprint=sha256((content or evidence).encode()).hexdigest(),
                         assumptions=params or assumptions(), approved=approved,
                         dependent_group_ids=dependencies, conditional_model=conditional)


def test_blueprint_positive_negative_against_independent_decimal():
    with localcontext() as ctx:
        ctx.prec = 60
        p, a, b = Decimal("0.30"), Decimal("0.80"), Decimal("0.20")
        pos = a * p / (a * p + b * (1 - p))
        neg = (1 - a) * p / ((1 - a) * p + (1 - b) * (1 - p))
    result = binary_posteriors(.3, .8, .2)
    assert result["positive"] == pytest.approx(float(pos), abs=1e-15)
    assert result["negative"] == pytest.approx(float(neg), abs=1e-15)
    assert result["positive"] == pytest.approx(12 / 19)
    assert result["negative"] == pytest.approx(3 / 31)
    assert result["p_positive"] == pytest.approx(.38)
    assert result["p_negative"] == pytest.approx(.62)


@pytest.mark.parametrize("p", [0, .1, .3, .5, .99, 1])
def test_uninformative_evidence_leaves_prior(p):
    assert posterior(p, .37, .37) == pytest.approx(p)


@pytest.mark.parametrize("args", [(0, 1, 0), (1, 0, 1), (.3, 0, 0)])
def test_impossible_observation_has_no_arbitrary_posterior(args):
    with pytest.raises(ValueError, match="zero prior-predictive"):
        posterior(*args)


def test_extremely_small_likelihood_scaling_and_impossible_branch():
    assert posterior(.3, 1e-310, 1e-310) == pytest.approx(.3)
    assert binary_posteriors(.3, 0, 0) == {"positive": None, "negative": .3, "p_positive": 0, "p_negative": 1}


@pytest.mark.parametrize("value", [True, False, "0.3", -1, 1.001, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_invalid_probability_rejected(value, index):
    args = [.3, .8, .2]
    args[index] = value
    with pytest.raises(ValueError):
        posterior(*args)


def test_assumptions_are_strict_provenanced_and_missing_values_remain_missing():
    assert assumptions().complete
    missing = assumptions(likelihood_not_h=None)
    assert not missing.complete
    for changes in ({"assumption_source": " "}, {"as_of": "2026-02-30"}, {"extra": 1}, {"prior": True}):
        raw = assumptions().model_dump()
        raw.update(changes)
        with pytest.raises(ValueError):
            ProbabilityAssumptions.model_validate(raw)


def test_sequential_approved_independent_update_matches_direct_joint_calculation():
    ledger = BayesianLedger()
    first = observe(ledger)
    second = observe(ledger, evidence="e2", group="g2", params=assumptions(first.posterior, .75, .30))
    expected = .3 * .8 * .75 / (.3 * .8 * .75 + .7 * .2 * .30)
    assert second.status == "applied"
    assert second.posterior == pytest.approx(expected)
    assert ledger.beliefs == {"h1": pytest.approx(expected)}
    assert json.loads(json.dumps(ledger.snapshot()))["history"][1]["assumption_source"]


def test_no_approval_and_missing_parameters_never_change_belief():
    ledger = BayesianLedger()
    assert observe(ledger, approved=False).status == "unapproved"
    assert ledger.beliefs == {}
    assert observe(ledger, params=assumptions(likelihood_h=None)).status == "missing_parameters"
    assert ledger.beliefs == {}
    assert observe(ledger).status == "applied"


def test_duplicate_evidence_id_and_repeated_source_are_not_multiplied():
    ledger = BayesianLedger()
    original = observe(ledger)
    repeated = observe(ledger)
    assert repeated.status == "duplicate"
    assert repeated.posterior == original.posterior
    # Renaming an identical quote and assigning a new group cannot bypass the guard.
    repeated_content = observe(ledger, evidence="e2", group="g2", content="e1")
    assert repeated_content.status == "duplicate"
    assert ledger.beliefs["h1"] == original.posterior


def test_applied_evidence_id_is_immutable():
    ledger = BayesianLedger()
    observe(ledger)
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="reused"):
        observe(ledger, content="changed text")
    assert ledger.snapshot() == before


def test_same_independence_group_blocks_different_document_and_quote():
    ledger = BayesianLedger()
    first = observe(ledger)
    result = observe(ledger, evidence="pitch-deck-repetition", content="same claim rephrased")
    assert result.status == "dependent"
    assert result.posterior == first.posterior


@pytest.mark.parametrize("reverse", [False, True])
def test_declared_dependency_is_symmetric(reverse):
    ledger = BayesianLedger()
    if reverse:
        first = observe(ledger, group="g1", dependencies=("g2",))
        second = observe(ledger, group="g2", evidence="e2")
    else:
        first = observe(ledger, group="g1")
        second = observe(ledger, group="g2", evidence="e2", dependencies=("g1",))
    assert second.status == "dependent"
    assert second.posterior == first.posterior


def test_declared_dependency_is_transitive_even_through_blocked_event():
    ledger = BayesianLedger()
    first = observe(ledger, group="g1", dependencies=("g2",))
    assert observe(ledger, group="g2", evidence="e2", dependencies=("g3",)).status == "dependent"
    assert observe(ledger, group="g3", evidence="e3").status == "dependent"
    assert ledger.beliefs["h1"] == first.posterior


def test_duplicate_source_group_alias_retains_dependence():
    ledger = BayesianLedger()
    first = observe(ledger, group="a", content="original")
    assert observe(ledger, group="b", evidence="e2", content="original").status == "duplicate"
    assert observe(ledger, group="c", evidence="e3", dependencies=("b",)).status == "dependent"
    assert ledger.beliefs["h1"] == first.posterior


def conditional_model(**kwargs):
    values = dict(model_id="conditional-t2", hypothesis_id="h1", evidence_id="e2",
                  assumption_id="test-explicit-v1", conditioning_evidence_ids=["e1"],
                  likelihood_h=.75, likelihood_not_h=.30,
                  conditioning_group_ids=["g1"], assumption_source="P(T2|H,T1)=.75, P(T2|not H,T1)=.30; synthetic chain rule",
                  reviewer_id="synthetic-reviewer", reviewed_at="2026-11-03", review_status="approved")
    values.update(kwargs)
    return ConditionalLikelihoodModel(**values)


def test_correlated_new_observation_needs_reviewed_full_history_conditional_model():
    ledger = BayesianLedger()
    first = observe(ledger)
    params = assumptions(first.posterior, .75, .30)
    # Same group with distinct actual execution evidence: independence is invalid.
    assert observe(ledger, evidence="e2", params=params).status == "dependent"
    result = observe(ledger, evidence="e2", params=params, conditional=conditional_model())
    assert result.status == "applied"
    assert result.posterior == pytest.approx(.3 * .8 * .75 / (.3 * .8 * .75 + .7 * .2 * .30))
    assert result.conditional_model_id == "conditional-t2"
    assert result.conditioning_evidence_ids == ("e1",)
    assert "independence is not assumed" in result.reason
    assert result.likelihood_h == .75
    # Exact replays remain duplicates although the current history has advanced.
    assert observe(ledger, evidence="e2", params=params, conditional=conditional_model()).status == "duplicate"


def test_valid_conditional_model_handles_both_arrival_orders_and_new_group_alias():
    ledger = BayesianLedger()
    first = observe(ledger, group="g1", dependencies=("g2",))
    result = observe(ledger, evidence="e2", group="g2", params=assumptions(first.posterior, .75, .30),
                     conditional=conditional_model())
    assert result.status == "applied"
    # An unreviewed further correlated source remains blocked after the joint update.
    blocked = observe(ledger, evidence="e3", group="g3", dependencies=("g2",))
    assert blocked.status == "dependent"
    assert blocked.posterior == result.posterior


def test_conditional_model_cannot_bypass_identical_source_or_future_unapproved_history():
    ledger = BayesianLedger()
    first = observe(ledger, content="contract")
    duplicate = observe(ledger, evidence="e2", group="g2", content="contract",
                        params=assumptions(first.posterior, .75, .30), conditional=conditional_model())
    assert duplicate.status == "duplicate"
    assert duplicate.posterior == first.posterior
    for changes in ({"conditioning_evidence_ids": ["future"]}, {"conditioning_group_ids": ["renamed"]},
                    {"conditioning_evidence_ids": ["e1", "future"]}, {"hypothesis_id": "h2"},
                    {"assumption_id": "wrong"}, {"evidence_id": "e9"},
                    {"assumption_version": 2}, {"likelihood_h": .99}, {"likelihood_not_h": .01}):
        before = ledger.snapshot()
        with pytest.raises(ValueError):
            observe(ledger, evidence="e2", group="g2", params=assumptions(first.posterior, .75, .30),
                    conditional=conditional_model(**changes))
        assert ledger.snapshot() == before


def test_conditional_model_requires_review_and_complete_prior_history():
    with pytest.raises(ValueError):
        conditional_model(review_status="draft")
    with pytest.raises(ValueError):
        conditional_model(assumption_source=" ")
    with pytest.raises(ValueError):
        conditional_model(conditioning_evidence_ids=["e1", "e1"])
    empty = BayesianLedger()
    with pytest.raises(ValueError, match="complete accepted"):
        observe(empty, evidence="e2", params=assumptions(.3, .75, .30), conditional=conditional_model())
    ledger = BayesianLedger()
    first = observe(ledger)
    observe(ledger, evidence="e3", group="g3", params=assumptions(first.posterior))
    with pytest.raises(ValueError, match="complete accepted"):
        observe(ledger, evidence="e2", params=assumptions(first.posterior, .75, .30), conditional=conditional_model())


def test_late_dependence_between_already_counted_groups_requires_replay():
    ledger = BayesianLedger()
    first = observe(ledger)
    observe(ledger, evidence="e2", group="g2", params=assumptions(first.posterior))
    previous = ledger.snapshot()
    with pytest.raises(ValueError, match="replay"):
        observe(ledger, evidence="e3", group="g3", dependencies=("g1", "g2"))
    assert ledger.snapshot() == previous


def test_stale_prior_and_impossible_event_are_atomic_failures():
    ledger = BayesianLedger()
    first = observe(ledger)
    previous = ledger.snapshot()
    with pytest.raises(ValueError, match="stale"):
        observe(ledger, evidence="e2", group="g2")
    assert ledger.snapshot() == previous
    with pytest.raises(ValueError, match="zero"):
        observe(ledger, evidence="e2", group="g2", params=assumptions(first.posterior, 0, 0))
    assert ledger.snapshot() == previous


def test_dependence_is_scoped_to_hypothesis_and_returned_state_is_immutable():
    ledger = BayesianLedger()
    observe(ledger)
    assert observe(ledger, hypothesis="h2").status == "applied"
    beliefs = ledger.beliefs
    beliefs["h1"] = 1
    assert ledger.beliefs["h1"] != 1
    assert isinstance(ledger.history, tuple)


@pytest.mark.parametrize("overrides", [
    {"approved": "yes"}, {"source_fingerprint": "not-a-hash"}, {"hypothesis_id": " "},
    {"dependent_group_ids": ["g2"]}, {"dependent_group_ids": ("",)},
])
def test_invalid_ledger_inputs_are_rejected_without_mutation(overrides):
    ledger = BayesianLedger()
    params = dict(hypothesis_id="h1", evidence_id="e1", evidence_group_id="g1",
                  source_fingerprint=sha256(b"source").hexdigest(), assumptions=assumptions(), approved=True)
    params.update(overrides)
    with pytest.raises(ValueError):
        ledger.update(**params)
    assert not ledger.beliefs
    assert not ledger.history

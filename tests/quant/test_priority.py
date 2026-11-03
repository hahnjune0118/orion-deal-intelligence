import pytest

from orion.quant.priority import ResearchPriorityPolicy, ResearchQuestion, rank_research, sensitivity_analysis


def question(identifier="q1", **kwargs):
    values = dict(question_id=identifier, materiality=4, gap=5, obtainability=4,
                  eig_bits=.24, eig_assumption_source="synthetic binary experiment",
                  days=5, external_cost_minor=50000, evidence_overlap=0,
                  review_status="approved")
    values.update(kwargs)
    return ResearchQuestion(**values)


def test_disclosed_weighted_formula_and_cost_units():
    row = rank_research([question()])[0]
    # T=1/(1+5/10+50000/100000)=0.5; all factors normalized.
    assert row.score == pytest.approx(100 * (.3 * .8 + .25 * 1 + .2 * .24 + .15 * .8 + .1 * .5))
    assert sum(row.effective_weights.values()) == pytest.approx(1)
    assert row.components["time_cost"] == .5
    assert not row.provisional


def test_high_information_does_not_automatically_beat_financial_materiality():
    high_information = question("high_info", materiality=1, gap=2, eig_bits=1)
    material = question("material", materiality=5, gap=5, eig_bits=.1)
    assert rank_research([high_information, material])[0].question_id == "material"


def test_missing_eig_is_null_and_weights_renormalize_with_explicit_fallback():
    row = rank_research([question(eig_bits=None, eig_assumption_source=None)])[0]
    assert row.components["eig"] is None
    assert row.effective_weights["eig"] == 0
    assert row.effective_weights["materiality"] == pytest.approx(.3 / .8)
    assert row.provisional
    assert "EIG_MISSING_QUALITATIVE_FALLBACK" in row.reasons


def test_time_cost_not_counted_twice_and_missing_inputs_are_flagged():
    derived = rank_research([question(obtainability_includes_cost_time=True)])[0]
    assert derived.components["time_cost"] is None
    assert not derived.provisional
    missing = rank_research([question(materiality=None, obtainability=None, days=None)])[0]
    assert missing.provisional
    assert missing.components["materiality"] == .6
    assert missing.components["obtainability"] == .4


def test_overlap_discount_and_review_filter():
    values = [question("full"), question("half", evidence_overlap=.5),
              question("all_overlap", evidence_overlap=1), question("draft", review_status="draft"),
              question("rejected", review_status="rejected"), question("resolved", resolved=True)]
    rows = rank_research(values)
    assert [row.question_id for row in rows] == ["full", "half", "all_overlap"]
    assert rows[1].score == rows[0].score / 2
    assert rows[2].score == 0


def test_deterministic_tie_order_and_duplicate_id_rejection():
    assert [r.question_id for r in rank_research([question("z"), question("a")])] == ["a", "z"]
    with pytest.raises(ValueError, match="unique"):
        rank_research([question(), question()])


def test_research_sensitivity_can_change_order_and_reports_ablation():
    values = [question("information", materiality=2, gap=4, eig_bits=.9),
              question("financial", materiality=5, gap=4, eig_bits=.1)]
    report = sensitivity_analysis(values)
    variants = {row["policy"]["label"]: row for row in report["variants"]}
    assert variants["balanced"]["top3"][0] == "financial"
    assert variants["information_first"]["top3"][0] == "information"
    assert variants["no_bayesian_eig"]["ranking"][0]["effective_weights"]["eig"] == 0
    assert report["production_scoring_version"] == "1.0.0_unchanged"


@pytest.mark.parametrize("changes", [{"materiality": 6}, {"gap": float("nan")},
                                    {"days": -1}, {"eig_bits": .2, "eig_assumption_source": None},
                                    {"evidence_overlap": 1.1}, {"materiality": True}, {"external_cost_minor": True}])
def test_invalid_research_input_rejected(changes):
    with pytest.raises(ValueError):
        question(**changes)


def test_invalid_policy_and_no_available_weight_rejected():
    with pytest.raises(ValueError, match="sum"):
        ResearchPriorityPolicy(eig_weight=.5)
    with pytest.raises(ValueError):
        ResearchPriorityPolicy(time_scale_days=0)
    only_eig = ResearchPriorityPolicy(materiality_weight=0, gap_weight=0,
                                     eig_weight=1, obtainability_weight=0, time_cost_weight=0)
    with pytest.raises(ValueError, match="no positive weight"):
        rank_research([question(eig_bits=None)], only_eig)


def test_empty_or_duplicate_sensitivity_policy_labels_rejected():
    with pytest.raises(ValueError):
        sensitivity_analysis([question()], [])
    with pytest.raises(ValueError):
        sensitivity_analysis([question()], [ResearchPriorityPolicy(), ResearchPriorityPolicy()])


def test_executed_quantitative_report_contains_real_sensitivity_and_core_invariance():
    from orion.quant.report import build_quantitative_report

    report = build_quantitative_report()
    assert report["result_kind"] == "executed_deterministic_fixture_calculations"
    assert report["model_benchmark"] == "not_run"
    assert report["ranking_changes_observed"]
    assert all(row["unchanged"] and row["before_digest"] == row["after_digest"]
               for row in report["production_no_bayes_invariance"])
    assert report["conditional_joint_example"]["unreviewed_joint_model_result"]["status"] == "dependent"
    assert report["conditional_joint_example"]["reviewed_joint_model_result"]["posterior"] == pytest.approx(30 / 37)
    assert report["null_eig_fallback"]["assumptions"][0]["eig"] is None

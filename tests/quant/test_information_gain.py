import math

import pytest

from orion.quant.information_gain import (AnswerLikelihood, binary_eig, eig_sensitivity,
                                         entropy, expected_information_gain)


def independent_mutual_information(p, a, b):
    """KL definition from a 2x2 joint table; independent of posterior/entropy code."""
    joint = ((p * a, p * (1 - a)), ((1 - p) * b, (1 - p) * (1 - b)))
    rows = (p, 1 - p)
    columns = tuple(sum(joint[r][c] for r in range(2)) for c in range(2))
    return sum(joint[r][c] * math.log2(joint[r][c] / (rows[r] * columns[c]))
               for r in range(2) for c in range(2) if joint[r][c])


def test_blueprint_eig_against_independent_joint_mutual_information():
    result = binary_eig(.3, .8, .2, "Blueprint illustrative, explicitly synthetic")
    assert result.eig_bits == pytest.approx(independent_mutual_information(.3, .8, .2), abs=1e-15)
    assert result.eig_bits == pytest.approx(.236113927338937, abs=1e-14)
    assert result.answers[0].probability == pytest.approx(.38)
    assert result.answers[0].posterior == pytest.approx(12 / 19)
    assert result.answers[1].posterior == pytest.approx(3 / 31)


@pytest.mark.parametrize("p", [0, .01, .3, .5, .9, 1])
def test_perfect_test_extracts_all_prior_entropy(p):
    assert binary_eig(p, 1, 0, "synthetic").eig_bits == pytest.approx(entropy(p))


@pytest.mark.parametrize("p,a,b", [(0, .8, .2), (1, .8, .2), (.3, .6, .6), (.5, 0, 0), (.5, 1, 1)])
def test_zero_information_and_impossible_answer_handling(p, a, b):
    result = binary_eig(p, a, b, "synthetic")
    assert result.eig_bits == pytest.approx(0, abs=1e-14)
    assert math.fsum(x.probability for x in result.answers) == pytest.approx(1)
    for answer in result.answers:
        if answer.probability == 0:
            assert answer.posterior is None
            assert answer.entropy_bits is None


def test_three_answer_exhaustive_model():
    answers = [AnswerLikelihood(answer=label, likelihood_h=a, likelihood_not_h=b)
               for label, a, b in [("positive", .6, .1), ("neutral", .3, .4), ("negative", .1, .5)]]
    result = expected_information_gain(.4, answers, "authored ternary answer scenario")
    assert math.fsum(x.probability for x in result.answers) == pytest.approx(1)
    assert 0 < result.eig_bits < entropy(.4)


@pytest.mark.parametrize("args", [(None, .8, .2, "source"), (.3, None, .2, "source"),
                                  (.3, .8, None, "source"), (.3, .8, .2, None), (.3, .8, .2, " ")])
def test_missing_probability_or_source_returns_null(args):
    assert binary_eig(*args) is None


@pytest.mark.parametrize("answers", [[], [(.8, .2)], [(.8, .2), (.3, .8)], [(.8, .2), (.2, .9)]])
def test_incomplete_or_excess_answer_mass_rejected(answers):
    items = [AnswerLikelihood(answer=str(i), likelihood_h=a, likelihood_not_h=b) for i, (a, b) in enumerate(answers)]
    with pytest.raises(ValueError):
        expected_information_gain(.3, items, "source")


def test_duplicate_answer_labels_and_forged_model_rejected():
    answer = AnswerLikelihood(answer="same", likelihood_h=.5, likelihood_not_h=.5)
    with pytest.raises(ValueError, match="unique"):
        expected_information_gain(.3, [answer, answer], "source")
    forged = AnswerLikelihood.model_construct(answer="bad", likelihood_h=float("nan"), likelihood_not_h=.5)
    with pytest.raises(ValueError):
        expected_information_gain(.3, [forged], "source")


@pytest.mark.parametrize("value", [-.01, 1.01, float("nan"), float("inf"), True, "0.5"])
def test_entropy_rejects_nonprobabilities(value):
    with pytest.raises(ValueError):
        entropy(value)


def test_prior_sensitivity_discloses_assumptions_and_varies_eig():
    rows = eig_sensitivity([.1, .3, .5], .8, .2, "synthetic prior sensitivity")
    assert [row["prior"] for row in rows] == [.1, .3, .5]
    assert rows[0]["eig_bits"] < rows[1]["eig_bits"] < rows[2]["eig_bits"]
    with pytest.raises(ValueError):
        eig_sensitivity([.3], .8, .2, "")

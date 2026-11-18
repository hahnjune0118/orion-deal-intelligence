"""Charts reflect trusted records and preserve engine values."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from plotly.utils import PlotlyJSONEncoder

from orion.services.web_workspace import WebWorkspace
from orion.web.layout import render_page
from orion.web.visuals import score_waterfall, distribution, probability_waterfall


@pytest.fixture(scope="module")
def workspace():
    return WebWorkspace(Path(__file__).resolve().parents[2], "visual-tests-only-secret-32-characters")


@pytest.mark.parametrize("case", ["nb", "mf", "lm"])
def test_all_pages_preserve_trusted_view(workspace, case):
    token = workspace.new(case, "visual-session-123456789012345678901234567890")
    view = workspace.view(token, "visual-session-123456789012345678901234567890")
    before = deepcopy(view)
    for page in ["evidence", "thesis", "questions", "review", "analytics", "export"]:
        rendered = render_page(page, view)
        serialized = json.dumps(rendered, cls=PlotlyJSONEncoder, ensure_ascii=False)
        assert "시각 분석" in serialized
        assert "visual-panel" in serialized
    assert view == before
    for question in view["questions"]:
        if question["score"] is not None:
            chart = score_waterfall(question).figure.data[0]
            assert sum(chart.y[:3]) == pytest.approx(float(question["score"]))
            assert chart.y[3] == float(question["score"])


def test_distribution_conserves_records_and_missing_probability_is_not_zero():
    records = [{"support_status": "missing"}, {"support_status": "supported"}, {"support_status": "supported"}]
    chart = distribution("test-distribution", records, "support_status")
    assert sum(chart.figure.data[0].values) == len(records)
    empty = json.dumps(probability_waterfall({}), cls=PlotlyJSONEncoder, ensure_ascii=False)
    assert "승인된 확률 업데이트가 없습니다" in empty
    assert "waterfall" not in empty


def test_probability_waterfall_matches_single_approved_update(workspace):
    token = workspace.new("nb", "belief-session-123456789012345678901234567890")
    view = workspace.view(token, "belief-session-123456789012345678901234567890")
    event = next(e for e in view["events"] if e["available"])
    result = workspace.act(token, "belief-session-123456789012345678901234567890", action="approve", event_id=event["id"],
                           expected_revision=view["revision"], idempotency_key="visual-belief-1", reason="Review original evidence.")
    updated = workspace.view(result["token"], "belief-session-123456789012345678901234567890")
    belief = updated["analytics"]["belief_snapshots"][-1]
    component = probability_waterfall(updated)
    values = component.children[1].figure.data[0].y
    assert values[0] + values[1] == pytest.approx(belief["posterior"])
    assert values[2] == pytest.approx(belief["posterior"])

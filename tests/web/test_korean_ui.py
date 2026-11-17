"""Presentation translations preserve source text and machine-readable values."""
import json

from plotly.utils import PlotlyJSONEncoder

from orion.web.callbacks import safe_error
from orion.web.layout import (CASE_OPTIONS, FORMAT_OPTIONS, change_grid, column, grid, human,
                              metadata_value, render_span, render_thesis)


def test_labels_do_not_replace_selection_values_or_grid_records():
    assert [item["value"] for item in CASE_OPTIONS] == ["nb", "mf", "lm"]
    assert [item["value"] for item in FORMAT_OPTIONS] == ["dd_xlsx", "dd_csv", "evidence_csv", "memo_docx", "memo_md"]
    rows = [{"id": "evidence_test", "review_status": "approved", "statement": "Original English source."}]
    component = grid("evidence-grid", rows, [column("review_status", "검토")])
    assert component.rowData == rows
    assert component.getRowId == "params.data.id"
    assert component.columnDefs[0]["valueFormatter"]["function"] == "orionKoreanValue(params)"
    assert "tooltipField" not in component.columnDefs[0]
    assert component.columnDefs[0]["tooltipValueGetter"]["function"] == "orionKoreanValue(params)"
    assert component.columnDefs[0]["useValueFormatterForExport"] is False
    assert component.dashGridOptions["context"]["displayLabels"]["approved"] == "승인"
    assert component.dashGridOptions["localeText"]["noRowsToShow"] == "표시할 행이 없습니다"


def test_source_excerpt_and_unknown_identifiers_remain_verbatim():
    span = {"id": "span_original_id", "filename": "source.docx", "quote": "Original company claim.",
            "prefix": "Before. ", "suffix": " After.", "text_sha256": "a" * 64}
    component = render_span(span)
    excerpt = component.children[3]
    assert excerpt.children[0] == span["prefix"]
    assert excerpt.children[1].children == span["quote"]
    assert excerpt.children[2] == span["suffix"]
    assert human("span_original_id") == "span_original_id"
    assert "원문 무결성" in json.dumps(component, cls=PlotlyJSONEncoder, ensure_ascii=False)


def test_errors_are_korean_and_never_expose_exception_details():
    class Error(ValueError):
        code = "REVISION_CONFLICT"
    assert safe_error(Error("private source")) == "REVISION_CONFLICT: 스냅샷이 변경되었습니다. 현재 리비전을 검토한 뒤 다시 시도하세요."
    assert "요청이 거부되었습니다" in safe_error(ValueError("private source"))
    assert "private source" not in safe_error(ValueError("private source"))


def test_metadata_translates_only_typed_statuses_and_preserves_source_collisions():
    assert metadata_value("review_status", "approved") == "승인"
    for key in ("id", "criterion_keys", "label", "heading_path", "quote", "rationale", "filename"):
        assert metadata_value(key, "company") == "company"
        assert metadata_value(key, ["positive", "open"]) == "positive; open"
    assert metadata_value("requirements", [{"key": "open", "label": "company"}]) == "키: open; 이름: company"
    span = {"quote": "positive", "prefix": "company", "suffix": "open",
            "locator": {"kind": "docx_paragraph", "heading_path": ["company", "open"]}}
    component = render_span(span)
    assert "company; open" in component.children[2].children
    assert component.children[3].children[1].children == "positive"


def test_thesis_and_ranking_rows_keep_raw_values_for_formatters():
    thesis = {"id": "thesis_test", "claims_summary": "company", "verification_requirements": "open",
              "financial_drivers": "revenue_quality", "evidence_status": "supported", "question_ids": ["question_test"]}
    assert render_thesis({"theses": [thesis]}).children[2].rowData == [thesis]
    change = {"question_id": "question_test", "reason": "CRITERIA_SATISFIED"}
    component = change_grid({"changes": [change]})
    assert component.rowData[0]["reason_codes"] == "CRITERIA_SATISFIED"
    assert change == {"question_id": "question_test", "reason": "CRITERIA_SATISFIED"}

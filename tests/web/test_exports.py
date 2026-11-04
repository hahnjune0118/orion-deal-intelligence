"""Native source integrity, export approval boundaries and output semantics."""
from io import BytesIO, StringIO
from pathlib import Path
import csv

import pytest

from orion.config import BoundaryError
from orion.domain.grounding import canonical_hash
from orion.domain.models import AnalystDecision
from orion.domain.scoring import build_snapshot
from orion.domain.transitions import apply_approved_update
from orion.services.export import ExportService, _safe_cell
from orion.services.workspace import ActorContext
from orion.synthetic.load import load_scenario


ROOT = Path(__file__).resolve().parents[2]
ACTOR = ActorContext("actor_web_reviewer", "reviewer")
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def native():
    return load_scenario(ROOT / "chunk3_synthetic_evaluation", "nb")


@pytest.fixture
def service():
    return ExportService("test-export-secret-at-least-32-bytes", clock=lambda: "2026-11-04T00:00:00Z")


def approval(service, native, format="all", question_ids=None):
    state, _, resolver = native
    return service.approve(state, resolver, actor=ACTOR, session_id="session-a",
                           reason="Reviewed current synthetic scope", format=format, question_ids=question_ids)


def test_csv_xlsx_have_identical_approved_rows_and_typed_scores(service, native):
    from openpyxl import load_workbook
    state, _, resolver = native
    head = next(s for s in state.ranking_snapshots if s.id == state.head_snapshot_id)
    selected = [head.rows[2].question_id, head.rows[0].question_id]
    token = approval(service, native, question_ids=selected)
    csv_artifact = service.generate(state, resolver, token, session_id="session-a", format="dd_csv")
    xlsx_artifact = service.generate(state, resolver, token, session_id="session-a", format="dd_xlsx")
    csv_rows = list(csv.reader(StringIO(csv_artifact.content.decode("utf-8-sig"))))
    assert csv_rows[0][:15] == ["rank", "question_id", "issue", "request_text", "financial_driver", "gap",
        "materiality", "obtainability", "score", "provisional", "workflow_status", "owner_label",
        "source_references", "unresolved_notes", "snapshot_id"]
    workbook = load_workbook(BytesIO(xlsx_artifact.content), data_only=False)
    sheet = workbook["DD Requests"]
    excel_rows = list(sheet.iter_rows(min_row=6, values_only=True))
    assert csv_rows == [["" if value is None else str(value) for value in row] for row in excel_rows]
    assert csv_rows[1][1] == head.rows[0].question_id
    assert csv_rows[2][1] == head.rows[2].question_id
    assert isinstance(sheet["I7"].value, (int, float))
    assert sheet["I7"].value == head.rows[0].score
    assert sheet.freeze_panes == "E7"
    assert all(cell.data_type != "f" for row in sheet for cell in row)
    assert xlsx_artifact.content == service.generate(state, resolver, token, session_id="session-a", format="dd_xlsx").content


@pytest.mark.parametrize("format", ["dd_csv", "dd_xlsx", "evidence_csv", "memo_md", "memo_docx"])
def test_all_formats_generate_with_audit_receipts_without_mutating_state(service, native, format):
    state, _, resolver = native
    before = state.model_dump(mode="json")
    artifact = service.generate(state, resolver, approval(service, native, format), session_id="session-a", format=format)
    assert artifact.content
    assert artifact.filename.startswith("deal_nb_")
    assert "/" not in artifact.filename and "\\" not in artifact.filename
    assert artifact.decision.target_id == state.head_snapshot_id
    assert artifact.decision.actor_role == "reviewer"
    assert [event.event_type for event in artifact.audit_events] == ["export_approved", "exported"]
    assert artifact.audit_events[1].previous_hash == artifact.audit_events[0].event_hash
    for event in artifact.audit_events:
        raw = event.model_dump(mode="json")
        assert raw.pop("event_hash") == canonical_hash(raw)
    assert before == state.model_dump(mode="json")


def test_evidence_export_uses_exact_current_quotes_and_excludes_future_sources(service, native):
    state, _, resolver = native
    artifact = service.generate(state, resolver, approval(service, native, "evidence_csv"), session_id="session-a", format="evidence_csv")
    rows = list(csv.DictReader(StringIO(artifact.content.decode("utf-8-sig"))))
    evidence = {e.id: e for e in state.evidence}
    spans = {s.id: s for s in state.source_spans}
    assert len(rows) == len(evidence)
    for row in rows:
        original = evidence[row["Evidence ID"]]
        assert row["Exact source excerpts"] == "\n".join(spans[sid].quote for sid in original.source_span_ids)
        assert row["Review status"] == original.review_status
        assert row["Verification level"] == original.verification_level
    assert b"nb_doc_contract" not in artifact.content
    assert b"nb_doc_followup" not in artifact.content


def test_memo_keeps_uncertainty_and_document_statuses(service, native):
    from docx import Document
    state, _, resolver = native
    md = service.generate(state, resolver, approval(service, native, "memo_md"), session_id="session-a", format="memo_md").content.decode()
    document = service.generate(state, resolver, approval(service, native, "memo_docx"), session_id="session-a", format="memo_docx")
    text = "\n".join(p.text for p in Document(BytesIO(document.content)).paragraphs)
    for value in ("not a completed FDD report", "no live LLM calls", "document_only", "company_reported", "Counter-thesis", "Export receipt", "Evidence update and approval history"):
        assert value in md
        assert value in text
    assert "nb_doc_followup" not in md


@pytest.mark.parametrize("token", [None, "", "forged.approval", "not-a-token"])
def test_unsigned_or_missing_approval_rejected(service, native, token):
    state, _, resolver = native
    with pytest.raises(BoundaryError, match="valid export approval"):
        service.generate(state, resolver, token, session_id="session-a", format="dd_csv")


def test_session_binding_and_signed_payload_tampering(service, native):
    state, _, resolver = native
    token = approval(service, native)
    with pytest.raises(BoundaryError):
        service.generate(state, resolver, token, session_id="session-b", format="dd_csv")
    body, signature = token.split(".")
    altered = ("A" if body[0] != "A" else "B") + body[1:] + "." + signature
    with pytest.raises(BoundaryError):
        service.generate(state, resolver, altered, session_id="session-a", format="dd_csv")


def test_format_is_bound_to_approval(service, native):
    state, _, resolver = native
    token = approval(service, native, "memo_md")
    with pytest.raises(BoundaryError, match="format was not approved"):
        service.generate(state, resolver, token, session_id="session-a", format="dd_csv")
    all_token = approval(service, native)
    with pytest.raises(BoundaryError):
        service.generate(state, resolver, all_token, session_id="session-a", format="memo_docx")
    with pytest.raises(BoundaryError):
        service.generate(state, resolver, all_token, session_id="session-a", format="../../secret")


def test_approved_update_invalidates_export_approval(service, native):
    state, events, resolver = native
    token = approval(service, native)
    event = events[0]
    decision = AnalystDecision(id="decision_export_test_t1", entity_version=1, deal_id=state.deal.id,
        actor_id=ACTOR.actor_id, actor_role=ACTOR.role, target_type="evidence_update", target_id=event.id,
        target_version=1, selection_digest=None, action="approve", reason="Synthetic approval",
        base_revision=state.state_revision, decided_at=event.created_at)
    changed = apply_approved_update(state, event, decision=decision, snapshot_id="snapshot_export_test_t1",
                                    now=event.created_at, source_resolver=resolver)
    with pytest.raises(BoundaryError) as caught:
        service.generate(changed, resolver, token, session_id="session-a", format="dd_csv")
    assert caught.value.code in {"EXPORT_APPROVAL_STALE", "EXPORT_SELECTION_INVALID"}


def test_export_requires_trusted_reviewer_and_native_source(service, native):
    state, _, resolver = native
    for actor in (ActorContext("actor_analyst", "analyst"), {"actor_id": "actor_forged", "role": "reviewer"}):
        with pytest.raises(ValueError):
            service.approve(state, resolver, actor=actor, session_id="session-a", reason="reviewed")
    with pytest.raises(BoundaryError):
        service.approve(state, None, actor=ACTOR, session_id="session-a", reason="reviewed")
    with pytest.raises(BoundaryError):
        service.approve(state, resolver, actor=ACTOR, session_id="session-a", reason=" ")
    with pytest.raises(BoundaryError):
        approval(service, native, question_ids=["not_a_question"])


@pytest.mark.parametrize("value", ["=SUM(1,1)", "+cmd", "-1+2", "@SUM(A1)", "  =formula", "\tformula", "\nformula", "\ufeff=1"])
def test_formula_injection_prefixes_are_escaped(value):
    assert _safe_cell(value) == "'" + value


def test_numeric_values_and_normal_text_keep_types():
    assert _safe_cell(97) == 97
    assert _safe_cell(0.5) == 0.5
    assert _safe_cell("Aster contract") == "Aster contract"


def test_formula_looking_question_text_is_literal_in_both_exports(service, native):
    from openpyxl import load_workbook
    state, _, resolver = native
    state = state.model_copy(deep=True)
    target = state.dd_questions[0]
    target.issue = '=HYPERLINK("https://invalid.example","click")'
    target.owner_label = "\t=1+1"
    head = next(s for s in state.ranking_snapshots if s.id == state.head_snapshot_id)
    replacement = build_snapshot(state, head.id, head.created_at, source_resolver=resolver)
    state.ranking_snapshots = [replacement if s.id == head.id else s for s in state.ranking_snapshots]
    token = service.approve(state, resolver, actor=ACTOR, session_id="session-a",
                            question_ids=[target.id], reason="Review literal formula-looking fixture")
    csv_artifact = service.generate(state, resolver, token, session_id="session-a", format="dd_csv")
    rows = list(csv.DictReader(StringIO(csv_artifact.content.decode("utf-8-sig"))))
    assert rows[0]["issue"] == "'" + target.issue
    assert rows[0]["owner_label"] == "'" + target.owner_label
    xlsx_artifact = service.generate(state, resolver, token, session_id="session-a", format="dd_xlsx")
    sheet = load_workbook(BytesIO(xlsx_artifact.content))["DD Requests"]
    assert sheet["C7"].data_type == "s" and sheet["C7"].value.startswith("'=")
    assert sheet["L7"].data_type == "s" and sheet["L7"].value.startswith("'\t=")


def test_forged_source_quote_cannot_be_exported(service, native):
    state, _, resolver = native
    forged = state.model_copy(deep=True)
    forged.source_spans[0].quote += " forged"
    with pytest.raises(ValueError):
        service.approve(forged, resolver, actor=ACTOR, session_id="session-a", reason="Attempted forgery")

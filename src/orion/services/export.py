"""Snapshot-bound, reviewer-approved exports from validated server state.

This module never accepts browser-supplied rows, passages, scores or paths.
Approval receipts are signed and session-bound. The canonical DealState is
unchanged; returned decision/audit receipts describe the synthetic export.
"""
from __future__ import annotations

import base64
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
from io import BytesIO, StringIO
import json
import math
from typing import Callable
from uuid import uuid4
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from orion.config import BoundaryError
from orion.domain.grounding import canonical_hash
from orion.domain.models import AnalystDecision, AuditEvent, DealState
from orion.domain.scoring import evaluate_requirements
from orion.domain.transitions import assert_current_state
from orion.services.workspace import ActorContext, require_actor


FORMATS = {
    "dd_csv": ("csv", "text/csv; charset=utf-8"),
    "dd_xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "evidence_csv": ("csv", "text/csv; charset=utf-8"),
    "memo_md": ("md", "text/markdown; charset=utf-8"),
    "memo_docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}
_FORMAT_CONTRACT = {"dd_csv": "csv", "dd_xlsx": "xlsx", "memo_md": "markdown",
                    "memo_docx": "docx", "evidence_csv": "evidence_csv", "all": "all"}
_ALL_FORMATS = frozenset({"dd_csv", "dd_xlsx", "memo_md"})
_SCOPE = {"questions": "selected_current_ranked_questions", "evidence": "current_workspace",
          "theses": "current_workspace", "screen_sort": "canonical_rank"}
_NOTICE = ("Preliminary investment screening based on fictional synthetic information. "
           "This is not a completed FDD report, investment recommendation or real analyst sign-off. "
           "Export approval authorizes this document and does not independently verify its findings.")
_LIMITS = (
    "The deterministic demo uses authored synthetic records and makes no live LLM calls.",
    "A validated quotation establishes what a document reports; it does not establish real-world truth.",
    "Financial drivers and materiality are qualitative rubric mappings unless a source explicitly supplies a numerical input. No DCF, valuation sensitivity or EVSI is calculated.",
    "Canonical priority is 9 × evidence gap + 8 × materiality + 3 × obtainability. Bayesian probabilities and information gain, when shown in the workbench, are separate hypothetical analyses and do not change this score.",
    "Draft, rejected, disputed and company-reported items retain their labels. No preliminary finding is promoted to an independently verified conclusion by exporting it.",
)


@dataclass(frozen=True)
class ExportArtifact:
    filename: str
    mime_type: str
    content: bytes
    decision: AnalystDecision
    audit_events: tuple[AuditEvent, ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _safe_cell(value):
    """Escape spreadsheet formula prefixes, including whitespace-obscured ones."""
    if isinstance(value, str):
        stripped = value.lstrip(" \t\r\n\ufeff")
        if value.startswith(("\t", "\r", "\n")) or (stripped and stripped[0] in "=+-@"):
            return "'" + value
    return value


def locator_text(span) -> str:
    locator = span.locator.model_dump(mode="json")
    kind = locator.pop("kind")
    return kind + ": " + ", ".join(f"{key}={_json(value) if isinstance(value, (list,dict)) else value}"
                                      for key, value in locator.items())


def _source_refs(state: DealState, span_ids) -> str:
    spans = {span.id: span for span in state.source_spans}
    docs = {doc.id: doc for doc in state.documents}
    return "\n".join(f"{spans[sid].id} | {docs[spans[sid].document_id].filename} v{spans[sid].document_version} | {locator_text(spans[sid])}"
                     for sid in dict.fromkeys(span_ids))


def _selected(state: DealState, question_ids) -> list[str]:
    head = next(row for row in state.ranking_snapshots if row.id == state.head_snapshot_id)
    ranked = [row.question_id for row in head.rows]
    if question_ids is None:
        return ranked
    if type(question_ids) is not list or any(type(item) is not str for item in question_ids):
        raise BoundaryError("EXPORT_SELECTION_INVALID", "Question selection must contain only current question IDs.")
    if len(question_ids) != len(set(question_ids)) or not set(question_ids).issubset(ranked):
        raise BoundaryError("EXPORT_SELECTION_INVALID", "Only unique current ranked questions may be selected.")
    return [qid for qid in ranked if qid in question_ids]


def _validate_state(state: DealState, resolver) -> DealState:
    if not isinstance(state, DealState) or resolver is None:
        raise BoundaryError("EXPORT_SOURCE_REQUIRED", "A native-validated server workspace is required.")
    fresh = DealState.model_validate(state.model_dump(mode="json"))
    if any(doc.asset_status != "file_verified" or doc.parse_status != "parsed" for doc in fresh.documents):
        raise BoundaryError("EXPORT_SOURCE_REQUIRED", "All included documents require validated native sources.")
    assert_current_state(fresh, source_resolver=resolver)
    return fresh


def _selection_digest(state: DealState, question_ids: list[str], format: str) -> str:
    head = next(row for row in state.ranking_snapshots if row.id == state.head_snapshot_id)
    return canonical_hash(dict(snapshot_id=head.id, snapshot_input_digest=head.input_digest,
                               included_question_ids=sorted(question_ids),
                               export_format=_FORMAT_CONTRACT[format], normalized_filters=_SCOPE))


def _audit(state: DealState, decision: AnalystDecision, event_type: str, previous: AuditEvent | None) -> AuditEvent:
    token = canonical_hash({"decision_id": decision.id, "event_type": event_type})[:24]
    payload = dict(id=f"audit_export_{token}", entity_version=1, deal_id=state.deal.id,
                   sequence=(previous.sequence + 1) if previous else 1, event_type=event_type,
                   actor_id=decision.actor_id, decision_id=decision.id,
                   before_revision=state.state_revision, after_revision=state.state_revision,
                   idempotency_key=f"export:{decision.id}:{event_type}",
                   before_snapshot_id=state.head_snapshot_id, after_snapshot_id=state.head_snapshot_id,
                   reason=("Synthetic reviewer approved current snapshot and selected export scope."
                           if event_type == "export_approved" else "Approved synthetic export generated."),
                   created_at=decision.decided_at, previous_hash=previous.event_hash if previous else None)
    return AuditEvent.model_validate({**payload, "event_hash": canonical_hash(payload)})


class ExportService:
    """A server-owned signer. Never instantiate with a browser-provided secret."""

    def __init__(self, signing_secret: str | bytes, *, clock: Callable[[], str] = _utc_now):
        key = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
        if not isinstance(key, bytes) or len(key) < 16:
            raise ValueError("Export signing secret must have at least 16 bytes")
        self._key = key
        self._clock = clock

    def approve(self, state: DealState, source_resolver, *, actor: ActorContext, session_id: str,
                question_ids: list[str] | None = None, reason: str,
                format: str = "all") -> str:
        require_actor(actor, reviewer=True)
        if format not in _FORMAT_CONTRACT:
            raise BoundaryError("EXPORT_FORMAT_INVALID", "Unsupported export format.")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise BoundaryError("EXPORT_APPROVAL_REQUIRED", "A meaningful export review reason is required.")
        if not isinstance(session_id, str) or not session_id:
            raise BoundaryError("EXPORT_APPROVAL_REQUIRED", "A server session is required.")
        state = _validate_state(state, source_resolver)
        selected = _selected(state, question_ids)
        decision = AnalystDecision(id=f"decision_export_{uuid4().hex}", entity_version=1,
            deal_id=state.deal.id, actor_id=actor.actor_id, actor_role=actor.role,
            target_type="snapshot_export", target_id=state.head_snapshot_id, target_version=1,
            selection_digest=_selection_digest(state, selected, format), action="approve",
            reason=reason.strip(), base_revision=state.state_revision, decided_at=self._clock())
        payload = dict(version=1, session_id=session_id, state_digest=canonical_hash(state.model_dump(mode="json")),
                       question_ids=selected, format=format, decision=decision.model_dump(mode="json"))
        body = base64.urlsafe_b64encode(_json(payload).encode()).rstrip(b"=")
        signature = hmac.new(self._key, b"orion-export-v1." + body, hashlib.sha256).hexdigest()
        return body.decode("ascii") + "." + signature

    def _approval(self, state, source_resolver, token, session_id, format):
        if format not in FORMATS:
            raise BoundaryError("EXPORT_FORMAT_INVALID", "Unsupported export format.")
        try:
            if not isinstance(token, str) or len(token) > 100_000:
                raise ValueError()
            body, signature = token.rsplit(".", 1)
            expected = hmac.new(self._key, b"orion-export-v1." + body.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError()
            raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
            payload = json.loads(raw)
            if type(payload) is not dict or set(payload) != {"version", "session_id", "state_digest", "question_ids", "format", "decision"}:
                raise ValueError()
            if type(payload["version"]) is not int or payload["version"] != 1 or payload["session_id"] != session_id:
                raise ValueError()
            decision = AnalystDecision.model_validate(payload["decision"])
        except Exception as exc:
            raise BoundaryError("EXPORT_APPROVAL_REQUIRED", "A valid export approval for this session is required.") from exc
        state = _validate_state(state, source_resolver)
        signed_format = payload["format"]
        if signed_format not in _FORMAT_CONTRACT or not (signed_format == format or signed_format == "all" and format in _ALL_FORMATS):
            raise BoundaryError("EXPORT_SELECTION_MISMATCH", "This export format was not approved.")
        if (payload["state_digest"] != canonical_hash(state.model_dump(mode="json"))
                or decision.target_id != state.head_snapshot_id or decision.base_revision != state.state_revision
                or decision.deal_id != state.deal.id):
            raise BoundaryError("EXPORT_APPROVAL_STALE", "The workspace changed. Review the current snapshot before exporting.")
        selected = _selected(state, payload["question_ids"])
        if (decision.action != "approve" or decision.actor_role != "reviewer" or decision.target_type != "snapshot_export"
                or decision.selection_digest != _selection_digest(state, selected, signed_format)):
            raise BoundaryError("EXPORT_SELECTION_MISMATCH", "The export selection differs from its approval.")
        return state, selected, decision

    def generate(self, state: DealState, source_resolver, approval_token: str, *, session_id: str,
                 format: str) -> ExportArtifact:
        state, selected, decision = self._approval(state, source_resolver, approval_token, session_id, format)
        prior = max(state.audit_events, key=lambda event: event.sequence, default=None)
        approved = _audit(state, decision, "export_approved", prior)
        exported = _audit(state, decision, "exported", approved)
        report = _report(state, selected, decision, (approved, exported))
        if format == "dd_csv":
            content = _csv(report["question_headers"], report["question_rows"])
        elif format == "evidence_csv":
            content = _csv(report["evidence_headers"], report["evidence_rows"])
        elif format == "dd_xlsx":
            content = _xlsx(report)
        elif format == "memo_docx":
            content = _docx(report)
        else:
            content = _markdown(report).encode("utf-8")
        extension, mime = FORMATS[format]
        name = f"{state.deal.id}_{format}_r{state.state_revision}.{extension}"
        return ExportArtifact(name, mime, content, decision, (approved, exported))


def _report(state, selected, decision, audit):
    head = next(row for row in state.ranking_snapshots if row.id == state.head_snapshot_id)
    questions = {question.id: question for question in state.dd_questions}
    claims = {claim.id: claim for claim in state.claims}
    rows = []
    for scored in head.rows:
        if scored.question_id not in selected:
            continue
        question = questions[scored.question_id]
        span_ids = [*claims[question.claim_id].source_span_ids, *question.materiality.source_span_ids]
        for evidence in state.evidence:
            if evidence.claim_id == question.claim_id:
                span_ids.extend(evidence.source_span_ids)
        assessment = evaluate_requirements(state, question.claim_id, question.requirements)
        missing = sorted({requirement.key for requirement in question.requirements} - assessment.credited_keys)
        unresolved = []
        if missing:
            unresolved.append("Missing qualifying evidence: " + ", ".join(missing))
        if assessment.conflict_keys:
            unresolved.append("Conflicting evidence: " + ", ".join(sorted(assessment.conflict_keys)))
        rows.append([scored.rank, question.id, question.issue, question.request_text,
                     question.financial_driver, scored.gap, scored.materiality, scored.obtainability,
                     scored.score, scored.provisional, question.workflow_status, question.owner_label,
                     _source_refs(state, span_ids), "; ".join(unresolved), head.id,
                     question.review_status, question.claim_id, question.materiality.rationale,
                     question.obtainability.rationale])
    evidence_rows = []
    spans = {span.id: span for span in state.source_spans}
    for evidence in state.evidence:
        evidence_rows.append([evidence.id, evidence.claim_id, claims[evidence.claim_id].statement,
            evidence.stance, evidence.provenance, evidence.review_status, evidence.lifecycle,
            evidence.verification_level, evidence.source_reliability, evidence.reliability_rationale,
            "; ".join(evidence.criterion_keys), _source_refs(state, evidence.source_span_ids),
            "\n".join(spans[sid].quote for sid in evidence.source_span_ids)])
    return dict(state=state, decision=decision, audit=audit, snapshot=head, selected=selected,
        question_headers=["rank", "question_id", "issue", "request_text", "financial_driver",
                          "gap", "materiality", "obtainability", "score", "provisional",
                          "workflow_status", "owner_label", "source_references", "unresolved_notes", "snapshot_id",
                          "review_status", "claim_id", "materiality_rationale", "obtainability_rationale"], question_rows=rows,
        evidence_headers=["Evidence ID", "Claim ID", "Claim", "Stance", "Provenance", "Review status",
                          "Lifecycle", "Verification level", "Reliability", "Reliability rationale",
                          "Criteria", "Source references", "Exact source excerpts"], evidence_rows=evidence_rows)


def _csv(headers, rows) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    def cell(value):
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return _safe_cell(value)
    writer.writerows([cell(value) for value in row] for row in rows)
    return stream.getvalue().encode("utf-8-sig")


def _canonical_ooxml(content: bytes) -> bytes:
    result = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(result, "w", compression=ZIP_DEFLATED) as dest:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, (2026, 11, 4, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            dest.writestr(info, source.read(name))
    return result.getvalue()


def _xlsx(report) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
    state, decision = report["state"], report["decision"]
    book = Workbook()
    book.properties.creator = "Orion synthetic DD workbench"
    book.properties.created = datetime.fromisoformat(decision.decided_at.replace("Z", "+00:00")).replace(tzinfo=None)
    book.properties.modified = book.properties.created
    sheet = book.active
    sheet.title = "DD Requests"
    sheet.sheet_view.showGridLines = False
    sheet.append([f"{state.deal.name} DD Request List"])
    sheet.append(["Synthetic preliminary screening. Export approval does not verify the underlying findings."])
    sheet.append([f"As of {state.deal.as_of} | Revision {state.state_revision} | Snapshot {state.head_snapshot_id}"])
    sheet.append([f"Export reviewer {decision.actor_id} | {decision.decided_at} | Selected questions {len(report['selected'])}"])
    sheet.append([])
    sheet.append(report["question_headers"])
    for row in report["question_rows"]:
        sheet.append([_safe_cell(value) for value in row])
    widths = [9, 27, 40, 65, 25, 16, 16, 17, 17, 18, 18, 24, 100, 55, 34, 18, 27, 55, 55]
    for col, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(col)].width = width
    for row in sheet:
        for cell in row:
            cell.font = Font(name="Calibri", size=11, color="172B3A")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if isinstance(cell.value, str):
                cell.data_type = "s"
    for row in range(1, 5):
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(widths))
        sheet.row_dimensions[row].height = 30 if row == 1 else 24
    sheet["A1"].font = Font(name="Calibri", size=18, bold=True, color="172B3A")
    sheet.row_dimensions[6].height = 34
    for cell in sheet[6]:
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="172B3A")
    for index, row in enumerate(report["question_rows"], 7):
        line_count = max(sum(max(1, math.ceil(len(line) / max(8, widths[col] - 3)))
                             for line in str(value or "").split("\n")) for col, value in enumerate(row))
        sheet.row_dimensions[index].height = min(409, max(60, line_count * 16))
        for column in (1, 6, 7, 8, 9):
            value = sheet.cell(index, column).value
            sheet.cell(index, column).number_format = "0" if float(value).is_integer() else "0.00"
    if report["question_rows"]:
        table = Table(displayName="DDRequests", ref=f"A6:{get_column_letter(len(widths))}{sheet.max_row}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(table)
    sheet.freeze_panes = "E7"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = "1:6"
    raw = BytesIO()
    book.save(raw)
    return _canonical_ooxml(raw.getvalue())


def _memo_blocks(report):
    state, decision, snapshot = report["state"], report["decision"], report["snapshot"]
    blocks = [("title", f"{state.deal.name} Preliminary Investment Screening"), ("p", _NOTICE),
        ("h", "Company and review scope"),
        ("p", f"{state.deal.name} operates in {state.deal.business_model}. Source pack as of {state.deal.as_of}; reporting currency {state.deal.currency}. All entities and source records are synthetic."),
        ("p", f"Revision {state.state_revision}; snapshot {snapshot.id}; scoring version {snapshot.scoring_version}. Export reviewer {decision.actor_id} approved {len(report['selected'])} ranked questions on {decision.decided_at}. Review reason: {decision.reason}"),
        ("h", "Highest priority diligence requests")]
    for row in report["question_rows"][:5]:
        blocks.extend([("h2", f"Rank {row[0]}  {row[2]}"),
            ("p", f"{row[1]} | Score {row[8]} | Gap {row[5]} | Materiality {row[6]} | Obtainability {row[7]} | Provisional {row[9]} | Review {row[15]} | Workflow {row[10]}"),
            ("p", row[3]), ("p", f"Financial driver: {row[4]}. Materiality basis: {row[17]}"),
            ("p", row[13] or "No unresolved requirement is recorded for this selected request.")])
    if not report["question_rows"]:
        blocks.append(("p", "No current ranked questions are selected. This does not imply completion of a full FDD engagement."))
    elif len(report["question_rows"]) > 5:
        blocks.append(("p", f"This memo summarizes the five highest priority requests. The selected DD list contains {len(report['question_rows'])} requests; download the CSV or XLSX for the complete list."))
    blocks.append(("h", "Investment thesis and outstanding uncertainty"))
    for thesis in state.theses:
        blocks.extend([("h2", thesis.title), ("p", f"Review status: {thesis.review_status}. Counter-thesis: {thesis.counter_thesis}")])
        for claim in state.claims:
            if claim.thesis_id != thesis.id:
                continue
            blocks.extend([("p", f"{claim.id}: {claim.statement}"),
                ("p", f"Classification {claim.claim_kind}; evidence support {claim.support_status}; truth status {claim.truth_status}; review {claim.review_status}. Required verification: {', '.join(claim.required_criterion_keys)}.")])
    blocks.append(("h", "Financial implications and assumptions"))
    for driver in dict.fromkeys(row[4] for row in report["question_rows"]):
        related = [row[1] for row in report["question_rows"] if row[4] == driver]
        blocks.append(("p", f"{driver}: {', '.join(related)}. This is a qualitative financial-driver mapping; no numerical sensitivity is implied."))
    for item in _LIMITS:
        blocks.append(("p", item))
    blocks.append(("h", "Supporting and contradictory evidence"))
    for row in report["evidence_rows"]:
        blocks.extend([("h2", f"{row[0]}  {row[3]}"),
            ("p", f"Claim {row[1]}; provenance {row[4]}; review {row[5]}; lifecycle {row[6]}; verification {row[7]}; reliability {row[8]}. Criteria: {row[10] or 'context only'}."),
            ("quote", row[12]), ("source", row[11])])
    blocks.append(("h", "Evidence update and approval history"))
    if not state.audit_events:
        for review in state.analyst_decisions:
            if review.target_type == "evidence_update":
                blocks.append(("p", f"{review.decided_at} | {review.action} | {review.target_id} | {review.actor_id}. {review.reason}"))
    for event in sorted(state.audit_events, key=lambda item: item.sequence):
        blocks.append(("p", f"{event.sequence}. {event.created_at} | {event.event_type} | {event.actor_id} | revision {event.before_revision} to {event.after_revision}. {event.reason}"))
    for event in report["audit"]:
        blocks.append(("p", f"{event.sequence}. {event.event_type} | {event.actor_id} | {event.created_at}. {event.reason}"))
    blocks.extend([("h", "Export receipt"),
        ("p", f"Decision {decision.id}. Selection digest {decision.selection_digest}. Snapshot input digest {snapshot.input_digest}. These identifiers bind this preliminary export to its reviewed scope."),
        ("p", "The export receipt is a session-bound synthetic workflow record. It is not a durable legal signature or independent certification.")])
    return blocks


def _markdown(report) -> str:
    lines = []
    for kind, text in _memo_blocks(report):
        # Avoid active HTML while retaining readable literal source quotations.
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if kind == "title":
            lines.append("# " + text)
        elif kind == "h":
            lines.append("## " + text)
        elif kind == "h2":
            lines.append("### " + text)
        elif kind == "quote":
            lines.append("\n".join("> " + line for line in text.splitlines()))
        else:
            lines.append(text)
    return "\n\n".join(lines) + "\n"


def _docx(report) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document()
    doc.core_properties.title = f"{report['state'].deal.name} Preliminary Investment Screening"
    doc.core_properties.author = "Orion synthetic DD workbench"
    created = datetime.fromisoformat(report["decision"].decided_at.replace("Z", "+00:00")).replace(tzinfo=None)
    doc.core_properties.created = created
    doc.core_properties.modified = created
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(0.7)
    section.left_margin = section.right_margin = Inches(0.75)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string("172B3A")
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.08
    for name, size in (("Title", 24), ("Heading 1", 15), ("Heading 2", 12)):
        style = doc.styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = True
        style.paragraph_format.keep_with_next = True
        for border in style.element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
    doc.styles["Title"].paragraph_format.space_after = Pt(12)
    blocks = _memo_blocks(report)
    for index, (kind, text) in enumerate(blocks):
        style = {"title": "Title", "h": "Heading 1", "h2": "Heading 2"}.get(kind, "Normal")
        paragraph = doc.add_paragraph(text, style)
        if kind == "quote":
            paragraph.paragraph_format.left_indent = Inches(0.16)
            for run in paragraph.runs:
                run.italic = True
        elif kind == "source":
            for run in paragraph.runs:
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor.from_string("475569")
        if index + 1 < len(blocks) and blocks[index + 1][0] in {"quote", "source"}:
            paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.widow_control = True
    footer = section.footer.paragraphs[0]
    footer.text = "SYNTHETIC PRELIMINARY SCREENING  |  "
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    for run in footer.runs:
        run.font.size = Pt(9)
    raw = BytesIO()
    doc.save(raw)
    return _canonical_ooxml(raw.getvalue())

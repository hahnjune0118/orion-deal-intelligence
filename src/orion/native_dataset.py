"""Deterministic native sources for the three immutable Foundation demo cases.

The independently authored text fixtures are content seeds, never native parse
results. Ingest creates a NEW runtime pack with genuine locators and hashes.
Original fixture/spec snapshots are never rewritten. No gold keys are loaded.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from importlib.resources import files
from io import BytesIO
import json
from pathlib import Path
import textwrap
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from orion.adapters.parsers.native import NativeSourceIndex, PARSER_VERSION
from orion.domain.grounding import canonical_hash, validate_grounding
from orion.domain.models import AnalystDecision, DealState, StagedEvidenceUpdate
from orion.domain.scoring import build_snapshot
from orion.domain.transitions import apply_approved_update, assert_current_state

CASES = ("ns", "cd", "lm")
NATIVE_NAMES = {
    "ns": ("ns_cim.pdf", "ns_finance.docx", "ns_pipeline.pptx", "ns_contract_a.docx"),
    "cd": ("cd_operations.docx", "cd_finance.pdf", "cd_customers.pptx", "cd_batch_acceptance.docx"),
    "lm": ("lm_contracts.pdf", "lm_capacity.docx", "lm_plan.pptx", "lm_side_letter.docx"),
}
STAMP = "2026-11-03T00:00:00Z"


def _json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _fixture(case: str, kind: str) -> dict:
    if case not in CASES:
        raise ValueError("Unknown allowlisted case")
    return json.loads(files("orion").joinpath("resources", "demo", case, kind + ".json").read_bytes())


def _truth() -> dict:
    truth = json.loads(files("orion").joinpath("resources", "native", "financial_truth.json").read_bytes())
    for case in truth["cases"]:
        if case["revenue"] - case["cogs"] - case["opex_excluding_da"] != case["ebitda"]:
            raise ValueError("Financial reconciliation failed")
        if sum(case["customer_revenue"]) != case["revenue"]:
            raise ValueError("Customer revenue reconciliation failed")
        if case["ar"] + case["inventory"] - case["ap"] != case["nwc_operating"]:
            raise ValueError("NWC reconciliation failed")
    return {row["case_id"]: row for row in truth["cases"]}


def _money(cents: int) -> str:
    return f"USD {cents / 100:,.0f}"


def _canonical_zip(raw: bytes) -> bytes:
    """Remove archive wall-clock metadata without changing OOXML content."""
    result = BytesIO()
    with ZipFile(BytesIO(raw)) as source, ZipFile(result, "w", compression=ZIP_DEFLATED, compresslevel=9) as dest:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, (2026, 11, 3, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            dest.writestr(info, source.read(name))
    return result.getvalue()


def _pdf(title: str, pages: list[list[str]]) -> bytes:
    """Small reproducible PDF writer using standard Courier and native text.

    This intentionally narrow fixture writer supports ASCII text, fixed pages,
    and no active content. It adds no dependency to the user's project.
    """
    def escaped(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    kids = []
    for number, paragraphs in enumerate(pages, 1):
        commands = ["BT", "/F1 17 Tf", "54 744 Td", f"({escaped(title)}) Tj", "/F1 10 Tf", "0 -25 Td",
                    "(SYNTHETIC EDUCATIONAL DATA / FY2025 unless stated / v1) Tj", "0 -30 Td"]
        for paragraph in paragraphs:
            for line in textwrap.wrap(paragraph, width=86, break_long_words=False):
                commands.extend([f"({escaped(line)}) Tj", "0 -15 Td"])
            commands.append("0 -10 Td")
        commands += ["ET", "BT", "/F1 9 Tf", "54 35 Td",
                     f"(SYNTHETIC / No real company disclosures / Page {number} of {len(pages)}) Tj", "ET"]
        stream = "\n".join(commands).encode("ascii")
        page_id = len(objects) + 1
        content_id = page_id + 1
        kids.append(page_id)
        objects += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode(),
                    b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Count {len(kids)} /Kids [".encode() + b" ".join(f"{n} 0 R".encode() for n in kids) + b"] >>"
    output = BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        output.write(f"{off:010d} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return output.getvalue()


def _docx(title: str, paragraphs: list[str], rows: list[tuple[str, str]]) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    doc = Document()
    doc.core_properties.created = datetime(2026, 11, 3)
    doc.core_properties.modified = datetime(2026, 11, 3)
    doc.core_properties.author = "Orion synthetic dataset generator"
    doc.core_properties.title = title
    doc.sections[0].top_margin = Inches(0.7)
    doc.sections[0].bottom_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(8)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        doc.styles[style_name].font.color.rgb = RGBColor(0, 0, 0)
        for border in doc.styles[style_name].element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
    for border in doc.styles.element.xpath(".//w:pBdr"):
        border.getparent().remove(border)
    doc.add_paragraph(title, "Title")
    doc.add_paragraph("SYNTHETIC EDUCATIONAL DATA. Independently authored fictional company records. Version 1, dated 2026-11-03.")
    doc.add_heading("Source narrative", level=1)
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    if rows:
        doc.add_heading("Supporting schedule", level=1)
        table = doc.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = OxmlElement("w:" + edge)
            border.set(qn("w:val"), "single")
            border.set(qn("w:sz"), "4")
            border.set(qn("w:color"), "D9D9D9")
            borders.append(border)
        table._tbl.tblPr.append(borders)
        for cell, value in zip(table.rows[0].cells, ("Item", "Reported value")):
            cell.text = value
        for label, value in rows:
            cells = table.add_row().cells
            cells[0].text, cells[1].text = label, value
    footer = doc.sections[0].footer.paragraphs[0]
    footer.text = "SYNTHETIC / EDUCATIONAL USE / No real company disclosure or legal signature"
    for run in footer.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(70, 70, 70)
    raw = BytesIO(); doc.save(raw)
    return _canonical_zip(raw.getvalue())


def _pptx(title: str, slides: list[tuple[str, list[str]]]) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    deck.core_properties.created = datetime(2026, 11, 3)
    deck.core_properties.modified = datetime(2026, 11, 3)
    deck.core_properties.author = "Orion synthetic dataset generator"
    deck.core_properties.title = title
    for heading, paragraphs in slides:
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        title_box = slide.shapes.add_textbox(Inches(0.65), Inches(0.5), Inches(12), Inches(0.8))
        p = title_box.text_frame.paragraphs[0]
        p.text = heading; p.font.size = Pt(30); p.font.bold = True
        box = slide.shapes.add_textbox(Inches(0.7), Inches(1.65), Inches(11.9), Inches(4.8))
        box.text_frame.word_wrap = True
        for idx, text in enumerate(paragraphs):
            p = box.text_frame.paragraphs[0] if idx == 0 else box.text_frame.add_paragraph()
            p.text = text; p.font.size = Pt(22); p.space_after = Pt(18)
        footer = slide.shapes.add_textbox(Inches(0.7), Inches(6.9), Inches(12), Inches(0.35))
        p = footer.text_frame.paragraphs[0]
        p.text = "SYNTHETIC EDUCATIONAL DATA / v1 / 2026-11-03 / No real company disclosure"
        p.font.size = Pt(10); p.font.color.rgb = RGBColor(80, 80, 80)
    raw = BytesIO(); deck.save(raw)
    return _canonical_zip(raw.getvalue())


def generate_synthetic(output: str | Path = "data/synthetic") -> dict:
    output = Path(output)
    truth = _truth()
    inventory = {"dataset_version": "legacy-native-1.0.0", "synthetic": True,
                 "generator_seed": 20261103, "source_of_figures": "fixed Foundation financial truth, cents",
                 "documents": []}
    for case in CASES:
        state = _fixture(case, "initial_state")
        event = _fixture(case, "staged_evidence_update")
        t = truth[case]
        name = state["deal"]["name"]
        narrative = state["source_spans"][0]["normalized_text"]
        update = event["source_spans"][0]["normalized_text"]
        rows = [(key.replace("_", " ").title(), _money(t[key])) for key in
                ("revenue", "cogs", "opex_excluding_da", "ebitda", "ar", "inventory", "ap", "nwc_operating", "cash", "debt")]
        finance_text = [f"FY2025 {label}: {value}." for label, value in rows]
        customers = [f"Fictional existing customer {i}: {_money(value)} FY2025 revenue."
                     for i, value in enumerate(t["customer_revenue"], 1)]
        metadata = deepcopy(state["documents"][0])
        fmt = metadata["format"]
        source0 = (_pdf(name + " source overview", [[narrative], finance_text[:5], finance_text[5:]]) if fmt == "pdf"
                   else _docx(name + " operations", [narrative, "The schedule reports historical figures for FY2025."], rows))
        if case == "cd":
            source1 = _pdf(name + " historical financial schedule", [finance_text[:4], finance_text[4:8], finance_text[8:] + customers])
        else:
            extra = (["Subscription revenue USD 900,000 plus services USD 300,000 equals FY2025 revenue USD 1,200,000. Aster and Birch are future prospects and are excluded from this historical total."]
                     if case == "ns" else ["FY2025 delivered hours 10,000 at USD 300 per hour. Available capacity is 12,000 hours. Direct cost is USD 180 per delivered hour."])
            source1 = _docx(name + (" financial schedule" if case == "ns" else " capacity schedule"), extra, rows)
        if case == "ns":
            slides = [("Northstar pipeline context", ["SYNTHETIC. Aster Labs and Birch Systems are PoC prospects. Their future paid conversion is unverified."]),
                      ("Historical customer revenue", customers[:2]), ("Historical customer revenue continued", customers[2:]),
                      ("Evidence requested", ["Signed paid contracts, acceptance and cash evidence remain distinct steps.", "Future 2027 annual contract value is excluded from FY2025 revenue."])]
        elif case == "cd":
            slides = [("Cedar customer concentration", customers[:2]), ("Remaining customer revenue", customers[2:]),
                      ("Cutoff evidence boundary", ["Batch C-17 invoice USD 180,000 is already included in FY2025 revenue.", "New acceptance evidence validates timing. It does not create additional revenue."])]
        else:
            slides = [("Lumen operating capacity", ["FY2025 delivered 10,000 billable hours from 12,000 available hours.", "USD 300 revenue and USD 180 direct cost per delivered hour."]),
                      ("Lumen customer concentration", customers[:2]), ("Lumen remaining customer revenue", customers[2:])]
        source2 = _pptx(name + " commercial schedule", slides)
        source3 = _docx(name + " evidence update", [update, "SYNTHETIC signature annotation only. No real electronic signature or counterparty verification is represented."], [])
        meta1 = {**metadata, "id": f"doc_{case}_finance_native", "format": NATIVE_NAMES[case][1].split(".")[-1], "origin_key": f"{case}:native:finance"}
        meta2 = {**metadata, "id": f"doc_{case}_schedule_native", "format": "pptx", "origin_key": f"{case}:native:schedule"}
        for position, (raw, meta) in enumerate(zip((source0, source1, source2, source3), (metadata, meta1, meta2, event["documents"][0]))):
            filename = NATIVE_NAMES[case][position]
            relative = f"{case}/{filename}"
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            meta = {**meta, "filename": filename}
            inventory["documents"].append({"case_id": case, "stage": "update" if position == 3 else "initial",
                                           "path": relative, "document": meta, "sha256": hashlib.sha256(raw).hexdigest(),
                                           "size_bytes": len(raw), "synthetic": True})
    _json(output / "source_inventory.json", inventory)
    return inventory


def _source_index(case: str, source_root: Path) -> tuple[NativeSourceIndex, list[dict]]:
    if case not in CASES:
        raise ValueError("Unknown allowlisted case")
    inventory = json.loads((source_root / "source_inventory.json").read_text(encoding="utf-8"))
    entries = [row for row in inventory["documents"] if row["case_id"] == case]
    if len(entries) != 4:
        raise ValueError("Expected exactly four allowlisted native sources")
    resolver = NativeSourceIndex()
    parsed = []
    allowed = {f"{case}/{n}" for n in NATIVE_NAMES[case]}
    for entry in entries:
        if entry["path"] not in allowed:
            raise ValueError("Source path is outside the static allowlist")
        source = source_root / entry["path"]
        if source.is_symlink() or source_root.resolve() not in source.resolve().parents:
            raise ValueError("Source path escaped its root")
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Source checksum mismatch")
        result = resolver.add(raw, entry["document"])
        if result.document.parse_status != "parsed":
            raise ValueError("Generated source did not parse cleanly")
        parsed.append({"stage": entry["stage"], "result": result})
    if sum(len(s.normalized_text) for row in parsed for s in row["result"].source_spans) > 300_000:
        raise ValueError("Deal text limit exceeded")
    return resolver, parsed


def _runtime_pack(case: str, source_root: Path):
    state, event = _fixture(case, "initial_state"), _fixture(case, "staged_evidence_update")
    resolver, parsed = _source_index(case, source_root)
    mapping = {"case_id": case, "fixture_input_digest": state["ranking_snapshots"][0]["input_digest"],
               "parser_version": PARSER_VERSION, "spans": [], "note": "New native runtime seed. Historical fixture snapshots remain unchanged."}
    for stage, envelope in (("initial", state), ("update", event)):
        old_spans = list(envelope["source_spans"])
        envelope["documents"], envelope["source_spans"] = [], []
        for row in parsed:
            if row["stage"] != stage:
                continue
            result = row["result"]
            envelope["documents"].append(result.document.model_dump(mode="json"))
            spans = [s.model_dump(mode="json") for s in result.source_spans]
            for old in old_spans:
                if old["document_id"] != result.document.id:
                    continue
                expected = " ".join(old["normalized_text"].split())
                matches = [s for s in spans if expected in " ".join(s["normalized_text"].split())]
                if len(matches) != 1:
                    raise ValueError("Fixture excerpt does not resolve uniquely in native source")
                native = matches[0]
                native["id"] = old["id"]
                mapping["spans"].append({"source_span_id": old["id"], "old_locator": old["locator"],
                                         "native_locator": native["locator"], "old_text_sha256": old["text_sha256"],
                                         "native_text_sha256": native["text_sha256"]})
            envelope["source_spans"].extend(spans)
    state["analysis_runs"] = []  # Authored extraction provenance remains in the untouched seed.
    state_model, event_model = DealState.model_validate(state), StagedEvidenceUpdate.model_validate(event)
    old_head = state_model.ranking_snapshots[0]
    state_model.ranking_snapshots = [build_snapshot(state_model, snapshot_id=old_head.id,
                                                   created_at=old_head.created_at, source_resolver=resolver)]
    mapping["native_input_digest"] = state_model.ranking_snapshots[0].input_digest
    validate_grounding(state_model, event_model, source_resolver=resolver).raise_for_errors()
    assert_current_state(state_model, source_resolver=resolver)
    return state_model, event_model, resolver, mapping


def replay_runtime(state: DealState, event: StagedEvidenceUpdate, resolver: NativeSourceIndex) -> DealState:
    decision = AnalystDecision(id=f"decision_native_{state.deal.id}", entity_version=1, deal_id=state.deal.id,
                               actor_id="actor_native_demo_reviewer", actor_role="reviewer", target_type="evidence_update",
                               target_id=event.id, target_version=1, selection_digest=None, action="approve",
                               reason="Explicit synthetic reviewer simulation on validated native sources.",
                               base_revision=state.state_revision, decided_at="2026-11-03T00:01:00Z")
    return apply_approved_update(state, event, decision=decision,
                                 snapshot_id=f"snap_native_{state.deal.id}_after", now=decision.decided_at,
                                 source_resolver=resolver)


def ingest(case: str = "all", mode: str = "demo", source_root: str | Path = "data/synthetic",
           output: str | Path = "data/parsed") -> dict:
    if mode != "demo":
        raise ValueError("Only allowlisted synthetic native ingestion is enabled")
    cases = CASES if case == "all" else (case,)
    source_root, output = Path(source_root), Path(output)
    summary = {"dataset_version": "legacy-native-1.0.0", "cases": [], "live_api_calls": 0}
    for case_id in cases:
        state, event, resolver, mapping = _runtime_pack(case_id, source_root)
        after = replay_runtime(state, event, resolver)
        _json(output / case_id / "initial_state.json", state.model_dump(mode="json"))
        _json(output / case_id / "staged_evidence_update.json", event.model_dump(mode="json"))
        _json(output / case_id / "source_mapping.json", mapping)
        summary["cases"].append({"case_id": case_id, "documents": len(state.documents) + len(event.documents),
                                  "source_spans": len(state.source_spans) + len(event.source_spans),
                                  "before_top3": state.ranking_snapshots[-1].top3,
                                  "after_top3": after.ranking_snapshots[-1].top3,
                                  "native_input_digest": mapping["native_input_digest"],
                                  "fixture_input_digest": mapping["fixture_input_digest"], "grounding_valid": True})
    _json(output / "ingestion_report.json", summary)
    return summary


def load_runtime(case: str, source_root: str | Path = "data/synthetic",
                 parsed_root: str | Path = "data/parsed") -> tuple[DealState, StagedEvidenceUpdate, NativeSourceIndex]:
    if case not in CASES:
        raise ValueError("Unknown allowlisted case")
    resolver, _ = _source_index(case, Path(source_root))
    folder = Path(parsed_root) / case
    state = DealState.model_validate_json((folder / "initial_state.json").read_bytes())
    event = StagedEvidenceUpdate.model_validate_json((folder / "staged_evidence_update.json").read_bytes())
    validate_grounding(state, event, source_resolver=resolver).raise_for_errors()
    assert_current_state(state, source_resolver=resolver)
    return state, event, resolver

from copy import deepcopy
from io import BytesIO
import hashlib
import json
import subprocess
from zipfile import ZipFile

import pytest

from orion.adapters.parsers.native import NativeParser, NativeSourceIndex, ParserLimitError, MAX_SOURCE_BYTES
from orion.domain.grounding import canonical_hash, text_sha256, validate_grounding
from orion.domain.models import DealState
from orion.native_dataset import (CASES, _docx, _fixture, _pdf, generate_synthetic, ingest,
                                  load_runtime, replay_runtime)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp("native")
    inventory = generate_synthetic(root / "sources")
    report = ingest(source_root=root / "sources", output=root / "parsed")
    runtime = {c: load_runtime(c, source_root=root / "sources", parsed_root=root / "parsed") for c in CASES}
    return root, inventory, report, runtime


def metadata(fmt):
    doc = deepcopy(_fixture("ns", "initial_state")["documents"][0])
    doc.update(format=fmt, filename="source." + fmt)
    return doc


def test_exactly_twelve_sources_and_deterministic_bytes(dataset, tmp_path):
    root, first, report, _ = dataset
    second = generate_synthetic(tmp_path)
    assert len(first["documents"]) == 12
    assert first == second
    for row in first["documents"]:
        assert (root / "sources" / row["path"]).read_bytes() == (tmp_path / row["path"]).read_bytes()
        assert row["sha256"] == hashlib.sha256((tmp_path / row["path"]).read_bytes()).hexdigest()
    assert sum(c["documents"] for c in report["cases"]) == 12


@pytest.mark.parametrize("case,before,after", [
    ("ns", ["contract_a", "contract_b", "accept_collect"], ["contract_b", "accept_collect", "concentration"]),
    ("cd", ["cutoff", "warranty", "inventory"], ["warranty", "inventory", "receivable"]),
    ("lm", ["labor", "margin", "cash"], ["renewal", "labor", "margin"]),
])
def test_native_replay_preserves_exact_contract_transition(dataset, case, before, after):
    state, event, resolver = dataset[3][case]
    assert validate_grounding(state, event, source_resolver=resolver).valid
    assert not validate_grounding(state, event, source_resolver=resolver).fixture_text_only
    result = replay_runtime(state, event, resolver)
    assert state.ranking_snapshots[-1].top3 == [f"q_{case}_{q}" for q in before]
    assert result.ranking_snapshots[-1].top3 == [f"q_{case}_{q}" for q in after]
    assert result.state_revision == 2
    assert len(result.analyst_decisions) == 2


@pytest.mark.parametrize("case", CASES)
def test_runtime_metadata_and_all_spans_resolve_against_native(dataset, case):
    state, event, resolver = dataset[3][case]
    docs = {d.id: d for d in [*state.documents, *event.documents]}
    for span in [*state.source_spans, *event.source_spans]:
        doc = docs[span.document_id].model_dump(mode="json")
        assert doc["asset_status"] == "file_verified"
        assert resolver.resolve_units(doc, span.locator.model_dump(mode="json")) == (span.normalized_text,)
        assert span.extraction_method == "parsed"
        assert span.quote == span.normalized_text[span.start:span.end]
        if doc["format"] == "docx":
            assert "page" not in span.locator.model_dump(mode="json")


@pytest.mark.parametrize("mutation", ["page", "block", "quote", "text", "checksum", "parser", "document", "version"])
def test_fabricated_pdf_source_fails_despite_consistent_json(dataset, mutation):
    state, event, resolver = dataset[3]["ns"]
    bad = state.model_dump(mode="json")
    span = next(s for s in bad["source_spans"] if s["id"] == "span_ns_overview")
    doc = next(d for d in bad["documents"] if d["id"] == span["document_id"])
    if mutation == "page": span["locator"]["page"] = 49
    elif mutation == "block": span["locator"]["block_index"] = 1
    elif mutation == "quote": span["quote"] = "Fictional fabricated claim"
    elif mutation == "text":
        span["normalized_text"] = span["quote"] = "Fully self-consistent fabricated source"
        span["start"], span["end"] = 0, len(span["quote"])
        span["text_sha256"] = text_sha256(span["quote"])
    elif mutation == "checksum": doc["file_sha256"] = "0" * 64
    elif mutation == "parser": doc["parser_version"] = "nonexistent-parser"
    elif mutation == "document": span["document_id"] = "doc_missing_source"
    elif mutation == "version": span["document_version"] = 99
    assert not validate_grounding(bad, source_resolver=resolver).valid


@pytest.mark.parametrize("kind,field", [("docx_paragraph", "block_index"), ("docx_table_cell", "row"),
                                       ("docx_table_cell", "column"), ("docx_table_cell", "table_index"),
                                       ("pptx", "slide"), ("pptx", "shape_id"), ("pptx", "paragraph_index")])
def test_native_docx_and_pptx_wrong_locator_rejected(dataset, kind, field):
    state, _, resolver = dataset[3]["ns"]
    bad = state.model_dump(mode="json")
    span = next(s for s in bad["source_spans"] if s["locator"]["kind"] == kind)
    span["locator"][field] += 50
    assert not validate_grounding(bad, source_resolver=resolver).valid


def test_source_index_reparses_original_bytes_not_runtime_span(dataset):
    state, _, _ = dataset[3]["ns"]
    assert not validate_grounding(state).valid


def test_pdf_scan_returns_ocr_without_validated_units():
    from pypdf import PdfWriter
    writer = PdfWriter(); writer.add_blank_page(width=612, height=792)
    source = BytesIO(); writer.write(source)
    result = NativeParser().parse_document(source.getvalue(), metadata("pdf"))
    assert result.document.parse_status == "needs_ocr"
    assert result.source_spans == ()
    assert "PAGE_REQUIRES_OCR" in result.warnings


def test_encrypted_pdf_requires_manual_review():
    from pypdf import PdfWriter
    writer = PdfWriter(); writer.add_blank_page(width=612, height=792); writer.encrypt("synthetic-only")
    source = BytesIO(); writer.write(source)
    result = NativeParser().parse_document(source.getvalue(), metadata("pdf"))
    assert result.document.parse_status == "needs_manual_review"
    assert result.source_spans == ()
    assert "ENCRYPTED_PDF" in result.warnings


@pytest.mark.parametrize("fmt,source", [("pdf", b"%PDF-1.4\ncorrupted"), ("docx", b"PK broken"), ("pptx", b"PK broken")])
def test_malformed_native_documents_fail_closed(fmt, source):
    result = NativeParser().parse_document(source, metadata(fmt))
    assert result.document.parse_status == "failed"
    assert result.source_spans == ()


def test_wrong_format_signature_and_size_limits():
    with pytest.raises(ParserLimitError, match="FORMAT_SIGNATURE"):
        NativeParser().parse_document(b"not a PDF", metadata("pdf"))
    with pytest.raises(ParserLimitError, match="SOURCE_SIZE"):
        NativeParser().parse_document(b"x" * (MAX_SOURCE_BYTES + 1), metadata("pdf"))


def test_pdf_page_limit():
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(51): writer.add_blank_page(width=612, height=792)
    source = BytesIO(); writer.write(source)
    with pytest.raises(ParserLimitError, match="PAGE_LIMIT"):
        NativeParser().parse_document(source.getvalue(), metadata("pdf"))


@pytest.mark.parametrize("change", ["merged", "nested", "tracked", "header_table"])
def test_complex_docx_requires_manual_review(change):
    from docx import Document
    from docx.oxml import OxmlElement
    doc = Document(); doc.add_paragraph("SYNTHETIC normal body")
    table = doc.add_table(rows=2, cols=2)
    for row in table.rows:
        for cell in row.cells: cell.text = "Synthetic cell"
    if change == "merged": table.cell(0, 0).merge(table.cell(0, 1))
    elif change == "nested": table.cell(0, 0).add_table(rows=1, cols=1)
    elif change == "tracked": doc.element.body.append(OxmlElement("w:ins"))
    elif change == "header_table":
        from docx.shared import Inches
        doc.sections[0].header.add_table(rows=1, cols=1, width=Inches(4))
    source = BytesIO(); doc.save(source)
    result = NativeParser().parse_document(source.getvalue(), metadata("docx"))
    assert result.document.parse_status == "needs_manual_review"
    assert all(s.locator_status == "unverified" for s in result.source_spans)


def test_docx_exact_cell_and_heading_native_locations():
    raw = _docx("Synthetic financial evidence", ["SYNTHETIC revenue context."], [("Revenue", "USD 120")])
    result = NativeParser().parse_document(raw, metadata("docx"))
    cell = next(s for s in result.source_spans if s.quote == "USD 120")
    assert cell.locator.model_dump(mode="json") == {"kind": "docx_table_cell", "part_uri": "word/document.xml",
            "table_index": 0, "row": 1, "column": 1, "paragraph_index": 0, "heading_path": ["Supporting schedule"]}


def test_pptx_table_cell_resolves_and_wrong_cell_does_not():
    from pptx import Presentation
    from pptx.util import Inches
    deck = Presentation(); slide = deck.slides.add_slide(deck.slide_layouts[6])
    shape = slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(6), Inches(2))
    shape.table.cell(1, 1).text = "SYNTHETIC 120"
    raw = BytesIO(); deck.save(raw)
    resolver = NativeSourceIndex(); result = resolver.add(raw.getvalue(), metadata("pptx"))
    span = next(s for s in result.source_spans if s.quote == "SYNTHETIC 120")
    locator = span.locator.model_dump(mode="json")
    assert locator["table_cell"] == {"row": 1, "column": 1}
    assert resolver.resolve_units(result.document.model_dump(mode="json"), locator) == ("SYNTHETIC 120",)
    locator["table_cell"]["column"] = 99
    assert resolver.resolve_units(result.document.model_dump(mode="json"), locator) == ()


def test_zip_bomb_path_and_entity_preflight():
    for name, body, code in [("../escape.xml", b"x", "INVALID_PACKAGE_PATH"),
                             ("bad.xml", b'<!ENTITY secret SYSTEM "file:///never">', "XML_ENTITY")]:
        out = BytesIO()
        with ZipFile(out, "w") as z:
            z.writestr("word/document.xml", b"<root/>"); z.writestr(name, body)
        with pytest.raises(ParserLimitError, match=code):
            NativeParser().parse_document(out.getvalue(), metadata("docx"))


def test_timeout_terminates_parse_boundary(monkeypatch):
    def expire(*args, **kwargs): raise subprocess.TimeoutExpired("parser", 20)
    monkeypatch.setattr(subprocess, "run", expire)
    with pytest.raises(ParserLimitError, match="PARSE_TIMEOUT"):
        NativeParser().parse_document(b"%PDF-1.4", metadata("pdf"))


def test_span_identity_changes_with_document_version_and_bytes():
    first = _docx("Synthetic source", ["SYNTHETIC original paragraph"], [])
    second = _docx("Synthetic source", ["SYNTHETIC changed paragraph"], [])
    parser = NativeParser()
    a = parser.parse_document(first, metadata("docx"))
    b = parser.parse_document(second, metadata("docx"))
    c = parser.parse_document(first, {**metadata("docx"), "document_version": 2})
    assert {s.id for s in a.source_spans}.isdisjoint(s.id for s in b.source_spans)
    assert {s.id for s in a.source_spans}.isdisjoint(s.id for s in c.source_spans)


def test_mutated_source_bytes_rejected_before_ingestion(dataset, tmp_path):
    import shutil
    root = dataset[0]
    shutil.copytree(root / "sources", tmp_path / "sources")
    target = tmp_path / "sources" / "ns" / "ns_cim.pdf"
    target.write_bytes(target.read_bytes() + b"\nmutated")
    with pytest.raises(ValueError, match="checksum"):
        ingest(case="ns", source_root=tmp_path / "sources", output=tmp_path / "parsed")


def test_interactive_pdf_falls_back_even_when_text_extracts():
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(_pdf("Synthetic source", [["SYNTHETIC normal text"]]))))
    with pytest.warns(DeprecationWarning, match="add_js"):
        writer.add_js("app.alert('synthetic adversarial example')")
    source = BytesIO(); writer.write(source)
    result = NativeParser().parse_document(source.getvalue(), metadata("pdf"))
    assert result.document.parse_status == "needs_manual_review"
    assert all(s.locator_status == "unverified" for s in result.source_spans)


def test_pptx_notes_and_merged_cells_require_review():
    from pptx import Presentation
    from pptx.util import Inches
    deck = Presentation(); slide = deck.slides.add_slide(deck.slide_layouts[6])
    shape = slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(6), Inches(2))
    shape.table.cell(0, 0).merge(shape.table.cell(0, 1))
    slide.notes_slide.notes_text_frame.text = "SYNTHETIC evidence in notes"
    source = BytesIO(); deck.save(source)
    result = NativeParser().parse_document(source.getvalue(), metadata("pptx"))
    assert result.document.parse_status == "needs_manual_review"
    assert "SPEAKER_NOTES_NOT_PARSED" in result.warnings
    assert "COMPLEX_TABLE_REQUIRES_REVIEW" in result.warnings


def test_cache_never_reuses_changed_source_or_mutable_parsed_values():
    parser = NativeParser()
    raw = _docx("Synthetic cache source", ["SYNTHETIC immutable bytes"], [])
    first = parser.parse_document(raw, metadata("docx"))
    first.source_spans[0].normalized_text = "mutated by a caller"
    second = parser.parse_document(raw, metadata("docx"))
    assert second.source_spans[0].normalized_text != "mutated by a caller"
    resolver = NativeSourceIndex(); resolver.add(raw, metadata("docx"))
    changed = _docx("Synthetic cache source", ["SYNTHETIC different bytes"], [])
    with pytest.raises(ValueError, match="Immutable"):
        resolver.add(changed, metadata("docx"))

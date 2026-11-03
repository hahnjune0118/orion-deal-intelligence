"""Bounded native text parsers and an independent original-byte source index.

A PDF block is one page's extracted plain text (block_index=0), not a guessed
visual paragraph. OOXML locators follow actual body/slide/table indices. No OCR,
macro execution, URL fetching, or HTML interpretation takes place.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import base64
import hashlib
from functools import lru_cache
from io import BytesIO
import json
from pathlib import PurePosixPath
import subprocess
import sys
from typing import Any
from zipfile import BadZipFile, ZipFile

from orion.adapters.parsers.base import ParsedDocument
from orion.domain.grounding import canonical_json, normalize_text, text_sha256
from orion.domain.models import Document, SourceSpan

PARSER_VERSION = "orion-native-1.0.0"
MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_UNITS = 2000
MAX_UNIT_CHARS = 100_000
MAX_TOTAL_CHARS = 100_000
MAX_PAGES = 50


class ParserLimitError(ValueError):
    """Only a stable code is exposed; source text never appears in errors."""


def _metadata(metadata: Mapping[str, Any], source: bytes, status: str) -> Document:
    data = dict(metadata)
    data.update(asset_status="file_verified", file_sha256=hashlib.sha256(source).hexdigest(),
                parse_status=status, parser_version=PARSER_VERSION)
    return Document.model_validate(data)


def _zip_check(source: bytes, expected_part: str) -> tuple[str, ...]:
    warnings: list[str] = []
    with ZipFile(BytesIO(source)) as z:
        info = z.infolist()
        if len(info) > 2048 or sum(i.file_size for i in info) > MAX_EXPANDED_BYTES:
            raise ParserLimitError("EXPANDED_SIZE_LIMIT")
        names = [i.filename for i in info]
        if len(names) != len(set(names)) or expected_part not in names:
            raise ParserLimitError("INVALID_PACKAGE")
        for i in info:
            p = PurePosixPath(i.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in i.filename:
                raise ParserLimitError("INVALID_PACKAGE_PATH")
            if i.flag_bits & 1:
                raise ParserLimitError("ENCRYPTED_PACKAGE")
            if "vbaproject" in i.filename.lower():
                raise ParserLimitError("MACROS_UNSUPPORTED")
            if i.file_size > 1024 * 1024 and i.file_size / max(1, i.compress_size) > 300:
                raise ParserLimitError("COMPRESSION_RATIO_LIMIT")
            if i.filename.endswith((".xml", ".rels")):
                content = z.read(i)
                if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                    raise ParserLimitError("XML_ENTITY_UNSUPPORTED")
                if i.filename.endswith(".rels") and b'TargetMode="External"' in content:
                    warnings.append("EXTERNAL_RELATIONSHIP_NOT_FOLLOWED")
        if any(n.startswith(("word/footnotes", "word/endnotes", "word/comments")) for n in names):
            warnings.append("ANNOTATIONS_UNSUPPORTED")
    return tuple(sorted(set(warnings)))


def _parse_bytes(source: bytes, metadata: Mapping[str, Any]) -> ParsedDocument:
    if not isinstance(source, bytes) or not source or len(source) > MAX_SOURCE_BYTES:
        raise ParserLimitError("SOURCE_SIZE_LIMIT")
    fmt = metadata.get("format")
    units: list[tuple[dict, str]] = []
    warnings: list[str] = []
    status = "parsed"
    try:
        if fmt == "pdf":
            if not source.startswith(b"%PDF-"):
                raise ParserLimitError("FORMAT_SIGNATURE_MISMATCH")
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(source), strict=True)
            if reader.is_encrypted:
                status, warnings = "needs_manual_review", ["ENCRYPTED_PDF"]
            elif len(reader.pages) > MAX_PAGES:
                raise ParserLimitError("PAGE_LIMIT")
            else:
                catalog = reader.trailer["/Root"]
                if any(key in catalog for key in ("/OpenAction", "/AA", "/AcroForm", "/Names")):
                    warnings.append("PDF_ACTIVE_OR_INTERACTIVE_CONTENT_NOT_PARSED")
                for page_no, page in enumerate(reader.pages, 1):
                    if page.get("/Annots"):
                        warnings.append("PDF_ANNOTATIONS_NOT_PARSED")
                    content = page.get_contents()
                    if content is not None and len(content.get_data()) > MAX_EXPANDED_BYTES:
                        raise ParserLimitError("EXPANDED_SIZE_LIMIT")
                    text = page.extract_text(extraction_mode="plain") or ""
                    text = normalize_text(text).rstrip("\n")
                    if text.strip():
                        units.append(({"kind": "pdf", "page": page_no, "block_index": 0}, text))
                    else:
                        warnings.append("PAGE_REQUIRES_OCR")
                if "PAGE_REQUIRES_OCR" in warnings:
                    status = "needs_ocr"
        elif fmt == "docx":
            warnings.extend(_zip_check(source, "word/document.xml"))
            from docx import Document as Docx
            from docx.oxml.ns import qn
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            doc = Docx(BytesIO(source))
            headings: list[str] = []
            block_index = table_index = 0
            unsupported = ("w:ins", "w:del", "w:altChunk", "w:drawing", "w:pict", "w:sdt", "w:fldSimple", "w:instrText")
            for tag in unsupported:
                if doc.element.body.xpath(".//" + tag):
                    warnings.append("UNSUPPORTED_BODY_CONTENT")
            for section in doc.sections:
                if section.header.tables or section.footer.tables:
                    warnings.append("HEADER_FOOTER_TABLE_UNSUPPORTED")
                # Repeated synthetic disclosure headers/footers are not evidence.
                if any(p.text.strip() and not p.text.startswith("SYNTHETIC")
                       for part in (section.header, section.footer) for p in part.paragraphs):
                    warnings.append("HEADER_FOOTER_EVIDENCE_NOT_PARSED")
            for child in doc.element.body:
                if child.tag == qn("w:p"):
                    paragraph = Paragraph(child, doc)
                    text = normalize_text(paragraph.text)
                    style = paragraph.style.name if paragraph.style else ""
                    if style.startswith("Heading "):
                        try: level = int(style.split()[-1])
                        except ValueError: level = 1
                        headings = headings[:level - 1] + [text]
                    if text:
                        units.append(({"kind": "docx_paragraph", "part_uri": "word/document.xml",
                                       "block_index": block_index, "paragraph_index": 0,
                                       "heading_path": list(headings)}, text))
                    block_index += 1
                elif child.tag == qn("w:tbl"):
                    table = Table(child, doc)
                    if child.xpath(".//w:gridSpan") or child.xpath(".//w:vMerge") or child.xpath(".//w:tbl"):
                        warnings.append("COMPLEX_TABLE_REQUIRES_REVIEW")
                    else:
                        for r, row in enumerate(table.rows):
                            for c, cell in enumerate(row.cells):
                                for pi, paragraph in enumerate(cell.paragraphs):
                                    text = normalize_text(paragraph.text)
                                    if text:
                                        units.append(({"kind": "docx_table_cell", "part_uri": "word/document.xml",
                                                       "table_index": table_index, "row": r, "column": c,
                                                       "paragraph_index": pi, "heading_path": list(headings)}, text))
                    table_index += 1
                    block_index += 1
        elif fmt == "pptx":
            warnings.extend(_zip_check(source, "ppt/presentation.xml"))
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE
            deck = Presentation(BytesIO(source))
            if len(deck.slides) > MAX_PAGES:
                raise ParserLimitError("PAGE_LIMIT")
            for sn, slide in enumerate(deck.slides, 1):
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None and slide.notes_slide.notes_text_frame.text.strip():
                    warnings.append("SPEAKER_NOTES_NOT_PARSED")
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                        warnings.append("GROUP_SHAPE_REQUIRES_REVIEW")
                    if shape.has_table:
                        table = shape.table
                        if any(cell.is_merge_origin or cell.is_spanned
                               for row in table.rows for cell in row.cells):
                            warnings.append("COMPLEX_TABLE_REQUIRES_REVIEW")
                            continue
                        for r, row in enumerate(table.rows):
                            for c, cell in enumerate(row.cells):
                                for pi, paragraph in enumerate(cell.text_frame.paragraphs):
                                    text = normalize_text(paragraph.text)
                                    if text:
                                        units.append(({"kind": "pptx", "slide": sn, "shape_id": shape.shape_id,
                                                       "paragraph_index": pi, "table_cell": {"row": r, "column": c}}, text))
                    elif shape.has_text_frame:
                        for pi, paragraph in enumerate(shape.text_frame.paragraphs):
                            text = normalize_text(paragraph.text)
                            if text:
                                units.append(({"kind": "pptx", "slide": sn, "shape_id": shape.shape_id,
                                               "paragraph_index": pi, "table_cell": None}, text))
                    elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        warnings.append("IMAGE_TEXT_NOT_PARSED")
                    elif not shape.has_text_frame and not shape.has_table:
                        warnings.append("UNSUPPORTED_SLIDE_CONTENT")
        else:
            raise ParserLimitError("UNSUPPORTED_FORMAT")
    except ParserLimitError:
        raise
    except (ValueError, KeyError, BadZipFile, TypeError, OSError, IndexError):
        status, warnings, units = "failed", ["MALFORMED_DOCUMENT"], []
    except Exception:
        # Optional parser libraries may raise version-specific format errors.
        status, warnings, units = "failed", ["PARSER_REJECTED_DOCUMENT"], []
    if len(units) > MAX_UNITS or sum(len(t) for _, t in units) > MAX_TOTAL_CHARS or any(len(t) > MAX_UNIT_CHARS for _, t in units):
        raise ParserLimitError("TEXT_LIMIT")
    if not units and status == "parsed":
        status, warnings = "needs_manual_review", [*warnings, "NO_SUPPORTED_TEXT"]
    if warnings and status == "parsed":
        status = "needs_manual_review"
    document = _metadata(metadata, source, status)
    spans: list[SourceSpan] = []
    for locator, text in units:
        token = hashlib.sha256(canonical_json({"document_id": document.id,
            "document_version": document.document_version, "file_sha256": document.file_sha256,
            "parser_version": document.parser_version, "locator": locator}).encode()).hexdigest()[:20]
        # Pydantic IDs are at most 64 characters.
        sid = f"span_{document.id[:35]}_{token}"
        spans.append(SourceSpan(
            id=sid, entity_version=1, deal_id=document.deal_id, document_id=document.id,
            document_version=document.document_version, locator=locator,
            normalized_text=text, text_sha256=text_sha256(text), quote=text, start=0, end=len(text),
            locator_status="validated" if status == "parsed" else "unverified", extraction_method="parsed",
        ))
    return ParsedDocument(document, tuple(spans), tuple(sorted(set(warnings))))


def _run_worker(source_bytes: bytes, meta_json: str, timeout_seconds: float) -> str:
    payload = json.dumps({"bytes": base64.b64encode(source_bytes).decode("ascii"), "metadata": json.loads(meta_json)})
    try:
        done = subprocess.run([sys.executable, "-m", "orion.adapters.parsers.worker"],
                              input=payload, capture_output=True, text=True,
                              timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ParserLimitError("PARSE_TIMEOUT") from exc
    if done.returncode:
        raise ParserLimitError("PARSER_PROCESS_FAILED")
    return done.stdout


@lru_cache(maxsize=32)
def _cached_worker(source_bytes: bytes, meta_json: str, timeout_seconds: float) -> str:
    # Full source bytes + all metadata + timeout bind the cache identity.
    return _run_worker(source_bytes, meta_json, timeout_seconds)


class NativeParser:
    """Run parsing in a bounded child process with a wall-clock timeout.

    The process receives bytes and validated metadata only. It never receives a
    filesystem path or URL. The timeout terminates pathological library parses.
    """
    def __init__(self, timeout_seconds: float = 20.0):
        if not 0 < timeout_seconds <= 20:
            raise ValueError("Invalid parser timeout")
        self.timeout_seconds = timeout_seconds

    def parse_document(self, source_bytes: bytes, metadata: Mapping[str, Any]) -> ParsedDocument:
        if not isinstance(source_bytes, bytes) or not source_bytes or len(source_bytes) > MAX_SOURCE_BYTES:
            raise ParserLimitError("SOURCE_SIZE_LIMIT")
        # Validate trusted metadata before the worker. Fixture hash is replaced.
        _metadata(metadata, source_bytes, "pending")
        meta_json = json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"))
        # Cache immutable parser output only, never mutable DealState or decisions.
        # Large uploads bypass the bounded (32 x <=1MiB) cache.
        worker = _cached_worker if len(source_bytes) <= 1024 * 1024 else _run_worker
        stdout = worker(source_bytes, meta_json, self.timeout_seconds)
        try:
            result = json.loads(stdout)
            if "error" in result:
                raise ParserLimitError(result["error"])
            return ParsedDocument(Document.model_validate(result["document"]),
                                  tuple(SourceSpan.model_validate(s) for s in result["source_spans"]),
                                  tuple(result["warnings"]))
        except (KeyError, json.JSONDecodeError) as exc:
            raise ParserLimitError("PARSER_PROCESS_FAILED") from exc


class NativeSourceIndex:
    """Server-owned original bytes and parser index; caller spans are not trusted."""
    def __init__(self):
        self._files: dict[tuple, bytes] = {}
        self._units: dict[tuple, dict[str, tuple[str, ...]]] = {}
        self._documents: dict[tuple, Document] = {}

    @staticmethod
    def _key(document: Mapping[str, Any] | Document) -> tuple:
        d = document.model_dump(mode="json") if isinstance(document, Document) else document
        return d["id"], d["document_version"], d["parser_version"]

    def add(self, source_bytes: bytes, metadata: Mapping[str, Any]) -> ParsedDocument:
        parsed = NativeParser().parse_document(source_bytes, metadata)
        key = self._key(parsed.document)
        if key in self._files and self._files[key] != source_bytes:
            raise ValueError("Immutable source key already exists")
        self._files[key] = source_bytes
        units: dict[str, list[str]] = {}
        for span in parsed.source_spans:
            loc = canonical_json(span.locator)
            units.setdefault(loc, []).append(span.normalized_text)
        self._units[key] = {k: tuple(v) for k, v in units.items()}
        self._documents[key] = parsed.document
        return parsed

    def file_bytes(self, document: Mapping[str, Any]) -> bytes:
        return self._files[self._key(document)]

    def resolve_units(self, document: Mapping[str, Any], locator: Mapping[str, Any]) -> tuple[str, ...]:
        key = self._key(document)
        if self._documents[key].parse_status != "parsed":
            return ()
        return self._units[key].get(canonical_json(locator), ())

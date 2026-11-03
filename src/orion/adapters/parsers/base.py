"""Native parser boundary only. PDF/DOCX/PPTX implementations begin in Chunk 3."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from orion.domain.models import Document, SourceSpan


@dataclass(frozen=True)
class ParsedDocument:
    document: Document
    source_spans: tuple[SourceSpan, ...]
    warnings: tuple[str, ...] = ()


class DocumentParser(Protocol):
    def parse_document(self, source_bytes: bytes, metadata: Mapping[str, Any]) -> ParsedDocument:
        """Parse trusted metadata + bounded bytes, never fetch URLs or paths.

        The Chunk 3 adapter owns format/signature, expanded-size and timeout
        enforcement. Ambiguous or unsupported units must never be validated.
        """
        ...


class NativeParserUnavailable:
    """Fail-closed placeholder; it never reports fixture text as parsed files."""
    def parse_document(self, source_bytes: bytes, metadata: Mapping[str, Any]) -> ParsedDocument:
        raise NotImplementedError("Native document parsing is not implemented in Chunk 1")

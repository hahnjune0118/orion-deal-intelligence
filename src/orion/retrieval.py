"""Deterministic lexical candidate retrieval from validated current source units.

Retrieval returns documentary snippets, not truth labels. Its input allowlist is
an explicit current DealState; staged future documents, gold keys, and expected
rankings are never globbed or read. Source instructions are inert plain text.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from collections.abc import Iterable
from typing import Any

from orion.domain.grounding import SourceResolver, validate_grounding
from orion.domain.models import DealState


@dataclass(frozen=True)
class RetrievalCandidate:
    source_span_id: str
    document_id: str
    document_version: int
    locator: dict[str, Any]
    text: str
    lexical_score: float
    instruction_status: str = "untrusted_source_data"

    def model_context(self) -> dict:
        return {"source_span_id": self.source_span_id, "document_id": self.document_id,
                "document_version": self.document_version, "locator": self.locator,
                "text": self.text, "instruction_status": self.instruction_status}


def retrieve(state: DealState, query: str, *, limit: int = 8,
             source_resolver: SourceResolver | None = None,
             allowed_document_ids: Iterable[str] | None = None) -> tuple[RetrievalCandidate, ...]:
    if not isinstance(query, str) or len(query) > 10_000 or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("Invalid retrieval request")
    validate_grounding(state, source_resolver=source_resolver).raise_for_errors()
    allowed = {d.id for d in state.documents}
    if allowed_document_ids is not None:
        requested = set(allowed_document_ids)
        if not requested <= allowed:
            raise ValueError("Document outside current source allowlist")
        allowed = requested
    terms = set(re.findall(r"[\w]+", query.casefold(), flags=re.UNICODE))
    scored = []
    seen: set[tuple[str, int, str]] = set()
    for span in state.source_spans:
        if span.document_id not in allowed or span.locator_status != "validated":
            continue
        key = (span.document_id, span.document_version, str(span.locator.model_dump(mode="json")))
        if key in seen:
            continue
        seen.add(key)
        tokens = set(re.findall(r"[\w]+", span.normalized_text.casefold(), flags=re.UNICODE))
        overlap = len(terms & tokens)
        score = overlap / len(terms) if terms else 0.0
        scored.append(RetrievalCandidate(span.id, span.document_id, span.document_version,
                                         span.locator.model_dump(mode="json"), span.normalized_text, score))
    scored.sort(key=lambda item: (-item.lexical_score, item.document_id, item.source_span_id))
    return tuple(scored[:limit])

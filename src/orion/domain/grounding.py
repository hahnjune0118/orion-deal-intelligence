"""Pure source/reference validation for contract 1.0.0.

This module never upgrades truth or review status and does not rank questions.
Fixture validation proves only consistency of authored text, never file parsing.
A Local Live resolver is a trusted server-owned adapter, not request JSON.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import hashlib
import json
from typing import Any, Literal, Protocol
import unicodedata


COLLECTIONS = (
    "documents", "source_spans", "theses", "claims", "evidence",
    "evidence_relations", "dd_questions", "ranking_snapshots",
    "analyst_decisions", "audit_events", "analysis_runs",
)
INPUT_COLLECTIONS = COLLECTIONS[:7]
ValidationMode = Literal["contract", "demo", "local_live"]


class SourceResolver(Protocol):
    """Resolve against server-owned parsed source index and original bytes.

    Exactly one unit must resolve. Adapters must key both lookups by immutable
    document ID/version and parser version; no URL or caller-provided path fetch.
    """
    def file_bytes(self, document: Mapping[str, Any]) -> bytes: ...
    def resolve_units(
        self, document: Mapping[str, Any], locator: Mapping[str, Any]
    ) -> Sequence[str | bytes]: ...


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class GroundingError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = tuple(issues)
        self.code = self.issues[0].code if self.issues else "SOURCE_MISMATCH"
        # Never interpolate quote, filename, raw document, or resolver exception.
        super().__init__("; ".join(f"{i.code} at {i.path}: {i.message}" for i in self.issues))


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()
    fixture_text_only: bool = False

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def code(self) -> str | None:
        return self.issues[0].code if self.issues else None

    def raise_for_errors(self) -> None:
        if self.issues:
            raise GroundingError(self.issues)


def _dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping or Pydantic model")
    return deepcopy(dict(value))


def normalize_text(value: str | bytes) -> str:
    """text-v1: strict UTF-8, Unicode NFC, then CRLF/CR -> LF only."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="strict")
    if not isinstance(value, str):
        raise TypeError("Source text must be str or UTF-8 bytes")
    return unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")


def text_sha256(value: str | bytes) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def input_digest(state: Any) -> str:
    """Hash a caller-selected current ranking input record set; no ranking.

    The Chunk 2 service must supply only records selected for approved evaluation.
    Ordered arrays inside entities (e.g. heading_path) are deliberately retained.
    """
    state = _dict(state)
    records = {"deal": state["deal"]}
    for name in INPUT_COLLECTIONS:
        records[name] = sorted(state[name], key=lambda item: (item["id"], item["entity_version"]))
    return canonical_hash({"contract_version": state["contract_version"], "scoring_version": "1.0.0", "records": records})


def split_quote(span: Any) -> tuple[str, str, str]:
    """Return code-point segments. A UI must render these as escaped text."""
    span = _dict(span)
    text, start, end = span["normalized_text"], span["start"], span["end"]
    if not 0 <= start < end <= len(text) or text[start:end] != span["quote"]:
        raise GroundingError([ValidationIssue("SOURCE_MISMATCH", "source_span", "Quote or offsets do not match")])
    return text[:start], text[start:end], text[end:]


def validate_grounding(
    state: Any,
    draft: Any | None = None,
    *,
    mode: ValidationMode = "contract",
    source_resolver: SourceResolver | None = None,
) -> ValidationReport:
    """Validate current state and optional staged candidate without mutating either.

    ``contract``/``demo`` allow explicit fixture text. ``local_live`` requires
    original bytes + independently resolved native units and rejects fixtures.
    Staging validates references but never recomputes current state or snapshots.
    """
    from .models import validate_envelope

    if mode not in {"contract", "demo", "local_live"}:
        raise ValueError("Unknown validation mode")
    issues: list[ValidationIssue] = []

    def bad(path: str, message: str, code: str = "REFERENCE_INVALID") -> None:
        issues.append(ValidationIssue(code, path, message))

    try:
        base = _dict(validate_envelope(_dict(state)))
        update = _dict(validate_envelope(_dict(draft))) if draft is not None else None
    except (ValueError, TypeError):
        return ValidationReport((ValidationIssue("CONTRACT_INVALID", "envelope", "Envelope does not satisfy the strict contract"),))
    if base["kind"] != "deal_state" or (update is not None and update["kind"] != "staged_evidence_update"):
        return ValidationReport((ValidationIssue("CONTRACT_INVALID", "kind", "A DealState and optional StagedEvidenceUpdate are required"),))
    if base["mode"] == "local_live":
        mode = "local_live"  # Never downgrade a live state via a caller option.
    deal_id = base["deal"]["id"]
    if update:
        if update["deal_id"] != deal_id:
            bad("draft.deal_id", "Cross-deal update")
        if update["base_revision"] != base["state_revision"]:
            bad("draft.base_revision", "Stale base revision", "REVISION_CONFLICT")

    # State holds one current version per entity; history belongs in repository.
    merged = deepcopy(base)
    ids: dict[str, tuple[str, dict[str, Any]]] = {deal_id: ("deal", base["deal"])}
    for name in COLLECTIONS:
        for entity in base[name]:
            path = f"{name}.{entity['id']}"
            if entity["deal_id"] != deal_id:
                bad(path + ".deal_id", "Cross-deal entity")
            if entity["id"] in ids:
                bad(path + ".id", "Entity IDs must be unique across types and current records")
            ids[entity["id"]] = (name, entity)
    if update:
        if update["id"] in ids:
            bad("draft.id", "Update ID collides with an entity")
        for name in ("documents", "source_spans", "evidence", "evidence_relations"):
            current = {item["id"]: item for item in merged[name]}
            seen: set[str] = set()
            for entity in update[name]:
                path = f"draft.{name}.{entity['id']}"
                if entity["deal_id"] != deal_id:
                    bad(path + ".deal_id", "Cross-deal entity")
                if entity["id"] == update["id"]:
                    bad(path + ".id", "Staged entity ID collides with its update ID")
                if entity["id"] in seen:
                    bad(path + ".id", "Duplicate staged entity ID")
                seen.add(entity["id"])
                previous = ids.get(entity["id"])
                if previous:
                    if previous[0] != name or entity["entity_version"] != previous[1]["entity_version"] + 1:
                        bad(path + ".entity_version", "Updated entity must advance the same type by exactly one version")
                    if name in {"documents", "evidence"} and entity["created_at"] != previous[1]["created_at"]:
                        bad(path + ".created_at", "Creation metadata is immutable across entity versions")
                    if name == "documents":
                        old = previous[1]
                        changed = any(entity[k] != old[k] for k in ("file_sha256", "parser_version", "asset_status", "format"))
                        expected = old["document_version"] + int(changed)
                        if entity["document_version"] != expected:
                            bad(path + ".document_version", "Source changes require a new document version; metadata changes retain it")
                    if name == "source_spans" and any(entity[k] != previous[1][k] for k in ("document_id", "document_version", "locator", "normalized_text", "text_sha256")):
                        bad(path + ".id", "Changed source text, native unit or document version requires a new SourceSpan ID")
                elif entity["entity_version"] != 1:
                    bad(path + ".entity_version", "A new entity begins at version one")
                current[entity["id"]] = entity
                ids[entity["id"]] = (name, entity)
            merged[name] = list(current.values())

    by = {name: {item["id"]: item for item in merged[name]} for name in COLLECTIONS}

    def ref(name: str, entity_id: str | None, path: str) -> dict[str, Any] | None:
        if entity_id is None:
            return None
        result = by[name].get(entity_id)
        if result is None:
            bad(path, "Unknown or incorrectly typed reference")
        return result

    for thesis_id in base["deal"]["thesis_ids"]:
        ref("theses", thesis_id, "deal.thesis_ids")
    if set(base["deal"]["thesis_ids"]) != set(by["theses"]):
        bad("deal.thesis_ids", "Deal/thesis membership must be bidirectional")
    for thesis in merged["theses"]:
        for claim_id in thesis["claim_ids"]:
            claim = ref("claims", claim_id, f"theses.{thesis['id']}.claim_ids")
            if claim and claim["thesis_id"] != thesis["id"]:
                bad(f"theses.{thesis['id']}.claim_ids", "Thesis/claim links disagree")
    policies: dict[tuple[str, str], tuple[int, bool]] = {}
    covered: dict[str, set[str]] = defaultdict(set)
    for q in merged["dd_questions"]:
        path = f"dd_questions.{q['id']}"
        claim = ref("claims", q["claim_id"], path + ".claim_id")
        keys = [r["key"] for r in q["requirements"]]
        if len(keys) != len(set(keys)):
            bad(path + ".requirements", "Duplicate requirement key")
        if claim and not set(keys) <= set(claim["required_criterion_keys"]):
            bad(path + ".requirements", "Requirement lies outside claim scope")
        for r in q["requirements"]:
            key, policy = (q["claim_id"], r["key"]), (r["min_reliability"], r["require_independent"])
            if key in policies and policies[key] != policy:
                bad(path + ".requirements", "Shared claim/key policies disagree")
            policies[key] = policy
            covered[q["claim_id"]].add(r["key"])
        for span_id in q["materiality"]["source_span_ids"]:
            ref("source_spans", span_id, path + ".materiality.source_span_ids")
        _validate_inputs(q, bad)
        if q["workflow_status"] == "duplicate":
            target = ref("dd_questions", q["duplicate_of"], path + ".duplicate_of")
            if not target or target["id"] == q["id"] or target["claim_id"] != q["claim_id"] or target["canonical_key"] != q["canonical_key"]:
                bad(path + ".duplicate_of", "Duplicate must reference the same claim/canonical question")
        elif q["duplicate_of"] is not None:
            bad(path + ".duplicate_of", "Only duplicate questions have duplicate_of")
    for claim in merged["claims"]:
        path = f"claims.{claim['id']}"
        thesis = ref("theses", claim["thesis_id"], path + ".thesis_id")
        if thesis and claim["id"] not in thesis["claim_ids"]:
            bad(path + ".thesis_id", "Thesis/claim links disagree")
        if set(claim["required_criterion_keys"]) != covered[claim["id"]]:
            bad(path + ".required_criterion_keys", "Every claim criterion needs a question requirement")
        if claim["period_start"] > claim["period_end"]:
            bad(path + ".period_end", "Claim period ends before it begins")
        for span_id in claim["source_span_ids"]:
            ref("source_spans", span_id, path + ".source_span_ids")
        if claim["claim_kind"] == "analyst_assumption" and claim["truth_status"] != "not_checked":
            bad(path + ".truth_status", "An analyst assumption is not a verified fact")

    fixture = False
    file_valid: dict[str, bool] = {}
    for document in merged["documents"]:
        path = f"documents.{document['id']}"
        if document["asset_status"] == "fixture_text_only":
            fixture = True
            file_valid[document["id"]] = mode != "local_live" and document["file_sha256"] is None
            if mode == "local_live":
                bad(path + ".asset_status", "Fixture text cannot be approved or presented as a verified Local Live source", "SOURCE_MISMATCH")
            if document["file_sha256"] is not None:
                bad(path + ".file_sha256", "Fixture text has no original file hash", "SOURCE_MISMATCH")
        else:
            file_valid[document["id"]] = False
            if source_resolver is None:
                bad(path, "Original file bytes and native source index are required", "SOURCE_MISMATCH")
            else:
                try:
                    raw = source_resolver.file_bytes(document)
                    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != document["file_sha256"]:
                        raise ValueError("Hash mismatch")
                    file_valid[document["id"]] = True
                except Exception:
                    bad(path + ".file_sha256", "Original file bytes do not match the recorded hash", "SOURCE_MISMATCH")
    valid_spans: set[str] = set()
    fixture_units: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for span in merged["source_spans"]:
        fixture_units[(span["document_id"], span["document_version"], canonical_json(span["locator"]))].add(span["normalized_text"])
    for span in merged["source_spans"]:
        path = f"source_spans.{span['id']}"
        before_count = len(issues)
        document = ref("documents", span["document_id"], path + ".document_id")
        if document:
            if span["document_version"] != document["document_version"]:
                bad(path + ".document_version", "Document version mismatch", "SOURCE_MISMATCH")
            expected_format = "docx" if span["locator"]["kind"].startswith("docx_") else span["locator"]["kind"]
            if expected_format != document["format"]:
                bad(path + ".locator", "Native locator and document format disagree", "SOURCE_MISMATCH")
            if span["locator"]["kind"] == "docx_paragraph" and span["locator"]["paragraph_index"] != 0:
                bad(path + ".locator.paragraph_index", "A native body paragraph has paragraph_index zero", "SOURCE_MISMATCH")
            if document["asset_status"] == "fixture_text_only":
                if span["extraction_method"] != "fixture":
                    bad(path + ".extraction_method", "Fixture text must remain explicitly labelled fixture", "SOURCE_MISMATCH")
                key = (span["document_id"], span["document_version"], canonical_json(span["locator"]))
                if len(fixture_units[key]) != 1:
                    bad(path + ".locator", "Fixture locator resolves to conflicting units", "SOURCE_MISMATCH")
            elif span["extraction_method"] == "fixture":
                bad(path + ".extraction_method", "A file-verified source cannot use fixture provenance", "SOURCE_MISMATCH")
            elif source_resolver is not None:
                try:
                    units = source_resolver.resolve_units(document, span["locator"])
                    if isinstance(units, (str, bytes)) or len(units) != 1 or normalize_text(units[0]) != span["normalized_text"]:
                        raise ValueError("Ambiguous or mismatched native unit")
                except Exception:
                    bad(path + ".locator", "Locator must resolve exactly one matching native unit", "SOURCE_MISMATCH")
        text = span["normalized_text"]
        if normalize_text(text) != text or text_sha256(text) != span["text_sha256"]:
            bad(path + ".text_sha256", "Normalized text or its text-v1 hash differs", "SOURCE_MISMATCH")
        if not 0 <= span["start"] < span["end"] <= len(text) or text[span["start"]:span["end"]] != span["quote"]:
            bad(path + ".quote", "Quote and code-point offsets must match exactly", "SOURCE_MISMATCH")
        if span["locator_status"] == "validated" and document and document["parse_status"] != "parsed":
            bad(path + ".locator_status", "A nonparsed source cannot have a validated locator", "SOURCE_MISMATCH")
        if len(issues) == before_count and document and file_valid.get(document["id"]) and span["locator_status"] == "validated":
            valid_spans.add(span["id"])

    for ev in merged["evidence"]:
        path = f"evidence.{ev['id']}"
        claim = ref("claims", ev["claim_id"], path + ".claim_id")
        if claim and not set(ev["criterion_keys"]) <= set(claim["required_criterion_keys"]):
            bad(path + ".criterion_keys", "Evidence lies outside claim scope")
        for span_id in ev["source_span_ids"]:
            ref("source_spans", span_id, path + ".source_span_ids")
            if ev["review_status"] == "approved" and span_id not in valid_spans:
                bad(path + ".source_span_ids", "Approved evidence needs every span validated against a parsed source", "SOURCE_MISMATCH")
        if ev["verification_level"] == "independent_check" and not ev["independent_check_reference"]:
            bad(path + ".independent_check_reference", "Independent verification requires its own reference")
    _validate_relations(merged, by, valid_spans, ref, bad)
    _validate_history(base, by, update, ref, bad)
    # Promotion cannot result merely from a matching quote or source-origin flag.
    for claim in merged["claims"]:
        if claim["truth_status"] != "independently_verified":
            continue
        supporting = [e for e in base["evidence"] if e["claim_id"] == claim["id"] and e["review_status"] == "approved" and e["lifecycle"] == "active" and e["stance"] == "supports" and e["verification_level"] == "independent_check" and e["independent_check_reference"] and all(s in valid_spans for s in e["source_span_ids"])]
        verified = {k for e in supporting for k in e["criterion_keys"] if e["source_reliability"] is not None and e["source_reliability"] >= policies.get((claim["id"], k), (6, True))[0]}
        decision = any(d["actor_role"] == "reviewer" and d["action"] == "approve" and d["target_type"] == "claim" and d["target_id"] == claim["id"] and d["target_version"] == claim["entity_version"] for d in base["analyst_decisions"])
        conflict = any(e["claim_id"] == claim["id"] and e["review_status"] == "approved" and e["lifecycle"] == "active" and e["stance"] == "refutes" and all(s in valid_spans for s in e["source_span_ids"]) and e["source_reliability"] is not None and any(e["source_reliability"] >= policies.get((claim["id"], key), (6, True))[0] for key in e["criterion_keys"]) for e in base["evidence"])
        if not set(claim["required_criterion_keys"]) <= verified or not decision or conflict:
            bad(f"claims.{claim['id']}.truth_status", "Independent truth status needs complete independent checks, an explicit reviewer claim decision and no unresolved refutation")
    return ValidationReport(tuple(issues), fixture_text_only=fixture)


def _validate_inputs(question: dict[str, Any], bad: Any) -> None:
    """Validate recorded bin inputs; does not calculate question priorities."""
    m, o = question["materiality"], question["obtainability"]
    path = f"dd_questions.{question['id']}"
    if m["basis"] == "unknown" and m["score"] is not None:
        bad(path + ".materiality.score", "Unknown materiality uses null, not zero")
    if m["basis"] == "analyst_rubric" and m["score"] is None:
        bad(path + ".materiality.score", "An analyst rubric requires a recorded score; use unknown for missing input")
    if m["basis"] == "objective_ratio":
        if m["exposure_minor"] is None or m["denominator_minor"] is None or m["denominator_minor"] <= 0 or not m["source_span_ids"]:
            bad(path + ".materiality", "Objective ratio needs exposure, positive denominator and source spans")
        else:
            ratio = Decimal(m["exposure_minor"]) / Decimal(m["denominator_minor"])
            expected = sum(ratio >= Decimal(t) for t in ("0.01", "0.03", "0.05", "0.10", "0.20"))
            if m["score"] != expected:
                bad(path + ".materiality.score", "Recorded materiality is inconsistent with fixed ratio bins")
    if o["basis"] == "unknown" and o["score"] is not None:
        bad(path + ".obtainability.score", "Unknown obtainability uses null, not zero")
    if o["basis"] == "analyst_estimate" and o["score"] is None:
        bad(path + ".obtainability.score", "An analyst estimate requires a recorded score; use unknown for missing input")
    if o["basis"] == "derived_cost_time":
        if o["days"] is None or o["external_cost_minor"] is None:
            bad(path + ".obtainability", "Derived obtainability needs both days and cost")
        else:
            days_score = next((score for score, limit in ((5, 1), (4, 3), (3, 7), (2, 14), (1, 30)) if o["days"] <= limit), 0)
            cost_score = next((score for score, limit in ((5, 0), (4, 10000), (3, 50000), (2, 150000), (1, 500000)) if o["external_cost_minor"] <= limit), 0)
            if o["score"] != min(days_score, cost_score):
                bad(path + ".obtainability.score", "Recorded obtainability is inconsistent with fixed time/cost bins")


def _validate_relations(state: dict[str, Any], by: Any, valid_spans: set[str], ref: Any, bad: Any) -> None:
    graph: dict[str, list[str]] = defaultdict(list)
    superseded: set[str] = set()
    for relation in state["evidence_relations"]:
        path = f"evidence_relations.{relation['id']}"
        source = ref("evidence", relation["from_evidence_id"], path + ".from_evidence_id")
        target = ref("evidence", relation["to_evidence_id"], path + ".to_evidence_id")
        if not source or not target:
            continue
        if source["id"] == target["id"]:
            bad(path, "A relation cannot refer to itself")
        scope = set(relation["scope_criterion_keys"])
        if source["claim_id"] != target["claim_id"] or not scope <= set(source["criterion_keys"]) & set(target["criterion_keys"]):
            bad(path + ".scope_criterion_keys", "Relation scope must lie within both evidence atoms on one claim")
        if relation["relation_type"] == "supersedes":
            graph[source["id"]].append(target["id"])
        if relation["review_status"] != "approved":
            continue
        if relation["relation_type"] == "duplicates" and (source["stance"] != target["stance"] or set(source["criterion_keys"]) != set(target["criterion_keys"]) or scope != set(target["criterion_keys"])):
            bad(path, "Duplicates require identical claim, stance and complete scope")
        if relation["relation_type"] == "supersedes":
            if source["review_status"] != "approved" or not all(s in valid_spans for s in source["source_span_ids"]):
                bad(path, "A superseder must be approved with validated spans")
            if target["lifecycle"] != "superseded" or scope != set(target["criterion_keys"]):
                bad(path, "Approved supersession requires complete atom replacement; split partial scope first")
            superseded.add(target["id"])
    for ev in state["evidence"]:
        if ev["lifecycle"] == "superseded" and ev["id"] not in superseded:
            bad(f"evidence.{ev['id']}.lifecycle", "Superseded lifecycle requires an approved complete replacement")
    # Kahn's algorithm avoids recursion limits on long, otherwise valid chains.
    indegree: dict[str, int] = {node: 0 for node in graph}
    for children in graph.values():
        for child in children:
            indegree[child] = indegree.get(child, 0) + 1
    queue = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for child in graph.get(node, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(indegree):
        bad("evidence_relations", "Supersedes must be a directed acyclic graph")


def _validate_history(state: dict[str, Any], by: Any, update: Any, ref: Any, bad: Any) -> None:
    for snapshot in state["ranking_snapshots"]:
        path = f"ranking_snapshots.{snapshot['id']}"
        qids = [r["question_id"] for r in snapshot["rows"]]
        if len(set(qids)) != len(qids) or [r["rank"] for r in snapshot["rows"]] != list(range(1, len(qids) + 1)) or snapshot["top3"] != qids[:3]:
            bad(path, "Snapshot question uniqueness, contiguous rank or Top-3 is inconsistent")
        for qid in qids:
            ref("dd_questions", qid, path + ".rows")
        if snapshot["state_revision"] > state["state_revision"]:
            bad(path + ".state_revision", "Snapshot lies beyond current revision")
    head = ref("ranking_snapshots", state["head_snapshot_id"], "head_snapshot_id")
    if head and head["state_revision"] != state["state_revision"]:
        bad("head_snapshot_id", "Head snapshot must match the latest committed revision")
    known_updates = {s["trigger_event_id"] for s in state["ranking_snapshots"] if s["trigger_event_id"] is not None}
    if update:
        known_updates.add(update["id"])
    target_types = {"claim": "claims", "question": "dd_questions", "evidence": "evidence", "relation": "evidence_relations", "snapshot_export": "ranking_snapshots"}
    for decision in state["analyst_decisions"]:
        path = f"analyst_decisions.{decision['id']}"
        if decision["base_revision"] > state["state_revision"]:
            bad(path + ".base_revision", "Decision lies beyond current state")
        target = None
        if decision["target_type"] in target_types:
            target = ref(target_types[decision["target_type"]], decision["target_id"], path + ".target_id")
        elif decision["target_type"] == "seed":
            target = state["deal"]
            if decision["target_id"] != target["id"]:
                bad(path + ".target_id", "Seed decision must reference its deal")
        elif decision["target_id"] not in known_updates:
            # Rejected/staged events are archived by repository, not in DealState.
            if not any(a["decision_id"] == decision["id"] and a["event_type"] in {"update_rejected", "update_staged"} for a in state["audit_events"]):
                bad(path + ".target_id", "Evidence update decision lacks an event/snapshot linkage")
        if target and decision["target_version"] > target["entity_version"]:
            bad(path + ".target_version", "Decision refers to a nonexistent future version")
        if decision["target_type"] == "evidence_update" and decision["target_version"] != 1:
            bad(path + ".target_version", "Staged updates are immutable version one")
        if decision["target_type"] == "snapshot_export":
            if decision["selection_digest"] is None:
                bad(path + ".selection_digest", "Export approval needs a selection digest")
        elif decision["selection_digest"] is not None:
            bad(path + ".selection_digest", "Only export decisions carry a selection digest")
        if decision["action"] in {"approve", "reject", "reopen"} and decision["actor_role"] != "reviewer" and not (decision["actor_role"] == "system" and decision["target_type"] == "seed" and decision["action"] == "approve"):
            bad(path + ".actor_role", "Approval actions require a server reviewer; system may only install a seed")
    previous_hash, previous_revision = None, 0
    for position, event in enumerate(sorted(state["audit_events"], key=lambda e: e["sequence"]), 1):
        path = f"audit_events.{event['id']}"
        if event["sequence"] != position or event["previous_hash"] != previous_hash:
            bad(path, "Audit sequence or hash-chain linkage is broken")
        if canonical_hash({k: v for k, v in event.items() if k != "event_hash"}) != event["event_hash"]:
            bad(path + ".event_hash", "Audit event content hash differs")
        if event["before_revision"] < previous_revision or event["after_revision"] < event["before_revision"] or event["after_revision"] > state["state_revision"]:
            bad(path, "Audit revision is inconsistent or moves backwards")
        previous_hash, previous_revision = event["event_hash"], event["after_revision"]
        ref("analyst_decisions", event["decision_id"], path + ".decision_id")
        for field in ("before_snapshot_id", "after_snapshot_id"):
            snapshot = ref("ranking_snapshots", event[field], path + "." + field)
            revision = event["before_revision" if field.startswith("before") else "after_revision"]
            if snapshot and snapshot["state_revision"] != revision:
                bad(path + "." + field, "Audit snapshot does not match its revision")
    for run in state["analysis_runs"]:
        path = f"analysis_runs.{run['id']}"
        if run["mode"] == "cached" and any(run[k] != 0 for k in ("token_input", "token_output", "reserved_cost_usd", "actual_cost_usd")):
            bad(path, "Cached runs have zero provider usage and cost")
        if run["mode"] == "live" and run["status"] == "completed" and any(run[k] is None for k in ("model_id", "pricing_version", "token_input", "token_output", "actual_cost_usd", "finished_at")):
            bad(path, "Completed live runs require model, pricing, usage and completion time")
        if run["finished_at"] and datetime.fromisoformat(run["finished_at"]) < datetime.fromisoformat(run["started_at"]):
            bad(path + ".finished_at", "Run completion precedes its start")


def validate_expected_transition(state: Any, draft: Any, expected: Any) -> ValidationReport:
    """Reference-check a test-only expectation, without treating it as model input.

    No expected ranking, formula, score, or status is executed by Foundation.
    """
    from .models import validate_envelope
    base, update = _dict(state), _dict(draft)
    try:
        item = _dict(validate_envelope(_dict(expected)))
    except (ValueError, TypeError):
        return ValidationReport((ValidationIssue("CONTRACT_INVALID", "expected", "Invalid expectation envelope"),))
    issues = []
    def bad(path: str, message: str) -> None:
        issues.append(ValidationIssue("REFERENCE_INVALID", path, message))
    if item["kind"] != "expected_top3_transition":
        bad("expected.kind", "ExpectedTransition required")
        return ValidationReport(tuple(issues))
    if item["deal_id"] != base["deal"]["id"] or item["approval"]["deal_id"] != item["deal_id"] or update["deal_id"] != item["deal_id"]:
        bad("expected.deal_id", "Cross-deal expectation")
    if item["event_id"] != update["id"] or item["approval"]["target_id"] != update["id"]:
        bad("expected.event_id", "Expectation must reference its staged event")
    if item["before_revision"] != base["state_revision"] or item["after_revision"] != item["before_revision"] + 1 or item["approval"]["base_revision"] != item["before_revision"]:
        bad("expected.before_revision", "Expected atomic revision increment is inconsistent")
    approval = item["approval"]
    if approval["actor_role"] != "reviewer" or approval["action"] != "approve" or approval["target_type"] != "evidence_update" or approval["target_version"] != 1 or approval["selection_digest"] is not None:
        bad("expected.approval", "Expected update approval must be a reviewer decision on immutable event version one")
    qids = {q["id"] for q in base["dd_questions"]}
    if any(q not in qids for q in item["before_top3"] + item["after_top3"] + [r["question_id"] for r in item["question_changes"]]):
        bad("expected.questions", "Unknown question reference")
    claim_ids = {c["id"] for c in base["claims"]}
    if any(c["claim_id"] not in claim_ids for c in item["claim_after"]):
        bad("expected.claim_after", "Unknown claim reference")
    head = next((s for s in base["ranking_snapshots"] if s["id"] == base["head_snapshot_id"]), None)
    if head and item["before_top3"] != head["top3"]:
        bad("expected.before_top3", "Expectation baseline differs from supplied snapshot")
    return ValidationReport(tuple(issues))

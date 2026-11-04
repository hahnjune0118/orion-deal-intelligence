"""Stateless, source-validated orchestration for the synthetic Dash workbench.

The browser carries a signed, session-bound action history, never authoritative
models or actor identity. Each request reconstructs a fresh state through the
same domain transition functions used by ReviewService. Demo deliberately does
not open ReviewService's SQLite repository: the preserved Demo architecture
forbids persistent visitor state. A signed historical token is a reproducible
branch, not a distributed multi-user database revision lock.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from orion.domain.grounding import canonical_hash, validate_grounding
from orion.domain.models import AnalystDecision, AuditEvent, DealState
from orion.domain.scoring import evaluate_requirements
from orion.domain.transitions import apply_approved_update, assert_current_state, question_changes
from orion.native_dataset import load_runtime
from orion.services.workspace import ActorContext, require_actor
from orion.synthetic.load import load_scenario, case_folder
from orion.synthetic.scenario import _bayesian
from orion.quant.information_gain import binary_eig

CASE_OPTIONS = [
    {"value": "nb", "label": "Northstar Analytics"},
    {"value": "mf", "label": "Manufacturing research case"},
    {"value": "lm", "label": "Lumen — conflicting evidence"},
    {"value": "ns", "label": "Northstar — foundation case"},
    {"value": "cd", "label": "Cedar — cutoff evidence"},
]
SERVER_ACTOR = ActorContext("actor_web_reviewer", "reviewer")
CaseID = Literal["nb", "mf", "lm", "ns", "cd"]
ID = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]


class WorkspaceError(ValueError):
    """Stable public error code without raw filesystem paths or secrets."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class _Action(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    action: Literal["approve", "reject"]
    event_id: ID
    expected_revision: Annotated[int, Field(ge=1)]
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    reviewed_at: str


class _Envelope(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    version: Literal[1] = 1
    case_id: CaseID
    session_binding: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    branch_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    actions: Annotated[list[_Action], Field(max_length=32)]


class _Command(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    action: Literal["approve", "reject", "reset"]
    event_id: ID | None = None
    expected_revision: Annotated[int, Field(ge=1)]
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    reason: Annotated[str, Field(min_length=1, max_length=2000)]


@dataclass
class _Replay:
    envelope: _Envelope
    state: DealState
    initial: DealState
    events: list
    resolver: object
    metadata: dict
    history: list
    approved_events: list


def _head(state):
    return next(s for s in state.ranking_snapshots if s.id == state.head_snapshot_id)


def locator_label(locator: dict) -> str:
    kind = locator["kind"]
    if kind == "pdf":
        return f"PDF page {locator['page']}, block {locator['block_index']}"
    if kind == "pptx":
        cell = locator.get("table_cell")
        suffix = f", table row {cell['row']}, column {cell['column']}" if cell else ""
        return f"Slide {locator['slide']}, shape {locator['shape_id']}, paragraph {locator['paragraph_index']}{suffix}"
    if kind == "docx_table_cell":
        return f"DOCX table {locator['table_index']}, row {locator['row']}, column {locator['column']}, paragraph {locator['paragraph_index']}"
    return f"DOCX paragraph {locator['paragraph_index']}, block {locator['block_index']}"


class WebWorkspace:
    """A reusable source loader with no mutable visitor state or network calls."""
    def __init__(self, root_path: str | Path, signing_secret: str | bytes):
        self.root = Path(root_path).resolve()
        self.secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("The workspace signing secret must contain at least 32 bytes")
        self._packs = {}  # Immutable source packs only; visitor histories are never cached.

    def _binding(self, session_id: str) -> str:
        if not isinstance(session_id, str) or not 16 <= len(session_id) <= 256:
            raise WorkspaceError("SESSION_REQUIRED", "A server-created browser session is required.")
        return hmac.new(self.secret, b"session:" + session_id.encode(), hashlib.sha256).hexdigest()

    def _encode(self, envelope: _Envelope) -> str:
        raw = envelope.model_dump_json().encode()
        body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        signature = hmac.new(self.secret, b"workspace-v1:" + body.encode(), hashlib.sha256).hexdigest()
        return body + "." + signature

    def _decode(self, token: str, session_id: str) -> _Envelope:
        binding = self._binding(session_id)
        try:
            if not isinstance(token, str) or len(token) > 131072:
                raise ValueError()
            body, signature = token.split(".")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", body) or not re.fullmatch(r"[a-f0-9]{64}", signature):
                raise ValueError()
            expected = hmac.new(self.secret, b"workspace-v1:" + body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            raw = base64.b64decode(body + "=" * (-len(body) % 4), altchars=b"-_", validate=True)
            envelope = _Envelope.model_validate_json(raw)
            if not hmac.compare_digest(envelope.session_binding, binding):
                raise ValueError()
            return envelope
        except (ValueError, TypeError, ValidationError):
            raise WorkspaceError("INVALID_TOKEN", "The workspace token is invalid or belongs to another browser session.") from None

    def _pack(self, case_id: str):
        if case_id not in {o["value"] for o in CASE_OPTIONS}:
            raise WorkspaceError("UNKNOWN_CASE", "Choose an allowlisted synthetic case.")
        if case_id not in self._packs:
            try:
                if case_id in {"nb", "mf"}:
                    dataset = self.root / "chunk3_synthetic_evaluation"
                    state, events, resolver = load_scenario(dataset, case_id)
                    inventory = json.loads((case_folder(dataset, case_id) / "structured/source_inventory.json").read_text(encoding="utf-8"))
                    metadata = {row["document_id"]: row for row in inventory}
                else:
                    state, event, resolver = load_runtime(case_id, self.root / "data/synthetic", self.root / "data/parsed")
                    events, metadata = [event], {}
                assert_current_state(state, mode="demo", source_resolver=resolver)
                self._packs[case_id] = (state, events, resolver, metadata)
            except Exception as exc:
                raise WorkspaceError("SOURCE_VALIDATION_FAILED", "The packaged source records could not be validated. Restore the supplied dataset and retry.") from exc
        state, events, resolver, metadata = self._packs[case_id]
        # Models returned to a caller are never the reusable originals.
        return state.model_copy(deep=True), [e.model_copy(deep=True) for e in events], resolver, dict(metadata)

    def new(self, case_id: str, session_id: str) -> str:
        self._pack(case_id)
        return self._encode(_Envelope(case_id=case_id, session_binding=self._binding(session_id), branch_id=uuid4().hex, actions=[]))

    initial = new

    @staticmethod
    def _decision(state, event, action, token, when, reason):
        require_actor(SERVER_ACTOR, reviewer=True)
        return AnalystDecision(id=f"decision_web_{token}", entity_version=1, deal_id=state.deal.id,
                               actor_id=SERVER_ACTOR.actor_id, actor_role=SERVER_ACTOR.role,
                               target_type="evidence_update", target_id=event.id, target_version=1,
                               selection_digest=None, action=action, reason=reason,
                               base_revision=state.state_revision, decided_at=when)

    @staticmethod
    def _audit(state, *, before, event_type, key, when, reason, token, decision_id=None):
        prior = max(state.audit_events, key=lambda a: a.sequence, default=None)
        value = dict(id=f"audit_web_{token}_{event_type}", entity_version=1,
                     deal_id=state.deal.id, sequence=1 if prior is None else prior.sequence + 1,
                     event_type=event_type, actor_id=SERVER_ACTOR.actor_id, decision_id=decision_id,
                     before_revision=before.state_revision, after_revision=state.state_revision,
                     idempotency_key=key, before_snapshot_id=before.head_snapshot_id,
                     after_snapshot_id=state.head_snapshot_id, reason=reason, created_at=when,
                     previous_hash=None if prior is None else prior.event_hash)
        state.audit_events.append(AuditEvent.model_validate({**value, "event_hash": canonical_hash(value)}))

    def _replay(self, token: str, session_id: str) -> _Replay:
        envelope = self._decode(token, session_id)
        state, events, resolver, metadata = self._pack(envelope.case_id)
        initial = state.model_copy(deep=True)
        history, approved = [], []
        seen, keys = set(), set()
        for recorded in envelope.actions:
            event = next((e for e in events if e.id == recorded.event_id), None)
            if event is None or event.id in seen or recorded.idempotency_key in keys:
                raise WorkspaceError("INVALID_HISTORY", "The signed history contains an invalid or repeated action.")
            if recorded.expected_revision != state.state_revision or event.base_revision != state.state_revision:
                raise WorkspaceError("REVISION_CONFLICT", "The evidence update is based on a different revision.")
            # Events are ordered authored scenarios. Rejection ends this branch.
            if history and history[-1]["action"] == "reject":
                raise WorkspaceError("BRANCH_REJECTED", "Reset this demo before continuing a rejected evidence branch.")
            expected = events[len(approved)] if len(approved) < len(events) else None
            if expected is None or event.id != expected.id:
                raise WorkspaceError("EVENT_NOT_AVAILABLE", "Approve the preceding evidence before opening this event.")
            validate_grounding(state, event, mode="demo", source_resolver=resolver).raise_for_errors()
            before = state.model_copy(deep=True)
            action_token = canonical_hash({"branch": envelope.branch_id, "key": recorded.idempotency_key})[:22]
            self._audit(state, before=before, event_type="update_staged", key=recorded.idempotency_key + ":stage",
                        when=recorded.reviewed_at, reason="Allowlisted native source staged; current ranking unchanged.", token=action_token)
            decision = self._decision(state, event, recorded.action, action_token, recorded.reviewed_at, recorded.reason)
            if recorded.action == "approve":
                state = apply_approved_update(state, event, decision=decision,
                                              snapshot_id=f"snapshot_web_{action_token}", now=recorded.reviewed_at,
                                              mode="demo", source_resolver=resolver)
                approved.append(event)
            else:
                state.analyst_decisions.append(decision)
            self._audit(state, before=before, event_type="update_approved" if recorded.action == "approve" else "update_rejected",
                        key=recorded.idempotency_key, when=recorded.reviewed_at,
                        reason=recorded.reason, token=action_token, decision_id=decision.id)
            assert_current_state(state, mode="demo", source_resolver=resolver)
            seen.add(event.id); keys.add(recorded.idempotency_key)
            rows = [r.model_dump(mode="json") for r in question_changes(before, state)]
            history.append({"event_id": event.id, "action": recorded.action, "stage": events.index(event) + 1,
                            "before_top3": list(_head(before).top3), "after_top3": list(_head(state).top3),
                            "changes": rows, "ranking_changed": any(r["reason"] != "UNCHANGED" for r in rows),
                            "top3_changed": _head(before).top3 != _head(state).top3,
                            "note": event.analyst_note, "reviewed_at": recorded.reviewed_at})
        return _Replay(envelope, state, initial, events, resolver, metadata, history, approved)

    def validated_state(self, token: str, session_id: str):
        replay = self._replay(token, session_id)
        return replay.state, replay.resolver

    @staticmethod
    def _available(replay: _Replay):
        if replay.history and replay.history[-1]["action"] == "reject":
            return None
        index = len(replay.approved_events)
        return replay.events[index] if index < len(replay.events) else None

    def act(self, token: str, session_id: str, action: str, event_id: str | None = None,
            expected_revision: int = 1, idempotency_key: str = "", reason: str = "Explicit synthetic analyst review.") -> dict:
        try:
            command = _Command(action=action, event_id=event_id, expected_revision=expected_revision,
                               idempotency_key=idempotency_key, reason=reason)
            if not command.reason.strip() or not command.idempotency_key.strip():
                raise ValueError()
            if (command.action == "reset") != (command.event_id is None):
                raise ValueError()
        except (ValidationError, ValueError):
            raise WorkspaceError("INVALID_COMMAND", "Supply an allowed action, event, revision and non-empty review reason.") from None
        replay = self._replay(token, session_id)
        for old in replay.envelope.actions:
            if old.idempotency_key == command.idempotency_key:
                if all(getattr(old, name) == getattr(command, name) for name in ("action", "event_id", "expected_revision", "reason")):
                    return {"token": token, "replayed": True, "message": "This request was already applied; no change.", "view": self._view(replay)}
                raise WorkspaceError("IDEMPOTENCY_CONFLICT", "This request identifier was already used for a different decision.")
        # Repeated approvals with a fresh click identifier are safe no-ops.
        old = next((a for a in replay.envelope.actions if a.event_id == command.event_id), None)
        if old:
            if old.action == command.action:
                return {"token": token, "replayed": True, "message": "This evidence event was already decided; no change.", "view": self._view(replay)}
            raise WorkspaceError("EVENT_ALREADY_DECIDED", "This immutable event already has a different decision. Reset to start a new branch.")
        if command.expected_revision != replay.state.state_revision:
            raise WorkspaceError("REVISION_CONFLICT", "The displayed revision is stale. Refresh the workspace and review again.")
        if command.action == "reset":
            new_token = self.new(replay.envelope.case_id, session_id)
            return {"token": new_token, "replayed": False, "message": "Demo restored to the initial state.", "view": self.view(new_token, session_id)}
        event = self._available(replay)
        if event is None or event.id != command.event_id:
            raise WorkspaceError("EVENT_NOT_AVAILABLE", "This event is unavailable. Approve its prerequisite or reset a rejected branch.")
        item = _Action(action=command.action, event_id=command.event_id, expected_revision=command.expected_revision,
                       idempotency_key=command.idempotency_key, reason=command.reason,
                       reviewed_at=(datetime.fromisoformat(event.created_at) + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"))
        candidate = replay.envelope.model_copy(update={"actions": [*replay.envelope.actions, item]})
        new_token = self._encode(_Envelope.model_validate(candidate.model_dump(mode="json")))
        # All reconstruction and validation must succeed before returning a new token.
        committed = self._replay(new_token, session_id)
        change = committed.history[-1]
        message = ("Evidence approved. Ranking updated." if change["top3_changed"] else
                   "Evidence approved. Top-3 unchanged; lower-priority questions changed." if change["ranking_changed"] else
                   "Evidence approved. Ranking unchanged; see the evidence and change explanation.") if action == "approve" else "Evidence rejected. Authoritative ranking unchanged. Reset to review a new branch."
        return {"token": new_token, "replayed": False, "message": message, "view": self._view(committed)}

    dispatch = act

    def _documents(self, documents, metadata):
        return [{**d.model_dump(mode="json"), "title": d.filename,
                 "date": metadata.get(d.id, {}).get("date", d.created_at[:10]),
                 "reporting_period": metadata.get(d.id, {}).get("reporting_period", "Not specified")}
                for d in documents]

    @staticmethod
    def _spans(spans, documents):
        docs = {d.id: d for d in documents}
        return [{**s.model_dump(mode="json"), "filename": docs[s.document_id].filename,
                 "source_origin": docs[s.document_id].source_origin,
                 "locator_label": locator_label(s.locator.model_dump(mode="json")),
                 "prefix": s.normalized_text[:s.start], "suffix": s.normalized_text[s.end:]}
                for s in spans]

    def _rows(self, state):
        head = _head(state)
        ranked = {r.question_id: r.model_dump(mode="json") for r in head.rows}
        claim_map = {c.id: c for c in state.claims}
        thesis_map = {t.id: t for t in state.theses}
        spans = {s.id: s for s in state.source_spans}
        docs = {d.id: d for d in state.documents}
        def refs(ids):
            return "; ".join(dict.fromkeys(f"{docs[spans[i].document_id].filename} · {locator_label(spans[i].locator.model_dump(mode='json'))}" for i in ids))
        questions = []
        for q in state.dd_questions:
            row = ranked.get(q.id, {})
            assessment = evaluate_requirements(state, q.claim_id, q.requirements)
            questions.append({**q.model_dump(mode="json"), "question_id": q.id, "rank": row.get("rank"),
                              "score": row.get("score"), "gap": row.get("gap"),
                              "materiality_score": row.get("materiality", q.materiality.score),
                              "obtainability_score": row.get("obtainability", q.obtainability.score),
                              "thesis_title": thesis_map[claim_map[q.claim_id].thesis_id].title,
                              "evidence_ids": list(assessment.supporting_evidence_ids + assessment.refuting_evidence_ids),
                              "reason_codes": row.get("reason_codes", []), "eig_bits": None,
                              "credited_requirements": sorted(assessment.credited_keys),
                              "conflicting_requirements": sorted(assessment.conflict_keys),
                              "outstanding_requirements": [r.label for r in q.requirements if r.key not in assessment.credited_keys or r.key in assessment.conflict_keys],
                              "score_formula": "9 × Evidence gap + 8 × Materiality + 3 × Obtainability"})
        questions.sort(key=lambda q: (q["rank"] is None, q["rank"] or 0, q["id"]))
        evidence = [{**e.model_dump(mode="json"), "statement": " ".join(spans[s].quote for s in e.source_span_ids),
                     "source_refs": refs(e.source_span_ids), "claim_statement": claim_map[e.claim_id].statement,
                     "truth_status": claim_map[e.claim_id].truth_status} for e in state.evidence]
        claims = []
        for c in state.claims:
            linked = [q for q in questions if q["claim_id"] == c.id]
            source_ids = list(dict.fromkeys(c.source_span_ids + [sid for e in state.evidence if e.claim_id == c.id for sid in e.source_span_ids]))
            claims.append({**c.model_dump(mode="json"), "thesis_title": thesis_map[c.thesis_id].title,
                           "financial_driver": ", ".join(sorted({q["financial_driver"] for q in linked})),
                           "source_refs": refs(source_ids), "linked_question_count": len(linked)})
        theses = []
        for t in state.theses:
            linked = [q for q in questions if q["claim_id"] in t.claim_ids]
            theses.append({**t.model_dump(mode="json"), "claims_summary": "\n".join(claim_map[c].statement for c in t.claim_ids),
                           "financial_drivers": ", ".join(sorted({q["financial_driver"] for q in linked})),
                           "evidence_status": ", ".join(dict.fromkeys(claim_map[c].support_status for c in t.claim_ids)),
                           "verification_requirements": "; ".join(dict.fromkeys(r for q in linked for r in q["outstanding_requirements"])),
                           "question_ids": [q["id"] for q in linked],
                           "materiality": max((q["materiality_score"] or 0 for q in linked), default=0)})
        return questions, evidence, claims, theses

    def _view(self, replay):
        state = replay.state
        questions, evidence, claims, theses = self._rows(state)
        next_event = self._available(replay)
        decisions = {a.event_id: a.action for a in replay.envelope.actions}
        events = []
        stage_labels = {"nb": ["Contract evidence", "Commercial execution", "Unit economics", "Ownership and reconciliation"],
                        "mf": ["Inventory count reconciliation"], "lm": ["Contract side letter and conflict"]}
        for index, event in enumerate(replay.events, 1):
            decided = decisions.get(event.id)
            available = next_event is not None and next_event.id == event.id
            labels = stage_labels.get(replay.envelope.case_id, ["Source-backed evidence"])
            events.append({"id": event.id, "stage": index, "label": f"T{index} · {labels[index-1]}",
                           "note": event.analyst_note if available or decided else "Available after prerequisite approval.",
                           "status": ("approved" if decided == "approve" else "rejected") if decided else ("available" if available else "locked"),
                           "available": available, "document_ids": [d.id for d in event.documents] if available or decided else []})
        analytics = _bayesian(replay.envelope.case_id, replay.approved_events)
        analytics["eig_candidates"] = []
        if replay.envelope.case_id == "nb":
            initial = analytics["initial_eig"]
            analytics["eig_candidates"].append({"label": "Initial contract verification scenario", "stage": 0, **initial})
            for belief in analytics["belief_snapshots"]:
                result = binary_eig(belief["prior"], belief["likelihood_h"], belief["likelihood_not_h"], belief["assumption_source"])
                analytics["eig_candidates"].append({"label": f"T{belief['stage']} · {belief['evidence_id']}", "stage": belief["stage"], **asdict(result)})
        analytics["candidate_eig"] = None
        if replay.envelope.case_id == "nb" and next_event is not None:
            # This is a prospective scenario calculation, not a committed belief
            # update. Parameters come verbatim from the preserved Chunk 3 engine.
            candidate_belief = _bayesian("nb", [*replay.approved_events, next_event])["belief_snapshots"][-1]
            candidate_result = binary_eig(candidate_belief["prior"], candidate_belief["likelihood_h"],
                                          candidate_belief["likelihood_not_h"], candidate_belief["assumption_source"])
            atom = next(e for e in next_event.evidence if e.id == candidate_belief["evidence_id"])
            affected = [q.id for q in state.dd_questions if q.claim_id == atom.claim_id
                        and set(atom.criterion_keys) & {r.key for r in q.requirements}]
            analytics["candidate_eig"] = {**asdict(candidate_result), "event_id": next_event.id,
                                          "evidence_id": atom.id, "question_ids": affected,
                                          "label": "Prospective hypothetical evidence model — unapproved",
                                          "committed": False}
            for question in questions:
                if question["id"] in affected:
                    question["eig_bits"] = candidate_result.eig_bits
                    question["eig_basis"] = "Prospective supplied hypothetical model; independent of canonical priority."
        analytics["eig_note"] = "Only the supplied hypothetical binary evidence models are parameterized. Question-level EIG is unavailable where no likelihood model is supplied. Prospective EIG is not an approved belief update and never changes canonical priority."
        analytics["financial_materiality"] = [{"question_id": q["id"], "issue": q["issue"], "driver": q["financial_driver"], **q["materiality"]} for q in questions]
        issue = {q["id"]: q["issue"] for q in questions}
        changes = [{**r, "issue": issue[r["question_id"]]} for r in replay.history[-1]["changes"]] if replay.history else []
        covered = sum(c.support_status == "supported" for c in state.claims)
        return {"case_id": replay.envelope.case_id, "deal": state.deal.model_dump(mode="json"),
                "revision": state.state_revision, "snapshot_id": state.head_snapshot_id, "stage": len(replay.approved_events),
                "summary": {"documents": len(state.documents), "theses": len(state.theses), "evidence": len(state.evidence),
                            "open_questions": sum(q.workflow_status == "open" for q in state.dd_questions),
                            "unresolved_risks": sum(c.support_status in {"missing", "partial", "contradicted"} for c in state.claims),
                            "evidence_coverage": round(100 * covered / len(state.claims), 1) if state.claims else 0,
                            "evidence_coverage_definition": "Share of claims with all required evidence satisfied; not independent truth verification.",
                            "last_update": replay.history[-1]["reviewed_at"] if replay.history else state.deal.as_of,
                            "review_status": "Rejected branch — reset to continue" if replay.history and replay.history[-1]["action"] == "reject" else "Synthetic analyst-reviewed state"},
                "documents": self._documents(state.documents, replay.metadata), "theses": theses, "claims": claims,
                "evidence": evidence, "questions": questions, "top3": [q for q in questions if q["id"] in _head(state).top3],
                "events": events, "changes": changes, "history": replay.history, "analytics": analytics,
                "audit": [a.model_dump(mode="json") for a in state.audit_events],
                "decisions": [d.model_dump(mode="json") for d in state.analyst_decisions],
                "score_formula": "P = 9G + 8M + 3O", "scoring_version": "1.0.0",
                "timestamp_basis": "Deterministic synthetic fixture-relative replay times; not real-world reviewer sign-off times.",
                "limitations": ["Synthetic preliminary screening; not a completed FDD report or investment recommendation.",
                                "Source matching proves that a document reports a statement, not that the statement is independently true.",
                                "Deterministic authored demo. No live LLM calls or real B0–B3 benchmark results.",
                                "Public Orion source ingestion remains pending; it is not offered as an ingested deal.",
                                "Session-bound demo branches are temporary. Reload/reset starts a new branch; no production VDR persistence is claimed."]}

    def view(self, token: str, session_id: str) -> dict:
        return self._view(self._replay(token, session_id))

    def preview(self, token: str, session_id: str, event_id: str) -> dict:
        replay = self._replay(token, session_id)
        event = self._available(replay)
        if event is None or event.id != event_id:
            raise WorkspaceError("EVENT_NOT_AVAILABLE", "Only the next available event can be previewed.")
        state = replay.state
        validate_grounding(state, event, mode="demo", source_resolver=replay.resolver).raise_for_errors()
        decision = self._decision(state, event, "approve", "preview", event.created_at, "Preview only; no analyst decision has been committed.")
        after = apply_approved_update(state, event, decision=decision, snapshot_id="snapshot_web_preview",
                                      now=event.created_at, mode="demo", source_resolver=replay.resolver)
        rows = [r.model_dump(mode="json") for r in question_changes(state, after)]
        names = {q.id: q.issue for q in state.dd_questions}
        rows = [{**r, "issue": names[r["question_id"]]} for r in rows]
        return {"event": {"id": event.id, "note": event.analyst_note, "base_revision": event.base_revision},
                "documents": self._documents(event.documents, replay.metadata),
                "evidence": [e.model_dump(mode="json") for e in event.evidence],
                "spans": self._spans(event.source_spans, [*state.documents, *event.documents]),
                "before_top3": list(_head(state).top3), "after_top3": list(_head(after).top3),
                "changes": rows, "ranking_changed": any(r["reason"] != "UNCHANGED" for r in rows),
                "top3_changed": _head(state).top3 != _head(after).top3,
                "note": event.analyst_note, "revision": state.state_revision,
                "label": "Preview — approval required; committed ranking is unchanged"}

    def inspect(self, token: str, session_id: str, kind: str, item_id: str) -> dict:
        replay = self._replay(token, session_id)
        state = replay.state
        collections = {"document": state.documents, "claim": state.claims, "question": state.dd_questions,
                       "thesis": state.theses, "evidence": state.evidence, "source": state.source_spans}
        if kind not in collections or not isinstance(item_id, str):
            raise WorkspaceError("UNKNOWN_SELECTION", "Select an available source, claim or question.")
        selected = next((i for i in collections[kind] if i.id == item_id), None)
        if selected is None:
            raise WorkspaceError("UNKNOWN_SELECTION", "The selected record is not in the current approved workspace.")
        claim_ids, span_ids = set(), set()
        if kind == "document":
            span_ids = {s.id for s in state.source_spans if s.document_id == item_id}
        elif kind == "source":
            span_ids = {item_id}
        elif kind == "claim":
            claim_ids = {item_id}
        elif kind == "thesis":
            claim_ids = set(selected.claim_ids)
        else:
            claim_ids = {selected.claim_id}
            if kind == "evidence": span_ids = set(selected.source_span_ids)
        if not claim_ids:
            claim_ids = {e.claim_id for e in state.evidence if set(e.source_span_ids) & span_ids}
            claim_ids |= {c.id for c in state.claims if set(c.source_span_ids) & span_ids}
        if kind not in {"document", "source", "evidence"}:
            span_ids |= {sid for c in state.claims if c.id in claim_ids for sid in c.source_span_ids}
            span_ids |= {sid for e in state.evidence if e.claim_id in claim_ids for sid in e.source_span_ids}
        questions, evidence, claims, _ = self._rows(state)
        title = getattr(selected, "filename", None) or getattr(selected, "statement", None) or getattr(selected, "issue", None) or getattr(selected, "title", None) or item_id
        return {"kind": kind, "id": item_id, "title": title, "metadata": selected.model_dump(mode="json"),
                "spans": self._spans([s for s in state.source_spans if s.id in span_ids], state.documents),
                "claims": [c for c in claims if c["id"] in claim_ids],
                "questions": [q for q in questions if q["claim_id"] in claim_ids],
                "evidence": [e for e in evidence if (e["id"] == item_id if kind == "evidence" else e["claim_id"] in claim_ids)],
                "verification_note": "Validated excerpt and native locator; this is not independent verification of the underlying claim."}

    def document_bytes(self, token: str, session_id: str, document_id: str):
        replay = self._replay(token, session_id)
        document = next((d for d in replay.state.documents if d.id == document_id), None)
        if document is None:
            raise WorkspaceError("UNKNOWN_DOCUMENT", "Only documents in the current workspace may be downloaded.")
        content = replay.resolver.file_bytes(document.model_dump(mode="json"))
        if hashlib.sha256(content).hexdigest() != document.file_sha256:
            raise WorkspaceError("SOURCE_MISMATCH", "The source checksum does not match.")
        return document.filename, content

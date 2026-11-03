"""Stage and decide immutable evidence updates inside a real SQLite transaction.

Only server-held staged IDs are accepted by the review command boundary. A
client cannot provide an ActorContext, evidence body, score or new snapshot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Annotated, Callable, Literal, Mapping
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from orion.adapters.sqlite_repo import (
    COLLECTIONS, RepositoryCommitResult, RepositoryError, RevisionWriter,
    SQLiteRepository, payload_digest,
)
from orion.domain.grounding import validate_grounding
from orion.domain.models import AnalystDecision, AuditEvent, DealState, StagedEvidenceUpdate
from orion.services.workspace import ActorContext, require_actor

ID = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]


@dataclass(frozen=True)
class CommitResult:
    state_revision: int
    snapshot_id: str
    changed_question_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    replayed: bool = False


def _compare_rows(before: list[dict], after: list[dict]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    old = {row["question_id"]: row for row in before}
    new = {row["question_id"]: row for row in after}
    changed = tuple(sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key)))
    reasons: set[str] = set()
    for key in changed:
        if key not in new:
            reasons.add("QUESTION_RESOLVED")
        elif key not in old:
            reasons.add("QUESTION_REOPENED")
        elif old[key]["score"] != new[key]["score"]:
            reasons.add("SCORE_CHANGED")
        elif old[key]["rank"] != new[key]["rank"]:
            reasons.add("RELATIVE_PROMOTION" if new[key]["rank"] < old[key]["rank"] else "RELATIVE_DEMOTION")
        else:
            reasons.add("EVIDENCE_STATUS_CHANGED")
    return changed, tuple(sorted(reasons)) if reasons else ("RANKING_UNCHANGED",)


class ReviewCommand(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    action: Literal["approve", "reject"]
    deal_id: ID
    event_id: ID
    expected_revision: Annotated[int, Field(ge=1)]
    idempotency_key: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _audit(state: DealState, *, actor: ActorContext, event_type: str, reason: str,
           key: str, now: str, decision_id: str | None = None, after: DealState | None = None) -> AuditEvent:
    after = state if after is None else after
    previous = max(state.audit_events, key=lambda x: x.sequence, default=None)
    value = dict(id=_id("audit"), entity_version=1, deal_id=state.deal.id,
                 sequence=1 if previous is None else previous.sequence + 1,
                 event_type=event_type, actor_id=actor.actor_id, decision_id=decision_id,
                 before_revision=state.state_revision, after_revision=after.state_revision,
                 idempotency_key=key, before_snapshot_id=state.head_snapshot_id,
                 after_snapshot_id=after.head_snapshot_id, reason=reason, created_at=now,
                 previous_hash=None if previous is None else previous.event_hash)
    return AuditEvent.model_validate({**value, "event_hash": payload_digest(value)})


def _persist_delta(writer: RevisionWriter, before: DealState, after: DealState) -> None:
    """Persist versions and immutable records; all writes share the same transaction."""
    for type_name, collection in COLLECTIONS.items():
        old = {entity.id: entity.model_dump(mode="json") for entity in getattr(before, collection)}
        for entity in getattr(after, collection):
            if old.get(entity.id) != entity.model_dump(mode="json"):
                writer.put_entity(type_name, entity)
    writer.set_head(after.head_snapshot_id)


class ReviewService:
    def __init__(self, repo: SQLiteRepository, actor: ActorContext, *, clock: Callable[[], str] = _now):
        self.repo = repo
        self.actor = require_actor(actor)
        self.clock = clock

    def _result(self, deal_id: str, result: RepositoryCommitResult, action: str) -> CommitResult:
        # Read the immutable result snapshots, never the workspace's current head.
        # Thus retries after later approvals retain the first command's result.
        changed: tuple[str, ...] = ()
        reasons = ("UPDATE_STAGED" if action == "stage" else "UPDATE_REJECTED",)
        if action == "approve":
            with self.repo.connect() as con:
                after = con.execute("SELECT payload FROM snapshots WHERE deal_id=? AND snapshot_id=?",
                                    (deal_id, result.snapshot_id)).fetchone()
                before = con.execute("SELECT payload FROM snapshots WHERE deal_id=? AND state_revision=?",
                                     (deal_id, result.state_revision - 1)).fetchone()
                if before is None or after is None:
                    raise RepositoryError("SOURCE_MISMATCH", "Committed comparison snapshots are missing")
                changed, reasons = _compare_rows(json.loads(before[0])["rows"], json.loads(after[0])["rows"])
        return CommitResult(result.state_revision, result.snapshot_id, changed, reasons, result.replayed)

    def stage(self, event: StagedEvidenceUpdate | dict, *, idempotency_key: str,
              source_blobs: Mapping[str, bytes] | None = None) -> CommitResult:
        """Trusted ingestion entry point, not a browser payload route.

        Parser/extraction code supplies the full candidate. Its claimed status is
        never sufficient: references and source bytes are validated again here.
        Staging does not activate any evidence or change a ranking Snapshot.
        """
        require_actor(self.actor)
        raw = event.model_dump(mode="json") if isinstance(event, StagedEvidenceUpdate) else event
        candidate = StagedEvidenceUpdate.model_validate(raw)
        blobs = dict(source_blobs or {})
        for digest, content in blobs.items():
            if type(content) is not bytes or sha256(content).hexdigest() != digest:
                raise RepositoryError("SOURCE_MISMATCH", "Source bytes do not match their declared digest")
        if candidate.validation_status != "validated":
            raise RepositoryError("SOURCE_MISMATCH", "The candidate must pass validation before staging")
        payload = {"action": "stage", "actor_id": self.actor.actor_id, "actor_role": self.actor.role,
                   "event": candidate.model_dump(mode="json"), "source_sha256": sorted(blobs)}

        def change(writer: RevisionWriter) -> None:
            from orion.domain.transitions import assert_current_state
            state = writer.read_state()
            assert_current_state(state, mode=self.repo.validation_mode, source_resolver=self.repo.source_resolver)
            validate_grounding(state, candidate, mode=self.repo.validation_mode,
                               source_resolver=self.repo.source_resolver).raise_for_errors()
            for digest, content in blobs.items():
                writer.put_source_blob(content, expected_sha256=digest)
            writer.archive_staged(candidate)
            writer.append_audit(_audit(state, actor=self.actor, event_type="update_staged",
                                      reason=candidate.analyst_note, key=idempotency_key, now=self.clock()))

        result = self.repo.transact_audit(candidate.deal_id, idempotency_key=idempotency_key,
                                         request_payload=payload, expected_revision=candidate.base_revision,
                                         mutate=change)
        return self._result(candidate.deal_id, result, "stage")

    def execute(self, command: ReviewCommand | dict) -> CommitResult:
        """Strict callback-safe command; actor is exclusively the bound context."""
        require_actor(self.actor, reviewer=True)
        raw = command.model_dump(mode="json") if isinstance(command, ReviewCommand) else command
        parsed = ReviewCommand.model_validate(raw)
        if not parsed.reason.strip():
            raise ValueError("A meaningful review reason is required")
        payload = {**parsed.model_dump(mode="json"), "actor_id": self.actor.actor_id,
                   "actor_role": self.actor.role}

        def change(writer: RevisionWriter) -> None:
            from orion.domain.transitions import apply_approved_update, assert_current_state
            before = writer.read_state()
            assert_current_state(before, mode=self.repo.validation_mode, source_resolver=self.repo.source_resolver)
            event = writer.read_staged(parsed.event_id)
            if event.base_revision != parsed.expected_revision:
                raise RepositoryError("REVISION_CONFLICT", "Staged event is bound to a different base revision")
            validate_grounding(before, event, mode=self.repo.validation_mode,
                               source_resolver=self.repo.source_resolver).raise_for_errors()
            now = self.clock()
            decision = AnalystDecision.model_validate(dict(
                id=_id("decision"), entity_version=1, deal_id=before.deal.id,
                actor_id=self.actor.actor_id, actor_role=self.actor.role,
                target_type="evidence_update", target_id=event.id, target_version=1,
                selection_digest=None, action=parsed.action, reason=parsed.reason,
                base_revision=before.state_revision, decided_at=now))
            if parsed.action == "approve":
                after = apply_approved_update(before, event, decision=decision,
                                              snapshot_id=_id("snapshot"), now=now,
                                              mode=self.repo.validation_mode,
                                              source_resolver=self.repo.source_resolver)
                old_head = next(s for s in before.ranking_snapshots if s.id == before.head_snapshot_id)
                new_head = next(s for s in after.ranking_snapshots if s.id == after.head_snapshot_id)
                changed, reasons = _compare_rows([r.model_dump(mode="json") for r in old_head.rows],
                                                 [r.model_dump(mode="json") for r in new_head.rows])
                audit = _audit(before, actor=self.actor, event_type="update_approved",
                               reason=f"{parsed.reason} | {','.join(reasons)} | questions={','.join(changed)}",
                               key=parsed.idempotency_key, now=now,
                               decision_id=decision.id, after=after)
                after = after.model_copy(update={"audit_events": [*after.audit_events, audit]})
                validate_grounding(after, mode=self.repo.validation_mode,
                                   source_resolver=self.repo.source_resolver).raise_for_errors()
                _persist_delta(writer, before, after)
            else:
                writer.append_decision(decision)
                writer.append_audit(_audit(before, actor=self.actor, event_type="update_rejected",
                                          reason=parsed.reason, key=parsed.idempotency_key, now=now,
                                          decision_id=decision.id))
            writer.resolve_staged(event.id, parsed.action, decision.id)

        transaction = self.repo.transact if parsed.action == "approve" else self.repo.transact_audit
        result = transaction(parsed.deal_id, idempotency_key=parsed.idempotency_key,
                             request_payload=payload, expected_revision=parsed.expected_revision, mutate=change)
        return self._result(parsed.deal_id, result, parsed.action)

    def approve(self, deal_id: str, event_id: str, *, expected_revision: int,
                idempotency_key: str, reason: str) -> CommitResult:
        return self.execute(dict(action="approve", deal_id=deal_id, event_id=event_id,
                                 expected_revision=expected_revision, idempotency_key=idempotency_key, reason=reason))

    def reject(self, deal_id: str, event_id: str, *, expected_revision: int,
               idempotency_key: str, reason: str) -> CommitResult:
        return self.execute(dict(action="reject", deal_id=deal_id, event_id=event_id,
                                 expected_revision=expected_revision, idempotency_key=idempotency_key, reason=reason))

"""Stateless, allowlisted synthetic replay without storage or external providers.

Only packaged synthetic inputs can be loaded. No gold/expected-result loader,
database, request-global session, provider import or filesystem path parameter.
``replay_reviewed_demo`` is the Chunk 2 engine entry point. ``replay_demo``
preserves the Foundation seed-only API, including its fail-closed behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orion.config import BoundaryError
from orion.domain.models import DealState, StagedEvidenceUpdate, validate_envelope

CaseID = Literal["ns", "cd", "lm"]


class DemoAction(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    action: Literal["approve", "reject", "reset"]
    event_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")] | None

    @model_validator(mode="after")
    def reset_has_no_event(self):
        if (self.action == "reset") != (self.event_id is None):
            raise ValueError("reset requires null event_id; other actions require an event ID")
        return self


class DemoRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    case_id: CaseID
    actions: Annotated[list[DemoAction], Field(max_length=32)]


@dataclass(frozen=True)
class ReplayInput:
    """Fresh request-owned objects, never shared between callers."""
    state: DealState
    staged_event: StagedEvidenceUpdate
    actions: tuple[DemoAction, ...]


def prepare_replay(request: DemoRequest | dict) -> ReplayInput:
    # Revalidation prevents model_construct / mutable nested input bypasses.
    raw = request.model_dump(mode="json") if isinstance(request, DemoRequest) else request
    parsed = DemoRequest.model_validate(raw)
    folder = files("orion").joinpath("resources", "demo", parsed.case_id)
    state = validate_envelope(folder.joinpath("initial_state.json").read_bytes())
    event = validate_envelope(folder.joinpath("staged_evidence_update.json").read_bytes())
    if not isinstance(state, DealState) or not isinstance(event, StagedEvidenceUpdate):
        raise BoundaryError("DEMO_ACTION_NOT_ALLOWED", "Invalid packaged fixture type.")
    from orion.domain.grounding import validate_grounding

    validate_grounding(state, event, mode="demo").raise_for_errors()
    seen: set[str] = set()
    active_actions: list[DemoAction] = []
    for action in parsed.actions:
        if action.action == "reset":
            seen.clear()
            active_actions.clear()
            continue
        if action.event_id != event.id:
            raise BoundaryError("DEMO_ACTION_NOT_ALLOWED", "Event is not allowed for this synthetic case.")
        if action.event_id in seen:
            raise BoundaryError("DEMO_ACTION_NOT_ALLOWED", "An event may be decided once per branch.")
        seen.add(action.event_id)
        active_actions.append(action)
    return ReplayInput(state, event, tuple(active_actions))


def replay_demo(request: DemoRequest | dict) -> DealState:
    """Legacy Foundation seed/reset API; review is explicitly opt-in elsewhere."""
    prepared = prepare_replay(request)
    if prepared.actions:
        raise BoundaryError("FEATURE_NOT_IMPLEMENTED", "Approval/rejection replay requires the Chunk 2 engine.")
    return prepared.state


def replay_reviewed_demo(request: DemoRequest | dict) -> DealState:
    """Rebuild a reviewed synthetic branch from trusted fixtures on every call.

    The client supplies only a case and allowlisted action log. Actor, review
    scope, source records, clock, IDs, scores and revisions are server-derived.
    Deterministic fixture-relative timestamps describe a simulation, not a real
    analyst's review time. No server database or shared mutable state is used.
    """
    from datetime import datetime, timedelta

    from orion.domain.grounding import canonical_hash, validate_grounding
    from orion.domain.models import AnalystDecision, AuditEvent
    from orion.domain.transitions import apply_approved_update, assert_current_state

    prepared = prepare_replay(request)
    state, event = prepared.state, prepared.staged_event
    assert_current_state(state)
    for action in prepared.actions:
        # prepare_replay has already reduced resets and checked event ownership.
        token = canonical_hash({"event": event.id, "action": action.action})[:24]
        when = datetime.fromisoformat(event.created_at)
        stage_time = when.isoformat().replace("+00:00", "Z")
        decision_time = (when + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        actor_id = "actor_demo_reviewer"

        def audit(target: DealState, *, suffix: str, event_type: str,
                  decision_id: str | None, before_revision: int,
                  before_snapshot: str, reason: str, created_at: str) -> None:
            prior = max(target.audit_events, key=lambda row: row.sequence, default=None)
            payload = {
                "id": f"audit_demo_{token}_{suffix}", "entity_version": 1,
                "deal_id": target.deal.id, "sequence": 1 if prior is None else prior.sequence + 1,
                "event_type": event_type, "actor_id": actor_id, "decision_id": decision_id,
                "before_revision": before_revision, "after_revision": target.state_revision,
                "idempotency_key": f"demo:{event.id}:{suffix}",
                "before_snapshot_id": before_snapshot, "after_snapshot_id": target.head_snapshot_id,
                "reason": reason, "created_at": created_at,
                "previous_hash": None if prior is None else prior.event_hash,
            }
            target.audit_events.append(AuditEvent.model_validate({
                **payload, "event_hash": canonical_hash(payload),
            }))

        audit(state, suffix="staged", event_type="update_staged", decision_id=None,
              before_revision=state.state_revision, before_snapshot=state.head_snapshot_id,
              reason="Allowlisted synthetic evidence staged; ranking unchanged.", created_at=stage_time)
        decision = AnalystDecision(
            id=f"decision_demo_{token}", entity_version=1, deal_id=state.deal.id,
            actor_id=actor_id, actor_role="reviewer", target_type="evidence_update",
            target_id=event.id, target_version=1, selection_digest=None,
            action=action.action, reason="Explicit synthetic reviewer simulation.",
            base_revision=state.state_revision, decided_at=decision_time,
        )
        before_revision, before_snapshot = state.state_revision, state.head_snapshot_id
        if action.action == "approve":
            state = apply_approved_update(
                state, event, decision=decision,
                snapshot_id=f"snapshot_demo_{token}", now=decision_time,
            )
        else:
            state.analyst_decisions.append(decision)
        audit(state, suffix=action.action,
              event_type="update_approved" if action.action == "approve" else "update_rejected",
              decision_id=decision.id, before_revision=before_revision,
              before_snapshot=before_snapshot,
              reason="Synthetic evidence approved; ranking recomputed." if action.action == "approve"
              else "Synthetic evidence rejected; ranking unchanged.", created_at=decision_time)
        validate_grounding(state, mode="demo").raise_for_errors()
        assert_current_state(state)
    return state

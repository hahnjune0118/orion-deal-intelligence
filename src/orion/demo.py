"""Stateless Foundation boundary, not the Chunk 2 approval/ranking engine.

Only packaged synthetic inputs can be loaded. No gold/expected-result loader,
database, request-global session, provider import or filesystem path parameter.
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
    prepared = prepare_replay(request)
    if prepared.actions:
        raise BoundaryError("FEATURE_NOT_IMPLEMENTED", "Approval/rejection replay requires the Chunk 2 engine.")
    return prepared.state

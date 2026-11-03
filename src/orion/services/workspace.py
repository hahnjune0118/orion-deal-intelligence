"""Trusted server identity and read-only workspace access.

Construct ActorContext from the local server configuration/authentication layer,
never from callback JSON. This is a single-user local app, not a remote identity
provider. ReviewService accepts an actual context object, never an actor dict.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from orion.adapters.sqlite_repo import RepositoryError, SQLiteRepository
from orion.domain.models import DealState


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: Literal["analyst", "reviewer", "system"]

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", self.actor_id):
            raise ValueError("Actor ID must satisfy the contract ID format")
        if self.role not in {"analyst", "reviewer", "system"}:
            raise ValueError("Unknown server actor role")


def require_actor(actor: ActorContext, *, reviewer: bool = False) -> ActorContext:
    if type(actor) is not ActorContext:
        raise RepositoryError("UNAUTHORIZED", "A trusted server ActorContext is required")
    if actor.role not in ({"reviewer"} if reviewer else {"analyst", "reviewer"}):
        raise RepositoryError("UNAUTHORIZED", "This action is not allowed for the server actor")
    return actor


class WorkspaceService:
    def __init__(self, repo: SQLiteRepository, actor: ActorContext):
        self.repo = repo
        self.actor = require_actor(actor)

    def get_state(self, deal_id: str) -> DealState:
        require_actor(self.actor)
        state = self.repo.read_state(deal_id)
        from orion.domain.transitions import assert_current_state
        assert_current_state(state, mode=self.repo.validation_mode, source_resolver=self.repo.source_resolver)
        return state

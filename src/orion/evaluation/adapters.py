"""Honest benchmark adapters. No real LLM invocation is implemented in Chunk 3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .inputs import assert_safe_bundle
from .models import SystemOutput


class ModelAdapter(Protocol):
    model_version: str
    prompt_version: str

    def generate(self, source_input: dict) -> SystemOutput: ...


@dataclass(frozen=True)
class AuthoredFixtureAdapter:
    """Explicit test double. Fixture output is authored separately from gold.

    It deliberately makes no claim to extraction ability. The source digest is
    pinned by the caller's manifest so a fixture cannot silently become a model
    run. Human-reviewed annotation stays solely on the evaluation side.
    """
    fixture: SystemOutput
    model_version: str = "not_applicable:authored-fixture"
    prompt_version: str = "eval-1.0"

    def generate(self, source_input: dict) -> SystemOutput:
        assert_safe_bundle(source_input)
        result = self.fixture.model_copy(deep=True)
        if result.provenance != "authored-fixture":
            raise ValueError("Authored fixture adapter cannot impersonate a model run")
        return result


@dataclass(frozen=True)
class UnimplementedLiveAdapter:
    model_version: str = "not_run"
    prompt_version: str = "eval-1.0"

    def generate(self, source_input: dict) -> SystemOutput:
        assert_safe_bundle(source_input)
        return SystemOutput(provenance="not_run", status="not_run")

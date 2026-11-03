"""No-network cached-generation adapter with explicit provenance and digests.

An authored fixture is never described as an actual language-model experiment.
A model-generated cache requires its real model/run identifier, input hash, and
prompt hash, so adding this adapter cannot silently upgrade fixture provenance.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from orion.domain.grounding import canonical_hash


class CacheRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    cache_id: str = Field(min_length=1)
    provenance: Literal["authored-fixture", "model-generated-cache"]
    model_id: str | None
    original_run_id: str | None
    prompt_version: str = Field(min_length=1)
    prompt_digest: str = Field(pattern="^[a-f0-9]{64}$")
    input_digest: str = Field(pattern="^[a-f0-9]{64}$")
    output_digest: str = Field(pattern="^[a-f0-9]{64}$")
    output: dict[str, Any]

    @model_validator(mode="after")
    def check_provenance(self):
        if self.provenance == "authored-fixture" and (self.model_id is not None or self.original_run_id is not None):
            raise ValueError("Authored fixtures cannot claim a model run")
        if self.provenance == "model-generated-cache" and (not self.model_id or not self.original_run_id):
            raise ValueError("Model caches require an original model and run")
        if canonical_hash(self.output) != self.output_digest:
            raise ValueError("Cache output checksum mismatch")
        return self


class CachedLLMAdapter:
    """Read only an explicit cache ID allowlist; no directory search or paths."""
    def __init__(self, records: list[CacheRecord]):
        self._records = {}
        for record in records:
            validated = CacheRecord.model_validate(record.model_dump(mode="json"))
            if validated.cache_id in self._records:
                raise ValueError("Duplicate cache identity")
            self._records[validated.cache_id] = validated

    def generate(self, cache_id: str, *, source_context: dict, prompt: dict) -> dict:
        if cache_id not in self._records:
            raise ValueError("Cache ID not allowlisted")
        record = self._records[cache_id]
        if canonical_hash(source_context) != record.input_digest or canonical_hash(prompt) != record.prompt_digest:
            raise ValueError("Cache input or prompt does not match")
        return {"output": deepcopy(record.output), "provenance": record.provenance,
                "model_id": record.model_id, "original_run_id": record.original_run_id,
                "output_digest": record.output_digest, "live_api_calls": 0,
                "token_input": 0, "token_output": 0, "actual_cost_usd": 0,
                "measurement_kind": "fixture_functional" if record.provenance == "authored-fixture" else "replayed_model_output"}

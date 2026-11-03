"""Startup-only policy. Client requests cannot select mode or obtain secrets.

This module validates configuration; provider execution and budget reservation
are deliberately deferred to the integration chunk.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoundaryError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class BudgetConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)
    per_run_usd: Annotated[float, Field(gt=0, le=0.50)] = 0.50
    daily_usd: Annotated[float, Field(gt=0, le=2.00)] = 2.00
    evaluation_usd: Annotated[float, Field(gt=0, le=5.00)] = 5.00
    active_runs: Literal[1] = 1
    requests_per_run: Annotated[int, Field(ge=1, le=3)] = 3
    max_input_tokens: Annotated[int, Field(ge=1, le=12000)] = 12000
    max_output_tokens: Annotated[int, Field(ge=1, le=2000)] = 2000
    sdk_retries: Literal[0] = 0
    day_timezone: Literal["UTC"] = "UTC"

    @field_validator("active_runs", "sdk_retries", mode="before")
    @classmethod
    def strict_integer_literals(cls, value):
        if type(value) is not int:
            raise ValueError("integer policy values cannot be coerced")
        return value

    @model_validator(mode="after")
    def consistent_caps(self):
        if self.per_run_usd > self.daily_usd or self.per_run_usd > self.evaluation_usd:
            raise ValueError("per-run cap must not exceed aggregate caps")
        return self


class Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)
    mode: Literal["demo", "local_live"] = "demo"
    bind_host: Literal["127.0.0.1", "0.0.0.0"] = "127.0.0.1"
    port: Annotated[int, Field(ge=1, le=65535)] = 8050
    data_dir: Annotated[str, Field(min_length=1)] = ".local/orion"
    budget: BudgetConfig = Field(default_factory=BudgetConfig)

    @model_validator(mode="after")
    def local_is_loopback(self):
        if self.mode == "local_live" and self.bind_host != "127.0.0.1":
            raise ValueError("Local Live must bind to 127.0.0.1")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        # API keys are intentionally neither read nor retained here.
        values = {field: env[name] for name, field in (
            ("ORION_MODE", "mode"), ("ORION_HOST", "bind_host"),
            ("ORION_DATA_DIR", "data_dir"),
        ) if name in env}
        if "ORION_PORT" in env:
            raw = env["ORION_PORT"]
            if not raw.isascii() or not raw.isdecimal():
                raise ValueError("ORION_PORT must be an integer")
            values["port"] = int(raw)
        return cls.model_validate(values)

    def require_upload(self) -> None:
        if self.mode == "demo":
            raise BoundaryError("DEMO_ACTION_NOT_ALLOWED", "Uploads are disabled in Demo.")
        raise BoundaryError("FEATURE_NOT_IMPLEMENTED", "Native file ingestion starts in Chunk 3.")

    def require_local_repository(self) -> None:
        if self.mode != "local_live":
            raise BoundaryError("DEMO_ACTION_NOT_ALLOWED", "Demo cannot open persistent visitor storage.")

    def validate_local_request(self, *, host: str, origin: str | None, method: str) -> None:
        """Reusable future HTTP guard; no HTTP endpoint is created in Foundation.

        Forwarded host/origin headers are never consulted. Missing Origin on a
        state-changing request fails closed; authentication is outside this MVP.
        """
        if self.mode != "local_live":
            return
        authority = f"127.0.0.1:{self.port}"
        expected_origin = f"http://{authority}"
        if host != authority or (origin is not None and origin != expected_origin):
            raise BoundaryError("LOCAL_ORIGIN_DENIED", "Host or Origin is outside the local application.")
        if method.upper() not in {"GET", "HEAD", "OPTIONS"} and origin != expected_origin:
            raise BoundaryError("LOCAL_ORIGIN_DENIED", "A same-origin request is required.")


def create_live_adapter(settings: Settings, factory: Callable | None = None):
    """Fail before importing or constructing any provider, even with an env key."""
    if settings.mode == "demo":
        raise BoundaryError("DEMO_ACTION_NOT_ALLOWED", "Live adapters are disabled in Demo.")
    # A factory parameter cannot bypass pricing/budget controls not yet built.
    raise BoundaryError("FEATURE_NOT_IMPLEMENTED", "Live provider and budget execution are not implemented.")


def open_local_repository(settings: Settings):
    settings.require_local_repository()
    from pathlib import Path
    from orion.adapters.sqlite_repo import SQLiteRepository

    root = Path(settings.data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    repo = SQLiteRepository(root / "orion.sqlite3")
    repo.initialize()
    return repo

"""Offline developer commands for Chunk 1 Foundation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from orion.config import BoundaryError, Settings, open_local_repository
from orion.domain.models import DealState, ExpectedTransition, StagedEvidenceUpdate, validate_envelope


def _load(path: Path):
    return validate_envelope(path.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orion 2.0 — Chunk 1 Foundation (offline)")
    parser.add_argument("--version", action="version", version="orion-foundation 0.1.0; contract 1.0.0")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-fixture", help="Validate contract + source/reference integrity")
    validate.add_argument("path", type=Path)
    validate.add_argument("--base", type=Path, help="Base DealState; defaults to sibling initial_state.json")
    validate.add_argument("--update", type=Path, help="Expected transition's staged event")
    validate.add_argument("--mode", choices=["contract", "demo", "local_live"], default="contract")
    seed = sub.add_parser("seed-demo", help="Validate a fresh synthetic seed; never writes visitor state")
    seed.add_argument("--case", choices=["ns", "cd", "lm"], default="ns")
    sub.add_parser("init-db", help="Initialize SQLite only with ORION_MODE=local_live")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-fixture":
            from orion.domain.grounding import validate_expected_transition, validate_grounding

            envelope = _load(args.path)
            if isinstance(envelope, DealState):
                report = validate_grounding(envelope, mode=args.mode)
            else:
                base = _load(args.base or args.path.with_name("initial_state.json"))
                if not isinstance(base, DealState):
                    raise ValueError("base input must be DealState")
                if isinstance(envelope, StagedEvidenceUpdate):
                    report = validate_grounding(base, envelope, mode=args.mode)
                elif isinstance(envelope, ExpectedTransition):
                    update = _load(args.update or args.path.with_name("staged_evidence_update.json"))
                    validate_grounding(base, update, mode=args.mode).raise_for_errors()
                    report = validate_expected_transition(base, update, envelope)
                else:
                    raise ValueError("unsupported envelope")
            report.raise_for_errors()
            print(json.dumps({"status": "valid", "kind": envelope.kind, "contract_version": "1.0.0",
                              "mode": args.mode, "scoring_executed": False}, ensure_ascii=False))
        elif args.command == "seed-demo":
            from orion.demo import replay_demo

            state = replay_demo({"case_id": args.case, "actions": []})
            print(json.dumps({"status": "valid", "mode": "demo", "deal_id": state.deal.id,
                              "state_revision": state.state_revision, "persisted": False,
                              "live_api_calls": 0}, ensure_ascii=False))
        elif args.command == "init-db":
            repo = open_local_repository(Settings.from_env())
            if hasattr(repo, "close"):
                repo.close()
            print(json.dumps({"status": "initialized", "mode": "local_live"}))
        return 0
    except ValidationError as error:
        # Do not print Pydantic's raw input values (they may contain source text).
        print(json.dumps({"status": "invalid", "code": "CONTRACT_INVALID", "error_count": error.error_count()}), file=sys.stderr)
    except (BoundaryError, ValueError, OSError) as error:
        print(json.dumps({"status": "invalid", "code": getattr(error, "code", "VALIDATION_FAILED")}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

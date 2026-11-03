"""Offline developer commands for the core and synthetic evaluation workbench."""
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
    parser = argparse.ArgumentParser(description="Orion 2.0 — Synthetic Data and Evaluation (offline)")
    parser.add_argument("--version", action="version", version="orion 0.3.0; contract 1.0.0; scoring 1.0.0")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-fixture", help="Validate contract + source/reference integrity")
    validate.add_argument("path", type=Path)
    validate.add_argument("--base", type=Path, help="Base DealState; defaults to sibling initial_state.json")
    validate.add_argument("--update", type=Path, help="Expected transition's staged event")
    validate.add_argument("--mode", choices=["contract", "demo", "local_live"], default="contract")
    seed = sub.add_parser("seed-demo", help="Validate a fresh synthetic seed; never writes visitor state")
    seed.add_argument("--case", choices=["ns", "cd", "lm"], default="ns")
    rank = sub.add_parser("rank", help="Validate and rank an approved DealState")
    rank.add_argument("--state", type=Path, required=True)
    replay = sub.add_parser("replay", help="Replay an allowlisted synthetic evidence event")
    replay.add_argument("--case", choices=["ns", "cd", "lm"], required=True)
    replay.add_argument("--event", choices=["staged"], required=True)
    outcome = replay.add_mutually_exclusive_group()
    outcome.add_argument("--approve", action="store_true")
    outcome.add_argument("--reject", action="store_true")
    replay.add_argument("--output", type=Path, required=True)
    generate = sub.add_parser("generate-synthetic", help="Generate immutable legacy native synthetic sources")
    generate.add_argument("--output", type=Path, default=Path("data/synthetic"))
    ingest = sub.add_parser("ingest", help="Parse the allowlisted synthetic native documents")
    ingest.add_argument("--case", choices=["all", "ns", "cd", "lm"], default="all")
    ingest.add_argument("--mode", choices=["demo"], default="demo")
    ingest.add_argument("--source-root", type=Path, default=Path("data/synthetic"))
    ingest.add_argument("--output", type=Path, default=Path("data/parsed"))
    dataset = sub.add_parser("generate-dataset", help="Generate expanded Northstar and manufacturing packs")
    dataset.add_argument("--output", type=Path, default=Path("chunk3_synthetic_evaluation"))
    check_dataset = sub.add_parser("validate-dataset", help="Validate source, financial and gold integrity")
    check_dataset.add_argument("--root", type=Path, default=Path("chunk3_synthetic_evaluation"))
    scenario = sub.add_parser("replay-scenario", help="Run sequential analyst-reviewed evidence events")
    scenario.add_argument("--case", choices=["nb", "mf"], default="nb")
    scenario.add_argument("--root", type=Path, default=Path("chunk3_synthetic_evaluation"))
    scenario.add_argument("--output", type=Path)
    audit = sub.add_parser("audit-model-inputs", help="Audit source allowlists and stage visibility")
    audit.add_argument("--cases", nargs="+", default=["all"])
    audit.add_argument("--dataset-root", type=Path, default=Path("chunk3_synthetic_evaluation"))
    audit.add_argument("--output", type=Path, default=Path("evaluation/results"))
    evaluate = sub.add_parser("evaluate", help="Run authored fixtures and deterministic engines, without LLM calls")
    evaluate.add_argument("--arms", nargs="+", choices=["B0", "B1", "B2", "B3", "B1-R"], default=["B0", "B1", "B2", "B3", "B1-R"])
    evaluate.add_argument("--cases", nargs="+", default=["all"])
    evaluate.add_argument("--mode", choices=["cached", "live"], default="cached")
    evaluate.add_argument("--dataset-root", type=Path, default=Path("chunk3_synthetic_evaluation"))
    evaluate.add_argument("--output", type=Path, default=Path("evaluation/results"))
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
        elif args.command == "rank":
            from orion.domain.scoring import rank_state, ranking_input_digest
            from orion.domain.transitions import assert_current_state

            state = _load(args.state)
            if not isinstance(state, DealState):
                raise ValueError("rank input must be DealState")
            # No trusted native source resolver exists in this offline command.
            if state.mode != "demo":
                raise BoundaryError("SOURCE_MISMATCH", "Local Live requires a trusted source resolver.")
            assert_current_state(state)
            rows = rank_state(state)
            print(json.dumps({"deal_id": state.deal.id, "state_revision": state.state_revision,
                              "input_digest": ranking_input_digest(state),
                              "top3": [r.question_id for r in rows[:3]],
                              "rows": [r.model_dump(mode="json") for r in rows]}, ensure_ascii=False))
        elif args.command == "replay":
            from orion.demo import prepare_replay, replay_reviewed_demo
            from orion.domain.transitions import question_changes

            prepared = prepare_replay({"case_id": args.case, "actions": []})
            actions = []
            if args.approve or args.reject:
                actions = [{"action": "approve" if args.approve else "reject",
                            "event_id": prepared.staged_event.id}]
            state = replay_reviewed_demo({"case_id": args.case, "actions": actions})
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
            head = next(s for s in state.ranking_snapshots if s.id == state.head_snapshot_id)
            changes = question_changes(prepared.state, state)
            print(json.dumps({"case_id": args.case, "state_revision": state.state_revision,
                              "top3": head.top3, "scores": [r.score for r in head.rows[:3]],
                              "input_digest": head.input_digest,
                              "question_changes": [c.model_dump(mode="json") for c in changes],
                              "output": str(args.output), "live_api_calls": 0,
                              "source_validation": "fixture_text_only"}, ensure_ascii=False))
        elif args.command == "generate-synthetic":
            from orion.native_dataset import generate_synthetic
            print(json.dumps(generate_synthetic(args.output), ensure_ascii=False, default=str))
        elif args.command == "ingest":
            from orion.native_dataset import ingest
            print(json.dumps(ingest(case=args.case, mode=args.mode, source_root=args.source_root,
                                    output=args.output), ensure_ascii=False, default=str))
        elif args.command == "generate-dataset":
            from orion.synthetic import generate_dataset
            print(json.dumps(generate_dataset(args.output), ensure_ascii=False, default=str))
        elif args.command == "validate-dataset":
            from orion.synthetic import validate_dataset
            result = validate_dataset(args.root)
            print(json.dumps(result, ensure_ascii=False, default=str))
            if result.get("valid") is False or result.get("passed") is False or result.get("status") in {"failed", "invalid"}:
                return 2
        elif args.command == "replay-scenario":
            from orion.synthetic import replay_scenario
            result = replay_scenario(args.root, case=args.case)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, default=str))
        elif args.command in {"audit-model-inputs", "evaluate"}:
            from orion.evaluation import audit_model_inputs, run_evaluation
            cases = "all" if args.cases == ["all"] else args.cases
            kwargs = dict(cases=cases, output=args.output, dataset_root=args.dataset_root)
            result = (audit_model_inputs(**kwargs) if args.command == "audit-model-inputs"
                      else run_evaluation(arms=args.arms, mode=args.mode, **kwargs))
            print(json.dumps(result, ensure_ascii=False, default=str))
            if result.get("valid") is False or result.get("passed") is False or result.get("status") in {"failed", "invalid"}:
                return 2
        elif args.command == "init-db":
            repo = open_local_repository(Settings.from_env())
            if hasattr(repo, "close"):
                repo.close()
            print(json.dumps({"status": "initialized", "mode": "local_live"}))
        return 0
    except ValidationError as error:
        # Do not print Pydantic's raw input values (they may contain source text).
        print(json.dumps({"status": "invalid", "code": "CONTRACT_INVALID", "error_count": error.error_count()}), file=sys.stderr)
    except (KeyError, TypeError):
        # Malformed local dataset metadata is an input error at this CLI boundary.
        print(json.dumps({"status": "invalid", "code": "CONTRACT_INVALID"}), file=sys.stderr)
    except (BoundaryError, ValueError, OSError) as error:
        print(json.dumps({"status": "invalid", "code": getattr(error, "code", "VALIDATION_FAILED")}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

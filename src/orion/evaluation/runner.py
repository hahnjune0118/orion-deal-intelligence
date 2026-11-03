"""Executable authored-fixture benchmark and deterministic engine evaluation.

Gold is loaded only after system output construction. B0/B1 fixtures exercise
protocol plumbing and intentionally do not estimate model capability. B1-R has
an adapter/prompt but no invented regeneration result.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Sequence

from orion.demo import prepare_replay
from orion.domain.grounding import canonical_hash, validate_grounding
from orion.domain.models import AnalystDecision, DealState
from orion.domain.scoring import rank_state, ranking_input_digest
from orion.domain.transitions import apply_approved_update, question_changes

from .adapters import AuthoredFixtureAdapter, UnimplementedLiveAdapter
from .inputs import PROMPTS, audit_bundle, elements_from_bundle, prompt_for, source_bundle
from .metrics import aggregate, compute_metrics, event_metrics, ratio, wilson_interval, reproducibility
from .models import Citation, EvaluationGold, PredictedClaim, QuestionAnnotation, SystemOutput

LEGACY_CASES = ("ns", "cd", "lm")
ARMS = ("B0", "B1", "B2", "B3", "B1-R")
NOW = "2026-11-04T00:01:00Z"


def _repo_root() -> Path:
    candidate = Path(__file__).resolve().parents[3]
    return candidate if (candidate / "spec").is_dir() else Path.cwd()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _cases(cases: str | Sequence[str]) -> list[str]:
    if cases == "all" or cases == ["all"] or cases == ("all",):
        return [*LEGACY_CASES, "nb", "mf"]
    selected = [cases] if isinstance(cases, str) else list(cases)
    if not selected or len(set(selected)) != len(selected) or any(case not in (*LEGACY_CASES, "nb", "mf") for case in selected):
        raise ValueError("Cases must be unique ns/cd/lm/nb/mf or all")
    return selected


def _load_legacy(case: str):
    root = _repo_root()
    if (root / "data/parsed" / case / "initial_state.json").is_file():
        from orion.native_dataset import load_runtime
        state, event, resolver = load_runtime(case, source_root=root / "data/synthetic", parsed_root=root / "data/parsed")
        return state, event, resolver, "native-source"
    prepared = prepare_replay({"case_id": case, "actions": []})
    return prepared.state, prepared.staged_event, None, "fixture-text-only"


def _approve(state, event, *, suffix: str, resolver=None):
    decision = AnalystDecision(id=f"decision_eval_{suffix}", entity_version=1, deal_id=state.deal.id,
                               actor_id="actor_eval_reviewer", actor_role="reviewer", target_type="evidence_update",
                               target_id=event.id, target_version=1, selection_digest=None,
                               action="approve", reason="Scripted analyst-reviewed synthetic evidence; no automatic final investment decision.",
                               base_revision=state.state_revision, decided_at=NOW)
    return apply_approved_update(state, event, decision=decision, snapshot_id=f"snapshot_eval_{suffix}", now=NOW,
                                 mode="local_live" if resolver else "contract", source_resolver=resolver)


def _rows(state, resolver=None):
    return rank_state(state, mode="local_live" if resolver else "contract", source_resolver=resolver)


def _signature(state, resolver=None):
    return [(row.question_id, row.rank, row.score, row.gap) for row in _rows(state, resolver)]


def _fixture_output(state: DealState, arm: str, resolver=None) -> SystemOutput:
    """Use pre-existing author-curated objects, never evaluation gold.

    This common fixture deliberately holds question/claim quality constant.
    B0 omits citations solely to test missing-citation accounting. It does not
    suggest that real B0 output would omit citations or be less capable.
    """
    spans = {span.id: span for span in state.source_spans}
    questions = {question.id: question for question in state.dd_questions}
    output = SystemOutput(provenance="deterministic-engine" if arm == "B3" else "authored-fixture")
    for claim in state.claims:
        citations = [Citation(document_id=spans[key].document_id,
                              document_version=spans[key].document_version,
                              locator=spans[key].locator.model_dump(mode="json"), quote=spans[key].quote)
                     for key in claim.source_span_ids]
        # Entailment has not received independent blind annotation. Preserve NA.
        output.claims.append(PredictedClaim(prediction_id=claim.id, matched_claim_id=claim.id,
                                           text=claim.statement, citations=[] if arm == "B0" else citations,
                                           entailment_supported=None))
    for row in _rows(state, resolver)[:10]:
        question = questions[row.question_id]
        output.questions.append(QuestionAnnotation(
            output_id=question.id, text=question.request_text, family_id=question.id, match_reviewed=True,
            reviewer="fixture-author (single-rater; provisional)",
            match_rationale="Identity mapping of the pre-authored request; not a semantic model prediction.",
            target_present=True, artifact_present=True, period_present=bool(re.search(r"FY20\d{2}|20\d{2}-\d{2}-\d{2}", question.request_text)), criterion_present=True,
            financial_relevance=True))
    output.hypothesis_statuses = {claim.id: claim.support_status for claim in state.claims}
    return output


def _legacy_gold(case: str, stage: int, *, before: DealState, after: DealState) -> tuple[EvaluationGold, dict, dict]:
    root = _repo_root()
    gold = json.loads((root / "evaluation/gold" / f"{case}_gold.json").read_text(encoding="utf-8"))
    directory = root / "spec" / ("EXAMPLES" if case == "ns" else f"DATASET_SPECS/{case}")
    expected = json.loads((directory / "expected_top3_transition.json").read_text(encoding="utf-8"))
    judgments = gold["initial_claim_judgments"] if stage == 0 else gold["expected_claim_after"]
    critical = gold["critical_before"] if stage == 0 else gold["critical_after"]
    resolved = [change["question_id"] for change in expected["question_changes"] if change["after_status"] == "resolved"] if stage else []
    return EvaluationGold(claim_ids=[j["claim_id"] for j in gold["initial_claim_judgments"]],
                          critical_families=critical, relevance={q: float(3 - i) for i, q in enumerate(critical)},
                          hypothesis_statuses={j["claim_id"]: j["support_status"] for j in judgments},
                          resolved_question_families=resolved), gold, expected


def negative_controls(case: str) -> list[dict]:
    """Five controls per legacy case; rejected events must actually be rejected."""
    from orion.adapters.sqlite_repo import SQLiteRepository
    from orion.services.review import ReviewService
    from orion.services.workspace import ActorContext
    result = []
    for control in ("duplicate", "unrelated", "invalid_locator", "unapproved", "stale_revision"):
        state, template, resolver, source_mode = _load_legacy(case)
        event = template.model_copy(deep=True)
        before = _signature(state, resolver)
        rejected = False
        error_code = None
        actual_after = before
        try:
            if control == "duplicate":
                event.documents = []
                event.source_spans = []
                event.evidence_relations = []
                atom = state.evidence[0].model_copy(deep=True)
                atom.id = f"ev_{case}_eval_duplicate"
                atom.review_status = "draft"
                event.evidence = [atom]
                actual_after = _signature(_approve(state, event, suffix=f"{case}_duplicate", resolver=resolver), resolver)
            elif control == "unrelated":
                event.evidence[0].stance = "context"
                event.evidence[0].criterion_keys = []
                event.evidence_relations = []
                actual_after = _signature(_approve(state, event, suffix=f"{case}_unrelated", resolver=resolver), resolver)
            elif control in {"invalid_locator", "stale_revision"}:
                if control == "invalid_locator":
                    # This must fail validation before any approval is committed.
                    locator = event.source_spans[0].locator
                    if hasattr(locator, "paragraph_index"):
                        locator.paragraph_index = 99999
                    elif hasattr(locator, "page"):
                        locator.page = 99999
                    else:
                        locator.slide = 99999
                    # Text-only contract fixtures cannot independently resolve a
                    # physical position; explicitly flag invalid in that mode.
                    if resolver is None:
                        event.source_spans[0].locator_status = "invalid"
                else:
                    # A genuinely stale event: state has advanced, while the
                    # submitted event is still bound to its earlier revision.
                    state = _approve(state, template, suffix=f"{case}_pre_stale", resolver=resolver)
                    before = _signature(state, resolver)
                    actual_after = before
                actual_after = _signature(_approve(state, event, suffix=f"{case}_{control}", resolver=resolver), resolver)
            else:
                with TemporaryDirectory(prefix="orion-eval-review-") as folder:
                    repo = SQLiteRepository(Path(folder) / "review.sqlite3", validation_mode="local_live" if resolver else "contract", source_resolver=resolver)
                    repo.initialize()
                    blobs = {doc.file_sha256: resolver.file_bytes(doc.model_dump(mode="json")) for doc in state.documents} if resolver else None
                    repo.install_seed(state, source_blobs=blobs)
                    service = ReviewService(repo, ActorContext("actor_eval_reviewer", "reviewer"), clock=lambda: NOW)
                    event_blobs = {doc.file_sha256: resolver.file_bytes(doc.model_dump(mode="json")) for doc in event.documents} if resolver else None
                    service.stage(event, idempotency_key=f"eval:{case}:stage", source_blobs=event_blobs)
                    staged = repo.read_state(state.deal.id)
                    actual_after = _signature(staged, resolver)
                    if staged.state_revision != state.state_revision or staged.head_snapshot_id != state.head_snapshot_id:
                        raise AssertionError("Staging changed a committed state")
        except Exception as error:
            # Catch only expected typed boundary errors for control success.
            from orion.domain.grounding import GroundingError
            from orion.domain.transitions import TransitionError
            from orion.adapters.sqlite_repo import RepositoryError
            if not isinstance(error, (GroundingError, TransitionError, RepositoryError)):
                raise
            rejected = True
            error_code = getattr(error, "code", type(error).__name__)
        should_reject = control in {"invalid_locator", "stale_revision"}
        passed = rejected == should_reject and actual_after == before
        result.append({"case": case, "control": control, "expected_rejection": should_reject,
                       "rejected": rejected, "error_code": error_code, "passed": passed,
                       "before": before, "after": actual_after, "expected_change": False,
                       "transition_pass": passed, "source_mode": source_mode,
                       "repeated_group_attempts": int(control == "duplicate"), "repeated_group_updates": 0 if passed else int(control == "duplicate")})
    return result


def _ablations(state: DealState, resolver=None) -> dict:
    rows = _rows(state, resolver)
    questions = {q.id: q for q in state.dd_questions}
    weights = {"no_gap": (0, 0.40, 0.15), "no_materiality": (0.45, 0, 0.15), "no_obtainability": (0.45, 0.40, 0)}
    scenarios = {}
    for name, (g, m, o) in weights.items():
        denominator = g + m + o
        scored = [(100 * (g * row.gap + m * row.materiality + o * row.obtainability) / (5 * denominator), row) for row in rows]
        scored.sort(key=lambda pair: (-pair[0], -pair[1].materiality, -pair[1].gap, -pair[1].obtainability,
                                      questions[pair[1].question_id].canonical_key, pair[1].question_id))
        scenarios[name] = {"weights": [g / denominator, m / denominator, o / denominator],
                           "top3": [row.question_id for _, row in scored[:3]],
                           "scores": {row.question_id: score for score, row in scored}}
    # No mutable Bayesian flag is allowed to enter production rank inputs.
    first = _signature(state, resolver)
    second = _signature(state.model_copy(deep=True), resolver)
    scenarios["no_bayesian"] = {"production_rank_invariant": first == second,
                                 "top3": [row.question_id for row in rows[:3]],
                                 "status": "structural_invariant; legacy scenarios have no Bayesian toggle",
                                 "meaning": "Optional scenario panel is isolated; expanded cases execute the actual Bayesian on/off replay. This is not proof of predictive benefit."}
    scenarios["reproducibility"] = reproducibility(
        {"rows": first, "input_digest": ranking_input_digest(state)},
        [{"rows": second, "input_digest": ranking_input_digest(state.model_copy(deep=True))}])
    return scenarios


def audit_model_inputs(*, cases: str | Sequence[str] = "all", output: Path | str = Path("evaluation/results"),
                       dataset_root: Path | str = Path("chunk3_synthetic_evaluation")) -> dict:
    output, dataset_root = Path(output), Path(dataset_root)
    checks = []
    selected = _cases(cases)
    for case in selected:
        if case not in LEGACY_CASES:
            continue
        state, event, _, _ = _load_legacy(case)
        for stage in (0, 1):
            bundle = source_bundle(case, state, event=event if stage else None, stage=stage)
            expected = {doc.id for doc in state.documents} | ({doc.id for doc in event.documents} if stage else set())
            checks.append(audit_bundle(bundle, expected_documents=expected))
            for arm in ARMS:
                path = output / "model_inputs" / f"{case}_t{stage}_{arm}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(prompt_for(arm, bundle) + "\n", encoding="utf-8")
    for case in (case for case in selected if case in {"nb", "mf"}):
        manifest = dataset_root / "gold" / f"{case}_gold.json"
        if not manifest.exists():
            checks.append({"case": case, "valid": False, "status": "not_run", "reason": "Requested expanded dataset not generated"})
            continue
        from orion.synthetic import agent_visible_bundle, replay_scenario
        replay = replay_scenario(dataset_root, case=case)
        for entry in replay["states"]:
            stage = entry["stage"]
            visible = agent_visible_bundle(dataset_root, case=case, stage=stage)
            # The synthetic module owns its extended source-only contract/audit.
            from .synthetic_bridge import audit_extended_bundle
            check = audit_extended_bundle(visible, case, stage)
            checks.append(check)
            _write(output / "model_inputs" / f"{case}_t{stage}_source.json", visible)
    result = {"valid": all(row.get("valid") for row in checks), "checks": checks,
              "boundary": "No gold, world truth, expected ranks or future stage documents are serialized to adapters. Repository files require external process isolation for hostile code."}
    _write(output / "model_input_audit.json", result)
    return result


def run_evaluation(*, arms: Sequence[str] = ARMS, cases: str | Sequence[str] = "all", mode: str = "cached",
                   output: Path | str = Path("evaluation/results"), dataset_root: Path | str = Path("chunk3_synthetic_evaluation")) -> dict:
    if mode not in {"cached", "live"}:
        raise ValueError("Mode must be cached or live")
    if not arms or len(set(arms)) != len(arms) or any(arm not in ARMS for arm in arms):
        raise ValueError("Unknown or repeated evaluation arm")
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    timer = perf_counter()
    output, dataset_root = Path(output), Path(dataset_root)
    rows, manifests, transitions, negatives, ablations = [], [], [], [], {}
    selected = _cases(cases)
    for case in selected:
        if case not in LEGACY_CASES:
            continue
        before, event, resolver, source_mode = _load_legacy(case)
        after = _approve(before, event, suffix=case, resolver=resolver)
        for stage in (0, 1):
            visible = source_bundle(case, before, event=event if stage else None, stage=stage)
            for arm in arms:
                # Build predictions without loading gold.
                if mode == "live" or arm == "B1-R":
                    predicted = UnimplementedLiveAdapter().generate(visible)
                else:
                    state = after if stage and arm == "B3" else before
                    predicted = _fixture_output(state, arm, resolver)
                    if predicted.provenance == "authored-fixture":
                        predicted = AuthoredFixtureAdapter(predicted).generate(visible)
                gold, raw_gold, expected = _legacy_gold(case, stage, before=before, after=after)
                measured = compute_metrics(predicted, gold, elements_from_bundle(visible))
                if predicted.status == "not_run":
                    for value in measured.values():
                        value["status"] = "not_run"
                        value["value"] = None
                row = {"case": case, "split": "development" if case == "ns" else "public-frozen-regression",
                       "arm": arm, "stage": stage, "provenance": predicted.provenance,
                       "status": "fixture_only" if predicted.status == "completed" else predicted.status,
                       "source_mode": source_mode, "metrics": measured,
                       "top3": [q.family_id for q in predicted.questions[:3]], "cost_usd": 0.0}
                rows.append(row)
                key = f"{case}_t{stage}_{arm}"
                _write(output / "outputs" / f"{key}.json", predicted.model_dump(mode="json"))
                if stage == 0 and predicted.provenance == "authored-fixture":
                    _write(output / "authored_fixtures" / f"{case}_{arm}.json", predicted.model_dump(mode="json"))
                prompt = prompt_for(arm, visible)
                manifests.append({"case": case, "arm": arm, "stage": stage, "mode": mode,
                                  "model_version": "not_run" if predicted.status == "not_run" else "not_applicable:authored-or-deterministic",
                                  "prompt_version": "eval-1.0", "prompt_sha256": sha256(prompt.encode()).hexdigest(),
                                  "dataset_version": "legacy-contract-1.0.0", "contract_version": "1.0.0", "scoring_version": "1.0.0",
                                  "seed": 20261103, "timestamp_utc": started, "input_checksum": canonical_hash(visible),
                                  "output_checksum": canonical_hash(predicted.model_dump(mode="json")),
                                  "gold_checksum": canonical_hash(raw_gold), "source_hashes": {doc.id: doc.file_sha256 for doc in [*before.documents, *(event.documents if stage else [])]},
                                  "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "live_calls": 0,
                                  "reviewer_minutes": None, "reviewer_status": "scripted-provisional; independent review not_run",
                                  "configuration": {"max_questions": 10, "top_k": 3, "bayesian_panel": arm == "B3"},
                                  "status": row["status"], "limitations": "Not an actual model benchmark."})
        _, _, expected = _legacy_gold(case, 1, before=before, after=after)
        changes = [change.model_dump(mode="json") for change in question_changes(before, after)]
        actual_before, actual_after = [r.question_id for r in _rows(before, resolver)[:3]], [r.question_id for r in _rows(after, resolver)[:3]]
        passed = (actual_before == expected["before_top3"] and actual_after == expected["after_top3"]
                  and {c["question_id"]: c for c in changes} == {c["question_id"]: c for c in expected["question_changes"]})
        transitions.append({"case": case, "event": event.id, "before": actual_before, "after": actual_after,
                            "expected_change": True, "transition_pass": passed, "changes": changes})
        negatives.extend(negative_controls(case))
        ablations[case] = {"before": _ablations(before, resolver), "after": _ablations(after, resolver)}
    extended = {"status": "not_requested", "valid": True}
    if any(case in {"nb", "mf"} for case in selected):
        from .synthetic_bridge import run_extended_evaluation
        extended = run_extended_evaluation(dataset_root, output=output / "expanded", cases=[case for case in selected if case in {"nb", "mf"}], arms=arms, mode=mode)
        rows.extend(extended["baseline_rows"])
        manifests.extend(json.loads((output / "expanded/run_manifest.json").read_text(encoding="utf-8"))["runs"])
    audit = audit_model_inputs(cases=cases, output=output, dataset_root=dataset_root)
    summaries = {}
    for arm in arms:
        for subset, predicate in (("all", lambda row: True), ("public_frozen_regression_only", lambda row: row["case"] in {"cd", "lm", "mf"})):
            metrics = [row["metrics"] for row in rows if row["arm"] == arm and predicate(row)]
            summaries[f"{arm}:{subset}"] = {name: aggregate(metrics, name) for name in ("citation_precision", "top3_critical_dd_coverage", "ndcg_at_3")}
    rate = ratio(sum(row["passed"] for row in negatives), len(negatives))
    combined_events = event_metrics([*transitions, *negatives])
    combined_events["transition_exact_match"] = event_metrics(transitions)["transition_exact_match"]
    report = {"status": "fixture_only" if mode == "cached" else "not_run", "valid": audit["valid"] and extended["valid"] and all(t["transition_pass"] for t in transitions) and all(n["passed"] for n in negatives),
              "actual_model_benchmark": "not_run", "live_api_calls": 0, "gold_review": "self-authored, provisional; independent blind review not_run",
              "rows": rows, "summaries": summaries, "transitions": transitions, "negative_controls": negatives,
              "negative_control_stability": {**rate.as_dict(), "wilson95_descriptive": wilson_interval(int(rate.numerator), int(rate.denominator))},
              "event_metrics": combined_events, "ablations": ablations, "expanded": extended,
              "targets": {"locator_precision": 0.95, "top3_critical_dd_coverage": 0.80, "fabricated_citations": 0, "final_approval_without_hitl": 0},
              "target_status": "Development targets; fixture outcomes cannot certify actual model targets.",
              "limitations": ["B0/B1 are authored protocol test doubles, not model samples.", "B1-R and all live model arms are not_run.", "Public frozen cases are regression controls, not secret held-out data.", "Rows within a deal are dependent; intervals do not establish population performance.", "Actionability annotations are fixture-author provisional, not blind reviewer measurements."]}
    _write(output / "report.json", report)
    _write(output / "run_manifest.json", {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "duration_seconds": perf_counter() - timer, "runs": manifests})
    _write(output / "ablations.json", ablations)
    _write(output / "negative_controls.json", negatives)
    _write(output / "baseline_results.json", {"actual_model_benchmark": "not_run", "fixture_only_summaries": summaries})
    return report

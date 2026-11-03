"""AT08–17: exercise service authorization and actual durable atomic commits."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest
from pydantic import ValidationError

from orion.adapters.sqlite_repo import RepositoryError, RevisionWriter, SQLiteRepository
from orion.domain.models import DealState
from orion.services.review import ReviewService
from orion.services.workspace import ActorContext, WorkspaceService

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-11-03T10:00:00Z"
REVIEWER = ActorContext("actor_reviewer", "reviewer")
ANALYST = ActorContext("actor_analyst", "analyst")


def load_case(case):
    folder = ROOT / "spec" / ("EXAMPLES" if case == "ns" else f"DATASET_SPECS/{case}")
    return tuple(json.loads((folder / name).read_text()) for name in
                 ("initial_state.json", "staged_evidence_update.json", "expected_top3_transition.json"))


@pytest.fixture
def prepared(tmp_path):
    seed, event, expected = load_case("ns")
    repo = SQLiteRepository(tmp_path / "orion.sqlite3", validation_mode="contract")
    repo.initialize()
    repo.install_seed(seed)
    service = ReviewService(repo, REVIEWER, clock=lambda: NOW)
    return repo, service, event


def counts(repo):
    with repo.connect() as con:
        tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {table: con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}


def approve(service, event, **overrides):
    args = dict(deal_id=event["deal_id"], event_id=event["id"], expected_revision=event["base_revision"],
                idempotency_key="approve_once", reason="Reviewed exact synthetic contract scope")
    args.update(overrides)
    return service.approve(**args)


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_three_case_durable_review_flow_preserves_history(tmp_path, case):
    seed, event, expected = load_case(case)
    repo = SQLiteRepository(tmp_path / f"{case}.sqlite3", validation_mode="contract")
    repo.initialize()
    repo.install_seed(seed)
    service = ReviewService(repo, REVIEWER, clock=lambda: NOW)
    original = repo.read_state(seed["deal"]["id"])
    stage = service.stage(event, idempotency_key="stage_once")
    assert stage.state_revision == 1 and stage.snapshot_id == original.head_snapshot_id
    staged = repo.read_state(seed["deal"]["id"])
    assert staged.ranking_snapshots == original.ranking_snapshots
    assert staged.evidence == original.evidence
    result = approve(service, event)
    reopened = SQLiteRepository(repo.path, validation_mode="contract")
    after = WorkspaceService(reopened, REVIEWER).get_state(event["deal_id"])
    head = next(s for s in after.ranking_snapshots if s.id == after.head_snapshot_id)
    assert result.state_revision == 2
    assert head.top3 == expected["after_top3"]
    assert after.ranking_snapshots[0] == original.ranking_snapshots[0]
    assert after.audit_events[:len(original.audit_events)] == original.audit_events
    decision = next(d for d in after.analyst_decisions if d.id == after.audit_events[-1].decision_id)
    assert after.audit_events[-1].before_snapshot_id == original.head_snapshot_id
    assert len(after.evidence) > len(original.evidence)
    assert decision.actor_id == REVIEWER.actor_id
    assert decision.actor_role == "reviewer"
    assert result.changed_question_ids
    assert "QUESTION_REOPENED" in result.reason_codes if case == "lm" else "QUESTION_RESOLVED" in result.reason_codes


@pytest.mark.parametrize("case", ["ns", "cd", "lm"])
def test_staging_and_rejection_never_change_snapshot_or_scores(tmp_path, case):
    seed, event, _ = load_case(case)
    repo = SQLiteRepository(tmp_path / f"{case}.sqlite3", validation_mode="contract")
    repo.initialize()
    repo.install_seed(seed)
    service = ReviewService(repo, REVIEWER, clock=lambda: NOW)
    original = repo.read_state(event["deal_id"])
    service.stage(event, idempotency_key="stage_once")
    service.reject(event["deal_id"], event["id"], expected_revision=1,
                   idempotency_key="reject_once", reason="Scope not accepted")
    after = repo.read_state(event["deal_id"])
    assert after.state_revision == original.state_revision
    assert after.head_snapshot_id == original.head_snapshot_id
    assert after.ranking_snapshots == original.ranking_snapshots
    for name in ("evidence", "claims", "dd_questions", "evidence_relations"):
        assert getattr(after, name) == getattr(original, name)
    assert after.audit_events[-1].event_type == "update_rejected"
    with pytest.raises(RepositoryError, match="DUPLICATE_EVENT"):
        approve(service, event)


def test_stage_retry_returns_original_without_duplicate_audit(prepared):
    repo, service, event = prepared
    first = service.stage(event, idempotency_key="stage_once")
    before = counts(repo)
    again = service.stage(event, idempotency_key="stage_once")
    assert again.replayed and again.snapshot_id == first.snapshot_id
    assert counts(repo) == before


def test_approval_retry_returns_original_after_revision_advanced(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    first = approve(service, event)
    before = counts(repo)
    again = approve(service, event)
    assert again.replayed and again.snapshot_id == first.snapshot_id and again.state_revision == 2
    assert counts(repo) == before


def test_reject_retry_does_not_append_audit(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    args = dict(expected_revision=1, idempotency_key="reject_once", reason="Rejected for review")
    first = service.reject(event["deal_id"], event["id"], **args)
    before = counts(repo)
    again = service.reject(event["deal_id"], event["id"], **args)
    assert again.replayed and again.snapshot_id == first.snapshot_id
    assert counts(repo) == before


def test_idempotency_binds_actor_and_reason(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    approve(service, event)
    before = counts(repo)
    with pytest.raises(RepositoryError, match="IDEMPOTENCY_CONFLICT"):
        approve(service, event, reason="Different semantic command")
    other = ReviewService(repo, ActorContext("actor_other", "reviewer"), clock=lambda: NOW)
    with pytest.raises(RepositoryError, match="IDEMPOTENCY_CONFLICT"):
        approve(other, event)
    assert counts(repo) == before


def test_stale_approval_rolls_back_all_writes(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    approve(service, event)
    before = counts(repo)
    with pytest.raises(RepositoryError, match="REVISION_CONFLICT"):
        approve(service, event, idempotency_key="new_stale_command")
    assert counts(repo) == before


def test_invalid_locator_blocks_stage_without_any_write(prepared):
    repo, service, event = prepared
    event["source_spans"][0]["quote"] += " altered"
    before = counts(repo)
    with pytest.raises(ValueError):
        service.stage(event, idempotency_key="bad_locator")
    assert counts(repo) == before


def test_locator_revalidated_at_approval(prepared, monkeypatch):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    read_staged = RevisionWriter.read_staged
    def tampered(writer, event_id):
        result = read_staged(writer, event_id).model_copy(deep=True)
        result.source_spans[0].quote += " altered"
        return result
    monkeypatch.setattr(RevisionWriter, "read_staged", tampered)
    before = counts(repo)
    with pytest.raises(ValueError):
        approve(service, event)
    assert counts(repo) == before


def test_analyst_can_stage_but_cannot_approve_or_reject(prepared):
    repo, reviewer, event = prepared
    analyst = ReviewService(repo, ANALYST, clock=lambda: NOW)
    analyst.stage(event, idempotency_key="stage_once")
    before = counts(repo)
    for action in ("approve", "reject"):
        with pytest.raises(RepositoryError, match="UNAUTHORIZED"):
            getattr(analyst, action)(event["deal_id"], event["id"], expected_revision=1,
                                    idempotency_key=action, reason="Attempted analyst action")
    assert counts(repo) == before


def test_server_actor_context_cannot_be_a_client_dictionary(prepared):
    repo, _, _ = prepared
    with pytest.raises(RepositoryError, match="UNAUTHORIZED"):
        ReviewService(repo, {"actor_id": "actor_forged", "role": "reviewer"})


@pytest.mark.parametrize("field,value", [("role", "reviewer"), ("actor_id", "actor_forged"),
                                          ("score", 100), ("raw_evidence", []), ("snapshot", {})])
def test_callback_payload_rejects_role_score_and_evidence_injection(prepared, field, value):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    before = counts(repo)
    command = dict(action="approve", deal_id=event["deal_id"], event_id=event["id"],
                   expected_revision=1, idempotency_key="approve_once", reason="Review", **{field: value})
    with pytest.raises(ValidationError):
        service.execute(command)
    assert counts(repo) == before


@pytest.mark.parametrize("failure_type", ["Evidence", "RankingSnapshot", "AuditEvent"])
def test_real_commit_failure_rolls_back_all_tables_and_preserves_retry(prepared, monkeypatch, failure_type):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    before = counts(repo)
    state = repo.read_state(event["deal_id"])
    original = RevisionWriter.put_entity
    def fail(writer, type_name, entity):
        original(writer, type_name, entity)
        if type_name == failure_type:
            raise RuntimeError("injected commit failure")
    with monkeypatch.context() as patch:
        patch.setattr(RevisionWriter, "put_entity", fail)
        with pytest.raises(RuntimeError, match="injected commit failure"):
            approve(service, event)
    assert counts(repo) == before
    assert repo.read_state(event["deal_id"]) == state
    assert approve(service, event).state_revision == 2


def test_staging_failure_rolls_back_archive_and_audit(prepared, monkeypatch):
    repo, service, event = prepared
    before = counts(repo)
    original = RevisionWriter.append_audit
    def fail(writer, audit):
        original(writer, audit)
        raise RuntimeError("injected staging failure")
    monkeypatch.setattr(RevisionWriter, "append_audit", fail)
    with pytest.raises(RuntimeError, match="injected staging failure"):
        service.stage(event, idempotency_key="stage_once")
    assert counts(repo) == before


def test_two_concurrent_approvals_commit_exactly_once(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    def run(_):
        local = ReviewService(SQLiteRepository(repo.path, validation_mode="contract"), REVIEWER, clock=lambda: NOW)
        return approve(local, event)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(item.replayed for item in results) == [False, True]
    assert results[0].snapshot_id == results[1].snapshot_id
    assert counts(repo)["snapshots"] == 2
    assert counts(repo)["staged_resolutions"] == 1


@pytest.mark.parametrize("table", ["staged_updates", "staged_resolutions"])
def test_event_archive_and_resolution_are_append_only(prepared, table):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    approve(service, event)
    with repo.connect() as con, pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        con.execute(f"DELETE FROM {table}")


def test_stage_same_event_id_cannot_be_overwritten(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    event["analyst_note"] = "Changed candidate with reused immutable ID"
    before = counts(repo)
    with pytest.raises(RepositoryError, match="DUPLICATE_EVENT"):
        service.stage(event, idempotency_key="new_stage")
    assert counts(repo) == before


def test_cross_deal_review_is_rejected(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    before = counts(repo)
    with pytest.raises(RepositoryError, match="UNKNOWN_DEAL"):
        approve(service, event, deal_id="deal_other")
    assert counts(repo) == before


def test_retry_retains_first_comparison_after_a_later_commit(prepared):
    repo, service, event = prepared
    service.stage(event, idempotency_key="stage_once")
    first = approve(service, event)
    later = deepcopy(event)
    later.update(id="update_later", base_revision=2, idempotency_key="event_later",
                 documents=[], source_spans=[])
    later["evidence"][0]["id"] = "evidence_later_duplicate"
    service.stage(later, idempotency_key="stage_later")
    second = approve(service, later, idempotency_key="approve_later", expected_revision=2)
    assert second.state_revision == 3 and second.changed_question_ids == ()
    assert second.reason_codes == ("RANKING_UNCHANGED",)
    before = counts(repo)
    again = approve(service, event)
    assert again.replayed and again.state_revision == 2 and again.snapshot_id == first.snapshot_id
    assert again.changed_question_ids == first.changed_question_ids
    assert again.reason_codes == first.reason_codes
    assert counts(repo) == before


@pytest.mark.parametrize("tamper", ["input_digest", "rows"])
@pytest.mark.parametrize("action", ["stage", "approve", "reject"])
def test_stale_head_blocked_inside_transaction(prepared, monkeypatch, tamper, action):
    repo, service, event = prepared
    if action != "stage":
        service.stage(event, idempotency_key="stage_once")
    original = RevisionWriter.read_state
    def changed_head(writer):
        result = original(writer).model_copy(deep=True)
        head = next(s for s in result.ranking_snapshots if s.id == result.head_snapshot_id)
        if tamper == "input_digest":
            head.input_digest = "0" * 64
        else:
            head.rows[0].score -= 1
        return result
    monkeypatch.setattr(RevisionWriter, "read_state", changed_head)
    before = counts(repo)
    with pytest.raises(ValueError):
        if action == "stage":
            service.stage(event, idempotency_key="stage_once")
        else:
            getattr(service, action)(event["deal_id"], event["id"], expected_revision=1,
                                     idempotency_key="decision_once", reason="Review stale head")
    assert counts(repo) == before


def test_stage_retry_revalidates_actual_blob_bytes_before_idempotency(prepared):
    from hashlib import sha256
    repo, service, event = prepared
    content = b"synthetic bytes"
    digest = sha256(content).hexdigest()
    service.stage(event, idempotency_key="stage_once", source_blobs={digest: content})
    before = counts(repo)
    with pytest.raises(RepositoryError, match="SOURCE_MISMATCH"):
        service.stage(event, idempotency_key="stage_once", source_blobs={digest: b"altered bytes"})
    assert counts(repo) == before

"""Real file-backed SQLite tests; callbacks stand in for the later review service.

Snapshots are supplied fixtures, not claims that a ranking engine exists.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from orion.adapters.sqlite_repo import RepositoryError, SQLiteRepository, payload_digest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def seed():
    return json.loads((ROOT / "spec/EXAMPLES/initial_state.json").read_text())


@pytest.fixture
def repo(tmp_path, seed):
    value = SQLiteRepository(tmp_path / "data" / "orion.sqlite3", validation_mode="contract")
    value.initialize()
    value.install_seed(seed)
    return value


def counts(repo):
    with repo.connect() as con:
        return {name: con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in
                ["deals", "entity_versions", "source_blobs", "snapshots", "decisions", "audit_events",
                 "processed_commands", "analysis_runs", "budget_ledger"]}


def mutation(writer, *, fail_after=None):
    """Trusted, precomputed metadata-only service commit for storage tests."""
    state = writer.read_state().model_dump(mode="json")
    question = deepcopy(state["dd_questions"][0])
    question["entity_version"] += 1
    question["owner_label"] = "Assigned synthetic reviewer"
    writer.put_entity("DDQuestion", question)
    if fail_after == "entity":
        raise RuntimeError("injected after entity")
    snapshot = deepcopy(state["ranking_snapshots"][-1])
    snapshot.update(id=f"snap_test_{writer.target_revision}", state_revision=writer.target_revision)
    # Placeholder supplied by this storage-only test. Chunk 2 computes this.
    snapshot["input_digest"] = payload_digest({"storage_test": writer.target_revision})
    writer.append_snapshot(snapshot)
    if fail_after == "snapshot":
        raise RuntimeError("injected after snapshot")
    decision = deepcopy(state["analyst_decisions"][0])
    decision.update(id=f"decision_test_{writer.target_revision}", target_type="question", target_id=question["id"],
                    target_version=question["entity_version"], base_revision=writer.base_revision,
                    reason="Storage boundary test: authorized owner metadata update")
    writer.append_decision(decision)
    audit = deepcopy(state["audit_events"][-1])
    audit.update(id=f"audit_test_{writer.target_revision}", sequence=audit["sequence"] + 1,
                 event_type="edit_applied", before_revision=writer.base_revision, after_revision=writer.target_revision,
                 idempotency_key=writer.idempotency_key, before_snapshot_id=writer.before_snapshot_id,
                 after_snapshot_id=snapshot["id"], decision_id=decision["id"], previous_hash=audit["event_hash"])
    audit["event_hash"] = payload_digest({key: value for key, value in audit.items() if key != "event_hash"})
    writer.append_audit(audit)
    writer.set_head(snapshot["id"])
    if fail_after == "audit":
        raise RuntimeError("injected after audit")


def commit(repo, *, key="command_test", revision=1, payload=None, mutate=mutation):
    return repo.transact("deal_ns", idempotency_key=key, expected_revision=revision,
                         request_payload=payload or {"action": "update_owner", "actor": "trusted_reviewer"}, mutate=mutate)


def test_initialization_pragmas_and_reconnect(repo):
    assert set(counts(repo)) == {"deals", "entity_versions", "source_blobs", "snapshots", "decisions",
                               "audit_events", "processed_commands", "analysis_runs", "budget_ledger"}
    for _ in range(2):
        with repo.connect() as con:
            assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    reopened = SQLiteRepository(repo.path, validation_mode="contract")
    assert reopened.read_state("deal_ns").head_snapshot_id == "snap_ns_initial"
    assert reopened.read_state("deal_ns").state_revision == 1


@pytest.mark.parametrize("relative", ["EXAMPLES/initial_state.json", "DATASET_SPECS/cd/initial_state.json",
                                      "DATASET_SPECS/lm/initial_state.json"])
def test_each_case_seed_persists_without_rewriting_input(tmp_path, relative):
    source = json.loads((ROOT / "spec" / relative).read_text())
    before = deepcopy(source)
    store = SQLiteRepository(tmp_path / "orion.sqlite3", validation_mode="contract")
    store.initialize()
    store.install_seed(source)
    result = store.read_state(source["deal"]["id"]).model_dump(mode="json")
    assert source == before
    assert result["ranking_snapshots"] == source["ranking_snapshots"]
    assert result["audit_events"] == source["audit_events"]
    for collection in ["documents", "source_spans", "claims", "dd_questions"]:
        assert sorted(result[collection], key=lambda x: x["id"]) == sorted(source[collection], key=lambda x: x["id"])


def test_commit_persists_versions_snapshot_decision_and_audit(repo):
    old = repo.read_state("deal_ns").model_dump(mode="json")
    result = commit(repo)
    assert (result.state_revision, result.snapshot_id, result.replayed) == (2, "snap_test_2", False)
    state = SQLiteRepository(repo.path, validation_mode="contract").read_state("deal_ns").model_dump(mode="json")
    assert state["state_revision"] == 2
    assert len(state["ranking_snapshots"]) == len(old["ranking_snapshots"]) + 1
    assert len(state["audit_events"]) == len(old["audit_events"]) + 1
    qid = old["dd_questions"][0]["id"]
    history = repo.entity_history("deal_ns", "DDQuestion", qid)
    assert [q["entity_version"] for q in history] == [1, 2]
    assert history[0] == old["dd_questions"][0]


def test_same_idempotency_payload_replays_before_stale_revision_check(repo):
    commit(repo)
    before = counts(repo)
    def must_not_execute(_):
        raise AssertionError("Replay executed mutation")
    result = commit(repo, mutate=must_not_execute)
    assert result.replayed is True
    assert result.state_revision == 2
    assert counts(repo) == before


def test_same_key_changed_payload_conflicts_without_any_write(repo):
    commit(repo)
    before = counts(repo)
    with pytest.raises(RepositoryError, match="IDEMPOTENCY_CONFLICT"):
        commit(repo, payload={"action": "different"})
    assert counts(repo) == before


def test_revision_conflict_blocks_new_command(repo):
    commit(repo)
    before = counts(repo)
    with pytest.raises(RepositoryError, match="REVISION_CONFLICT"):
        commit(repo, key="new_command", revision=1)
    assert counts(repo) == before


@pytest.mark.parametrize("point", ["entity", "snapshot", "audit"])
def test_all_tables_roll_back_at_failure_points(repo, point):
    before = counts(repo)
    state = repo.read_state("deal_ns").model_dump(mode="json")
    with pytest.raises(RuntimeError, match="injected"):
        commit(repo, mutate=lambda writer: mutation(writer, fail_after=point))
    assert counts(repo) == before
    assert repo.read_state("deal_ns").model_dump(mode="json") == state
    assert commit(repo).state_revision == 2


def test_two_writers_same_command_only_one_callback_runs(repo):
    calls = []
    def run(_):
        store = SQLiteRepository(repo.path, validation_mode="contract")
        def change(writer):
            calls.append(1)
            mutation(writer)
        return commit(store, mutate=change)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(result.replayed for result in results) == [False, True]
    assert len(calls) == 1
    assert counts(repo)["processed_commands"] == 1


def test_concurrent_different_commands_one_revision_wins(repo):
    def run(key):
        try:
            return commit(SQLiteRepository(repo.path, validation_mode="contract"), key=key).state_revision
        except RepositoryError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ["command_one", "command_two"]))
    assert 2 in results and "REVISION_CONFLICT" in results
    assert counts(repo)["processed_commands"] == 1


@pytest.mark.parametrize("table,id_column", [("snapshots", "snapshot_id"), ("audit_events", "audit_id"),
                                               ("entity_versions", "entity_id"), ("decisions", "decision_id")])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_history_is_append_only_even_via_sql(repo, table, id_column, operation):
    with repo.connect() as con, pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        if operation == "UPDATE":
            con.execute(f"UPDATE {table} SET {id_column}={id_column}")
        else:
            con.execute(f"DELETE FROM {table}")


@pytest.mark.parametrize("version", [1, 3])
def test_skipped_or_reused_entity_version_rejected(repo, version):
    question = repo.read_state("deal_ns").dd_questions[0].model_dump(mode="json")
    question["entity_version"] = version
    before = counts(repo)
    with pytest.raises(RepositoryError, match="ENTITY_VERSION_CONFLICT"):
        commit(repo, mutate=lambda writer: writer.put_entity("DDQuestion", question))
    assert counts(repo) == before


def test_cross_deal_entity_rejected(repo):
    question = repo.read_state("deal_ns").dd_questions[0].model_dump(mode="json")
    question.update(deal_id="deal_other", entity_version=2)
    with pytest.raises(RepositoryError, match="CROSS_DEAL_REFERENCE"):
        commit(repo, mutate=lambda writer: writer.put_entity("DDQuestion", question))


def test_cross_type_id_rejected(repo):
    state = repo.read_state("deal_ns")
    claim = state.claims[0].model_dump(mode="json")
    claim["id"] = state.dd_questions[0].id
    with pytest.raises(RepositoryError, match="ENTITY_ID_CONFLICT"):
        commit(repo, mutate=lambda writer: writer.put_entity("Claim", claim))


def test_source_hash_mismatch_and_blob_rollback(repo):
    before = counts(repo)
    def change(writer):
        writer.put_source_blob(b"synthetic source bytes")
        writer.put_source_blob(b"changed bytes", expected_sha256="0" * 64)
    with pytest.raises(RepositoryError, match="SOURCE_MISMATCH"):
        commit(repo, mutate=change)
    assert counts(repo) == before


def test_verified_document_must_reference_stored_blob(repo, seed):
    document = deepcopy(seed["documents"][0])
    document.update(id="doc_new_verified", asset_status="file_verified", file_sha256=sha256(b"new bytes").hexdigest())
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        commit(repo, mutate=lambda writer: writer.put_entity("Document", document))


def test_snapshot_and_decision_foreign_keys_cannot_cross_deals(repo):
    with repo.connect() as con, pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        con.execute("INSERT INTO processed_commands VALUES (?,?,?,?,?)",
                    ("deal_ns", "foreign_snapshot", "0"*64, 1, "snap_other"))


def test_duplicate_seed_does_not_overwrite_history(repo, seed):
    before = counts(repo)
    with pytest.raises(RepositoryError, match="DEAL_EXISTS"):
        repo.install_seed(seed)
    assert counts(repo) == before


def test_local_live_rejects_text_only_fixture_seed(tmp_path, seed):
    store = SQLiteRepository(tmp_path / "live.sqlite3")
    store.initialize()
    with pytest.raises(ValueError):
        store.install_seed(seed)
    assert counts(store)["deals"] == 0


def test_incomplete_commit_rolls_back(repo):
    before = counts(repo)
    with pytest.raises(RepositoryError, match="INCOMPLETE_COMMIT"):
        commit(repo, mutate=lambda writer: None)
    assert counts(repo) == before


def test_writer_cannot_be_reused_after_commit(repo):
    captured = []
    def change(writer):
        captured.append(writer)
        mutation(writer)
    commit(repo, mutate=change)
    with pytest.raises(RepositoryError, match="TRANSACTION_CLOSED"):
        captured[0].read_state()


def test_invalid_entity_data_is_not_coerced(repo):
    question = repo.read_state("deal_ns").dd_questions[0].model_dump(mode="json")
    question["entity_version"] = "2"
    with pytest.raises(ValueError):
        commit(repo, mutate=lambda writer: writer.put_entity("DDQuestion", question))
    assert repo.read_state("deal_ns").state_revision == 1


def test_final_reference_validation_rolls_back_transaction(repo):
    before = counts(repo)
    def invalid(writer):
        mutation(writer)
        question = writer.read_state().dd_questions[-1].model_dump(mode="json")
        question["entity_version"] += 1
        question["claim_id"] = "claim_nonexistent"
        writer.put_entity("DDQuestion", question)
    with pytest.raises(ValueError):
        commit(repo, mutate=invalid)
    assert counts(repo) == before


@pytest.mark.parametrize("schema_version", [-1, 2, 99])
def test_initialize_rejects_unsupported_database_version_without_relabeling(tmp_path, schema_version):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version={schema_version}")
    store = SQLiteRepository(path, validation_mode="contract")
    with pytest.raises(RepositoryError, match="SCHEMA_VERSION_UNSUPPORTED"):
        store.initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == schema_version
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0


@pytest.mark.parametrize("type_name,collection", [("Document", "documents"), ("Evidence", "evidence")])
def test_creation_time_is_immutable_across_entity_versions(repo, type_name, collection):
    state = repo.read_state("deal_ns").model_dump(mode="json")
    entity = deepcopy(state[collection][0])
    entity["entity_version"] += 1
    entity["created_at"] = "2026-11-04T00:00:00Z"
    before = counts(repo)
    with pytest.raises(RepositoryError, match="IMMUTABLE_METADATA"):
        commit(repo, mutate=lambda writer: writer.put_entity(type_name, entity))
    assert counts(repo) == before


def test_document_parser_change_requires_new_document_version(repo):
    document = repo.read_state("deal_ns").documents[0].model_dump(mode="json")
    document["entity_version"] += 1
    document["parser_version"] = "new-parser-version"
    with pytest.raises(RepositoryError, match="DOCUMENT_VERSION_CONFLICT"):
        commit(repo, mutate=lambda writer: writer.put_entity("Document", document))


def test_changed_extraction_unit_requires_new_span_id(repo):
    span = repo.read_state("deal_ns").source_spans[0].model_dump(mode="json")
    span["entity_version"] += 1
    span["normalized_text"] += " new extraction"
    span["text_sha256"] = sha256(span["normalized_text"].encode("utf-8")).hexdigest()
    with pytest.raises(RepositoryError, match="SOURCE_VERSION_CONFLICT"):
        commit(repo, mutate=lambda writer: writer.put_entity("SourceSpan", span))


def test_existing_snapshot_id_cannot_receive_new_version(repo):
    snapshot = repo.read_state("deal_ns").ranking_snapshots[0].model_dump(mode="json")
    snapshot.update(entity_version=2, state_revision=2)
    with pytest.raises(RepositoryError, match="IMMUTABLE_ENTITY"):
        commit(repo, mutate=lambda writer: writer.append_snapshot(snapshot))

"""Native-source web orchestration tests; no external provider or browser claimed."""
from concurrent.futures import ThreadPoolExecutor
import base64
import json
from pathlib import Path
import socket
import sqlite3

import pytest

from orion.domain.grounding import validate_grounding
from orion.services.web_workspace import WebWorkspace, WorkspaceError, SERVER_ACTOR
from orion.synthetic.scenario import replay_scenario

ROOT = Path(__file__).resolve().parents[2]
SESSION = "server-created-browser-session-one"
OTHER_SESSION = "server-created-browser-session-two"


@pytest.fixture(scope="module")
def workspace():
    service = WebWorkspace(ROOT, b"test-only-workspace-key-32-bytes!!")
    # Native parsing is actual, cached by the preserved parser after verification.
    for case in ("nb", "mf", "lm", "ns", "cd"):
        service.new(case, SESSION)
    return service


def approve_next(workspace, token, key="approve-next"):
    view = workspace.view(token, SESSION)
    event = next(e for e in view["events"] if e["available"])
    return workspace.act(token, SESSION, "approve", event["id"], view["revision"], key, "Reviewed the native synthetic source.")


def test_initial_rows_match_authoritative_snapshot_and_native_sources(workspace):
    token = workspace.new("nb", SESSION)
    state, resolver = workspace.validated_state(token, SESSION)
    view = workspace.view(token, SESSION)
    head = next(s for s in state.ranking_snapshots if s.id == state.head_snapshot_id)
    assert [(q["id"], q["rank"], q["score"]) for q in view["questions"] if q["rank"]] == [(r.question_id, r.rank, r.score) for r in head.rows]
    assert all(d["asset_status"] == "file_verified" for d in view["documents"])
    validate_grounding(state, mode="demo", source_resolver=resolver).raise_for_errors()
    assert view["score_formula"] == "P = 9G + 8M + 3O"
    assert "state" not in view and "gold" not in view
    assert view["analytics"]["belief_snapshots"] == []
    candidate = view["analytics"]["candidate_eig"]
    assert candidate["committed"] is False
    assert candidate["event_id"] == "nb_update_t1"
    assert candidate["eig_bits"] == view["analytics"]["initial_eig"]["eig_bits"]
    contract = next(q for q in view["questions"] if q["id"] == "nb_q_contract_a")
    assert contract["eig_bits"] == candidate["eig_bits"] and contract["score"] == 100


def test_preview_is_non_committing_and_future_events_are_locked(workspace):
    token = workspace.new("nb", SESSION)
    before = workspace.validated_state(token, SESSION)[0].model_dump()
    preview = workspace.preview(token, SESSION, "nb_update_t1")
    assert preview["after_top3"] != preview["before_top3"]
    assert preview["spans"] and all(s["locator_status"] == "validated" for s in preview["spans"])
    assert workspace.validated_state(token, SESSION)[0].model_dump() == before
    with pytest.raises(WorkspaceError, match="next available"):
        workspace.preview(token, SESSION, "nb_update_t4")
    assert all(d["id"] != "nb_doc_followup" for d in workspace.view(token, SESSION)["documents"])
    with pytest.raises(WorkspaceError):
        workspace.inspect(token, SESSION, "document", "nb_doc_followup")


def test_northstar_four_updates_equal_existing_engine_and_t3_top3_unchanged(workspace):
    token = workspace.new("nb", SESSION)
    reference = replay_scenario(ROOT / "chunk3_synthetic_evaluation", "nb")
    for index in range(4):
        result = approve_next(workspace, token, f"full-sequence-{index}")
        token, view = result["token"], result["view"]
        expected = reference["states"][index + 1]
        state, resolver = workspace.validated_state(token, SESSION)
        assert state.state_revision == index + 2
        assert [q["id"] for q in view["top3"]] == expected["top3"]
        assert [{k: q[k] for k in ("question_id", "rank", "score")} for q in view["questions"] if q["rank"]] == [{k: r[k] for k in ("question_id", "rank", "score")} for r in expected["ranking"]]
        assert all(d.actor_id == SERVER_ACTOR.actor_id for d in state.analyst_decisions if d.id.startswith("decision_web_"))
        validate_grounding(state, mode="demo", source_resolver=resolver).raise_for_errors()
        if index == 2:
            assert not view["history"][-1]["top3_changed"]
            assert view["history"][-1]["ranking_changed"]  # cost-detail question resolves below Top-3
            assert "Top-3 unchanged" in result["message"]
        assert view["analytics"]["belief_snapshots"] == reference["bayesian"]["belief_snapshots"][:index+1]
    assert not any(e["available"] for e in view["events"])
    assert view["analytics"]["core_ranking_affected"] is False


def test_rejection_keeps_evidence_rank_revision_and_native_hash_chain(workspace):
    token = workspace.new("nb", SESSION)
    before, _ = workspace.validated_state(token, SESSION)
    result = workspace.act(token, SESSION, "reject", "nb_update_t1", 1, "reject-source", "Not accepted for this demo branch.")
    after, resolver = workspace.validated_state(result["token"], SESSION)
    assert after.evidence == before.evidence
    assert after.ranking_snapshots == before.ranking_snapshots
    assert after.state_revision == before.state_revision
    assert after.audit_events[-1].event_type == "update_rejected"
    validate_grounding(after, mode="demo", source_resolver=resolver).raise_for_errors()
    assert all(r["reason"] == "UNCHANGED" for r in result["view"]["changes"])
    assert not any(e["available"] for e in result["view"]["events"])
    with pytest.raises(WorkspaceError):
        workspace.act(result["token"], SESSION, "approve", "nb_update_t1", 1, "approve-rejected", "Retry rejected event.")


def test_duplicate_idempotency_stale_revision_and_reset(workspace):
    token = workspace.new("nb", SESSION)
    result = approve_next(workspace, token, "idempotent-one")
    approved = result["token"]
    identical_retry = approve_next(workspace, token, "idempotent-one")
    assert identical_retry["token"] == approved  # same old token + command has identical signed result
    repeated = workspace.act(approved, SESSION, "approve", "nb_update_t1", 1, "idempotent-one", "Reviewed the native synthetic source.")
    assert repeated["token"] == approved and repeated["replayed"]
    repeated_click = workspace.act(approved, SESSION, "approve", "nb_update_t1", 2, "fresh-click", "Reviewed again.")
    assert repeated_click["token"] == approved and repeated_click["replayed"]
    with pytest.raises(WorkspaceError) as exc:
        workspace.act(approved, SESSION, "approve", "nb_update_t2", 1, "stale", "Stale screen.")
    assert exc.value.code == "REVISION_CONFLICT"
    with pytest.raises(WorkspaceError) as exc:
        workspace.act(approved, SESSION, "reject", "nb_update_t2", 2, "idempotent-one", "Conflicting retry.")
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    reset = workspace.act(approved, SESSION, "reset", None, 2, "reset-branch", "Reset demo.")
    assert reset["view"]["revision"] == 1 and reset["view"]["history"] == []
    assert workspace.view(approved, SESSION)["revision"] == 2  # historical branch is reproducible


@pytest.mark.parametrize("case", ["mf", "lm", "ns", "cd"])
def test_other_synthetic_deals_execute_actual_event(workspace, case):
    token = workspace.new(case, SESSION)
    result = approve_next(workspace, token, f"case-{case}")
    assert result["view"]["revision"] == 2
    assert result["view"]["analytics"]["status"] == "not_parameterized"
    if case == "lm":
        assert any(row["reason"] == "CONFLICT_REOPENED" for row in result["view"]["changes"])


def test_source_inspection_uses_server_spans_and_source_download_allowlist(workspace):
    token = workspace.new("nb", SESSION)
    view = workspace.view(token, SESSION)
    for kind, key in [("question", "questions"), ("claim", "claims"), ("evidence", "evidence"), ("thesis", "theses"), ("document", "documents")]:
        detail = workspace.inspect(token, SESSION, kind, view[key][0]["id"])
        assert detail["spans"]
        for span in detail["spans"]:
            assert span["normalized_text"][span["start"]:span["end"]] == span["quote"]
            assert span["prefix"] + span["quote"] + span["suffix"] == span["normalized_text"]
            assert span["locator_label"]
    filename, source = workspace.document_bytes(token, SESSION, view["documents"][0]["id"])
    assert filename.endswith(".docx") and source.startswith(b"PK")
    for item in ("../../.env", "nb_doc_followup", "unknown_document"):
        with pytest.raises(WorkspaceError):
            workspace.document_bytes(token, SESSION, item)


def test_token_integrity_browser_isolation_and_concurrent_tabs(workspace):
    token_a = workspace.new("nb", SESSION)
    token_b = workspace.new("nb", OTHER_SESSION)
    with pytest.raises(WorkspaceError):
        workspace.view(token_a, OTHER_SESSION)
    with pytest.raises(WorkspaceError):
        workspace.view(token_a[:-1] + ("0" if token_a[-1] != "0" else "1"), SESSION)
    raw, signature = token_a.split(".")
    body = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    assert set(body) == {"version", "case_id", "session_binding", "branch_id", "actions"}
    body["actor_role"] = "reviewer"
    forged = base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b"=").decode() + "." + signature
    with pytest.raises(WorkspaceError):
        workspace.view(forged, SESSION)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(approve_next, workspace, token_a, f"parallel-{i}") for i in range(2)]
        results = [f.result() for f in futures]
    assert all(r["view"]["revision"] == 2 for r in results)
    assert workspace.view(token_a, SESSION)["revision"] == 1
    assert workspace.view(token_b, OTHER_SESSION)["revision"] == 1
    changed = results[0]["view"]
    changed["claims"].clear()
    assert workspace.view(results[0]["token"], SESSION)["claims"]


@pytest.mark.parametrize("action,event,revision", [("upload", None, 1), ("approve", "../../etc/passwd", 1), ("approve", "nb_update_t1", True), ("reset", "nb_update_t1", 1)])
def test_browser_cannot_send_uncontrolled_commands(workspace, action, event, revision):
    token = workspace.new("nb", SESSION)
    with pytest.raises(WorkspaceError):
        workspace.act(token, SESSION, action, event, revision, "invalid-request", "Review.")
    assert workspace.view(token, SESSION)["revision"] == 1


def test_demo_actions_have_no_database_or_network_side_effects(workspace, monkeypatch):
    token = workspace.new("nb", SESSION)
    def deny(*args, **kwargs):
        raise AssertionError("Unexpected network or persistent database operation")
    monkeypatch.setattr(sqlite3, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-never-send-web-test")
    result = approve_next(workspace, token, "offline-review")
    assert result["view"]["revision"] == 2
    assert "dummy-never-send-web-test" not in json.dumps(result)


def test_failed_transition_returns_no_partial_history_or_ranking(workspace, monkeypatch):
    token = workspace.new("nb", SESSION)
    before = workspace.view(token, SESSION)
    def fail(*args, **kwargs):
        raise RuntimeError("Simulated transition failure before token issuance")
    monkeypatch.setattr("orion.services.web_workspace.apply_approved_update", fail)
    with pytest.raises(RuntimeError):
        workspace.act(token, SESSION, "approve", "nb_update_t1", 1, "failed-transition", "Review source.")
    after = workspace.view(token, SESSION)
    assert after["revision"] == before["revision"]
    assert after["questions"] == before["questions"]
    assert after["audit"] == before["audit"]


def test_corrupt_pack_fails_closed_before_demo_creation(tmp_path):
    import shutil
    source = ROOT / "chunk3_synthetic_evaluation/data/synthetic_northstar"
    destination = tmp_path / "chunk3_synthetic_evaluation/data/synthetic_northstar"
    shutil.copytree(source, destination)
    target = destination / "documents/nb_doc_cim.docx"
    target.write_bytes(target.read_bytes() + b"tampered")
    service = WebWorkspace(tmp_path, b"test-only-workspace-key-32-bytes!!")
    with pytest.raises(WorkspaceError) as exc:
        service.new("nb", SESSION)
    assert exc.value.code == "SOURCE_VALIDATION_FAILED"
    assert str(tmp_path) not in str(exc.value)

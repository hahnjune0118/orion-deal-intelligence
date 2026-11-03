"""Foundation service tests; no browser/HTTP implementation is claimed."""
import concurrent.futures
import copy
import importlib.resources
import json
import socket

import pytest
from pydantic import ValidationError

from orion.config import BoundaryError, BudgetConfig, Settings, create_live_adapter, open_local_repository
from orion.demo import DemoAction, prepare_replay, replay_demo

pytestmark = pytest.mark.security


def test_demo_is_default_with_key_and_factory_never_constructed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "foundation-dummy-secret")
    monkeypatch.delenv("ORION_MODE", raising=False)
    settings = Settings.from_env()
    assert settings.mode == "demo"
    assert "foundation-dummy-secret" not in settings.model_dump_json()
    assert "foundation-dummy-secret" not in repr(settings)
    called = []
    with pytest.raises(BoundaryError) as error:
        create_live_adapter(settings, lambda: called.append(True))
    assert error.value.code == "DEMO_ACTION_NOT_ALLOWED"
    assert called == []


def test_demo_no_network_and_no_database(monkeypatch, tmp_path):
    calls = []

    def deny(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Demo attempted network access")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setenv("OPENAI_API_KEY", "foundation-dummy-secret")
    for case in ["ns", "cd", "lm"]:
        result = replay_demo({"case_id": case, "actions": []})
        assert result.mode == "demo"
        assert result.deal.synthetic is True
    settings = Settings(data_dir=str(tmp_path / "should-not-exist"))
    with pytest.raises(BoundaryError):
        open_local_repository(settings)
    with pytest.raises(BoundaryError):
        settings.require_upload()
    assert not (tmp_path / "should-not-exist").exists()
    assert calls == []


def test_two_concurrent_requests_and_reset_are_isolated():
    request = {"case_id": "ns", "actions": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(replay_demo, [request, request]))
    pristine = b.model_dump(mode="json")
    a.claims.clear()
    a.documents[0].filename = "changed in request A"
    assert b.model_dump(mode="json") == pristine
    assert replay_demo(request).model_dump(mode="json") == pristine
    reset = {"case_id": "ns", "actions": [{"action": "reset", "event_id": None}]}
    assert replay_demo(reset).model_dump(mode="json") == pristine
    assert replay_demo({"case_id": "cd", "actions": []}).deal.id != b.deal.id


@pytest.mark.parametrize("extra", [
    {"mode": "local_live"}, {"actor_role": "reviewer"}, {"score": 100},
    {"state_revision": 99}, {"path": "../../.env"}, {"evidence": {}},
])
def test_untrusted_request_fields_are_rejected(extra):
    with pytest.raises(ValidationError):
        prepare_replay({"case_id": "ns", "actions": [], **extra})


@pytest.mark.parametrize("case", ["../ns", "https://example.org", "gold", "NS", "not_known"])
def test_case_allowlist(case):
    with pytest.raises(ValidationError):
        prepare_replay({"case_id": case, "actions": []})


def test_allowed_event_validation_and_engine_is_fail_closed():
    prepared = prepare_replay({"case_id": "ns", "actions": []})
    event_id = prepared.staged_event.id
    action = {"action": "approve", "event_id": event_id}
    request = {"case_id": "ns", "actions": [action]}
    assert len(prepare_replay(request).actions) == 1
    with pytest.raises(BoundaryError) as error:
        replay_demo(request)
    assert error.value.code == "FEATURE_NOT_IMPLEMENTED"
    with pytest.raises(BoundaryError):
        prepare_replay({"case_id": "cd", "actions": [action]})
    with pytest.raises(BoundaryError):
        prepare_replay({"case_id": "ns", "actions": [action, action]})
    with pytest.raises(ValidationError):
        prepare_replay({"case_id": "ns", "actions": [{"action": "reset", "event_id": None}] * 33})
    with pytest.raises(ValidationError):
        prepare_replay({"case_id": "ns", "actions": [{**action, "actor_id": "reviewer_attacker"}]})
    reset_request = {"case_id": "ns", "actions": [action, {"action": "reset", "event_id": None}]}
    assert replay_demo(reset_request).model_dump() == prepared.state.model_dump()


def test_no_gold_or_expected_inputs_in_runtime_resources():
    root = importlib.resources.files("orion").joinpath("resources", "demo")
    for case in root.iterdir():
        assert sorted(p.name for p in case.iterdir()) == ["initial_state.json", "staged_evidence_update.json"]


@pytest.mark.parametrize("settings", [
    {"mode": "local_live", "bind_host": "0.0.0.0"}, {"bind_host": "example.org"},
    {"mode": "LIVE"}, {"port": "8050"}, {"port": True}, {"public_upload": True},
])
def test_bad_startup_settings(settings):
    with pytest.raises(ValidationError):
        Settings.model_validate(settings)


@pytest.mark.parametrize("budget", [
    {"per_run_usd": -1.0}, {"per_run_usd": float("nan")}, {"daily_usd": float("inf")},
    {"per_run_usd": 0.51}, {"max_input_tokens": 12001}, {"max_output_tokens": 2001},
    {"sdk_retries": 1}, {"active_runs": 2}, {"requests_per_run": 4},
    {"sdk_retries": False}, {"sdk_retries": 0.0}, {"active_runs": True}, {"active_runs": 1.0},
    {"daily_usd": 0.1}, {"max_input_tokens": "100"},
])
def test_bad_budget_config(budget):
    with pytest.raises(ValidationError):
        BudgetConfig.model_validate(budget)


def test_local_request_host_and_origin_guards():
    config = Settings(mode="local_live")
    config.validate_local_request(host="127.0.0.1:8050", origin="http://127.0.0.1:8050", method="POST")
    for host, origin in [("evil.example", None), ("127.0.0.1:8050", "https://evil.example"), ("127.0.0.1:8050", None)]:
        with pytest.raises(BoundaryError):
            config.validate_local_request(host=host, origin=origin, method="POST")
    with pytest.raises(BoundaryError):
        create_live_adapter(config, lambda: pytest.fail("unverified provider instantiated"))


def test_startup_env_parser_never_reads_key():
    class KeyGuard(dict):
        def __getitem__(self, key):
            assert key != "OPENAI_API_KEY"
            return super().__getitem__(key)
    env = KeyGuard(OPENAI_API_KEY="never-read", ORION_MODE="demo", ORION_PORT="8051")
    assert Settings.from_env(env).port == 8051
    with pytest.raises(ValueError):
        Settings.from_env({"ORION_PORT": "8050\n"})


def test_nested_constructed_model_cannot_bypass_action_validation():
    event = prepare_replay({"case_id": "ns", "actions": []}).staged_event.id
    invalid = DemoAction.model_construct(action="delete_all", event_id=event)
    with pytest.raises(ValidationError):
        prepare_replay({"case_id": "ns", "actions": [invalid]})

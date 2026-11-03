"""Chunk 2 server boundary checks; no browser or native parser is implied."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import socket
import sqlite3

import pytest
from pydantic import ValidationError

from orion.config import BoundaryError
from orion.demo import DemoAction, DemoRequest, prepare_replay, replay_reviewed_demo
from orion.domain.grounding import validate_grounding
from orion.domain.transitions import question_changes

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def request(case, action='approve'):
    event = prepare_replay({'case_id': case, 'actions': []}).staged_event
    return {'case_id': case, 'actions': [{'action': action, 'event_id': event.id}]}


@pytest.mark.parametrize('case,folder', [('ns', 'EXAMPLES'), ('cd', 'DATASET_SPECS/cd'), ('lm', 'DATASET_SPECS/lm')])
def test_whole_replay_matches_frozen_expected_transition(case, folder):
    expected = json.loads((ROOT / 'spec' / folder / 'expected_top3_transition.json').read_text())
    before = replay_reviewed_demo({'case_id': case, 'actions': []})
    after = replay_reviewed_demo(request(case))
    head = next(s for s in after.ranking_snapshots if s.id == after.head_snapshot_id)
    assert after.state_revision == expected['after_revision']
    assert head.top3 == expected['after_top3']
    changes = {row.question_id: row.model_dump() for row in question_changes(before, after)}
    for wanted in expected['question_changes']:
        assert changes[wanted['question_id']] == wanted
    for wanted in expected['claim_after']:
        claim = next(c for c in after.claims if c.id == wanted['claim_id'])
        assert claim.support_status == wanted['support_status']
        assert claim.truth_status == wanted['truth_status']
    validate_grounding(after, mode='demo').raise_for_errors()
    assert before.ranking_snapshots[0] == after.ranking_snapshots[0]
    assert before.audit_events[0] == after.audit_events[0]
    assert len(after.audit_events) == len(before.audit_events) + 2
    assert after.analyst_decisions[-1].actor_id == 'actor_demo_reviewer'
    assert after.analyst_decisions[-1].actor_role == 'reviewer'


@pytest.mark.parametrize('case', ['ns', 'cd', 'lm'])
def test_reject_reset_and_unapproved_keep_ranking(case):
    initial = replay_reviewed_demo({'case_id': case, 'actions': []})
    rejected = replay_reviewed_demo(request(case, 'reject'))
    assert rejected.ranking_snapshots == initial.ranking_snapshots
    assert rejected.evidence == initial.evidence
    assert rejected.state_revision == initial.state_revision
    assert rejected.analyst_decisions[-1].action == 'reject'
    assert rejected.audit_events[-1].event_type == 'update_rejected'
    reset = request(case)
    reset['actions'].append({'action': 'reset', 'event_id': None})
    assert replay_reviewed_demo(reset) == initial
    approved = replay_reviewed_demo(request(case))
    assert replay_reviewed_demo(request(case)) == approved  # deterministic branch, no extra audit


def test_network_database_and_provider_calls_are_zero_for_all_branches(monkeypatch):
    attempts = []
    def deny(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('Replay attempted external I/O')
    for attr in ['create_connection', 'getaddrinfo']:
        monkeypatch.setattr(socket, attr, deny)
    for attr in ['connect', 'connect_ex']:
        monkeypatch.setattr(socket.socket, attr, deny)
    monkeypatch.setattr(sqlite3, 'connect', deny)
    monkeypatch.setenv('OPENAI_API_KEY', 'dummy-chunk-two-never-send')
    for case in ['ns', 'cd', 'lm']:
        for action in ['approve', 'reject']:
            state = replay_reviewed_demo(request(case, action))
            assert 'dummy-chunk-two-never-send' not in state.model_dump_json()
            assert all(run.mode == 'cached' for run in state.analysis_runs)
    assert attempts == []


def test_concurrent_branches_are_request_owned_and_reset_isolated():
    requests = [request('ns'), request('ns', 'reject'), request('cd'), request('lm')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        states = list(pool.map(replay_reviewed_demo, requests))
    pristine = [s.model_dump() for s in states]
    states[0].claims.clear()
    states[0].documents[0].filename = 'mutated-in-one-request'
    for index in range(1, len(states)):
        assert states[index].model_dump() == pristine[index]
    assert replay_reviewed_demo(requests[0]).model_dump() == pristine[0]
    assert states[1].state_revision == 1


@pytest.mark.parametrize('payload', [
    {'score': 100}, {'actor_role': 'reviewer'}, {'actor_id': 'actor_attacker'},
    {'raw_evidence': {}}, {'state_revision': 10}, {'mode': 'local_live'},
    {'path': '../../.env'}, {'snapshot': {}},
])
def test_reviewed_boundary_forbids_client_scores_roles_and_raw_records(payload):
    raw = request('ns')
    with pytest.raises(ValidationError):
        replay_reviewed_demo({**raw, **payload})
    raw['actions'][0].update(payload)
    with pytest.raises(ValidationError):
        replay_reviewed_demo(raw)


def test_model_construct_unknown_event_repeated_action_and_cross_deal_are_rejected():
    raw = request('ns')
    forged = DemoAction.model_construct(action='upload', event_id=raw['actions'][0]['event_id'])
    # A forged action enum cannot bypass full revalidation even through an instance.
    with pytest.raises(ValidationError):
        replay_reviewed_demo(DemoRequest.model_construct(case_id='ns', actions=[forged]))
    for changed in [
        {**raw, 'case_id': 'lm'},
        {**raw, 'actions': raw['actions'] * 2},
        {**raw, 'actions': [{'action': 'approve', 'event_id': 'unknown_event'}]},
    ]:
        with pytest.raises(BoundaryError):
            replay_reviewed_demo(changed)
    assert replay_reviewed_demo(raw).state_revision == 2

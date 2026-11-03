"""Upgrade a real DB made by the supplied, unmodified Foundation wheel."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from orion.adapters.sqlite_repo import SQLiteRepository
from orion.services.review import ReviewService
from orion.services.workspace import ActorContext, WorkspaceService

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_additive_upgrade_preserves_original_versions_then_approves(tmp_path):
    wheel = ROOT / 'artifacts/orion_deal_intelligence-0.1.0-py3-none-any.whl'
    db = tmp_path / 'from_chunk01.sqlite3'
    seed = ROOT / 'spec/EXAMPLES/initial_state.json'
    code = '''
import sys,json
sys.path.insert(0,sys.argv[1])
import orion
assert sys.argv[1] in orion.__file__
from orion.adapters.sqlite_repo import SQLiteRepository
repo=SQLiteRepository(sys.argv[2],validation_mode='contract')
repo.initialize()
with open(sys.argv[3],encoding='utf-8') as source:
    repo.install_seed(json.load(source))
with repo.connect() as con:
    names={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'staged_updates' not in names
print(repo.read_state('deal_ns').model_dump_json())
'''
    created = subprocess.run([sys.executable, '-c', code, str(wheel), str(db), str(seed)],
                             text=True, capture_output=True, check=False)
    assert created.returncode == 0, created.stderr
    original = json.loads(created.stdout)
    repo = SQLiteRepository(db, validation_mode='contract')
    repo.initialize()
    repo.initialize()  # Repeated startup is additive and safe.
    assert repo.read_state('deal_ns').model_dump(mode='json') == original
    with repo.connect() as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM staged_updates').fetchone()[0] == 0
    actor = ActorContext('actor_upgrade_reviewer', 'reviewer')
    service = ReviewService(repo, actor, clock=lambda: '2026-11-04T00:02:00Z')
    event = json.loads((ROOT / 'spec/EXAMPLES/staged_evidence_update.json').read_text())
    service.stage(event, idempotency_key='upgrade_stage')
    result = service.approve('deal_ns', event['id'], expected_revision=1,
                             idempotency_key='upgrade_approve', reason='Reviewed exact synthetic scope')
    state = WorkspaceService(repo, actor).get_state('deal_ns')
    assert result.state_revision == 2
    assert next(s for s in state.ranking_snapshots if s.id == result.snapshot_id).top3 == [
        'q_ns_contract_b', 'q_ns_accept_collect', 'q_ns_concentration']
    for snapshot in original['ranking_snapshots']:
        assert next(s for s in state.ranking_snapshots if s.id == snapshot['id']).model_dump(mode='json') == snapshot
    for audit in original['audit_events']:
        assert next(a for a in state.audit_events if a.id == audit['id']).model_dump(mode='json') == audit

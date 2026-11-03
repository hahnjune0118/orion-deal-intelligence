import json
from pathlib import Path
import subprocess
import sys

import pytest

from orion.domain.models import DealState, validate_envelope

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    return subprocess.run([sys.executable, '-m', 'orion.cli', *map(str, args)], capture_output=True, text=True)


@pytest.mark.parametrize('case,scores', [('ns', [97, 89, 86]), ('cd', [94, 89, 86]), ('lm', [97, 92, 89])])
def test_cli_replay_writes_valid_state_and_rank_recomputes(case, scores, tmp_path):
    path = tmp_path / case / 'after.json'
    result = run('replay', '--case', case, '--event', 'staged', '--approve', '--output', path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['scores'] == scores
    state = validate_envelope(path.read_bytes())
    assert isinstance(state, DealState)
    ranked = run('rank', '--state', path)
    assert ranked.returncode == 0, ranked.stderr
    assert json.loads(ranked.stdout)['top3'] == payload['top3']
    assert json.loads(ranked.stdout)['input_digest'] == payload['input_digest']


def test_cli_initial_rank_and_rejected_event(tmp_path):
    result = run('rank', '--state', ROOT / 'spec/EXAMPLES/initial_state.json')
    assert result.returncode == 0, result.stderr
    assert [r['score'] for r in json.loads(result.stdout)['rows'][:3]] == [100, 97, 89]
    for outcome in [[], ['--reject']]:
        output = tmp_path / ('rejected.json' if outcome else 'staged.json')
        result = run('replay', '--case', 'ns', '--event', 'staged', *outcome, '--output', output)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['scores'] == [100, 97, 89]
        assert json.loads(result.stdout)['state_revision'] == 1


def test_cli_invalid_inputs_are_redacted_and_do_not_create_output(tmp_path):
    payload = json.loads((ROOT / 'spec/EXAMPLES/initial_state.json').read_text())
    payload['private'] = 'not-for-logs'
    bad = tmp_path / 'invalid.json'
    bad.write_text(json.dumps(payload))
    result = run('rank', '--state', bad)
    assert result.returncode == 2
    assert 'not-for-logs' not in result.stdout + result.stderr
    path = tmp_path / 'should-not-exist.json'
    result = run('replay', '--case', '../ns', '--event', 'staged', '--approve', '--output', path)
    assert result.returncode == 2
    assert not path.exists()


def test_all_domain_imports_remain_independent_of_ui_provider_and_database():
    code = ('import sys; import orion.domain.scoring; import orion.domain.transitions; '
            "assert not {'dash', 'dash_ag_grid', 'openai', 'sqlite3'} & set(sys.modules)")
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

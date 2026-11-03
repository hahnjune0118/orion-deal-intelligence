import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.contracts


@pytest.mark.parametrize("case", ["EXAMPLES", "DATASET_SPECS/cd", "DATASET_SPECS/lm"])
@pytest.mark.parametrize("name", ["initial_state.json", "staged_evidence_update.json", "expected_top3_transition.json"])
def test_validate_fixture_cli(case, name):
    result = subprocess.run([sys.executable, "-m", "orion.cli", "validate-fixture", str(ROOT / "spec" / case / name)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "valid"
    assert output["scoring_executed"] is False


def test_cli_redacts_bad_input(tmp_path):
    payload = json.loads((ROOT / "spec/EXAMPLES/initial_state.json").read_text())
    payload["private"] = "source-text-that-must-not-appear-in-log"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload))
    result = subprocess.run([sys.executable, "-m", "orion.cli", "validate-fixture", str(path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "source-text-that-must-not-appear-in-log" not in result.stdout + result.stderr
    assert json.loads(result.stderr)["code"] == "CONTRACT_INVALID"


def test_demo_seed_works_outside_repository(tmp_path):
    result = subprocess.run([sys.executable, "-m", "orion.cli", "seed-demo", "--case", "lm"],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["persisted"] is False


def test_database_cli_respects_startup_mode(tmp_path):
    env = dict(os.environ, ORION_MODE="demo", ORION_DATA_DIR=str(tmp_path / "db"))
    command = [sys.executable, "-m", "orion.cli", "init-db"]
    denied = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert denied.returncode == 2
    assert not (tmp_path / "db").exists()
    env["ORION_MODE"] = "local_live"
    allowed = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert allowed.returncode == 0, allowed.stderr
    assert (tmp_path / "db/orion.sqlite3").exists()


def test_domain_import_does_not_import_ui_provider_or_database():
    code = (
        "import sys; import orion.domain.models; import orion.domain.grounding; "
        "assert not {'dash','dash_ag_grid','openai','sqlite3'} & set(sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

"""User-facing commands must fail on a detected dataset discrepancy."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.integration


def run(*arguments):
    return subprocess.run([sys.executable, "-m", "orion.cli", *map(str, arguments)],
                          cwd=ROOT, capture_output=True, text=True, check=False)


def test_cli_reports_detected_financial_mismatch_as_nonzero(tmp_path):
    source = ROOT / "chunk3_synthetic_evaluation"
    dataset = tmp_path / "dataset"
    shutil.copytree(source / "data", dataset / "data")
    shutil.copytree(source / "gold", dataset / "gold")
    world_path = dataset / "gold/nb_world_model.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world["income_2025"]["revenue"] += 1
    world_path.write_text(json.dumps(world), encoding="utf-8")
    result = run("validate-dataset", "--root", dataset)
    assert result.returncode == 2, result.stderr
    if not result.stdout.strip():
        diagnostic = subprocess.run(
            [
                sys.executable, "-c",
                "from orion.synthetic import validate_dataset; "
                "import sys; validate_dataset(sys.argv[1])",
                str(dataset),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        pytest.fail(
            f"CLI stderr: {result.stderr!r}\n"
            f"Direct validator returncode: {diagnostic.returncode}\n"
            f"Direct validator stderr: {diagnostic.stderr}\n"
            f"Direct validator stdout: {diagnostic.stdout[:2000]}"
        )
    report = json.loads(result.stdout)
    assert report["passed"] is False
    assert report["cases"]["nb"]["passed"] is False


def test_live_evaluation_cli_does_not_invent_model_results(tmp_path):
    result = run("evaluate", "--cases", "ns", "--arms", "B0", "--mode", "live",
                 "--output", tmp_path / "evaluation")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), (
        f"CLI returned no JSON. "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )
    report = json.loads(result.stdout)
    assert report["status"] == "not_run"
    assert report["actual_model_benchmark"] == "not_run"
    assert report["live_api_calls"] == 0
    assert all(row["status"] == "not_run" for row in report["rows"])
    assert all(row["metrics"]["top3_critical_dd_coverage"]["value"] is None
               for row in report["rows"])

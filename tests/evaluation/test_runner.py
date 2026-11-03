import json
from pathlib import Path

import pytest

from orion.demo import prepare_replay
from orion.evaluation import runner

pytestmark = pytest.mark.evaluation


@pytest.fixture
def fixture_loader(monkeypatch):
    def load(case):
        prepared = prepare_replay({"case_id": case, "actions": []})
        return prepared.state, prepared.staged_event, None, "fixture-text-only"
    monkeypatch.setattr(runner, "_load_legacy", load)


def test_legacy_functional_protocol_and_all_negative_controls(tmp_path, fixture_loader):
    report = runner.run_evaluation(cases=["ns", "cd", "lm"], output=tmp_path / "results", dataset_root=tmp_path / "absent")
    assert report["valid"]
    assert report["actual_model_benchmark"] == "not_run"
    assert report["status"] == "fixture_only"
    assert report["live_api_calls"] == 0
    assert len(report["rows"]) == 30
    assert len(report["negative_controls"]) == 15
    assert report["negative_control_stability"]["value"] == 1
    assert all(row["transition_pass"] for row in report["transitions"])
    assert all(row["provenance"] == "not_run" for row in report["rows"] if row["arm"] == "B1-R")
    assert all(row["metrics"]["citation_precision"]["value"] is None for row in report["rows"] if row["arm"] in {"B0", "B1-R"})
    for case in ("ns", "cd", "lm"):
        assert report["ablations"][case]["after"]["no_bayesian"]["production_rank_invariant"]
    manifest = json.loads((tmp_path / "results/run_manifest.json").read_text())
    assert all(row["model_version"].startswith("not_") and len(row["output_checksum"]) == 64 for row in manifest["runs"])


def test_live_mode_explicitly_unimplemented(tmp_path, fixture_loader):
    report = runner.run_evaluation(arms=["B3"], cases=["ns"], mode="live", output=tmp_path / "results", dataset_root=tmp_path / "absent")
    assert report["status"] == "not_run"
    assert report["live_api_calls"] == 0
    assert all(row["status"] == "not_run" for row in report["rows"])
    assert all(row["metrics"]["top3_critical_dd_coverage"]["value"] is None for row in report["rows"])


@pytest.mark.parametrize("cases", [[], ["orion_real"], ["ns", "ns"]])
def test_invalid_case_selection_rejected(cases, tmp_path):
    with pytest.raises(ValueError): runner.run_evaluation(cases=cases, output=tmp_path)


def test_nonexistent_arm_rejected(tmp_path):
    with pytest.raises(ValueError): runner.run_evaluation(arms=["fake"], output=tmp_path)

from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from orion.evaluation.synthetic_bridge import audit_extended_bundle, independent_numeric_targets, run_extended_evaluation
from orion.synthetic import agent_visible_bundle

pytestmark = pytest.mark.evaluation
ROOT = Path(__file__).resolve().parents[2] / "chunk3_synthetic_evaluation"


def test_independent_fraction_targets():
    target = independent_numeric_targets()
    assert target["positive"] == pytest.approx(12 / 19)
    assert target["negative"] == pytest.approx(3 / 31)
    assert target["eig_bits"] == pytest.approx(0.23611392733893727)
    assert target["sequential"]["4"] == pytest.approx(30 / 79)


def test_expanded_source_allowlist_rejects_future_data_and_labels():
    initial = agent_visible_bundle(ROOT, case="nb", stage=0)
    later = agent_visible_bundle(ROOT, case="nb", stage=4)
    assert audit_extended_bundle(initial, "nb", 0)["valid"]
    forged = deepcopy(initial)
    forged["documents"] = later["documents"]
    assert not audit_extended_bundle(forged, "nb", 0)["valid"]
    forged = deepcopy(initial)
    forged["answer_key"] = {"expected": "yes"}
    assert not audit_extended_bundle(forged, "nb", 0)["valid"]


def test_primary_case_four_arm_adapters_actual_toggle_and_numeric_checks(tmp_path):
    report = run_extended_evaluation(ROOT, output=tmp_path, cases=["nb", "mf"])
    assert report["valid"]
    assert len(report["rows"]) == 7
    assert len(report["baseline_rows"]) == 35
    assert {row["arm"] for row in report["baseline_rows"]} == {"B0", "B1", "B2", "B3", "B1-R"}
    assert all(row["label_status"] == "authored_stage_labels" for row in report["rows"])
    assert all(row["expected_hypothesis_support_pass"] for row in report["rows"])
    assert report["no_bayesian_ablation"]["nb"]["stages_tested"] == 5
    assert report["no_bayesian_ablation"]["nb"]["production_rank_invariant"]
    assert report["quantitative_validation"]["nb"]["posterior_error"]["error"]["value"] < 1e-12
    assert report["quantitative_validation"]["nb"]["eig_error"]["error"]["value"] < 1e-12
    assert all(row["metrics"]["claim_recall"]["status"] == "not_run" for row in report["baseline_rows"])
    assert all(row["status"] == "not_run" for row in report["baseline_rows"] if row["arm"] == "B1-R")


def test_primary_case_requested_arm_and_live_mode_are_honored(tmp_path):
    report = run_extended_evaluation(ROOT, output=tmp_path, cases=["nb"], arms=["B0"], mode="live")
    assert report["status"] == "not_run"
    assert len(report["baseline_rows"]) == 5
    assert all(row["arm"] == "B0" and row["status"] == "not_run" for row in report["baseline_rows"])
    assert report["engine_validation_status"] == "fixture_only"


def test_missing_requested_case_is_not_silently_dropped(tmp_path):
    report = run_extended_evaluation(tmp_path / "missing", output=tmp_path / "result", cases=["nb"])
    assert not report["valid"]
    assert report["missing_cases"][0]["case"] == "nb"


def test_altered_independent_status_gold_fails_gate_not_prediction(tmp_path):
    dataset = tmp_path / "dataset"
    shutil.copytree(ROOT / "data", dataset / "data")
    shutil.copytree(ROOT / "gold", dataset / "gold")
    path = dataset / "gold/nb_gold.json"
    gold = json.loads(path.read_text())
    gold["stages"]["0"]["expected_hypothesis_statuses"]["nb_claim_h1"] = "supported"
    path.write_text(json.dumps(gold), encoding="utf-8")
    report = run_extended_evaluation(dataset, output=tmp_path / "result", cases=["nb"], arms=["B3"])
    assert not report["valid"]
    assert report["rows"][0]["expected_hypothesis_support_pass"] is False
    assert report["rows"][0]["top3"] == ["nb_q_contract_a", "nb_q_contract_b", "nb_q_execution_a"]

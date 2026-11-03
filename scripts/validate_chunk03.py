"""Run the offline Chunk 3 workflow and retain real exit codes and UTC logs.

Run from an installed Python 3.12 environment. This script makes no network
calls, does not install packages and does not start the future web UI.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    evidence = ROOT / "implementation_evidence"
    logs = evidence / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), ORION_MODE="demo")
    commands = [
        ("generate-native", ["-m", "orion.cli", "generate-synthetic", "--output", "data/synthetic"]),
        ("ingest-native", ["-m", "orion.cli", "ingest", "--case", "all", "--mode", "demo"]),
        ("generate-expanded", ["-m", "orion.cli", "generate-dataset"]),
        ("validate-expanded", ["-m", "orion.cli", "validate-dataset"]),
        ("replay-northstar", ["-m", "orion.cli", "replay-scenario", "--case", "nb", "--output", "implementation_evidence/chunk03-northstar-replay.json"]),
        ("replay-manufacturing", ["-m", "orion.cli", "replay-scenario", "--case", "mf", "--output", "implementation_evidence/chunk03-manufacturing-replay.json"]),
        ("input-audit", ["-m", "orion.cli", "audit-model-inputs", "--cases", "all"]),
        ("evaluation", ["-m", "orion.cli", "evaluate", "--arms", "B0", "B1", "B2", "B3", "B1-R", "--cases", "all", "--mode", "cached"]),
        ("quantitative-report", ["-m", "orion.quant.report", "--output", "evaluation/results/quantitative_report.json"]),
        ("spec-integrity", ["scripts/verify_spec.py"]),
        ("full-pytest", ["-m", "pytest", "-q", "--strict-markers", "--junitxml=implementation_evidence/chunk03-pytest.xml"]),
        ("pip-check", ["-m", "pip", "check"]),
        ("compile", ["-m", "compileall", "-q", "src"]),
    ]
    report = {
        "started_at_utc": now(), "os": platform.platform(), "python": sys.version,
        "source_import_root": str(ROOT / "src"), "live_api_calls": 0,
        "model_benchmark_status": "not_run", "native_windows_status": "not_run",
        "locks": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(ROOT.glob("requirements-*.lock"))},
        "commands": [],
    }
    for name, arguments in commands:
        command = [sys.executable, *arguments]
        record = {"name": name, "command": command, "started_at_utc": now()}
        log = logs / f"chunk03-{name}.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
        record.update(finished_at_utc=now(), exit_code=result.returncode,
                      status="pass" if result.returncode == 0 else "failed",
                      log=str(log.relative_to(evidence)))
        report["commands"].append(record)
        print(f"{name}: {record['status']} (exit {result.returncode})", flush=True)
    digest = hashlib.sha256()
    for folder in ("src", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
            digest.update(path.read_bytes())
    report.update(finished_at_utc=now(), source_test_sha256=digest.hexdigest())
    report["status"] = "pass" if all(c["exit_code"] == 0 for c in report["commands"]) else "failed"
    (evidence / "chunk03-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

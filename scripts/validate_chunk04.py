"""Run the complete installed source-tree regression and retain observed results.

No dependency installation, dataset regeneration, external APIs or git writes.
Use --require-browser for a release gate that fails when Chromium is absent.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "implementation_evidence"


def verify_baseline() -> dict:
    manifest = json.loads((EVIDENCE / "chunk04-baseline-manifest.json").read_text(encoding="utf-8"))
    allowed = {"README.md", "pyproject.toml", "CHECKSUMS.sha256", "DELIVERY_FILES.txt", "REPOSITORY_TREE.txt"}
    modified, missing, preserved = [], [], 0
    for name, digest in manifest["files"].items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            modified.append(name)
        else:
            preserved += 1
    unexpected = sorted(set(modified) - allowed)
    return dict(status="pass" if not missing and not unexpected else "failed",
                original_zip_sha256=manifest["zip_sha256"], original_file_count=len(manifest["files"]),
                byte_identical_files=preserved, modified_original_files=modified,
                missing_original_files=missing, unexpected_changes=unexpected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-browser", action="store_true")
    args = parser.parse_args()
    logs = EVIDENCE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, ORION_MODE="demo", PYTHONPATH=str(ROOT / "src"))
    if args.require_browser:
        env["ORION_REQUIRE_BROWSER"] = "1"
    report = dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
                  python=sys.version, platform=platform.platform(),
                  native_windows_status="not_run", real_llm_benchmark_status="not_run",
                  public_deployment_status="not_run", require_browser=args.require_browser,
                  baseline_preservation=verify_baseline(), commands=[])
    commands = [
        ("spec-integrity", ["scripts/verify_spec.py"]),
        ("pip-check", ["-m", "pip", "check"]),
        ("compile", ["-m", "compileall", "-q", "src"]),
        ("full-regression", ["-m", "pytest", "-q", "--strict-markers",
                             "--junitxml=implementation_evidence/chunk04-pytest.xml"]),
    ]
    for name, arguments in commands:
        command = [sys.executable, *arguments]
        log = logs / f"chunk04-{name}.log"
        started = datetime.now(timezone.utc).isoformat()
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
        report["commands"].append(dict(name=name, command=command, started_at_utc=started,
            finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode,
            status="pass" if result.returncode == 0 else "failed", log=str(log.relative_to(ROOT))))
        print(f"{name}: exit {result.returncode}", flush=True)
    report["status"] = "pass" if report["baseline_preservation"]["status"] == "pass" and all(
        row["exit_code"] == 0 for row in report["commands"]) else "failed"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (EVIDENCE / "chunk04-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

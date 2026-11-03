"""Regenerate target-specific locks with a pinned resolver (Python 3.12)."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    version = subprocess.check_output(["uv", "--version"], text=True)
    if not version.startswith("uv 0.13.4 "):
        raise SystemExit("Use uv==0.13.4 from requirements-tooling.lock")
    for target, platform in (("linux", "x86_64-unknown-linux-gnu"), ("win", "x86_64-pc-windows-msvc")):
        subprocess.run(["uv", "pip", "compile", "requirements.in", "--python-version", "3.12",
                        "--python-platform", platform, "--generate-hashes", "--output-file",
                        f"requirements-{target}.lock"], cwd=ROOT, check=True)

if __name__ == "__main__":
    main()

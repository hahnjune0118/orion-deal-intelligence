# Foundation dependency verification

Verification date: 2026-11-03. Product contract/scoring versions remain **1.0.0**. The original `spec/CONFIG/requirements-candidate.txt` is unchanged.

## Candidate installation and justified implementation changes

The original 17 direct package candidates installed successfully under CPython 3.12.14 / Linux x86_64. Initial Python package audit subsequently detected two known advisories. An additional primary-source review identified an embedded Playwright installer issue, which the Python audit did not report.

| Candidate | Implementation pin | Reason |
|---|---|---|
| pytest 8.4.2 | 9.0.3 | Fix PYSEC-2026-1845 / CVE-2025-71176 / GHSA-6w46-j5rx-g56g (unsafe temporary-directory handling). |
| pytest-playwright 0.7.1 | 0.7.2 | Original plugin requires pytest <9; 0.7.2 resolves with patched pytest 9.0.3. |
| python-dotenv 1.1.1 | 1.2.2 | Fix PYSEC-2026-2270 / CVE-2026-28684 / GHSA-mf9w-mj56-hr94 (symlink-following file rewrite). |
| playwright 1.55.0 | 1.56.0 | Original Python wheel bundles a macOS installer with `curl ... -k`; patched Python 1.56.0 bundles driver 1.56.1 without that flag. Python 1.55.1 does not exist in the index (failed attempt retained in log). |

All other direct candidate versions remain unchanged. These are build/test/provider dependencies; no contract fields, enum, ranking formula or expected fixture was altered. See `DEPENDENCY_SECURITY_REVIEW.md` for primary source links. Source-only Foundation does not use native parser or live provider APIs, despite retaining their planned dependencies for integration compatibility.

## Reproducible environment

- Resolver: **uv 0.13.4**; audit: **pip-audit 2.9.0**. Tool pins plus transitive hashes are in `requirements-tooling.lock` (Linux maintenance/CI environment).
- `requirements-linux.lock`: CPython 3.12, `x86_64-unknown-linux-gnu`; includes gunicorn.
- `requirements-win.lock`: CPython 3.12, `x86_64-pc-windows-msvc`; includes Colorama and omits gunicorn.
- Both use exact transitive pins and distribution SHA-256 hashes. The Windows lock is a separate target resolution, not a renamed Linux lock.
- Generation commands are in the lock headers and `scripts/lock_dependencies.py`. Installation uses `pip install --require-hashes`; project installation is `pip install --no-deps --no-build-isolation -e .` using locked setuptools.
- `implementation_evidence/dependency_inventory.json` records installed metadata, requirement relationships, license locations and lock hashes. `THIRD_PARTY_NOTICES.md` and `third_party_licenses/` retain upstream notices, including the Windows-only Colorama license from the verified wheel.

## Actual verification and limits

| Check | Actual status | Evidence |
|---|---|---|
| Original candidate install | PASS | `logs/candidate-install.log` |
| Final candidate patch resolution/install | PASS | `logs/security-patch-resolution.log`, `logs/security-patches-install.log` |
| Final Linux/Windows target resolution | PASS | `logs/resolve-linux.log`, `logs/resolve-win.log` |
| Final Linux hash-locked install in fresh `.venv-release` | PASS | `logs/hash-lock-final-clean-install.log` |
| Final fresh-environment `pip check` | PASS | `logs/pip-check-final-clean.log` |
| Windows CPython3.12 x64 wheel availability and SHA-256 verification | PASS | `logs/windows-final-wheel-download.log` |
| Dash3.2.0 + AGGrid32.3.2 Community import/serialization and Flask layout route | PASS | `logs/dash-grid-clean-smoke.log` (one smoke test) |
| Final Linux lock automated vulnerability audit | PASS, no known vulnerabilities returned | `dependency-audit-linux.json`, `logs/audit-linux-final.log` |
| Final Windows lock automated vulnerability audit | PASS, no known vulnerabilities returned | `dependency-audit-win.json`, `logs/audit-win-final.log` |
| Native Windows execution | **not_run** | This executor is Linux; `.github/workflows/ci.yml` defines the real Windows Python3.12 job. |
| Actual browser rendering / visual / accessibility tests | **not_run** | Foundation only serializes components and checks the local layout route; full UI is later scope. |
| Hosted GitHub Actions run | **not_run** | Workflow file created; no remote repository or CI execution was requested. |

Audit pass means the configured advisory service reported no known vulnerabilities for these versions at execution time; it does not certify absence of defects, audit JavaScript/browser bundles comprehensively, or replace safe parsing/security policies. The initial reports are retained as `dependency-audit-*-before-patches.json`; findings were addressed, not suppressed. No live key or LLM call was used.

## Re-run commands

```sh
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-linux.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -m pytest tests/smoke -q --strict-markers
python -m venv .venv-tooling
.venv-tooling/bin/python -m pip install --require-hashes -r requirements-tooling.lock
.venv-tooling/bin/python -m pip_audit -r requirements-linux.lock --disable-pip --no-deps
.venv-tooling/bin/python -m pip_audit -r requirements-win.lock --disable-pip --no-deps
```

On Windows use `.venv\Scripts\python.exe` and `requirements-win.lock`. Native Windows test success must be recorded before claiming the cross-platform execution portion of G1 is complete.

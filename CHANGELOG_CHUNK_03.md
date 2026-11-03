# Chunk 3 change log

Package 0.3.0 extends the attached integrated 0.2.0 baseline. Contract and production scoring remain 1.0.0. No original files or tests were deleted; no existing domain API was deprecated.

| Area | Change | Purpose |
|---|---|---|
| `src/orion/adapters/parsers/` | Native parsers, bounded subprocess worker, original-byte source index; existing placeholder retained | Real PDF/DOCX/PPTX locators and explicit unsupported-content fallbacks |
| `src/orion/native_dataset.py`, `resources/native/` | Deterministic legacy document generator and runtime pack adapter | Preserve all three existing semantic transitions with actual source files |
| `src/orion/retrieval.py`, `adapters/cached_llm.py` | Deterministic retrieval and provenance-bound cached draft interface | Separate authored fixtures from actual model-generated cache |
| `src/orion/synthetic/` | Expanded sources, additive models, source-only visibility, finance/gold audits and sequential replay | Northstar and independent manufacturing evaluation cases |
| `src/orion/quant/` | Bayesian/EIG, dependence ledger, explicit conditional model, research policy and sensitivity | Deterministic arithmetic with acknowledged hypothetical assumptions |
| `src/orion/evaluation/` | Metrics, adapters, source allowlist, legacy and expanded runners | Honest fixture/not-run reporting and reproducible benchmarks |
| `src/orion/cli.py` | Add generation, ingestion, dataset validation, scenario, audit and evaluation commands | Complete offline workflow without a provider or UI |
| `tests/` | 241 new test cases; all original 823 retained | Financial/source/quantitative/evaluation/CLI regression and negative cases |
| `data/`, `chunk3_synthetic_evaluation/`, `evaluation/` | Native sources, structured records, isolated gold, inputs, outputs and manifests | Downloadable, reproducible research artifacts |
| `pyproject.toml` | Version 0.3.0, native resource package-data and test markers | Installable integration; no new runtime dependencies |
| `.gitattributes` | Mark PDF/DOCX/PPTX/wheel as binary | Preserve exact bytes and checksums across Git line-ending settings |
| `.github/workflows/ci.yml` | Add complete Chunk 3 validation to existing matrix | Prepare Windows/Linux CI; remote CI not executed here |
| `scripts/validate_chunk03.py`, `scripts/write_chunk03_report.py` | Actual command recording and evidence-derived Korean report | Reproducible handoff with real exit codes |
| README / implementation evidence / manifests | Installation, scope, review findings, test results and exact file hashes | Reviewable integration and Windows application instructions |

The exact per-file added/modified list is `review/CHANGED_FILES.txt` in the delivery ZIP. `review/CHUNK_03.patch` includes binary sources and can be applied to the original attached Chunk 2 baseline. `review/PATCH_VALIDATION.json` records actual patch application and byte comparison. These are local artifacts; no GitHub access, commit or push occurred.

Development checks identified and fixed source-stage metadata leakage, dependence-alias handling, circular status gold, insufficient company-claim source annotations, metric failure/abstention handling and native document layout issues. One early CLI test encountered stale generated `label_stage` metadata while the generator was being updated; regenerated artifacts passed the complete final validation. Earlier logs remain distinguishable from the final logs.

Excluded from this change: full Dash UI, real LLM calls/benchmarks, production export, public deployment, actual public-company findings and native Windows execution. Gold remains self-authored/provisional.

# Chunk 3 Synthetic Data and Evaluation

This directory is part of the integrated Orion repository. It contains original fictional sources, separately controlled synthetic worlds, provisional human-reviewable gold and sequential approved evidence scenarios. It is a runnable dataset, not a completed investment diligence product or an actual LLM benchmark.

The `nb` case is an **independent expanded research variant** of Northstar Analytics. It is not a continuation of the immutable Chunk 1/2 `ns` case. Both happen to use the same fictional display name. Do not combine their observations, contract values or cash balances.

| Namespace | Purpose | Source documents | Questions | Evidence | Events |
| --- | --- | ---: | ---: | ---: | ---: |
| `nb` | Expanded Northstar development example | 8 | 13 | 26 | 4 |
| `mf` | Ridgeway Homeware manufacturing regression example | 6 | 9 | 23 | 1 |
| `ns`, `cd`, `lm` | Unmodified legacy contract demos | See root documentation | Preserved | Preserved | Preserved |
| `public_orion` | Public-company ingestion specification | 0 pending | Not evaluated | 0 | 0 |

## Run

Use the repository's pinned Python **3.12** environment. The broader Python 3.11+ request is met by preserving the already working 3.12 technical baseline; support for other versions is not asserted.

From the repository root after installing the root platform lock and this package:

```bash
python -m pip install -e ".[parsers,test]"
python chunk3_synthetic_evaluation/src/generate_synthetic_data.py chunk3_synthetic_evaluation
python chunk3_synthetic_evaluation/src/validate_dataset.py chunk3_synthetic_evaluation
python -m pytest tests/dataset tests/quant -q
```

The root CLI also exposes integrated dataset/evaluation commands documented in the repository README. No provider key, cloud service or network request is required for generation and functional replay.

Programmatic integration:

```python
from orion.synthetic import agent_visible_bundle, replay_scenario, validate_dataset

root = "chunk3_synthetic_evaluation"
inputs = agent_visible_bundle(root, "nb", stage=1)  # source-only allowlist
trace = replay_scenario(root, "nb")               # explicit simulated analyst approvals
checks = validate_dataset(root)
assert checks["passed"]
```

## Directory correspondence

- `data/synthetic_northstar/documents`: eight original DOCX, corresponding Markdown and parsed source JSON.
- `data/synthetic_manufacturing/documents`: six original manufacturing sources in the same formats.
- Each case's `structured/initial_state.json`: existing `DealState` contract, unchanged schema 1.0.0.
- Each case's `updates/tN.json`: existing `StagedEvidenceUpdate` contract; inactive draft evidence until review approval.
- `gold/*_world_model.json`: privileged integer financial facts and intentional documentary inconsistencies.
- `gold/*_gold.json`: separate analyst hypotheses, actual company claim extraction labels, evidence groups, alternative question families, and independently authored expected stage statuses/ranks.
- `src`: convenience entrypoints/reexports of the integrated `orion.synthetic` and `orion.quant` implementation. There is only one calculation implementation.
- `schemas`: wrappers reuse core entities rather than define incompatible copies.
- `reports`: dataset card, evaluation methodology/results and technical report where produced.

## Source and evaluation boundary

The generator uses original source prose and separately authored world assumptions. Every DOCX source is explicitly fictional. Native parsers resolve real paragraph/table-cell locators; DOCX has no invented page locator. Immutable bytes, parser identity, document version and exact quotes are checked on read.

`agent_visible_bundle` reads only native sources whose disclosure stage is allowed. A code-owned source-only disclosure schedule blocks moving a future source into T0 by editing its JSON stage. It never loads `gold`, world-generation code, expected ranks, current engine states or later Q&A text into the serialized model input. This is an application input boundary, not an OS filesystem security sandbox: an arbitrary Python adapter with unrestricted disk access could still read repository gold. Live adapters must receive only the returned bundle.

The source-only input must not be replaced with a recursive repository or `data` directory upload. Prompt dumps and model-input audits are part of the evaluation harness.

## Adaptive behavior

Northstar: signed Aster contract → accepted deployment and partial cash → complete cost categories revealing negative contribution → Birch commercial milestones plus common ownership. Signature, acceptance, recognized revenue, invoice and cash are separate facts. Aster's USD 90,000 cash does not mean its USD 120,000 invoice is fully paid. Complete cost-category coverage does not mean positive margins or independent cost verification.

All questions are authored candidates. No generative question-creation capability is claimed in Chunk 3; event traces report an empty newly-generated list. The old high-priority request drops only after its scoped criteria are approved. T3 leaves the Top-3 unchanged even though negative economics become better documented. This is deliberate: receiving another document does not force a ranking change.

Manufacturing: a complete physical count resolves quantity reconciliation only. It cannot resolve recoverability, aged inventory write-downs, insurance normalization or future capacity financing.

Bayesian probability is a separate synthetic scenario panel. The primary prior 0.30 and positive likelihoods 0.80/0.20 yield 0.6315789474; negative evidence yields 0.0967741935; EIG is 0.2361139273 bits. Same-customer execution uses an explicitly reviewed conditional model rather than assuming independent evidence. Disabling this panel leaves the established core ranking unchanged.

## Limits

Gold is self-authored/provisional. Multiple engineering reviews are not independent financial-analyst validation. Manufacturing is a different business model with frozen-rule regression coverage; it is not a sequestered unseen statistical holdout. All answer keys are published for academic reproducibility, so contamination resistance in future public-model tests requires additional unpublished evaluation cases.

Source locator pass rates and authored scenario matches are functional evidence only. Actual B0–B3 provider performance, human semantic agreement and public Orion findings remain unmeasured. Windows execution, live extraction, the production Dash UI and production export are later-stage validation tasks; they are not implied by this dataset.

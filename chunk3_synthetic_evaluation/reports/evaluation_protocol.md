# Chunk 3 Evaluation Protocol

Protocol version `eval-1.0`. This package implements evaluation code and executes authored fixtures and deterministic engines. **Actual B0–B3 model benchmarking is not_run.** No API was invoked. Gold is self-authored and provisional, not independently reviewed ground truth.

## Arms and interpretation

| Arm | Implemented fixture behavior | Actual model status |
|---|---|---|
| B0 | Shared author-curated initial questions; citation omission deliberately tests missing-citation metrics | not_run |
| B1 | Same initial questions plus native citations; ranking remains static | not_run |
| B2 | Structured authored Claim–Evidence–DD records; initial deterministic rank frozen | not_run |
| B3 | Same initial records; reviewed evidence updates run through the existing Chunk 2 transition engine | not_run |
| B1-R | Re-prompt adapter and prompt with the same new source information; no invented regeneration output | not_run |

B0/B1 are **test doubles**, not purported samples of how an LLM performs. Their shared outputs hold input quality constant, and intentional citation omissions test the harness. B3 fixture results demonstrate state transitions, not superior investment judgment or extraction. B3 versus static B2 isolates a scripted update mechanism; B1-R is necessary before claiming advantages over re-prompting a real grounded model.

Production scoring remains contract `1.0.0`: `9 × Gap + 8 × Materiality + 3 × Obtainability`, each component 0–5. EIG is an optional, source-labelled scenario panel. The no-Bayesian ablation must leave production rankings unchanged. Separate experimental EIG policies are named/versioned and are not EVSI. No-gap/no-materiality/no-obtainability ablations renormalize retained weights and preserve resolved-question exclusion and tie-breakers.

## Evaluation separation

1. Sources are immutable native documents and deterministic structured elements. The input builder projects only document metadata and text/locators into a stage-specific allowlist.
2. Model inputs exclude `DealState`, curated extraction outputs, gold labels, world facts, scenario expectations, question priorities and future updates.
3. Cached fixtures are separately authored output records. A fixture is labelled `authored-fixture`; an actual model-generated cache would require model/run provenance. No such actual model run is included.
4. The evaluator loads gold only after output construction. It stores raw predictions, annotations and a separate manifest with model/prompt/dataset versions, timestamps, checksums, arm configuration, cost and failure status.
5. The source projection prevents API prompt leakage; it is **not a hostile-code filesystem sandbox**. A future local agent with file tools must run in an isolated process/container mounted only to exported `model_inputs`, with gold/source-generator/world directories absent.
6. Northstar is a development case. Cedar, Lumen and the manufacturing case are public frozen regression/generalization examples. Because their answer keys are publicly shipped, they are **not secret held-out cases**. Unseen external validation remains not_run. No claim of statistically significant superiority is supported by this small, dependent sample.

## Human-reviewable matching protocol

For each predicted DD question, a reviewer records one `family_id` or abstains, plus reviewer identity and rationale. A match requires the same target/customer, requested artifact, period/scope and verification criterion. Alternative wording is permitted; keyword overlap alone is insufficient. One prediction can match only one family, and a repeated family yields no additional coverage or NDCG gain. Two independent blinded reviewers should adjudicate disagreements in a future measured study. Current fixture mappings are identity mappings by the fixture author and stay provisional.

Claim identity matches and entailment labels are evaluator annotations, not model declarations of correctness. Exact quote/location validity is measured separately from whether the cited text entails a statement and from whether the underlying business assertion is true. Unknown entailment, actionability or semantic mappings remain `not_reviewed`, never automatically successful.

## Metric definitions

`N/A` means denominator zero, unless a specific failure rule below applies. Every implementation emits numerator, denominator, value, status and note. State and arm are separate units; results report macro average, pooled micro counts, minimum and number of unmeasured rows. All metrics are in `orion.evaluation.metrics`.

| Metric | Unit / numerator / denominator | Missing or abstained handling | Interpretation and limitation |
|---|---|---|---|
| Claim precision | Distinct correctly matched gold claims / all claim predictions | No predictions with gold: 0 | Duplicate predictions count against precision; evaluator claim mapping required |
| Claim recall | Distinct correctly matched gold claims / relevant visible gold claims | Missing predictions: 0 | Only stage-visible claims belong to gold |
| Claim F1 | `2TP / (predictions + gold claims)` | Both empty: N/A | Does not measure financial significance |
| Evidence retrieval recall | Unique retrieved relevant evidence IDs / visible gold evidence IDs | Omission: 0 | No gold evidence set: N/A; ID matching alone is not entailment |
| Evidence relationship accuracy | Unique correct `(claim,evidence,relation)` / submitted relations | No submissions: N/A, paired recall 0 | Duplicates cannot improve numerator |
| Evidence relationship recall | Unique correct triples / expected visible triples | Omission: 0 | Prevents accuracy inflation by submitting only one easy relation |
| Contradiction detection recall | Correct contradiction groups / visible gold contradiction groups | No detectable conflict: N/A | Depends on independently specified conflict groups |
| Citation precision | Exact document/version/locator/quote matches / submitted citations | No citations: N/A + generation/coverage flag | Does not establish truth or entailment |
| Locator accuracy | Unique valid document/version/native locator / submitted citations | No citations: N/A | Quote mismatch can coexist with a valid locator |
| Hallucinated citation rate | Invalid document/version/locator/quote citations / submitted citations | No citations: N/A | Includes incorrect quotations, not just nonexistent documents |
| Fabricated citations | Absolute invalid citation count | 0 with no citations, interpreted with completeness | Zero observations do not prove zero population risk |
| Citation completeness | Factual predictions with at least one valid citation / factual predictions | No factual predictions: N/A | Unsupported factual predictions stay in denominator |
| Entailment accuracy | Human-annotated supported factual claims / cited factual claims | Any missing annotation: not_reviewed/N/A | Exact quotation is insufficient; truth is separate |
| Unsupported claim rate | Factual claims lacking valid support or annotated non-entailment / factual predictions | Unknown entailment: not_reviewed/N/A | No citation is unsupported; external verification is not inferred |
| Critical DD coverage | Distinct matched critical families anywhere / gold critical families | Missing output: 0 | Paired precision/top-3 prevent apparent gain from excessive questions |
| Critical DD precision | Distinct matched critical families / all predicted questions | Missing output: 0 when critical set exists | Penalizes excessive and duplicate questions |
| Top-3 critical DD coverage | Distinct critical families in first three / gold critical families (1–3) | Fewer than 3 are not filled; empty: 0 | State-specific critical sets are scenario judgments, not universal optimum |
| Top-3 precision | Distinct critical hits in first three / actual top-three output count | Empty: 0 | Must be read alongside coverage |
| Duplicate question rate | Repeated annotated families after first / all predicted questions | Empty: N/A; any unreviewed family: not_reviewed | Reviewer family labels are required for semantic duplicates |
| Actionability | Questions containing target, artifact, period and criterion / all questions | Empty failed output: 0; incomplete annotations: N/A | Four-element checklist, not investment usefulness |
| Verification criterion completeness | Questions with explicit test criterion / all questions | Missing annotations: N/A | Assessed separately from artifact request |
| Financial relevance | Questions with reviewer-confirmed financial driver / all questions | Missing annotations: N/A | Mapping is interpretive and provisional |
| Top-k priority hit rate | Distinct critical hits within k / `min(k, gold critical count)` | Empty output: 0 | Implemented k=3; does not reward repetition |
| NDCG@3 | `Σ(2^relevance−1)/log2(rank+1)` / ideal DCG@3 | No relevance: N/A; missing list: 0 | Repeated family gains are zero; scenario relevance is not observed economic utility |
| Hypothesis update consistency | Exact expected visible-state status matches / labelled hypotheses | Missing status: incorrect | Distinguishes document support from independently verified truth |
| Resolved question removal accuracy | Correctly excluded resolved families / gold resolved families | Failed/empty output: 0; none resolved: N/A | Paired open-question coverage prevents removing everything |
| Unnecessary ranking change rate | Changed no-change controls / all no-change controls | No controls: N/A | Rejection validity also checked; unchanged invalid approval is not success |
| Evidence double-counting rate | Unsupported extra group updates / repeated-group attempts | No repeat attempts: N/A | Requires recorded dependence groups and actual update audit |
| Transition exact match | Correct ordered before/after and reason/state change / valid tested events | Failed event: 0 | Scripted expected behavior, not learned policy accuracy |
| Negative-control stability | Correct rejection or no-change result / attempted negative controls | Failed control retained | Invalid source acceptance fails even when ranks happen to stay equal |
| Bayesian posterior error | Sum absolute error / specified posterior targets | Any target missing: error withheld + coverage rate | Independent numeric target; scenario probability is not calibrated investment success |
| EIG calculation error | Sum absolute error / specified EIG targets | Any target missing: error withheld + coverage rate | Same probability assumptions required; EIG measured in bits |
| Numeric coverage | Returned required numeric targets / all required targets | Omission: 0 | Prevents cherry-picking the easiest numeric cases |
| Deterministic test pass rate | Passed / passed+failed+errors+skipped | Skips cannot count as passes | Reports actual pytest execution, not model accuracy |
| Final approval without HITL | Absolute count of final decisions without recorded review | Must be 0 | Scripted synthetic reviewer is explicitly labelled, not a human investment decision |
| Match-review coverage | Reviewed semantic question matches / output questions | Empty: N/A | Signals missing annotation, separate from model correctness |

The API also exposes descriptive Wilson 95% intervals for count ratios. Questions/stages within a deal are correlated; these intervals are descriptive and are not population confidence claims. Public examples are not used for claimed train/test performance. No model was trained in this chunk.

## Acceptance targets and actual status

Targets: locator precision >=95%; critical Top-3 coverage >=80%; hallucinated citations=0; final approvals without HITL=0; deterministic arithmetic tests=100%; scripted transitions match. These targets are **not claimed as achieved actual LLM performance**. See the generated `evaluation/results/report.json` for actual fixture/deterministic measurements, `run_manifest.json` for run provenance, and pytest logs for executed tests.

## Run

From the integrated repository after installation:

```bash
python -m orion.cli generate-synthetic --output data/synthetic
python -m orion.cli ingest --case all --mode demo
python -m orion.cli audit-model-inputs --cases all
python -m orion.cli evaluate --arms B0 B1 B2 B3 B1-R --cases all --mode cached
python -m pytest tests/evaluation -q --strict-markers
```

Expanded dataset generation must precede `--cases all`; a requested missing case is reported as a failure/not_run and cannot silently disappear. Actual live adapters intentionally remain unavailable until source authorization, model/version, prompt, token/cost limits and blinded annotations are supplied in a later chunk.

## Additional reporting details

`review_correction_rate` divides substantive corrections by all reviewed drafts; zero drafts is N/A. `reproducibility` compares ordered rank/score rows **and** canonical input digests across actual repeated deterministic runs, excluding audit timestamps. Review correction is not measured from an identity-converted fixture.

The expanded case's document-claim extraction, entailment and citation-performance metrics are explicitly **not_run**: fixed binary hypotheses are core-engine inputs, not an executed extraction adapter. Native source element/checksum validation and source-only input auditing are executed separately. Independently authored stage support/truth/resolved labels gate the scenario replay; engine-derived labels are not reused as expected values. Failed or abstained generations receive zero task credit even if a partial payload contains a correct-looking question; any partial citation diagnostic is excluded from successful-run aggregation.

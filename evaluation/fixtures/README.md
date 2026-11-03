# Authored protocol fixture sources

The benchmark uses existing author-curated initial DealState records as output fixtures, explicitly projected to the `SystemOutput` evaluation schema. No gold is loaded while constructing these outputs.

Executed fixture JSONs are written to `evaluation/results/authored_fixtures/` and every case/stage/arm output is under `evaluation/results/outputs/` or `evaluation/results/expanded/outputs/`. Model inputs are separate source-only dumps and never include these curated output objects.

B0/B1 share these authored questions by design; B0's missing citations are a test of metric missingness, not a claim about LLM behavior. B2 retains initial ranking; B3 runs the real reviewed deterministic update. A live model adapter and B1-R regeneration are explicitly not_run.

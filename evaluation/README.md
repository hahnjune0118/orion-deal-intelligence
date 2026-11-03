# Offline Evaluation

Run the repository `orion evaluate` CLI. Implementation is `src/orion/evaluation`.

- `gold/`: immutable copied legacy author-proposed labels, evaluator-only.
- `prompts/`: versioned arm templates.
- `fixtures/`: authored protocol fixtures, never model results.
- `results/`: actual execution outputs, manifests, source-only input dumps and metrics.
- Expanded source/world/gold separation lives in `chunk3_synthetic_evaluation`.

See `../chunk3_synthetic_evaluation/reports/evaluation_protocol.md` for every metric's definition, denominator, missing-output rules and limitations.

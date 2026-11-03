# Contract mapping

The shared `orion.domain.models` contract stays at 1.0.0. The additive dataset wrappers are `orion.synthetic.models`.

| Blueprint entity | Existing implementation / extension |
| --- | --- |
| Deal | Core `Deal` |
| Document | Core `Document` plus `DatasetDocument` date/title/type/stage/synthetic metadata |
| Evidence | Core `Evidence`, native `SourceSpan`; `EvidenceLabel` adds independence and contradiction groups |
| Hypothesis | `Hypothesis` wraps core `Claim(claim_kind='binary_hypothesis')` |
| Claim | Core `Claim`; exact company assertions have separate documentary extraction labels |
| ClaimEvidence | Core `Evidence.claim_id` plus `stance`; label relationships reference stable evidence IDs |
| DDQuestion | Core `DDQuestion`; `QuestionLabel` adds artifact/criterion/business impact/family and expected behavior |
| BeliefSnapshot | `orion.quant.bayes.BeliefSnapshot` records explicit probabilistic provenance and conditional dependencies; dataset schema aliases this same class |
| ReviewEvent | Core `AnalystDecision`, with existing `AuditEvent` when using persistence services |
| AnalysisRun | Core `AnalysisRun`; evaluation run manifest records authored fixture mode and zero model calls |

No schema claims that a citation proves its underlying commercial assertion. Exact-source validity, documentary support, independent truth and analyst approval are separate states. Engine review simulations record a reviewer action but do not constitute real human approval or final investment approval.

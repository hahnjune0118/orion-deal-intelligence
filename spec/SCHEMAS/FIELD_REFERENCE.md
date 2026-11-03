# Schema field reference

Generated from models.schema.json. Contract 1.0.0. 모든 열거 필드는 required이며 nullable은 명시한 필드만 허용한다. Schema 밖의 의미·참조·승인 규칙은 04_DATA_CONTRACTS.md를 따른다.

## PdfLocator

| Field | Type | Constraints |
|---|---|---|
| kind | const pdf | {} |
| page | integer | {"minimum": 1} |
| block_index | integer | {"minimum": 0} |

## PptxLocator

| Field | Type | Constraints |
|---|---|---|
| kind | const pptx | {} |
| slide | integer | {"minimum": 1} |
| shape_id | integer | {"minimum": 0} |
| paragraph_index | integer | {"minimum": 0} |
| table_cell | object / null | {} |

## DocxParagraphLocator

| Field | Type | Constraints |
|---|---|---|
| kind | const docx_paragraph | {} |
| part_uri | const word/document.xml | {} |
| block_index | integer | {"minimum": 0} |
| paragraph_index | integer | {"minimum": 0} |
| heading_path | array[string] | {"minItems": 0} |

## DocxTableLocator

| Field | Type | Constraints |
|---|---|---|
| kind | const docx_table_cell | {} |
| part_uri | const word/document.xml | {} |
| table_index | integer | {"minimum": 0} |
| row | integer | {"minimum": 0} |
| column | integer | {"minimum": 0} |
| paragraph_index | integer | {"minimum": 0} |
| heading_path | array[string] | {"minItems": 0} |

## Locator

oneOf: PdfLocator, PptxLocator, DocxParagraphLocator, DocxTableLocator

## Deal

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| name | string | {"minLength": 1} |
| business_model | string | {"minLength": 1} |
| currency | const USD | {} |
| synthetic | const True | {} |
| as_of | string | {"format": "date"} |
| thesis_ids | array[string] | {"minItems": 0, "uniqueItems": true} |

## Document

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| filename | string | {"minLength": 1} |
| format | enum: pdf, docx, pptx | {} |
| document_version | integer | {"minimum": 1} |
| asset_status | enum: fixture_text_only, file_verified | {} |
| file_sha256 | string / null | {} |
| parse_status | enum: pending, parsed, needs_ocr, needs_manual_review, failed | {} |
| parser_version | string | {"minLength": 1} |
| source_origin | enum: company, counterparty, independent, analyst | {} |
| origin_key | string | {"minLength": 1} |
| created_at | string | {"format": "date-time", "pattern": "Z$"} |

## SourceSpan

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| document_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| document_version | integer | {"minimum": 1} |
| locator | Locator | {} |
| normalized_text | string | {"minLength": 1} |
| text_sha256 | string | {"pattern": "^[a-f0-9]{64}$"} |
| quote | string | {"minLength": 1} |
| start | integer | {"minimum": 0} |
| end | integer | {"minimum": 1} |
| locator_status | enum: validated, unverified, invalid | {} |
| extraction_method | enum: parsed, ocr_reviewed, manual_checked, fixture | {} |

## Thesis

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| title | string | {"minLength": 1} |
| counter_thesis | string | {"minLength": 1} |
| claim_ids | array[string] | {"minItems": 1, "uniqueItems": true} |
| review_status | enum: draft, approved, rejected | {} |

## Claim

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| thesis_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| statement | string | {"minLength": 1} |
| subject_key | string | {"minLength": 1} |
| period_start | string | {"format": "date"} |
| period_end | string | {"format": "date"} |
| claim_kind | enum: company_reported, analyst_assumption, binary_hypothesis | {} |
| source_span_ids | array[string] | {"minItems": 0, "uniqueItems": true} |
| required_criterion_keys | array[string] | {"minItems": 1, "uniqueItems": true} |
| support_status | enum: missing, partial, supported, contradicted | {} |
| truth_status | enum: not_checked, document_only, independently_verified, disputed | {} |
| review_status | enum: draft, approved, rejected | {} |

## Evidence

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| claim_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| source_span_ids | array[string] | {"minItems": 1, "uniqueItems": true} |
| stance | enum: supports, refutes, context | {} |
| criterion_keys | array[string] | {"minItems": 0, "uniqueItems": true} |
| provenance | enum: company_reported, counterparty_reported, independent_source, analyst_note | {} |
| source_reliability | integer / null | {} |
| reliability_rationale | string | {"minLength": 1} |
| verification_level | enum: document_only, independent_check | {} |
| independent_check_reference | string / null | {} |
| origin_key | string | {"minLength": 1} |
| review_status | enum: draft, approved, rejected | {} |
| lifecycle | enum: active, superseded | {} |
| created_at | string | {"format": "date-time", "pattern": "Z$"} |

## EvidenceRelation

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| from_evidence_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| to_evidence_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| relation_type | enum: duplicates, contradicts, supersedes | {} |
| scope_criterion_keys | array[string] | {"minItems": 1, "uniqueItems": true} |
| review_status | enum: draft, approved, rejected | {} |
| rationale | string | {"minLength": 1} |

## Requirement

| Field | Type | Constraints |
|---|---|---|
| key | string | {"minLength": 1} |
| label | string | {"minLength": 1} |
| min_reliability | integer | {"minimum": 0, "maximum": 5} |
| require_independent | boolean | {} |

## MaterialityInput

| Field | Type | Constraints |
|---|---|---|
| score | integer / null | {} |
| basis | enum: objective_ratio, analyst_rubric, unknown | {} |
| exposure_minor | integer / null | {} |
| denominator_minor | integer / null | {} |
| rationale | string | {"minLength": 1} |
| source_span_ids | array[string] | {"minItems": 0, "uniqueItems": true} |

## ObtainabilityInput

| Field | Type | Constraints |
|---|---|---|
| score | integer / null | {} |
| basis | enum: derived_cost_time, analyst_estimate, unknown | {} |
| days | number / null | {} |
| external_cost_minor | integer / null | {} |
| rationale | string | {"minLength": 1} |

## DDQuestion

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| claim_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| canonical_key | string | {"minLength": 1} |
| issue | string | {"minLength": 1} |
| request_text | string | {"minLength": 1} |
| financial_driver | enum: revenue_quality, ebitda, nwc, net_debt, capex, customer_concentration, unit_economics | {} |
| requirements | array[Requirement] | {"minItems": 1} |
| materiality | MaterialityInput | {} |
| obtainability | ObtainabilityInput | {} |
| review_status | enum: draft, approved, rejected | {} |
| workflow_status | enum: open, awaiting_review, resolved, rejected, duplicate | {} |
| duplicate_of | string / null | {} |
| owner_label | string | {"minLength": 1} |

## ScoreRow

| Field | Type | Constraints |
|---|---|---|
| question_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| rank | integer | {"minimum": 1} |
| gap | number | {"minimum": 0, "maximum": 5} |
| materiality | integer | {"minimum": 0, "maximum": 5} |
| obtainability | integer | {"minimum": 0, "maximum": 5} |
| score | number | {"minimum": 0, "maximum": 100} |
| provisional | boolean | {} |
| reason_codes | array[string] | {"minItems": 1, "uniqueItems": true} |

## RankingSnapshot

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| state_revision | integer | {"minimum": 1} |
| scoring_version | const 1.0.0 | {} |
| input_digest | string | {"pattern": "^[a-f0-9]{64}$"} |
| created_at | string | {"format": "date-time", "pattern": "Z$"} |
| trigger_event_id | string / null | {} |
| rows | array[ScoreRow] | {"minItems": 0} |
| top3 | array[string] | {"minItems": 0, "uniqueItems": true, "maxItems": 3} |

## AnalystDecision

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| actor_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| actor_role | enum: analyst, reviewer, system | {} |
| target_type | enum: evidence_update, claim, question, evidence, relation, snapshot_export, seed | {} |
| target_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| target_version | integer | {"minimum": 1} |
| selection_digest | string / null | {} |
| action | enum: approve, reject, edit, reopen | {} |
| reason | string | {"minLength": 1} |
| base_revision | integer | {"minimum": 0} |
| decided_at | string | {"format": "date-time", "pattern": "Z$"} |

## AuditEvent

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| sequence | integer | {"minimum": 1} |
| event_type | enum: seed_created, update_staged, update_approved, update_rejected, ranking_changed, ranking_unchanged, export_approved, exported, edit_applied | {} |
| actor_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| decision_id | string / null | {} |
| before_revision | integer | {"minimum": 0} |
| after_revision | integer | {"minimum": 0} |
| idempotency_key | string | {"minLength": 1} |
| before_snapshot_id | string / null | {} |
| after_snapshot_id | string / null | {} |
| reason | string | {"minLength": 1} |
| created_at | string | {"format": "date-time", "pattern": "Z$"} |
| previous_hash | string / null | {} |
| event_hash | string | {"pattern": "^[a-f0-9]{64}$"} |

## AnalysisRun

| Field | Type | Constraints |
|---|---|---|
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| entity_version | integer | {"minimum": 1} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| mode | enum: cached, live | {} |
| status | enum: pending, running, completed, failed, budget_blocked, cancelled | {} |
| model_id | string / null | {} |
| prompt_version | string | {"minLength": 1} |
| input_digest | string | {"pattern": "^[a-f0-9]{64}$"} |
| output_digest | string / null | {} |
| token_input | integer / null | {} |
| token_output | integer / null | {} |
| reserved_cost_usd | number | {"minimum": 0} |
| actual_cost_usd | number / null | {} |
| pricing_version | string / null | {} |
| started_at | string | {"format": "date-time", "pattern": "Z$"} |
| finished_at | string / null | {} |
| error_code | string / null | {} |

## DealState

| Field | Type | Constraints |
|---|---|---|
| kind | const deal_state | {} |
| contract_version | const 1.0.0 | {} |
| state_revision | integer | {"minimum": 1} |
| mode | enum: demo, local_live | {} |
| deal | Deal | {} |
| documents | array[Document] | {"minItems": 0} |
| source_spans | array[SourceSpan] | {"minItems": 0} |
| theses | array[Thesis] | {"minItems": 0} |
| claims | array[Claim] | {"minItems": 0} |
| evidence | array[Evidence] | {"minItems": 0} |
| evidence_relations | array[EvidenceRelation] | {"minItems": 0} |
| dd_questions | array[DDQuestion] | {"minItems": 0} |
| ranking_snapshots | array[RankingSnapshot] | {"minItems": 0} |
| analyst_decisions | array[AnalystDecision] | {"minItems": 0} |
| audit_events | array[AuditEvent] | {"minItems": 0} |
| analysis_runs | array[AnalysisRun] | {"minItems": 0} |
| head_snapshot_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |

## StagedEvidenceUpdate

| Field | Type | Constraints |
|---|---|---|
| kind | const staged_evidence_update | {} |
| contract_version | const 1.0.0 | {} |
| id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| base_revision | integer | {"minimum": 1} |
| idempotency_key | string | {"minLength": 1} |
| validation_status | enum: validated, invalid, needs_review | {} |
| created_at | string | {"format": "date-time", "pattern": "Z$"} |
| documents | array[Document] | {"minItems": 0} |
| source_spans | array[SourceSpan] | {"minItems": 0} |
| evidence | array[Evidence] | {"minItems": 1} |
| evidence_relations | array[EvidenceRelation] | {"minItems": 0} |
| analyst_note | string | {"minLength": 1} |

## TransitionRow

| Field | Type | Constraints |
|---|---|---|
| question_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| before_rank | integer / null | {} |
| after_rank | integer / null | {} |
| before_score | number / null | {} |
| after_score | number / null | {} |
| before_status | string | {"minLength": 1} |
| after_status | string | {"minLength": 1} |
| reason | string | {"minLength": 1} |

## ExpectedTransition

| Field | Type | Constraints |
|---|---|---|
| kind | const expected_top3_transition | {} |
| contract_version | const 1.0.0 | {} |
| deal_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| event_id | string | {"pattern": "^[a-z][a-z0-9_-]{2,63}$"} |
| approval | AnalystDecision | {} |
| before_revision | integer | {"minimum": 1} |
| after_revision | integer | {"minimum": 1} |
| before_top3 | array[string] | {"minItems": 0, "uniqueItems": true, "maxItems": 3} |
| after_top3 | array[string] | {"minItems": 0, "uniqueItems": true, "maxItems": 3} |
| question_changes | array[TransitionRow] | {"minItems": 0} |
| claim_after | array[object] | {"minItems": 0} |
| expected_live_api_calls | const 0 | {} |


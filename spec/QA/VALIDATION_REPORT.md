# Specification validation report

Executed UTC: 2026-11-03T05:29:23.140963+00:00 · Python 3.12.14

**65 passed / 0 failed.** Contract arithmetic and file checks only. 제품 구현·성능 평가가 아니다.

| Check | Result | Detail |
|---|---|---|
| JSON Schema meta-validation | pass | null |
| schema rejects unknown root field | pass | "rejected as required" |
| DOCX fabricated page field rejected | pass | "rejected as required" |
| PPTX slide and table locator schema | pass | "Locator validated" |
| independent check requires reference | pass | "rejected as required" |
| export approval requires selection digest | pass | "rejected as required" |
| export approval digest accepted | pass | "AnalystDecision validated" |
| completed live run cannot omit usage | pass | "rejected as required" |
| support and truth enums stay separate | pass | "rejected as required" |
| score string rejected without coercion | pass | "rejected as required" |
| ns schema state | pass | "deal_state" |
| ns schema update | pass | "staged_evidence_update" |
| ns schema transition | pass | "expected_top3_transition" |
| ns reference and source integrity | pass | "16 unique entity IDs; sources/references/criterion policies/hash chain checked" |
| ns stored initial ranking | pass | null |
| ns input digest | pass | null |
| ns worked transition | pass | {"before": [["q_ns_contract_a", 100.0], ["q_ns_contract_b", 97.0], ["q_ns_accept_collect", 89.0]], "after": [["q_ns_contract_b", 97.0], ["q_ns_accept_collect", 89.0], ["q_ns_concentration", 86.0]]} |
| ns duplicate credit stability | pass | null |
| ns unrelated evidence stability | pass | null |
| ns unapproved update stability | pass | null |
| ns invalid quote rejected | pass | "rejected as required" |
| ns stale update rejected | pass | "rejected as required" |
| ns analyst approval rejected | pass | "rejected as required" |
| ns orphan source rejected | pass | "rejected as required" |
| ns cross deal rejected | pass | "rejected as required" |
| ns collection-order invariance | pass | null |
| cd schema state | pass | "deal_state" |
| cd schema update | pass | "staged_evidence_update" |
| cd schema transition | pass | "expected_top3_transition" |
| cd reference and source integrity | pass | "14 unique entity IDs; sources/references/criterion policies/hash chain checked" |
| cd stored initial ranking | pass | null |
| cd input digest | pass | null |
| cd worked transition | pass | {"before": [["q_cd_cutoff", 100.0], ["q_cd_warranty", 94.0], ["q_cd_inventory", 89.0]], "after": [["q_cd_warranty", 94.0], ["q_cd_inventory", 89.0], ["q_cd_receivable", 86.0]]} |
| cd duplicate credit stability | pass | null |
| cd unrelated evidence stability | pass | null |
| cd unapproved update stability | pass | null |
| cd invalid quote rejected | pass | "rejected as required" |
| cd stale update rejected | pass | "rejected as required" |
| cd analyst approval rejected | pass | "rejected as required" |
| cd orphan source rejected | pass | "rejected as required" |
| cd cross deal rejected | pass | "rejected as required" |
| cd collection-order invariance | pass | null |
| lm schema state | pass | "deal_state" |
| lm schema update | pass | "staged_evidence_update" |
| lm schema transition | pass | "expected_top3_transition" |
| lm reference and source integrity | pass | "15 unique entity IDs; sources/references/criterion policies/hash chain checked" |
| lm stored initial ranking | pass | null |
| lm input digest | pass | null |
| lm worked transition | pass | {"before": [["q_lm_labor", 92.0], ["q_lm_margin", 89.0], ["q_lm_cash", 84.0]], "after": [["q_lm_renewal", 97.0], ["q_lm_labor", 92.0], ["q_lm_margin", 89.0]]} |
| lm duplicate credit stability | pass | null |
| lm unrelated evidence stability | pass | null |
| lm unapproved update stability | pass | null |
| lm invalid quote rejected | pass | "rejected as required" |
| lm stale update rejected | pass | "rejected as required" |
| lm analyst approval rejected | pass | "rejected as required" |
| lm orphan source rejected | pass | "rejected as required" |
| lm cross deal rejected | pass | "rejected as required" |
| lm collection-order invariance | pass | null |
| rubric numerical boundaries | pass | "11 materiality boundaries, 7 day boundaries and combined cost/time checked" |
| null zero and tie rules | pass | "null=>75 provisional; zero=>45 nonprovisional; exact tie uses canonical key" |
| synthetic finance consistency | pass | "3 cases: EBITDA/customer totals/NWC; NS revenue split; Lumen hours" |
| hypothetical Bayes and EIG | pass | {"hypothetical_prior": 0.3, "P_positive": 0.38, "posterior_positive": 0.631578947368421, "posterior_negative": 0.09677419354838707, "EIG_bits": 0.23611392733893743, "not_empirical": true} |
| required deliverables | pass | {"required_files_present": 23} |
| internal Markdown links | pass | {"local_links_checked": 82} |
| publisher dependency metadata | pass | null |

## Not executed

- Windows dependency installation and security audit
- Native PDF/DOCX/PPTX parser tests
- Pydantic implementation parity
- Production transactions, authorization and export tests
- Dash browser accessibility and session isolation
- Hosting deployment and restart
- Live API budget enforcement and real model evaluation
- Independent gold annotation and empirical citation/Top-3 metrics

95% citation accuracy, zero fabricated product citations and 80% Top-3 coverage remain unmeasured targets. Authored fixture correctness is not LLM accuracy.

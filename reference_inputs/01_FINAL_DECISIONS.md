# Orion Deal Intelligence 2.0 — Current Decisions & Source Precedence
Version: 2026-11-03. This is a source-safe, implementation-oriented decision record, not a completed product or measured evaluation.

## Objective
Build a usable, professional, publicly demonstrable Evidence-Grounded Adaptive Due Diligence Workbench for PE / M&A IB / Deal Advisory preliminary screening, and an academic evaluation of adaptive question prioritization. Key demonstration: **new legitimate evidence changes the Top-3 DD questions in a justified, traceable, reproducible way**. This is not a full audit/FDD, autonomous underwriting, or transaction execution system.

## Fixed implementation decisions (override conflicting historic references)
- Frontend: **Plotly Dash + Dash AG Grid**; original, Hebbia Matrix-inspired document-centric UX, not a Hebbia clone. Use a dense three-pane workspace: left navigation/deal/docs, central evidence matrix/questions, right source inspector and human review. Optional supporting pages for Deal Overview, Adaptive Changes, Evaluation.
- Python core completely decoupled from UI. Document parsing PDF/DOCX/PPTX, explicit provenance, structured LLM extraction validated with Pydantic, analyst review, deterministic ranking, before/after audit snapshots. SQLite for local prototype with clearly specified persistence and public hosting limitations. Avoid unnecessary backend services unless justified.
- Primary **synthetic B2B AI deal 'Northstar Analytics'**, plus two independent fictional packs with materially different business models. Do not use employer documents or reverse-engineer confidential transactions as examples. Synthetic financials/customer records must be internally coherent.
- Grounding: LLM supplies proposed claim/evidence/question *drafts* with source locators. Program checks that locators and excerpts actually exist. Source citation supports the statement 'the document reports X', not necessarily the real-world truth of X. DOCX has no reliable page numbering by default; PPTX has slide indices; PDF has pages.
- Analyst approval or edit for final decisions and exports. User-facing item statuses: Draft, Reviewed/Approved, Rejected, etc. Evidence support statuses Supported/Partial/Missing/Contradicted must be separately defined.
- Priority ranking: explainable deterministic rubric emphasizing Evidence Gap, Financial Materiality, Obtainability (and cost/time when justified); do not fabricate likelihoods. Define weights, tie breaks, missing data policy, and evidence resolution/deduplication rules. Optional Bayesian updating/EIG for explicitly defined binary scenarios with analyst-supplied hypothetical prior/likelihood only; no faux empirical probability, no calling the score EVSI without decision utility.
- Core files: actual functioning application and tests; DD Request List CSV/XLSX export, screening memo Markdown minimum; source-backed updates and audit trails.
- Two modes: publicly deployable **Demo** with cached synthetic LLM outputs and *working* deterministic interactions, **Local Live** uses personally supplied OpenAI API key, limits input/tokens/cost, never exposes key to site visitors. Public demo must not accept unrelated arbitrary uploaded documents or allow account/visitor cross-contamination absent robust security.
- Existing `orion_dcf.py`, `fdd_model.py`, and valuation/DCF integration explicitly excluded from MVP; conceptual financial driver mapping only.
- Deliverable: source repository, tests/evaluation report with B0-B3 baseline/ablation, deployed read-only or session-isolated interactive synthetic demo, demo video, short portfolio write-up, ready before mid-December 2026. Solo developer; approx 2 hours on weekdays. Favor vertical-slice reliability and scope reduction.
- Academic targets (not measured results): location citation accuracy >=95%, fabricated citations 0, critical Top-3 coverage >=80%, reproducible deterministic transitions. Evaluation criteria, denominator, confidence and possible failures must be specified.

## Source precedence
1. This final-decision record (latest binding changes).
2. `source_documents/(연한준)프로젝트_기획안.docx` (2026-10-27 academic proposal; core product/methodology; its Streamlit recommendation is superseded).
3. `source_documents/3. (연한준) 금융인공지능실무 과제 기획안 피드백 보완 (2차).docx` (legal/UI storyboard coursework; validate current law independently before asserting legal conclusions).
4. `source_documents/2. (연한준)금융인공지능실무 과제 기획안 피드백 보완.docx` (Hebbia benchmark philosophy; the earlier 'one listed company and DCF integration' product scope is superseded).

Do not assume an original confidential 2026-10-23 development blueprint has been supplied. If useful technical concepts are absent in the sanitized record, independently design them rather than requesting internal employer files.

## Proposed product screens
1. Deal overview/document library.
2. Primary matrix: thesis -> claim -> source evidence -> verification state -> question.
3. Question grid: issue, requested evidence, financial impact category, evidence gap, rank/reason, owner/status.
4. Contextual source pane for page/slide/section/excerpt and approval.
5. Evidence update workflow showing Top-3 before/after, new evidence events, score deltas, provenance, and accepted edits.
6. Evaluation (developer/demo mode) with baseline comparison, metrics and scenarios.

## Must demonstrate
A. Initial synthetic pack: user can inspect source-backed hypotheses and see 3 high priority DD questions.
B. User introduces a staged evidence answer showing paid contract for one customer (but not independent signed contracts, acceptance and collection for all target customers).
C. Evidence status updates only after appropriate validation/review; the fulfilled request loses priority, residual verification questions become more important, and user sees *exactly why* with before/after snapshots.
D. An unrelated/duplicate/unsupported evidence upload does not spuriously change rankings.
E. No calls to a live API in public demo.

## Constraints and truthfulness
Clearly mark proposed architecture vs verified package/version capability, untested targets vs results, and mocked/cached generation vs real-time extraction. Do not claim tests passed without running them. Distinguish educational demonstration from live investment advice. Do not recreate employer-private scenarios.

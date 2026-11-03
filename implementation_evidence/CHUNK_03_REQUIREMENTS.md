Orion Deal Intelligence 2.0 — Chunk 3: Synthetic Data & Evaluation
0. Role & Objective
You are a Senior AI/ML Engineer, Financial Due Diligence Specialist, and Evaluation Researcher with expertise in Private Equity investment screening, evidence-grounded LLM systems, Bayesian decision theory, and synthetic financial dataset construction.
We are developing Orion Deal Intelligence 2.0 — Evidence-Grounded Adaptive Due Diligence Agent, a university financial AI project intended to become a functional, independently demonstrable web application.
Your assignment is to execute Chunk 3 — Synthetic Data & Evaluation.
The objective is to create a reproducible, financially realistic synthetic dataset and evaluation framework that can be directly integrated into the subsequent AI Agent development stages.
This is an implementation task, not merely a planning exercise. Produce actual usable files, data, Python code, tests, and documentation.
Read the attached Blueprint first. Preserve its established architecture, terminology, assumptions, and MVP scope. Where this prompt is more specific, treat it as the implementation-level specification.

0.1 Existing Project Files & Integration Requirements
I have attached the following existing project artifacts:
1.	Orion Adaptive DD Agent Blueprint
2.	Chunk 1 implementation ZIP
3.	Chunk 2 implementation ZIP
4.	Any available implementation reports or technical documentation
These files represent the existing project baseline. Your task is to extend the existing implementation, not rebuild the project from scratch.
Before implementing Chunk 3:
1.	Extract and inspect both ZIP archives.
2.	Identify the current repository structure, Python modules, schemas, dependencies, APIs, and tests.
3.	Determine which Chunk 1 and Chunk 2 components are already implemented.
4.	Compare the existing implementation against the Blueprint and the Chunk 3 requirements.
5.	Identify reusable components, missing dependencies, and potential integration conflicts.
6.	Preserve existing working functionality and established naming conventions wherever practical.
Implementation Rules
•	Extend existing schemas instead of creating incompatible duplicates.
•	Reuse existing financial calculations, data models, and validation utilities where applicable.
•	Preserve backward compatibility unless a breaking change is technically necessary.
•	Do not overwrite existing working code without justification.
•	Do not fabricate successful test results.
•	Clearly document every modified, added, or deprecated file.
•	If the attached ZIP files contain conflicting versions, identify the latest valid implementation using available version information and explain the selection.
•	Treat the Blueprint as the architectural reference, but treat the latest working implementation as the technical baseline.
Required Output
Deliver a fully integrated updated project ZIP, not merely a standalone Chunk 3 folder.
The updated ZIP must contain the existing working Chunk 1 and Chunk 2 components together with the new Chunk 3 implementation.
Also provide:
1.	Updated repository tree
2.	Change log
3.	Integration test results
4.	New dependencies, if any
5.	Instructions for running the complete project
6.	Known limitations and remaining tasks for Chunk 4
If integration cannot be completed, explain the precise technical blockers and provide the most complete runnable implementation possible.

________________________________________
1. Project Context
1.1 Product Definition
Orion Deal Intelligence is an AI-powered preliminary investment screening and adaptive due diligence application for:
•	Private Equity Investment Analysts
•	Investment Banking M&A Analysts
•	Big4 Deal Advisory / FDD / Commercial DD professionals
Its intended workflow is:
1.	Document ingestion
2.	Investment Thesis & Claim extraction
3.	Evidence identification and classification
4.	Counter-thesis and Evidence Gap assessment
5.	Due Diligence Question generation
6.	Question prioritization using Information Gain and Financial Materiality
7.	Adaptive updating following new management answers or supporting documentation
8.	Human-in-the-Loop review
9.	DD Request List and Preliminary Screening Memo export
The central research question is:
Can an AI system identify the most decision-relevant due diligence questions and adapt its priorities when new evidence changes the uncertainty surrounding an investment hypothesis?
The intended differentiator is not generating more DD questions, but determining which additional evidence is most useful and explaining why the next question changes.
1.2 Existing Design Principles
The attached Blueprint specifies the following:
•	Evidence-Grounded Reasoning and source traceability
•	Structured Claim–Evidence–Gap–Question relationships
•	Falsifiable investment hypotheses
•	Bayesian Updating using explicitly specified probabilistic assumptions
•	Expected Information Gain (EIG)
•	Financial Materiality
•	Analyst Review / Human-in-the-Loop
•	Reproducible evaluation across baseline architectures
LLMs must not invent actual investment success probabilities.
Bayesian probabilities used in this project are synthetic scenario assumptions, not empirically calibrated predictions.
LLM-generated interpretations must remain distinguishable from deterministic financial calculations.
The application supports preliminary investment screening, not completed FDD, legal opinions, investment advice, or automatic transaction execution.
________________________________________
2. Scope of Chunk 3
Build four interconnected components:
A. Synthetic Deal Data
Realistic fictional investment opportunities consisting of multiple interrelated financial and commercial documents.
B. Gold Standard
Human-reviewable ground truth connecting investment claims, source evidence, risks, and required DD questions.
C. Adaptive Decision Scenarios
Sequential evidence-arrival cases with explicit Bayesian assumptions, expected posterior updates, and question-priority changes.
D. Evaluation Harness
A reproducible Python framework evaluating extraction, citation accuracy, question quality, ranking quality, and adaptive updating.
All four components should share stable identifiers and machine-readable schemas.
Do not build the complete LLM agent or production web UI in this chunk.
However, design the outputs so subsequent development can connect them without substantial schema redesign.
________________________________________
3. Data Governance — Mandatory
All fictional company data must be generated independently.
Do not reproduce, paraphrase, or structurally reverse-engineer any confidential investment memorandum, internal business plan, portfolio-company document, management Q&A, or proprietary due diligence work product.
Do not use confidential materials from any employer, client, or investment target.
Do not attempt to infer confidential business facts from the user's professional background.
The synthetic deals must have:
•	Fictional company identities
•	Independently created operating histories
•	Original financial assumptions
•	Plausible but fabricated contracts and customers
•	Explicit synthetic-data labels
•	No real personal information
•	No unauthorized third-party information
Use industry-standard business logic rather than any company's confidential business information.
The data must be suitable for publication in an academic GitHub repository.
For the Orion case, distinguish genuine public-source evidence from synthetic additions. Do not mislabel synthetic documents as genuine disclosures.
________________________________________
4. Synthetic Deal Pack Construction
The Blueprint defines three target deal packs:
Deal	Description	Data Treatment
A	Orion — public-company screening	Publicly available, verifiable disclosures
B	Fictional B2B AI / Enterprise Software company	Fully synthetic
C	Fictional consumer goods / manufacturing company	Fully synthetic
4.1 Implementation Priority
Complete Deal B first as the primary end-to-end evaluation case.
Deal B should be sufficiently complete to demonstrate extraction, contradictory evidence, DD question prioritization, and adaptive updating.
Develop Deal C as a second independent synthetic case to test generalizability.
For Deal A, create the data ingestion manifest, public-source requirements, and evaluation specification. Only populate it with actual Orion public facts when relevant source documents are available and verifiable. Otherwise mark evidence as pending instead of inventing it.
The priority is depth, internal consistency, and meaningful evaluation rather than creating a large quantity of superficial documents.
4.2 Deal B — Fictional B2B AI Company
Use the fictional company name Northstar Analytics, unless there is a compelling reason to select another clearly fictional identity.
Create a realistic investment opportunity in enterprise AI software.
Suggested investment hypotheses:
•	H1: The company can secure at least two independent paying enterprise customers within the next 12 months, with contractual acceptance criteria satisfied.
•	H2: Customer-level contribution margins remain positive after implementation, cloud inference, customer support, and recurring delivery costs.
•	H3: Reported commercial traction and management forecasts are supported by sufficiently reliable underlying evidence.
These are starting hypotheses. Refine them into precise, falsifiable statements with measurable outcomes, time horizons, and thresholds.
Create approximately 6–8 coherent business documents, including:
1.	Confidential Information Memorandum (fictional CIM)
2.	Historical Financial Performance
3.	Business Plan / Revenue Forecast
4.	Customer Pipeline / CRM Summary
5.	Commercial Contracts and PoC Summary
6.	Unit Economics / Delivery Cost Schedule
7.	Initial Management Q&A
8.	Subsequent Management Q&A / Evidence Update
Include several types of analytical challenges:
•	PoC confused with a signed commercial contract
•	Contractual value confused with recognized revenue
•	Billing confused with cash collection
•	Pipeline opportunities represented too aggressively as committed ARR
•	Gross margin excluding material implementation or inference costs
•	Contradictory customer counts across documents
•	Revenue forecasts unsupported by deployment capacity
•	Different document versions containing inconsistent assumptions
•	Genuine strengths alongside negative evidence
•	Missing information that cannot be resolved from the supplied documents
Ensure inconsistencies are deliberate and traceable, not accidental.
The synthetic company's financial statements and operating metrics must reconcile where reconciliation is expected. Any mismatch intended to be detected by the agent must be explicitly recorded in the hidden ground truth.
4.3 Deal C — Fictional Manufacturing / Consumer Company
Create a second original fictional company from an industry with fundamentally different economic drivers.
Include approximately 4–6 documents covering:
•	Historical financial statements
•	Sales by product or geography
•	Inventory and working capital
•	Manufacturing capacity / CAPEX
•	Nonrecurring income or expenses
•	Management forecasts
•	Follow-up operational evidence
Relevant financial DD challenges should include:
•	Revenue growth versus inventory accumulation
•	EBITDA normalization
•	Customer or geographic concentration
•	Maintenance CAPEX versus expansion CAPEX
•	Working capital requirements
•	Cash conversion versus reported profitability
Do not mechanically reproduce the Deal B questions with different names.
The purpose is to assess whether the system generalizes across deal types.
4.4 Document Formats
Use realistic document structures containing tables, paragraphs, management claims, and supporting schedules.
Generate machine-readable source data and, where practical, corresponding PDF/DOCX/XLSX documents.
Each document must have:
•	Stable Document ID
•	Deal ID
•	Document title
•	Date / reporting period
•	Version
•	Document type
•	Synthetic flag
•	Page, paragraph, table, or cell locator
•	Source checksum
Use deterministic generation wherever feasible.
The original source documents must remain unchanged across evaluation runs.
________________________________________
5. Ground Truth / Gold Standard
Build a comprehensive, machine-readable ground truth dataset.
At minimum, Deal B should contain:
•	3 falsifiable investment hypotheses
•	15 or more distinct evidence records
•	10 or more meaningful DD questions
•	4 sequential evidence-update events
•	Explicit expected ranking changes
•	Both supporting and contradictory evidence
These are minimum coverage targets, not arbitrary upper limits.
5.1 Core Schema
Maintain compatibility with the Blueprint's principal entities:
•	Deal
•	Document
•	Evidence
•	Hypothesis
•	Claim
•	ClaimEvidence
•	DDQuestion
•	BeliefSnapshot
•	ReviewEvent
•	AnalysisRun
For each claim, record:
•	claim_id
•	hypothesis_id
•	statement
•	claim_type
•	source locator
•	evidence relationships
•	ground_truth_status
•	financial_driver
•	materiality
•	rationale
For each evidence item, record:
•	evidence_id
•	document_id
•	source locator
•	exact source excerpt
•	evidence type
•	provenance
•	evidence relationship
•	verification status
•	contradiction group, if applicable
•	evidence independence group
For each DD question, record:
•	question_id
•	hypothesis_id
•	question_text
•	unresolved_assumption
•	requested_artifact
•	verification_criterion
•	business_impact
•	linked_evidence_ids
•	financial_driver
•	analyst_defined_materiality
•	expected_priority
•	information_gain, where applicable
•	expected_update_behavior
Do not interpret a statement appearing in a fictional CIM as independently verified truth.
Distinguish:
•	Company-reported claims
•	Directly documented evidence
•	Independent verification, where simulated
•	Analyst assumptions
•	Missing evidence
•	Contradictory evidence
A supporting source citation is not equivalent to independent factual verification.
5.2 Ground Truth Integrity
Avoid using an LLM-generated answer as its own unquestioned ground truth.
Create objective labels from a separately controlled synthetic world model and explicitly designed documentary evidence.
Distinguish:
1.	Underlying synthetic world facts
2.	Information visible to the agent at each stage
3.	Labels determined by those facts and visible information
4.	Interpretive judgments requiring Analyst review
Preserve the distinction between world truth and document-visible truth.
The evaluation agent must not be able to access hidden answer keys, future management responses, privileged labels, or scenario-generation metadata.
Construct an answer-key audit that flags gold labels unsupported by the permitted documents.
Where multiple DD questions are equally valid, allow alternative acceptable answers instead of assuming one exact wording is uniquely correct.
________________________________________
6. Adaptive DD Scenarios
This is the most important research component.
Create evidence-arrival simulations demonstrating how an investment analyst's priorities should change as new information becomes available.
6.1 Scenario Sequence
For Deal B, implement at least four sequential evidence events.
An illustrative sequence:
T0 — Initial CIM
Management claims strong enterprise customer traction but presents insufficient proof of signed and paid contracts.
The leading DD priority may be commercial validation.
T1 — First Contractual Evidence
One signed customer contract is received.
The system should distinguish a signed contract from acceptance, invoicing, and collection.
T2 — Commercial Execution Evidence
Deployment, acceptance, billing, or collection records are added.
The highest-priority missing evidence may shift toward independent customer confirmation or revenue quality.
T3 — Unit Economics Evidence
A detailed cost schedule reveals additional implementation, inference, or recurring support costs.
The system may need to prioritize customer-level contribution margin.
T4 — Additional Evidence or Contradiction Resolution
New supporting or conflicting evidence changes the relative importance of outstanding DD questions.
These events are illustrative. Ensure the actual scenario is logically coherent and financially material.
6.2 Required State Transitions
For every event, provide:
•	Newly available documents/evidence
•	Previous hypothesis status
•	Updated evidence status
•	Previously unanswered questions
•	Questions now resolved
•	Questions still open
•	Newly generated questions
•	Duplicate or obsolete questions removed
•	Updated question ranking
•	Explanation for each important ranking change
•	Expected behavior if the evidence is incomplete or contradictory
Avoid preprogramming a rule that every new document automatically changes the top-ranked question.
If the information is redundant or immaterial, rankings should remain stable.
________________________________________
7. Bayesian Updating & Information Gain
Implement the mathematical layer using Python rather than relying on free-form LLM arithmetic.
7.1 Bayesian Updating
For a binary investment hypothesis H and new evidence E:
P(H|E) = P(E|H)P(H) / [P(E|H)P(H) + P(E|¬H)(1 − P(H))]
All prior and likelihood parameters must be explicit.
For the primary demonstration, start with the Blueprint's illustrative example:
•	Prior = 0.30
•	P(E_positive | H) = 0.80
•	P(E_positive | ¬H) = 0.20
Calculate and validate the positive and negative posteriors using deterministic code.
Explain their interpretation.
Do not describe them as empirically estimated investment success probabilities.
7.2 Expected Information Gain
For a binary hypothesis, define entropy:
H(p) = −p log₂(p) − (1−p) log₂(1−p)
Expected Information Gain:
EIG(Q) = H(H) − Σ P(a|Q) × H(H|a,Q)
Implement expected answer distributions and likelihood scenarios explicitly.
The agent should never generate numerical probabilities without an acknowledged assumption source.
If the required probability parameters are missing, return null EIG and use a transparent qualitative ranking fallback.
7.3 Evidence Dependence
An especially important challenge is correlated evidence.
A customer success statement repeated in a CIM, pitch deck, and management Q&A is not three independent confirmations.
Implement:
•	evidence_group_id
•	dependence checks
•	duplicate-detection safeguards
•	tests preventing double counting
Do not multiply likelihood ratios from correlated records without a valid joint probability model.
7.4 Question Prioritization
Design a transparent priority framework incorporating:
•	Expected Information Gain, when calculable
•	Financial Materiality
•	Evidence Gap Severity
•	Obtainability of requested evidence
•	Time / cost of obtaining the evidence
•	Existing evidence overlap
•	Analyst review status
Clearly distinguish informational uncertainty from economic materiality.
A question with high EIG does not necessarily have the highest investment relevance.
If using a weighted heuristic score, disclose the weights and normalization.
Do not label a heuristic priority score as EVSI.
Reserve Expected Value of Sample Information for cases with an explicit decision/action set and utility model.
Provide sensitivity analysis showing how rankings change under reasonable alternative assumptions.
________________________________________
8. Evaluation Framework
Create a runnable benchmark comparing four system configurations.
Baseline	Configuration	Evaluation Objective
B0	General LLM Prompt	Basic extraction and DD generation
B1	RAG + Source Citations	Grounding and citation improvements
B2	Structured Claim → Evidence → DD Workflow	Question quality and actionability
B3	B2 + Adaptive Bayesian/EIG Engine	Adaptive decision-making and ranking
Also include an ablation test disabling the Bayesian module.
Where full implementations of B0–B3 do not yet exist, create adapter interfaces and benchmark fixtures. Do not invent model outputs or claim that actual model benchmarking has occurred.
8.1 Evaluation Metrics
Implement clearly defined metrics for:
Evidence & Claim Extraction
•	Claim Recall / Precision / F1
•	Evidence Retrieval Recall
•	Evidence Relationship Accuracy
•	Contradiction Detection Recall
Grounding
•	Citation Precision
•	Invalid or Hallucinated Citation Rate
•	Unsupported Claim Rate
•	Locator Accuracy
DD Question Quality
•	Critical DD Coverage
•	Top-3 Critical DD Coverage
•	Duplicate Question Rate
•	Actionability
•	Verification Criterion Completeness
•	Financial Relevance
Adaptive Performance
•	Top-k Priority Hit Rate
•	Ranking Correlation or NDCG@k
•	Hypothesis Update Consistency
•	Resolved Question Removal Accuracy
•	Unnecessary Ranking Change Rate
•	Evidence Double-Counting Rate
Quantitative Correctness
•	Bayesian Posterior Error
•	EIG Calculation Error
•	Deterministic Unit Test Pass Rate
Each metric must specify:
•	Mathematical or operational definition
•	Evaluation unit and denominator
•	Gold labels required
•	Missing/abstained output handling
•	Implementation
•	Interpretation
•	Limitations
Avoid metrics whose denominator is undefined or whose apparent performance can be improved simply by generating excessive questions.
For semantically equivalent questions, use a documented matching protocol with human-reviewable decisions.
8.2 Initial Acceptance Targets
Use the targets from the existing Blueprint:
•	Source locator precision ≥95%
•	Deterministic calculation unit tests: 100% pass
•	Top-3 Critical DD Coverage ≥80%
•	Hallucinated citations: zero
•	Final approval without HITL: zero
•	Expected adaptive ranking changes correctly reproduced in scripted scenarios
These are development acceptance targets, not already achieved results.
Report actual measured results separately from targets.
8.3 Evaluation Integrity
Implement safeguards against:
•	Gold-label leakage
•	Train/test contamination
•	Overfitting to one synthetic company
•	Invalid numerical reconciliation
•	Synthetic documents with unrealistic financial relationships
•	Model outputs evaluated by the same prompt that generated them
•	Confusing scenario-defined rankings with universally optimal investment decisions
Separate public evaluation examples from held-out cases.
Use a fixed random seed for any stochastic generation.
Record model version, prompt version, dataset version, run timestamp, configuration, and output checksum.
________________________________________
9. Python Deliverables
Create a coherent project directory containing at least:
chunk3_synthetic_evaluation/
├── README.md
├── requirements.txt
├── config/
│   ├── dataset_config.yaml
│   └── evaluation_config.yaml
├── schemas/
│   ├── deal_schema.py
│   └── evaluation_schema.py
├── data/
│   ├── public_orion/
│   │   └── source_manifest.json
│   ├── synthetic_northstar/
│   │   ├── documents/
│   │   ├── structured/
│   │   └── updates/
│   └── synthetic_manufacturing/
│       ├── documents/
│       ├── structured/
│       └── updates/
├── gold/
│   ├── hypotheses.json
│   ├── claims.json
│   ├── evidence.json
│   ├── dd_questions.json
│   └── adaptive_scenarios.json
├── src/
│   ├── generate_synthetic_data.py
│   ├── validate_dataset.py
│   ├── bayes.py
│   ├── information_gain.py
│   ├── priority.py
│   ├── evaluation_metrics.py
│   └── run_evaluation.py
├── tests/
│   ├── test_data_integrity.py
│   ├── test_financial_reconciliation.py
│   ├── test_bayes.py
│   ├── test_information_gain.py
│   ├── test_evidence_dependence.py
│   └── test_adaptive_scenarios.py
└── reports/
    ├── dataset_card.md
    ├── evaluation_protocol.md
    └── baseline_results.md
You may revise filenames or modular organization where technically justified, but maintain a clear correspondence to these deliverables.
Use Python 3.11+, Pydantic, pandas, NumPy, pytest, and other lightweight dependencies as necessary.
Prefer simple, reproducible implementations over excessive architectural complexity.
Do not introduce unnecessary cloud infrastructure, orchestration frameworks, or third-party commercial APIs at this stage.
________________________________________
10. Required Validation
Before considering Chunk 3 complete, execute the following checks:
1.	Every source locator resolves to a real document element.
2.	Every Evidence ID resolves to a valid document and locator.
3.	Every claim-to-evidence relationship references valid IDs.
4.	Every DD question references at least one relevant hypothesis.
5.	Hidden ground truth is excluded from agent-visible datasets.
6.	Financial statements reconcile or explicitly identify intended exceptions.
7.	Forecast calculations are consistent with supporting operating assumptions.
8.	Bayesian outputs match independent mathematical calculations.
9.	EIG outputs match independently calculated benchmarks.
10.	Duplicate or correlated evidence does not trigger unsupported repeated updates.
11.	Each adaptive scenario produces a defensible Before/After state.
12.	Evaluation scripts distinguish actual results, fixture results, and untested metrics.
Include negative tests and edge cases, not just successful examples.
Use pytest and provide an execution summary.
Do not claim tests passed without executing them.
________________________________________
11. Deliverables & Final Report
Produce:
1.	Synthetic Deal Packs — downloadable source documents and structured records.
2.	Gold Standard Dataset — documented machine-readable labels.
3.	Adaptive Scenario Dataset — sequential evidence updates and expected outputs.
4.	Quantitative Engines — Bayesian Updating, EIG, and question-priority calculations.
5.	Evaluation Harness — metrics, baseline interfaces, and executable tests.
6.	Dataset & Evaluation Documentation — a reproducible setup guide and methodology.
7.	Chunk 3 Technical Report — design choices, outputs, validation, limitations, and next development steps.
Package the files into a single ZIP archive where possible.
If downloadable files can be created, provide actual links rather than merely describing the proposed structure.
Final Report Format
Write the final report primarily in Korean, retaining standard financial and technical terminology in English.
Structure it as:
1.	Executive Summary
2.	Dataset Architecture
3.	Synthetic Deal Case Design
4.	Gold Standard Methodology
5.	Adaptive Decision Scenarios
6.	Bayesian / EIG Implementation
7.	Evaluation Framework & Baselines
8.	Test Results
9.	Limitations & Risks
10.	Next Steps for Chunk 4
Include one detailed worked example tracing:
Document → Claim → Evidence Gap → DD Question → EIG / Priority → New Evidence → Posterior / Status Update → New DD Priority
Present the numerical calculations, ground-truth labels, source locators, and ranking changes for this example.
Explain specifically what the adaptive engine accomplishes that a conventional LLM-generated DD checklist does not.
________________________________________
12. Execution Instructions
First, inspect the attached Blueprint and identify any relevant discrepancies with this prompt.
Then implement Chunk 3 using the following priority:
P0 — Must Complete
•	Full Northstar synthetic deal pack
•	Gold Standard
•	Four adaptive evidence events
•	Bayesian/EIG functions
•	Deterministic tests
•	Core evaluation metrics
P1 — Should Complete
•	Second synthetic manufacturing deal
•	Baseline adapter framework
•	Evaluation reports and dataset documentation
P2 — Optional
•	Actual rendered PDF/DOCX versions of all synthetic source documents
•	Extended evaluation visualizations
•	Additional scenarios or industries
Do not sacrifice P0 completeness to maximize P2 presentation quality.
Make reasonable technical decisions independently. Do not ask for confirmation on minor design choices.
If execution resources are constrained, complete the highest-priority runnable deliverables and clearly identify what remains incomplete. Never substitute lengthy planning prose for runnable code.
Begin by reading the Blueprint and implementing the actual Synthetic Deal Pack and Gold Standard. The final goal is a reproducible evaluation-ready dataset, not an illustrative proposal.

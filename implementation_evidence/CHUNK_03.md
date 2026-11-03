# Orion Deal Intelligence 2.0 Chunk 3 기술 보고서

## 1. Executive Summary

Chunk 1·2 전체 코드에 Synthetic Data & Evaluation을 통합했습니다. 실제 실행한 전체 테스트는 **1064 passed**, 실패 0, 오류 0, skip 0입니다. 기존 823개 테스트와 원본 12개 테스트 파일을 보존하고 241개를 추가했습니다. 실제 원문 parsing, 재무 대사, 단계별 source visibility, 승인 전이, Bayesian/EIG, 평가 지표를 포함합니다.

기존 통합 ZIP의 package 0.2.0을 기준으로 0.3.0을 작성했습니다. 브랜치는 `feature/chunk-03-synthetic-evaluation`이며 GitHub 인증·원격 접근·commit·push는 수행하지 않았습니다. 원격 저장소 HEAD와의 동일성은 주장하지 않습니다. 변경사항은 로컬 index에 보관한 첨부 Chunk 2 baseline과 비교합니다. 원본 ZIP SHA-256은 `chunk03-input-baseline.json`에 있습니다.

**완성된 LLM agent나 웹서비스는 아닙니다.** 작성된 fixture와 deterministic engine을 실제 실행했으며 실제 모델 비교, Windows 실행, 공개 배포는 `not_run`입니다. Chunk 4 이후는 구현하지 않았습니다.

## 2. Dataset Architecture

기존 `src/orion/domain`의 contract/scoring 1.0.0, SQLite·review 서비스와 기존 ns/cd/lm fixture를 그대로 유지했습니다. 추가 모델은 기존 Deal, Document, SourceSpan, binary Claim, Evidence, DDQuestion을 감싸는 확장입니다. Hypothesis는 binary Claim에 연결하고 ClaimEvidence는 Evidence.claim_id/stance로 표현합니다. BeliefSnapshot은 독립된 가상 확률 기록이며 기존 RankingSnapshot을 덮어쓰지 않습니다.

| 경로 | 역할 |
|---|---|
| `src/orion/adapters/parsers/`, `native_dataset.py` | 실제 원본 bytes·native locator·SHA-256 검증 |
| `src/orion/synthetic/` | 독립 합성 세계, 문서 생성, 단계별 입력, 재무·gold 검증 |
| `src/orion/quant/` | Bayesian/EIG, 의존 증거, 연구용 우선순위·민감도 |
| `src/orion/evaluation/` | 지표, source allowlist, baseline adapter, 실제 functional replay |
| `data/synthetic/`, `data/parsed/` | 기존 세 사례의 12개 native 문서와 재파싱한 runtime pack |
| `chunk3_synthetic_evaluation/` | 심화 원문·structured records·gold·4단계 업데이트·문서 |
| `evaluation/results/` | 실행 결과, stage별 prompt dump, run manifest, ablation |

전체 트리는 `REPOSITORY_TREE.txt`, 파일별 추가·수정 목록과 적용 가능한 binary diff는 ZIP의 `review/`에 있습니다. 원본 명세 47개, 기존 fixture 6개, 기존 테스트, domain 모델·점수·전이 및 OS별 lock의 보존 검증은 `chunk03-baseline-preservation.json`에 기록했습니다.

Python **3.12**를 유지했습니다. 새 runtime dependency는 없습니다. 이 자료 규모에는 Python 표준 라이브러리와 기존 Pydantic·DOCX/PPTX/PDF 파서로 충분하여 NumPy/pandas를 추가하지 않았습니다. 설치에는 기존 플랫폼별 hash lock을 사용합니다.

## 3. Synthetic Deal Case Design

| 신규 case | 원문 문서 | 가설 | 증빙 | DD 질문 | 순차 이벤트 |
|---|---:|---:|---:|---:|---:|
| nb | 8 | 3 | 26 | 13 | 4 |
| mf | 6 | 3 | 23 | 9 | 1 |

`nb`는 Northstar Analytics의 **독립 연구 변형 사례**입니다. 기존 `ns`의 후속 시점이나 같은 장부로 합치면 안 됩니다. 두 사례의 FY2025 Revenue/COGS/OPEX/EBITDA는 같지만, 고객별 매출·cash·debt·Aster 계약 조건은 별개로 설계했습니다. 기존 ns의 cash 800,000·debt 200,000·Aster 연간 계약 120,000 USD를 변경하지 않았으며 nb는 각각 450,000·250,000·240,000 USD입니다.

Northstar는 PoC/계약, ARR/매출, 청구/수금, 누락된 inference·구축비, 고객 수·독립성, 배치 가능 인력과 매출 예측의 차이를 다룹니다. 정상적인 갱신 고객·기존 매출도 포함합니다. FY2024/25 손익·재무상태표, FY2025 현금흐름과 자산·자본 roll-forward는 대사됩니다. 계획의 8개 배치와 현 인력의 4개 처리능력 차이, 이후 계약 가격과 초기 평균단가 예측의 차이는 의도된 예외로 기록했습니다.

`mf`의 Ridgeway Homeware는 독립 제조업 사례입니다. 매출 증가와 재고 누적, 잠정 EBITDA 정상화, 고객·지역 집중도, 유지/확장 CAPEX, 운전자본과 현금전환을 다룹니다. 재고 실사 수량·장부금액이 확인되어도 순실현가치와 저회전 재고 위험은 해결되지 않습니다. 소프트웨어 계약 질문을 이름만 바꾼 사례가 아닙니다.

추가 14개 DOCX와 대응 JSON/Markdown, 기존 12개 native PDF/DOCX/PPTX를 포함합니다. 모든 원문은 합성 표시·Document ID·기간·버전·locator·checksum을 가집니다. 실제 인물·서명·계좌·회사 로고나 고용주의 비공개 자료를 사용하지 않았습니다.

공개 Orion은 `data/public_orion/source_manifest.json`의 **pending_verified_sources** 상태입니다. 실제 사실·문서 목록은 비어 있으며, 검증 가능한 1차 공개자료를 확보한 뒤 채울 조건만 정의했습니다.

## 4. Gold Standard Methodology

합성 세계 사실, 단계별로 볼 수 있는 문서, 기대 라벨, 해석 판단을 분리했습니다. `gold/*_world_model.json`은 모델 입력에서 제외되며, `gold/*_gold.json`의 순위·예상 상태는 별도 작성한 시나리오 정책입니다. 구현 출력으로 정답을 복사하지 않습니다. 회사 주장 추출 라벨은 실제 본문·원문 locator와 연결하고, Analyst가 만든 가설과 구분합니다.

source-only loader는 코드 소유 공개 시점 목록과 원본·machine JSON hash를 검사합니다. 모든 모델 prompt는 허용된 source projection으로 생성하며 gold, 미래 문서, expected rank를 넣지 않습니다. 원문을 인용할 수 있다는 사실은 독립 검증되었다는 뜻이 아닙니다. 시뮬레이션 counterparties 역시 실제 외부기관의 검증을 뜻하지 않습니다.

Answer-key audit는 ID/locator/정확한 발췌/단계/문서 상태와 근거 연결을 검사합니다. 경제적 의미·materiality의 타당성은 기계적 검사만으로 증명할 수 없으므로 **self-authored, provisional** 상태를 유지합니다. 동일한 질문 표현만 정답으로 강제하지 않고 요청 대상·범위·자료·판정기준에 따른 family와 대체 표현을 기록합니다. 한 출력 질문은 한 family에만 대응합니다.

## 5. Adaptive Decision Scenarios

실제 Chunk 2 승인 전이 엔진으로 재생한 Northstar 결과입니다. 아래 순위는 계약 점수이며 EIG를 곱하지 않습니다.

| 단계 | Top-3 질문 순서 | 점수 |
|---|---|---|
| T0 | contract_a → contract_b → execution_a | 100 / 97 / 94 |
| T1 | contract_b → execution_a → margin_a | 97 / 94 / 91 |
| T2 | contract_b → margin_a → independence | 97 / 91 / 89 |
| T3 | contract_b → margin_a → independence | 97 / 91 / 89 |
| T4 | margin_a → independence → arr | 91 / 89 / 81 |

T1은 Aster 계약만 해결합니다. T2는 Aster 검수와 첫 수금 조건을 만족하지만 잔액 30,000 USD는 별도 질문으로 남습니다. T3는 비용 범위를 완성하고 음의 공헌이익을 드러내지만, 이미 최대 gap이었던 질문의 Top-3는 그대로입니다. T4는 Birch 계약·검수를 해결하면서 공통 소유관계를 드러내 독립 고객 가설을 반박합니다. 새 문서마다 무조건 1위 질문을 바꾸는 규칙은 없습니다.

각 이벤트에는 이전/이후 가설 상태, 신규 문서·증빙, 해결/미해결 질문, 전체 순위와 score delta, 불완전·모순 증거 처리 설명이 있습니다. 질문 후보는 작성된 fixture입니다. `newly_generated_questions=[]`는 실제 LLM 질문 생성이 아직 없다는 뜻이며, 단순 재정렬을 새로운 질문 생성으로 표현하지 않습니다.

### 상세 Worked Example

1. **Document → Claim:** 초기 CIM은 4개 enterprise 고객·committed ARR 1,800,000 USD를 주장합니다. CRM은 기존 유료 2곳, Aster PoC, Birch 미서명 prospect로 나눕니다. 이 회사 주장과 Analyst의 `nb_claim_h1`(기간 내 독립 신규 유료·검수 고객 2곳)을 구분합니다.
2. **Evidence Gap → DD:** `nb_q_contract_a`는 서명된 Aster 상업 계약과 금액·기간·검수 조건을 요구합니다. Gap=5, Materiality=5, Obtainability=5이므로 `9×5 + 8×5 + 3×5 = 100`, 초기 1위입니다.
3. **EIG:** 별도 명시적 가정 p=0.30, P(E+|H)=0.80, P(E+|¬H)=0.20을 사용합니다. EIG는 **0.2361139273 bits**이며 가상 시나리오의 정보량입니다.
4. **New Evidence:** `nb_ev_contract_a` → `nb_doc_contract`, 실제 locator `{"block_index": 5, "heading_path": [], "kind": "docx_paragraph", "paragraph_index": 0, "part_uri": "word/document.xml"}`. 원본 SHA-256은 `2c9ba23fd2609d49038947932af2a3e803697107f3f4217e3bb214583f1a7d57`입니다. 정확한 발췌는 다음과 같습니다.

> Aster and Northstar signed a commercial contract for annual subscription fees USD 240,000 and a one-time implementation fee USD 60,000. Total first-year contractual value is USD 300,000. The PoC memorandum has been replaced by the commercial contract.

5. **Posterior / Status:** P(E+)=0.3×0.8+0.7×0.2=0.38, P(H|E+)=0.24/0.38=**12/19≈0.6315789474**. 반대 답변의 posterior는 0.06/(0.06+0.56)=**3/31≈0.0967741935**입니다. 승인 후 계약 질문만 resolved, H1은 partial/document_only입니다. 승인과 원문 일치는 독립적 사실 확정이 아닙니다.
6. **New DD Priority:** 다음 Top-3는 Birch 계약(97), Aster 검수·첫 수금(94), Aster 공헌이익(91)입니다. 단순 LLM checklist와 달리 실제 충족 조건·중복·반증·승인 상태를 계산하여 질문의 제외/잔존/재개와 원문별 변경 이유를 재현할 수 있습니다.

## 6. Bayesian / EIG Implementation

`posterior`, Shannon entropy, 예상 답변 분포와 EIG를 Python으로 계산합니다. 확률은 유한한 [0,1] 값, 답변 분포 합계 1, 식별 가능한 assumption source를 요구합니다. 입력이나 출처가 없으면 EIG=null이고 정성적 우선순위 fallback을 사용합니다. 불가능한 관측과 비정상 확률은 오류로 처리합니다.

H(0.30)=0.8812908992 bits, 예상 posterior entropy=0.6451769719 bits, 차이는 0.2361139273 bits입니다. 독립 Fraction 계산과 별도 Shannon 수식으로 결과를 비교했습니다.

| 단계 | 가설 | Prior | Posterior |
|---|---|---:|---:|
| T1 | `nb_hyp_h1` | 0.3000000000 | 0.6315789474 |
| T2 | `nb_hyp_h1` | 0.6315789474 | 0.8108108108 |
| T3 | `nb_hyp_h2` | 0.6500000000 | 0.3170731707 |
| T4 | `nb_hyp_h1` | 0.8108108108 | 0.3797468354 |

동일 evidence/group/hash와 대칭·전이 의존관계를 중복 계산하지 않습니다. 계약 뒤 같은 고객의 실행 기록을 반영하는 T2는 독립 증거라는 가정 대신 **전체 선행 evidence/group ID와 likelihood를 결합한 검토된 conditional model**을 요구합니다. T4도 이전 이력에 조건부인 명시적 가정입니다. 이는 실증 투자 성공확률이 아닙니다.

제품 점수는 `P=9G+8M+3O`(45%/40%/15%)입니다. 별도 `research-priority-1.0.0`은 M30%/G25%/EIG20%/O15%/시간·비용10%의 휴리스틱이며, 결측 성분은 제외 후 재정규화합니다. Evidence overlap과 review status도 처리합니다. 효용·행동 집합이 없으므로 EVSI라고 부르지 않습니다. 가중치·prior·likelihood 민감도와 실제 순위 변화, null fallback은 `evaluation/results/quantitative_report.json`에 있습니다. Bayesian 패널을 꺼도 기존 제품 순위는 동일합니다.

## 7. Evaluation Framework & Baselines

| 비교군 | 이번 실행의 의미 |
|---|---|
| B0 | 일반 prompt 인터페이스와 공통 작성 fixture, 모델 성능 아님 |
| B1 | citation 있는 작성 fixture, 실제 RAG 모델 성능 아님 |
| B2 | 구조화된 동일 초기 객체·초기 순위 유지 |
| B3 | 실제 승인 후 deterministic reranking + 별도 확률 계산 |
| B1-R | 재질문 adapter/prompt 준비, 실제 모델 출력 not_run |
| Bayesian off | 실제 on/off 재생 후 제품 순위·상태 불변 검증 |

Claim precision/recall/F1, evidence recall/관계/모순, citation·locator·unsupported claim, DD coverage/Top-3/중복/actionability/verification/financial relevance, NDCG·상태·해결·무변화·중복 계산, posterior/EIG error와 테스트 pass rate의 구현을 포함합니다. 각 지표의 분모·결측·abstention·한계는 `chunk3_synthetic_evaluation/reports/evaluation_protocol.md`를 참조하세요. 미검토 semantic annotation은 NA이며 실패 출력을 성공으로 집계하지 않습니다. 질문을 많이 생성해 coverage를 올리는 효과는 고정 출력 상한·precision·중복률을 함께 보며 통제합니다.

Run manifest는 dataset/model/prompt/config/seed/UTC/source·input·output·gold checksum 및 비용·not_run을 남깁니다. Northstar는 개발 사례이며 Cedar/Lumen/제조업은 공개 frozen-rule regression입니다. 저자가 내용을 알고 있으므로 진정한 비공개 blind holdout이나 통계적 일반화로 표현하지 않습니다.

## 8. Test Results

- 전체 pytest: **1064/1064 passed**; 실패 0, 오류 0, skip 0.
- 기존 및 심화 시나리오 전이: **8/8** 기대 순위 전이 일치.
- 기존 세 사례의 음성 대조군: **15/15**. 중복·무관·잘못된 locator·미승인·stale revision을 각각 실행했습니다.
- Source locator 95%, Top-3 coverage 80%, hallucination 0은 개발 목표입니다. **작성 fixture 결과로 실제 모델이 목표를 달성했다고 주장하지 않습니다.**
- 네이티브 문서는 최종 렌더링 후 검토했습니다. 정확한 문서 hash·페이지 수·검토 범위는 `chunk03-source-visual-qa.json`을 참조하세요.
- 실행 시작 UTC `2026-11-03T08:13:50.028556+00:00`, 종료 `2026-11-03T08:16:07.908301+00:00`. OS `Linux-6.18.57-x86_64-with-glibc2.39`. 원본 lock hash와 source/test tree digest는 `chunk03-validation.json`에 있습니다.

| 실행 | 결과 | 종료 코드 | 로그 |
|---|---|---:|---|
| `generate-native` | pass | 0 | `logs/chunk03-generate-native.log` |
| `ingest-native` | pass | 0 | `logs/chunk03-ingest-native.log` |
| `generate-expanded` | pass | 0 | `logs/chunk03-generate-expanded.log` |
| `validate-expanded` | pass | 0 | `logs/chunk03-validate-expanded.log` |
| `replay-northstar` | pass | 0 | `logs/chunk03-replay-northstar.log` |
| `replay-manufacturing` | pass | 0 | `logs/chunk03-replay-manufacturing.log` |
| `input-audit` | pass | 0 | `logs/chunk03-input-audit.log` |
| `evaluation` | pass | 0 | `logs/chunk03-evaluation.log` |
| `quantitative-report` | pass | 0 | `logs/chunk03-quantitative-report.log` |
| `spec-integrity` | pass | 0 | `logs/chunk03-spec-integrity.log` |
| `full-pytest` | pass | 0 | `logs/chunk03-full-pytest.log` |
| `pip-check` | pass | 0 | `logs/chunk03-pip-check.log` |
| `compile` | pass | 0 | `logs/chunk03-compile.log` |

## 9. Limitations & Risks

실제 LLM extraction·B0–B3 우월성·B1-R·외부 전문가 Gold 검토는 수행하지 않았습니다. Windows와 GitHub Actions도 이 Linux 작업 환경에서 실행하지 않았습니다. 기존 native Windows 미검증 상태를 전체 제품 완료로 바꾸지 않습니다.

parser는 bounded native text와 단순 표를 지원합니다. 스캔/OCR·암호·병합/복잡한 표·지원하지 않는 내용은 fallback하며 성공적으로 해석했다고 표시하지 않습니다. PDF locator는 페이지의 text unit이며 글자 bounding-box viewer는 Chunk 4 과제입니다.

source projection은 모델에 전달할 데이터 경계입니다. 전체 ZIP에 접근하는 임의 코드의 파일시스템 sandbox는 아닙니다. 실제 agent를 연결할 때 gold 폴더·코드·미래 자료의 도구 접근을 허용하지 않아야 합니다. 상관 증거의 의미적 판정도 신뢰된 그룹 지정이 필요하며 모든 paraphrase를 hash만으로 탐지할 수는 없습니다.

작은 저자 설계 synthetic 사례는 실거래의 복잡성·산업별 다양성을 대체하지 않습니다. 이 결과는 투자 승인, 완결 FDD, 가치평가 또는 법률 의견이 아닙니다.

## 10. Next Steps for Chunk 4

Dash + Dash AG Grid에 문서 목록·matrix·source inspector·승인 전후 변경·evaluation 화면을 연결합니다. 이번 source index, SourceResolver, ReviewService와 stage-only input API를 그대로 사용하고 프런트엔드에서 점수나 actor role을 다시 계산하지 않습니다. Bayesian 값과 가정 출처는 별도 패널로 표시합니다.

Windows에서 설치와 전체 테스트를 실행하고, 다음 단계에서 실제 두 브라우저 탭 격리·원문 위치 표시를 확인합니다. 실제 LLM 비교는 모델/프롬프트/예산/전송 범위가 준비된 별도 단계에서 실행하고 현재 fixture 표와 분리합니다. 이번 작업에서 UI·공개 배포·GitHub 반영은 하지 않았습니다.

### 실행 방법

프로젝트 루트에서 Python 3.12 가상환경과 플랫폼별 lock을 설치한 뒤:

```bash
python -m pip install --no-deps --no-build-isolation -e .
python scripts/validate_chunk03.py
```

Windows PowerShell의 구체적 명령은 `WINDOWS_APPLY_CHUNK_03.md`, 개별 CLI는 루트 README와 `chunk3_synthetic_evaluation/README.md`에 있습니다. 설치한 wheel 검증은 `chunk03-wheel-validation.json`, diff 적용·전체 byte 비교는 ZIP의 `review/PATCH_VALIDATION.json`에 기록합니다.

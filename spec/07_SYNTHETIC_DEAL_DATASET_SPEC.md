# Synthetic Deal Dataset Specification

Contract 1.0.0 · 모든 회사·고객·수치는 독립적으로 만든 가상 자료다. 원본 학술 자료에 등장하는 실제 상장사 수치·고용주 거래조건은 재사용하지 않는다.

## 세 사례와 재무 일관성

아래는 FY2025 USD다. JSON의 금액 단위는 cents다. 장부 truth는 [financial_truth.json](DATASET_SPECS/financial_truth.json)에 고정한다. 이는 생성기 정합성 기준이며 기업 현실의 truth를 뜻하지 않는다.

| 항목 | Northstar Analytics | Cedar Components | Lumen Field Services |
|---|---:|---:|---:|
| 사업 | AI 구독+구축 | 주문형 산업 부품 | 현장 유지보수 인력 서비스 |
| Revenue | 1,200,000 | 6,000,000 | 3,000,000 |
| COGS | 360,000 | 3,600,000 | 1,800,000 |
| OPEX excluding D&A | 720,000 | 1,800,000 | 900,000 |
| EBITDA | 120,000 | 600,000 | 300,000 |
| AR / Inventory / AP | 180,000 / 0 / 60,000 | 900,000 / 1,200,000 / 700,000 | 500,000 / 0 / 200,000 |
| 단순 Operating NWC | 120,000 | 1,400,000 | 300,000 |
| Cash / Debt | 800,000 / 200,000 | 400,000 / 1,100,000 | 250,000 / 300,000 |

NWC는 이 데이터셋의 AR+inventory−AP만 뜻하며 실제 거래의 NWC 정의가 아니다. EBITDA는 revenue−COGS−위 OPEX다. 장부가 완전한 재무제표인 것처럼 표시하지 않는다. Balance sheet balance와 현금흐름표는 본 MVP의 평가 대상이 아니다.

Northstar subscription 900,000 + services 300,000 = revenue 1,200,000. 기존 고객별 매출 360,000/300,000/240,000/300,000이 합계와 같다. Aster·Birch는 미래 유료 전환 검토 대상이며 기존 고객 매출에 포함하지 않는다. 신규 Aster 연간 계약 120,000의 서비스 기간은 2027-01-01~12-31, 초기 FY2025 숫자와 혼합하지 않는다.

Cedar 고객매출 1.8m/1.5m/1.2m/.9m/.6m=6m. Batch C-17 invoice 180,000은 매출에 이미 포함된 일부이며 update에서 다시 가산하지 않는다. Lumen 10,000시간×$300=3m, 직접원가 $180/시간=1.8m, 가용 12,000시간 대비 사용률 83.333…%, key client 매출1.5m=50%다. 신규 side letter는 이익 금액을 자동 변경하지 않고 renewal 검증을 다시 열게 한다.

## 실제 native 파일 생성 계약

현재 JSON은 텍스트 extraction fixture다. Chunk 3은 아래 **12개**의 작은 native source 파일을 실제 생성하고 SHA-256을 기록한다. source bytes→parser→span→expected outcome을 따로 검증한다. 제공된 text fixture는 콘텐츠 seed로 쓰되 그 locator를 실제 parser 결과로 확인/갱신한다. gold를 모델 context에 넣지 않는다.

| Pack | 초기 파일 3개 | staged 이벤트 1개 |
|---|---|---|
| Northstar | `ns_cim.pdf` 3쪽, `ns_finance.docx` 문단/단순 표, `ns_pipeline.pptx` 4장 | `ns_contract_a.docx` 계약 1건 |
| Cedar | `cd_operations.docx` 문단/표, `cd_finance.pdf` 3쪽, `cd_customers.pptx` 3장 | `cd_batch_acceptance.docx` 단일 batch 증빙 bundle |
| Lumen | `lm_contracts.pdf` 3쪽, `lm_capacity.docx` 표, `lm_plan.pptx` 3장 | `lm_side_letter.docx` 한 장의 반증 |

각 문서 첫 부분과 footer에 SYNTHETIC / 교육용 가상 자료를 표시한다. 실제 로고·서명·개인 신원·은행계좌 번호는 생성하지 않는다. 서명이 필요한 시나리오는 “가상 서명 완료로 설정” 같은 text annotation을 사용하고 실제 전자서명 유효성을 주장하지 않는다.

## 이벤트와 기대 Top-3

| Case | before | 단일 승인 이벤트 | after |
|---|---|---|---|
| ns | contract_a, contract_b, accept_collect | Aster 유료 계약 존재만 증빙 | contract_b, accept_collect, concentration |
| cd | cutoff, warranty, inventory | C-17 dispatch/acceptance 일치 | warranty, inventory, receivable |
| lm | labor, margin, cash | key-client renewal과 모순되는 side letter | renewal, labor, margin |

정확한 ID·점수·승인은 `EXAMPLES/*.json` 및 `DATASET_SPECS/cd/`, `DATASET_SPECS/lm/`에 있다. 각 positive/contradiction event는 base revision 1에서 독립 실행한다. 여러 이벤트를 한꺼번에 넣어 어떤 증거가 순위 변화의 원인인지 잃지 않는다. 일련의 이벤트 실험을 추가하면 순서와 중간 Snapshot을 사전 정의한다.

## 음성 대조군 생성

각 pack에서 event별 branch를 초기 state로 reset하고 아래 5개를 독립 실행한다.

1. Duplicate: 같은 origin/조건의 동일 계약 내용을 새 filename으로 제출. source 수가 늘어도 credit 증가 없음.
2. Unrelated: 사무실 행사 안내 등 claim criterion과 무관한 문서. 승인해도 gap·rank 불변.
3. Invalid locator: quote 1글자 또는 DOCX index를 변경. staging invalid, 승인 불가.
4. Unapproved: 유효 이벤트를 staging만 하거나 반려. 현재 Snapshot 불변.
5. Stale revision: 업데이트 승인 후 다른 command가 base=1을 사용. 전체 commit 거절.

추가 제품 시험에는 duplicate origin의 반대 진술(중복으로 숨기면 안 됨), source 삭제/변조, unsupported scan, 표 셀 병합, prompt injection text, 임의 서버 경로, analyst 권한의 승인 시도를 포함한다.

## Gold 분리와 leakage 방지

`EVAL_GOLD/*_gold.json`은 저자가 제안한 초기 gold이며 독립 검토 완료물이 아니다. `expected_top3_transition.json`도 gold다. 모델 input loader는 디렉터리 전체 glob이 아니라 승인된 native source 목록과 allowed source span 목록만 읽는다. 모델에는 materiality/obtainability의 rubric과 허용 input은 제공하되 expected rank·gold answer는 제공하지 않는다.

Northstar는 개발·튜닝 사례다. Cedar와 Lumen은 규칙·prompt를 freeze한 뒤 평가한다. 이 명세 작성자는 세 사례를 모두 보았으므로 완전 blind holdout이라고 주장하지 않는다. 평가 전에 다른 검토자가 새 문서 표현·경계 조건을 작성하는 추가 blind check를 권장한다. 추가 사례가 없으면 작은 author-designed synthetic evaluation이라는 한계를 명시한다.

3개 Deal 각각 초기 상태, 승인 이벤트1개, 음성 이벤트5개를 준비하면 3 positive/contradiction transition과 15 negative controls가 된다. native parser test corpus는 scan/표/locator adversarial fixture를 별도로 만들고 투자 질문 평가 표본과 섞지 않는다.

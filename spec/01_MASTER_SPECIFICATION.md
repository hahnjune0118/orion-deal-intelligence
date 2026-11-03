# Orion Deal Intelligence 2.0 Master Specification

Contract 1.0.0 · Scoring 1.0.0 · 2026-11-03 · 상태: **구현용 설계 확정안, 제품 구현·성능 미검증**

## 1 목적과 완료의 의미

PE·M&A IB·Deal Advisory의 초기 검토자가 회사의 주장, 실제 확보한 증빙, 아직 필요한 증빙을 구분하고 다음 실사 질문을 선택하도록 돕는다. 핵심 데모는 **합법적으로 사용 가능한 신규 증빙 하나를 검토·승인하면 Top-3 DD 질문이 재현 가능한 이유로 달라지고, 변경 전후의 원문과 판단을 추적할 수 있는 것**이다.

대상은 독립적인 가상 B2B AI 기업 **Northstar Analytics**, 제조업 **Cedar Components**, 노동집약 서비스업 **Lumen Field Services**다. 실제 회사와의 관련성을 의도하지 않는다. 고용주·고객의 내부자료, 고유 거래조건, 실제 투자성공 확률을 사용하지 않는다. 금융실사 완료, 감사의견, 거래 실행, 자동 투자결정은 제품이 제공하는 결과가 아니다.

학술적으로는 문서에 근거한 구조화와 신규 증빙 반영이 정적 LLM 체크리스트보다 질문 선택·갱신을 개선하는지 비교한다. 개선 여부는 [평가 프로토콜](08_EVALUATION_PROTOCOL.md)의 사전 등록된 비교로 검증한다.

## 2 범위와 일정

평일 약 2시간, 2026-11-03부터 12-11까지 29일, 총 약 58시간을 가정한다. 구현 48시간과 버퍼 10시간으로 나눈다. 개인 일정·휴일을 반영한 실제 가용시간은 개발 시작 시 기록한다. 12-14는 제출 버퍼이며, 주말 작업을 전제로 하지 않는다.

| 구분 | 기능 | 경계 |
|---|---|---|
| MVP | Dash + Dash AG Grid Community 3-pane 작업 화면 | 문서 탐색, 중앙 Matrix/질문 탭, 우측 근거·검토 |
| MVP | 작은 PDF/DOCX/PPTX의 텍스트와 단순 표 추출 | 스캔·복잡한 표는 차단/수동검토 상태로 설명 |
| MVP | Thesis → Claim → Evidence → DDQuestion | 원문 위치 검사와 분석가 검토를 통과한 증빙만 점수 반영 |
| MVP | 고정 루브릭 순위·Top-3·원자적 증빙 갱신 | 순위 계산·상태 전이·감사 기록은 Python 결정론 코드 |
| MVP | 세 합성 사례·증빙 이벤트·음성 대조군 | 개발용 Northstar, 잠금 평가용 Cedar/Lumen |
| MVP | CSV/XLSX DD 요청서, Markdown Screening Memo | 현재 Snapshot에 대한 최종 export 승인 필요 |
| MVP | 공개 Demo와 Local Live | Demo는 합성 데이터·캐시만, 외부 API 0회 |
| MVP | B0–B3 평가 실행기·보고서 | 경험적 성능은 실제 시행 전까지 `not_measured` |
| Optional | 독립 Bayesian/EIG 패널 | 가상 prior/likelihood를 명시한 이진 시나리오만, 순위에 영향 없음 |
| Optional | OCR·PDF 실제 좌표 하이라이트·고급 표 | 첫 출시에서는 추출 텍스트의 정확한 강조 표시가 기본 |
| Optional | 검색 임베딩·독립 Overview/Evaluation 페이지 | 작은 코퍼스는 결정론 토큰 검색·작업 화면 탭으로 충분 |
| Excluded | `orion_dcf.py`, `fdd_model.py`, DCF 자동수정·실제 가치평가 | 재무 driver 이름만 매핑 |
| Excluded | 공개 방문자 임의 업로드·공개 Live API·계정 협업·SSO | 인증·다중 임차인 운영 플랫폼 아님 |
| Excluded | 상장사 한 곳 고정, 실제 VDR, DART/KRX 수집 | 외부 데이터 커넥터를 추가하지 않음 |

Critical Path: 계약·참조 무결성 → Northstar 증빙 승인/재정렬 엔진 → 원문 파싱·세 사례와 gold 분리 → Matrix/inspector 연결 → export 승인 → 무API Demo·재시작·분리 검증 → 비교평가/시연.

시간 부족 시 제거 순서: Bayesian UI → 좌표 기반 PDF 강조 → OCR → 임베딩 검색 → 별도 Overview/Evaluation 페이지 → 고급 꾸미기. 세 기본 형식의 제한된 입력, 세 사례, 승인·무결성·Top-3·export·Demo 경계는 제거하지 않는다. 이들도 불가능하면 미완료 범위를 공개하고 완료라고 주장하지 않는다.

## 3 사용자 흐름

1. Deal을 선택하고 문서 목록에서 출처·파싱 상태를 확인한다. Local Live만 허용된 파일을 등록한다.
2. 추출 초안을 검토한다. LLM은 주장·근거 후보·질문 초안만 제안한다. 회사 주장과 분석가 가정은 별도 표시한다.
3. 근거를 클릭하면 원문 문서, 정확한 위치, 원문 snippet, 검증 결과를 본다. 승인과 사실 검증을 구별한다.
4. 질문을 승인하면 Evidence Gap, Materiality, Obtainability에 따른 Top-3와 점수 이유를 본다.
5. 신규 증빙 하나를 staging한다. 문서·인용 검사 중에는 기존 순위가 그대로다.
6. reviewer가 적용 범위와 충돌을 확인하고 승인하면 한 트랜잭션에서 근거·상태·순위·감사를 갱신한다.
7. Before/After에서 해결·재개·상대 승격을 구별한다. unchanged 이벤트도 이유를 기록한다.
8. 최신 Snapshot의 승인된 질문과 미확인 사항을 검토한 뒤 내보낸다. 수정 시 이전 export 승인은 재사용하지 않는다.

## 4 구속력 있는 요구사항

| ID | 계약 | 검증 |
|---|---|---|
| R01 | UI는 Plotly Dash + Dash AG Grid, 엔진은 UI import 없음 | AT01 |
| R02 | PDF page는 1 기반, PPTX slide는 1 기반, DOCX는 native paragraph/table locator | AT02–04 |
| R03 | 원문 해시·문서 버전·snippet·범위가 모두 맞아야 인용 유효 | AT05–06 |
| R04 | `support_status`, `truth_status`, `review_status` 분리 | AT07 |
| R05 | 단일 고객 유료 계약은 두 고객 검수·수금의 증거가 아님 | AT08 |
| R06 | 점수·동점·누락값·중복·상태 전이는 고정 규칙 | AT09–12 |
| R07 | staging·반려·미승인은 현재 순위에 영향을 주지 않음 | AT13 |
| R08 | optimistic concurrency·idempotency·원자적 commit | AT14–16 |
| R09 | 해결된 질문은 순위 제외, 충돌 시 재개 | AT17 |
| R10 | export는 현재 입력 digest와 Snapshot에 승인 결합 | AT18–19 |
| R11 | 공개 Demo는 API 요청 0, 업로드 불허, 방문자 간 상태 공유 없음 | AT20–22 |
| R12 | 개인 API key는 Local Live 서버 환경에만 존재 | AT23 |
| R13 | 토큰·입력·실행·일간 비용 한도, 불확실 청구 예약금 보존 | AT24 |
| R14 | 세 가상 사례의 재무합계가 일치하고 gold가 모델 입력에서 제외됨 | AT25–26 |
| R15 | B0–B3와 ablation·negative controls의 분모·실패 포함 보고 | AT27 |
| R16 | 키보드·포커스·대비·반응형·loading/error 상태 | AT28 |
| R17 | 로컬 DB와 공개 Demo 지속성 차이를 사용자에게 명시 | AT29 |
| R18 | 모든 코드 Chunk는 실행 로그·테스트 결과·diff로 완료 입증 | AT30 |

## 5 아키텍처 결정

Dash의 Flask 서버 한 프로세스 안에 application service를 두며 별도 FastAPI, Redis, 벡터 DB를 도입하지 않는다. 도메인은 UI와 LLM 제공자에서 독립적인 Python 함수·Pydantic 모델로 구성한다. 파서는 문서의 native 구조를 보존하고, 소규모 검색이 후보 span을 선택한다. LLM 출력은 타입 검증, 참조 검증, quote 검사 후 초안으로 저장된다.

Local Live는 단일 사용자·loopback 주소와 SQLite/WAL을 사용한다. 공개 Demo는 **strictly stateless replay**로 고정한다. 브라우저 탭은 허용된 합성 이벤트 ID/행동 목록만 보내며, 서버는 불변 fixture에서 상태를 매번 재계산한다. 임의 점수·승인자·파일 경로는 입력으로 받지 않는다. 공유 Python 전역 변수나 서버 SQLite를 방문자 상태로 쓰지 않는다.

AG Grid는 Community 기능만 사용한다. 원문 inspector는 Dash 컴포넌트이며 AG Grid Enterprise sidebar가 아니다. XLSX는 서버의 openpyxl로 만들고 Enterprise Excel export를 사용하지 않는다. Dash Mantine Components는 필수가 아니며 MVP 의존성에서 제외한다. 공식 Dash 3 호환 최소 버전이 있더라도 이 프로젝트에서의 호환·접근성 검증은 별도이므로 CSS와 기본 Dash 컴포넌트로 범위를 줄인다.

## 6 근거와 판단의 의미

`locator_status=validated`는 지정 문서 버전의 추출 단위에서 quote가 일치한다는 뜻이다. `review_status=approved`는 분석가가 그 증빙의 사용 범위를 승인했다는 뜻이다. 둘 다 현실의 진위를 보증하지 않는다. `truth_status=independently_verified`는 독립 확인 근거, 확인자 판단, 범위가 모두 존재할 때만 가능하다.

승인된 유효 근거라도 회사의 반복 주장이나 전달받은 동일 계약은 독립 관측 횟수를 늘리지 않는다. `origin_key`와 `EvidenceRelation`으로 중복·충돌·대체를 명시한다. 후속 문서가 오래된 문서를 자동으로 덮어쓰지 않는다. 권위 있는 대체 범위가 승인되지 않으면 충돌이 남는다.

Northstar의 신규 `USD 120,000` 계약은 상업적 유료 계약의 존재를 뜻한다. **실제 수금 완료를 뜻하지 않는다.** 회계 매출이나 은행잔액을 변경하지 않으며, 2027 계약금액을 FY2025 매출에 더하지 않는다.

## 7 순위 계약

각 질문의 승인된 요구조건 충족 수를 `k`, 전체 요구조건 수를 `n`이라 한다. 활성 반증이 있으면 `G=5`; 없으면 `G=5×(1−k/n)`이다. `M`과 `O`는 각각 0–5이며 점수는 **P=9G+8M+3O**, 범위 0–100이다. 모든 조건이 충족되고 반증이 없으면 점수 계산 전에 resolved로 제외한다. 높은 중요도가 해결된 질문을 다시 상위로 끌어올리지 못한다.

M 누락은 3, O 누락은 2로 처리하고 `provisional=true`를 표시한다. 누락을 0으로 취급하지 않는다. O는 시간·직접비의 하나의 부담 등급이므로 별도 비용 패널티를 중복 가산하지 않는다. 정확한 기준·동점은 [05](05_SCORING_AND_ADAPTIVE_ENGINE.md)가 구속한다. Bayesian/EIG는 순위와 독립적인 선택 기능이며 미입력 시 계산하지 않는다.

핵심 기대값: Northstar 초기 `q_ns_contract_a=100`, `q_ns_contract_b=97`, `q_ns_accept_collect=89`. 승인 후 A 계약 질문은 resolved로 제외되고 `[q_ns_contract_b, q_ns_accept_collect, q_ns_concentration]`이 Top-3다. B·검수/수금의 점수는 그대로이고 순위만 올라간다.

## 8 완료 및 검증 경계

출시 완료는 Windows Local Live 실행, 합성 PDF/DOCX/PPTX native 인용 검증, 세 사례 transition, 승인 export, Demo 네트워크 0회와 탭 분리, 재시작 후 reset 동작, B0–B3 실제 결과 보고, 시연 영상·짧은 포트폴리오 설명이 모두 갖춰졌을 때다. Live API가 준비되지 않으면 `Local Live 미검증`으로 공개하고 Demo 완료와 구별한다.

95% location citation accuracy, 허위 인용 0, 80% critical Top-3 coverage는 학술 목표다. 구현 단위테스트, 스키마 검사, 저자가 만든 예시의 일치율을 그 성능으로 발표하지 않는다. 작은 세 사례는 일반적인 Deal 모집단을 대표하지 않는다.

현재 패키지의 실제 검사 범위와 미검증 사항은 [검증 보고서](QA/VALIDATION_REPORT.md), 전체 파일은 [manifest](DELIVERY_MANIFEST.md)에 있다. 외부 정보는 [출처 기록](11_DECISION_LOG_AND_SOURCES.md)의 확인일과 한계를 따른다. 계약 변경은 [Orchestrator](PROMPTS/00_ORCHESTRATOR.md)의 변경관리 절차를 거친다.

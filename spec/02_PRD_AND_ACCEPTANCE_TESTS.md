# PRD와 Acceptance Tests

Contract 1.0.0 · 모든 아래 Gate는 **향후 제품 구현 시험**이다. 이번에 실행한 계약 검사는 QA 보고서와 구분한다.

## 사용자와 문제

Analyst는 분산된 문서의 주장을 좇으며 미확인 사항을 요청한다. Reviewer는 원문과 적용 범위를 확인하고 증빙 반영·최종 산출물을 승인한다. Local Live에서는 한 사람이 두 역할을 맡을 수 있으나 승인 행동은 명시적이어야 한다. Demo reviewer는 가상 시뮬레이션 역할이며 실제 조직 권한을 뜻하지 않는다.

성공한 사용자는 “무엇이 부족한가”, “왜 이 질문이 먼저인가”, “새 증빙 때문에 정확히 무엇이 변했는가”에 원문과 수치로 답할 수 있다. 질문 수, 화려한 차트, 자동 생성 문장량은 성공 척도가 아니다.

## 제품 시험표

| ID | Given / When | Then | 증빙 |
|---|---|---|---|
| AT01 | Dash 없이 core import·rank 실행 | 동일 JSON 입력은 동일 순위·digest | core import test, log |
| AT02 | text PDF 2쪽, 2쪽 quote 선택 | page=2 및 정확한 추출단위 강조 | parser test, source viewer capture |
| AT03 | PPTX 3번째 slide 내 표 셀 | slide/shape/cell로 정확히 이동 | parser test |
| AT04 | DOCX 문단·표 셀을 선택 | structural locator, page 숫자 없음 | XML fixture와 UI 비교 |
| AT05 | quote 1글자 변조·잘못된 offset·문서 hash 변경 | 승인 불가, `SOURCE_MISMATCH` | negative test |
| AT06 | image-only PDF, 병합 표, 암호 PDF | needs_ocr/needs_manual_review/failed, 무인용·무자동점수 변경 | fallback test |
| AT07 | 회사 문서 인용 승인 | document_only 유지; verified 배지 없음 | state assertion |
| AT08 | Northstar 계약A 이벤트만 승인 | qA resolved; B/검수/수금·독립성은 남음 | golden transition diff |
| AT09 | 동일 데이터 배열 순서 셔플, 100회 재계산 | 동일 raw score·tie order·digest | deterministic property test |
| AT10 | M/O 누락·0·경계값 | null은 3/2+provisional, 실제 0은 그대로 | table-driven test |
| AT11 | 동일 원본 중복·무관한 증빙 | 중복 카운트 없음, Top-3 불변 | negative control |
| AT12 | exact tie 및 표시 반올림만 같은 점수 | raw→M→G→O→canonical_key→ID | expected full ordering |
| AT13 | staging 후 미승인 또는 반려 | 기존 Snapshot 그대로 | before/after equality |
| AT14 | 동일 idempotency key 재전송 | 최초 결과 반환, commit 중복 없음 | DB count + response |
| AT15 | 현재 rev=2에서 base=1 승인 | `REVISION_CONFLICT`, 무쓰기 | transaction test |
| AT16 | commit 중간 강제 예외 | entity/snapshot/audit 전부 rollback | SQLite integration test |
| AT17 | Lumen 해결 질문에 승인된 반증 | renewal 재개, contradicted/disputed | golden transition diff |
| AT18 | export 승인 없음 또는 analyst-only actor | export 거부 | server service test |
| AT19 | export 승인 후 입력/필터/포함항목 변경 | 이전 승인 무효, 새 승인 요구 | digest-bound export test |
| AT20 | Demo에서 전 흐름 실행 | OpenAI/임베딩/외부 LLM network request 0 | network spy, outbound deny test |
| AT21 | Demo upload·임의 ID·점수·경로 주입 | 서버 차단, 사용자 파일 저장 0 | tampered callback test |
| AT22 | 두 브라우저 탭·서로 다른 Deal 동시 사용 | 한 탭의 승인/반려가 다른 탭에 영향 없음 | two-context Playwright test |
| AT23 | 개인 key를 설정한 Local Live 실행 | HTML/Store/URL/로그/export/git에 key 없음 | secret scan, response inspection |
| AT24 | 일간 budget 부족·동시 실행·timeout | 요청 전 차단/예약 원자적 처리, timeout 예약 유지 | budget integration test |
| AT25 | 3개 pack의 재무 장부 | revenue−COGS−OPEX=EBITDA; 고객합계·NWC 일치 | data invariants |
| AT26 | gold 접근 없이 모델 prompt 생성 | gold/expected 파일 내용 없음 | input allowlist + hash audit |
| AT27 | B0–B3, cache/live 구분하여 평가 | 실패·NA·분모·CI·seed/model/prompt 기록 | eval report |
| AT28 | 1440×900, 1280×720, 1024×768, 200% zoom | 행 선택·inspector·검토 접근, keyboard trap 없음 | keyboard + visual QA |
| AT29 | Demo 프로세스 재시작·로컬 앱 재시작 | Demo는 fixture replay/reset; 로컬은 DB 보존 | restart test |
| AT30 | 각 Chunk 종료 | 명령·exit code·pass/fail·diff·미완료 기록 | implementation evidence file |

## 입력과 출력의 제한

Local Live의 초기 상한: 문서 10개/Deal, 10 MiB/파일, 전체 50 MiB, PDF 50쪽·PPTX 50장·DOCX 100,000자/파일, 추출 text 300,000자/Deal. 제한을 넘기면 파일을 부분 분석한 듯 표시하지 않고 명시적으로 거절한다. parser worker timeout 20초/파일, 압축 해제 총 100 MiB, XML external entity 비활성화, macro/암호/중첩 OOXML 복잡도 초과를 거절한다. 이 값은 제품 정책이며 처리 성능 실측값이 아니다.

기본 export의 열 순서는 `rank, question_id, issue, request_text, financial_driver, gap, materiality, obtainability, score, provisional, workflow_status, owner_label, source_references, unresolved_notes, snapshot_id`다. UTF-8 CSV와 XLSX는 같은 행·값을 사용한다. 서버는 단위·순위·자릿수를 고정하고 수식 주입 문자열을 escape한다. Markdown memo는 Deal/기간/합성 여부, Thesis, Top-3, 지지·반증, 미확인 사항, 변경 요약, 원문 reference, 승인 Snapshot을 포함한다. 외부 발송은 하지 않는다.

## 오류와 상태 계약

사용자 메시지는 문제·영향·다음 행동을 한 문장씩 제시한다. `SOURCE_MISMATCH`, `UNSUPPORTED_FORMAT`, `NEEDS_OCR`, `PARSER_TIMEOUT`, `REVISION_CONFLICT`, `DUPLICATE_EVENT`, `APPROVAL_REQUIRED`, `BUDGET_EXCEEDED`, `PRICING_UNVERIFIED`, `PROVIDER_TIMEOUT`, `DEMO_ACTION_NOT_ALLOWED`를 안정적인 error code로 사용한다. Stack trace·key·문서 전체를 화면과 일반 로그에 노출하지 않는다. 원문 매칭 실패를 LLM 재질문으로 억지 통과시키지 않는다.

## Done 판정

모든 안전·정합성 Gate는 통과해야 한다. UX 개선항목과 optional panel은 미완료로 남길 수 있다. 학술 목표 미달은 제품 동작을 숨길 이유가 아니며 결과표에 그대로 보고한다. 특정 Gate를 실행하지 못했다면 `not_run`과 차단 원인을 기록한다. 자동테스트 성공만으로 실제 시연·읽기 쉬움·독립 gold 검토를 대신하지 않는다.

# Implementation Plan

Contract 1.0.0 · 2026-11-03~12-11, 평일 약 2시간. 29 weekday=58시간에서 계획 48시간, 버퍼10시간.

| Chunk | 기간 | 계획시간 | 반드시 남길 결과 |
|---|---|---:|---|
| 1 Foundation | 11/03–11/06 | 8 | strict models, source validator, SQLite transaction boundary, OS lock·CI |
| 2 Core Engine | 11/09–11/13 | 10 | deterministic scoring, reviewer commit, snapshots, no-op/reopen |
| 3 Synthetic Data & Evaluation | 11/16–11/20 | 10 | native 3-format files, frozen gold, baseline/eval runner |
| 4 Dash UI | 11/23–11/27 | 10 | Matrix/source/review, Top-3 comparison, keyboard/responsive |
| 5 Integration & Release | 11/30–12/04 | 10 | Live budget boundary, export approval, demo deploy smoke, real eval report |
| Buffer / submission | 12/07–12/11 | 10 | 결함 수정, 영상, portfolio, 제출 패키지 |

개인 일정상 공휴일을 쉬면 available hours가 줄어든다. 필수 범위를 추가하기 전에 이 예산을 갱신한다. 12/14는 최종 제출 예비일로 두며 그날 핵심 구현을 시작하지 않는다.

## 각 Chunk의 입출력과 Gate

정확한 구현 지시와 명령은 [PROMPTS](PROMPTS/00_ORCHESTRATOR.md)에 있다. 각 Chunk는 앞 단계의 실행 로그를 읽고 실패 Gate를 이어서 해결한 뒤 진행한다. 완성되었다는 설명만으로 넘어가지 않는다.

| Gate | 조건 | 실패 시 |
|---|---|---|
| G1 | 모델/Schema parity, 정상·음성 입력, referential validator, transaction rollback, lock smoke | UI로 우회하지 않고 계약부터 수정 |
| G2 | 세 transition·중복·미승인·충돌·tie/null·idempotency 재현 | formula/expected를 임의 변경 금지 |
| G3 | 실제 PDF/DOCX/PPTX quote locator·재무일치·gold 분리·eval dry-run | 미지원 구조를 명시하고 단순 지원 파일부터 완성 |
| G4 | 실제 callbacks, 두 탭 분리, source 정확성, focus/zoom | 장식·optional 페이지 제거 |
| G5 | export·비용·무API·재시작·공개 demo·평가 결과/한계 | blocked 기능은 명시, false release 금지 |

## 작업 단위

2시간 단위로 15분 이전 실패 확인, 75분 구현, 20분 해당 Gate 실행, 10분 diff·기록을 기본으로 한다. 작은 vertical slice가 동작하면 그 계약을 고정하고 다음 구간으로 간다. synthetic input을 hard-code한 UI screenshot을 동작 완료로 인정하지 않는다. fixture adapter는 명시적으로 이름 붙이고 실제 engine을 호출해야 한다.

## 위험과 scope reduction

| 위험 | 조기 신호 | 대응 |
|---|---|---|
| 파서/표 지원이 시간을 소모 | 2회 동일 구조 실패 | 단순 native text/table만 지원, 나머지 manual-review |
| UI 버전 충돌 | G1 component import/render 실패 | DMC 도입 금지, 검증된 pin 조합 고정 |
| Live API/가격 미준비 | G3 종료 시 credentials/pricing 불명 | Demo 계속 완성, Live 상태를 미검증으로 기록 |
| 합성 평가가 답안을 외움 | gold/expected context 감지 | loader allowlist와 arm input dump 검사 |
| 무료 hosting 신뢰성 | cold start/배포 실패 | 유료 대안 견적 또는 local video, 공개 배포 미완료 표시 |
| 시간이 8시간 이상 초과 | Chunk 3 이후 잔여 예산 부족 | Bayesian/좌표강조/OCR/임베딩/독립 페이지 순으로 제거 |

마감 산출물: repo와 lock, 테스트·실패 로그, 실제 eval 결과, 공개 synthetic demo(혹은 배포 차단 원인), 3–5분 시연 영상, 짧은 portfolio. 영상은 초기 Top-3→원문→staged 계약→승인→변경 이유→negative control→승인 export→Demo API0 순서다. 성능과 시간 절감 효과를 측정하지 않았으면 수치를 쓰지 않는다.

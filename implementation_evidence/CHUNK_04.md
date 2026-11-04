# Orion Deal Intelligence 2.0 — Chunk 4 구현 및 검증 보고서

작성일: 2026-11-04 · 실행 환경: Linux / Python 3.12.14 / Chromium 141

## 결과

사용자가 제공한 `orion-deal-intelligence-main.zip`에 Chunk 4 Dash 웹 애플리케이션을 통합했습니다. 원래 Core Engine, Bayesian/EIG, 합성 자료, 평가 harness, 기존 테스트, `spec/`, dependency lock, `.gitattributes`, 기존 `ci.yml`의 내용은 보존했습니다. GitHub Push·Pull Request·Merge·원격 CI 실행·공개 배포는 수행하지 않았습니다.

| 검증 | 실제 관측 결과 |
|---|---|
| 변경 전 기존 전체 테스트 | 1,064 passed / 294.09초 |
| 최종 전체 회귀 테스트 | 1,124 passed / 실패 0 / 생략 0 / 130.61초 |
| 새 웹 테스트 | 60개, 최종 전체 실행에 포함 |
| 기존 명세 무결성 | 원본 checksum 46개 검증 통과 |
| 의존성 정합성 / Python 컴파일 | pip check, compileall 종료 코드 0 |
| 실행 진입점 | `python -m orion.app` 실행, health·HTML·layout·dependencies·CSS 응답 200 |
| 실제 브라우저 | Northstar T1–T4, 반려·초기화, 제조업·Lumen, 브라우저와 탭 격리, 키보드 선택, 파일 다운로드 통과 |
| 실제 내보내기 | 원본 문서 SHA-256 일치, XLSX·DOCX 다운로드 확인, CSV/XLSX 계약 열·값 일치 |
| 문서 시각 검증 | Northstar T4 Word 메모 9쪽 렌더링·전 페이지 확인, Excel 렌더링 및 숫자 타입 확인 |
| 화면 검증 | 1440×900, 1280×720, 1024×768, 720×450 재배치 확인 |

검증 명령은 `python scripts/validate_chunk04.py --require-browser`입니다. 원시 로그와 JUnit, 명령별 종료 코드는 `implementation_evidence/logs/chunk04-*.log`, `chunk04-pytest.xml`, `chunk04-validation.json`에 있습니다. 검증 실행 시 `ORION_SCREENSHOT_DIR=implementation_evidence/screenshots`를 설정했습니다.

## 유일한 코드 기준본과 보존

- 기준본: `orion-deal-intelligence-main.zip` (원본 파일 662개)
- ZIP SHA-256: `11f1308464faaa72eaf8ccf8b4736c35841ffbb4d492ba0ade572e3f3f9fd1fe`
- 이전 Chunk 3 ZIP의 코드를 섞거나 GitHub에서 다른 코드를 가져오지 않았습니다.
- 기존 파일 중 기능 관련 변경은 `README.md`와 `pyproject.toml`뿐입니다. 버전은 0.4.0, 실행 명령은 `orion-web`, 웹 정적 자산의 패키지 포함 설정을 추가했습니다.
- 배포 목록·트리·checksum 세 파일은 통합 패키지에 맞춰 갱신했습니다. 나머지 기존 657개 파일은 원본과 바이트 단위로 같습니다.
- 기존 CI 파일을 유지하고, Chromium과 전체 테스트를 실행하는 별도 `.github/workflows/chunk04-web.yml`을 추가했습니다. 이 파일의 원격 실행 결과는 아직 없습니다.
- 전체 변경 원문은 `implementation_evidence/chunk04-source.patch`에 있습니다. Git 기록의 baseline commit은 이 작업 환경에서 ZIP을 기준으로 만든 로컬 비교 지점이며 GitHub commit이라고 주장하지 않습니다.

## 구현 구조

| 경로 | 실제 역할 |
|---|---|
| `src/orion/app.py` | Dash 앱 팩토리·실행 진입점, same-origin 요청 검사, 브라우저 세션 nonce, Demo 경계 |
| `src/orion/web/` | 7개 탐색 영역, AG Grid Community, Plotly 차트, source inspector, review·export callbacks, 반응형 CSS·키보드 동작 |
| `src/orion/services/web_workspace.py` | 서명된 탭별 행동 이력 검증, 원문 검증·기존 전이 엔진 재생, 읽기용 화면 데이터, 변경 비교·확률 시나리오 |
| `src/orion/services/export.py` | 검토한 상태에 묶인 승인, DD CSV/XLSX·증빙 CSV·메모 Markdown/DOCX 생성 |
| `tests/web/` | 브라우저·HTTP·승인 경합·내보내기·서비스 경계 회귀 테스트 |
| `docs/` | 한국어 설치·사용 안내, 5–7분 시연, 구조·한계 설명 |

Demo는 기존 설계에 따라 방문자 SQLite를 만들지 않습니다. 웹 승인 경로는 `ReviewService`가 사용하는 `apply_approved_update`, `assert_current_state`, 원문 검증을 재사용합니다. SQLite 기반 ReviewService 자체를 수정하거나 브라우저에 노출하지 않았으며, 기존 원자적 transaction·rollback 검증은 원래 테스트로 계속 확인합니다. 웹 경로는 재생·검증이 모두 성공해야 새 토큰을 반환하므로 중간 실패가 현재 토큰의 상태를 덮어쓰지 않습니다.

화면이 보내는 것은 허용된 사례·이벤트 ID·행동·검토 사유와 서명된 이력입니다. actor, 점수, 출처 해시, 원문, revision 전이는 서버가 결정합니다. 원문 다운로드는 현재 상태에 포함된 문서 ID만 허용하고 원본 bytes의 해시를 다시 검사합니다. 평가용 gold와 미래 문서를 현재 분석 결과로 노출하지 않습니다.

## 사용자 흐름과 실제 연결

1. **Deal overview**: 실제 기업 개요·문서 수·투자 thesis·열린 질문·미해결 claim과 현재 revision 표시.
2. **Evidence explorer**: 증거·주장 표에서 정확한 인용문, DOCX 구조/PDF 페이지/PPTX 슬라이드 locator와 관련 질문 확인.
3. **Investment thesis**: 주장·counter-thesis·증빙 상태·materiality·재무 driver·남은 검증 조건 확인.
4. **Adaptive DD matrix**: 기존 canonical 순위·점수, gap/materiality/obtainability, 선택 가능한 보조 열, 조회용 정렬·필터. 셀에서 점수를 변경하지 않습니다.
5. **Analyst review**: 미승인 preview와 원문을 검토한 뒤 승인/반려, 실제 before/after와 감사 이력 표시.
6. **Adaptive analytics**: 기존 엔진의 prior/posterior와 확률 가정 출처, binary answer distribution·EIG bits·별도 시나리오 비교 표시. 확률 입력이 없는 사례는 unavailable.
7. **Screening & export**: 화면에 표시된 token·revision·snapshot·형식을 확인한 뒤 서명된 승인 receipt를 만들고 다운로드. 다운로드 시 새 상태를 자동 승인하지 않습니다.

Northstar 심화 사례는 `nb_update_t1`부터 `nb_update_t4`까지 실행하여 revision 5에 도달합니다. T1 계약, T2 검수·청구·수금, T3 원가·공헌이익, T4 소유관계·대사를 실제 데이터와 연결했습니다. **T3에서는 Top-3가 유지되지만 하위 원가 확인 질문은 해결될 수 있어 전체 순위가 같다고 표현하지 않습니다.** 반려·중복 요청은 전체 authoritative 순위를 유지합니다. 제조업은 실제 존재하는 T1만, Lumen은 실제 반증에 따른 질문 재개만 사용합니다.

Canonical 점수 `P = 9G + 8M + 3O`는 그대로입니다. EIG를 이 점수에 더하지 않았으며, 다음 허용 증빙의 EIG는 별도 미승인 가상 시나리오로 표시합니다. 각 확률은 명시된 합성 가정에 따른 계산이며 실증 투자 성공확률이나 EVSI가 아닙니다. 재무 driver는 정성적 매핑이며 DCF·가치 민감도 모델을 추가하지 않았습니다.

## Export 계약과 검토 통제

DD CSV/XLSX의 앞 15개 열은 원래 계약 순서 그대로입니다: `rank, question_id, issue, request_text, financial_driver, gap, materiality, obtainability, score, provisional, workflow_status, owner_label, source_references, unresolved_notes, snapshot_id`. 추가 검토·근거 열은 그 뒤에 둡니다. 수식 주입 문자열을 escape하고 숫자 셀은 숫자로 보존합니다.

메모는 기업·가설·상위 요청·지지/반증·미확인 사항·정성적 재무 영향·원문·감사 이력을 포함합니다. 미승인·회사 보고·상충 상태를 검증 완료로 바꾸지 않습니다. 문서에 합성 자료 기반의 preliminary screening이며 완료된 FDD가 아님을 표시합니다. 문서 길이는 증빙 수에 따라 달라지며 전체 원문 근거를 포함합니다.

상태·형식 변경과 승인 체크박스 해제 시 이전 consent를 무효화합니다. 동일 revision이 유지되는 반려/초기화도 표시 token의 일치 여부로 구분합니다. 해당 경합에 대한 실제 HTTP callback 테스트 6개를 추가했습니다.

## 시각 검증과 보완

실제 화면 캡처는 `implementation_evidence/screenshots/01_...png`부터 `10_...png`까지입니다. 생성된 디자인 목업이 아닙니다. 표의 질문 열 최소 너비와 숫자/제목 열을 넓혀 단어가 여러 줄로 쪼개지는 문제를 수정했습니다. 긴 원문은 첫 발췌와 펼치기로 나누고 `Review update` 바로가기를 추가했습니다. 글자 크기 14px 이상, 명시적 상태 문구, focus 표시, Tab/방향키/Enter/Escape 동작을 확인했습니다.

720×450 검증은 1440×900 화면의 200% 확대에 대응하는 CSS 재배치 검증입니다. Headless Chromium의 확대 단축키가 실제 zoom을 바꾸지 않아 **실제 브라우저 200% 확대를 시험했다고 주장하지 않습니다.**

## 알려진 한계와 후속 범위

- 실제 Windows Python·브라우저 실행은 하지 않았습니다. Windows용 기존 hash lock과 한국어 명령을 보존·제공했습니다.
- 공개 배포, 실제 LLM 추출/질문 생성, 실제 B0–B3 benchmark, Local Live UI/업로드/비용 예약은 미구현 범위로 유지합니다. `ORION_MODE=local_live` 웹 시작은 명시적으로 거절합니다.
- 기존 authored fixture와 합성 확률 계산을 실제 모델 성능 또는 독립 전문가 검증으로 보고하지 않습니다.
- 서명된 과거 토큰은 재현 가능한 Demo branch입니다. 서버에 영구 저장되는 다중 사용자 revision lock·조직 인증·영구 서명 원장을 제공하는 것은 아닙니다.
- 검토/감사 시각은 동일 입력의 정확한 재실행을 위한 **합성 이벤트 기준 시각**입니다. 실제 사용자의 클릭 시각·인증된 실사 승인 시각이 아닙니다.
- Reset·새로고침·서버 재시작은 임시 Demo 진행을 초기화할 수 있습니다. 앱은 전체 소스 트리의 합성 원문 파일을 사용하므로 ZIP 안의 폴더 구조를 유지해 실행해야 합니다.
- 원본 native 문서 파일을 다운로드할 수 있지만 DOCX 페이지나 PDF bbox를 시각적으로 렌더링해 정확히 강조하는 기능은 구현하지 않았습니다. 검증된 locator·추출문을 보여줍니다.

## 실행

압축을 해제하고 `pyproject.toml`이 있는 폴더에서 한국어 안내 `docs/ORION_WEBAPP_USER_GUIDE.md`를 따라 Python 3.12 가상환경과 해당 OS의 lock을 설치합니다. 설치 후 `python -m orion.app`을 실행하고 `http://127.0.0.1:8050`을 엽니다. GitHub 반영은 사용자의 별도 로컬 환경에서 수행합니다.

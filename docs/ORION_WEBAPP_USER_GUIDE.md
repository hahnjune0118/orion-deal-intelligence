# Orion 웹 앱 사용 안내

이 안내는 Chunk 4 통합 소스의 로컬 합성 데모를 대상으로 합니다. 실제 원문 자료를 확인하고, 증빙을 승인 또는 반려하고, 기존 엔진이 계산한 실사 질문 우선순위를 비교하는 작업대입니다. 실시간 LLM 추출, 실제 기업 투자 판단, 공개 서버 배포를 완료했다는 의미는 아닙니다.

## 1. Windows 11 설치

Python **3.12**와 PowerShell을 사용합니다. ZIP을 압축 해제한 뒤 `pyproject.toml`, `requirements-win.lock`, `src` 폴더가 함께 있는 프로젝트 루트에서 아래 명령을 실행합니다. 기존 가상환경은 ZIP에 포함하지 않습니다.

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-win.lock
.\.venv\Scripts\python -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python -m pip check
```

첫 설치에는 패키지 다운로드를 위한 인터넷 연결이 필요합니다. 설치 뒤 합성 데모는 API 키 없이 실행할 수 있습니다. `requirements-win.lock`의 버전과 해시를 그대로 사용하고, 설치 문제를 해결하기 위해 임의로 최신 패키지로 올리지 않습니다. PowerShell 활성화 스크립트 없이 가상환경의 Python을 직접 호출하므로 실행 정책을 변경할 필요가 없습니다.

이 문서의 Windows 명령은 사용 절차입니다. Linux 검증 결과를 Windows 실행 결과로 간주하지 않습니다. 실제 실행 환경과 검증 범위는 `implementation_evidence/CHUNK_04.md`를 확인하세요.

## 2. 앱 시작과 종료

프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
$env:ORION_MODE = "demo"
.\.venv\Scripts\python -m orion.app
```

브라우저에서 `http://127.0.0.1:8050`을 엽니다. 서버가 실행된 터미널은 열어 둡니다. 종료할 때는 해당 터미널에서 `Ctrl+C`를 누릅니다. 다시 시작할 때는 설치를 반복하지 않고 같은 실행 명령을 사용합니다.

8050을 다른 프로그램이 사용한다면 포트를 바꿔 실행할 수 있습니다.

```powershell
$env:ORION_PORT = "8051"
.\.venv\Scripts\python -m orion.app
```

이때는 `http://127.0.0.1:8051`로 접속합니다. 기본 포트로 돌아가려면 `$env:ORION_PORT = "8050"`으로 설정합니다.

## 3. 분석 화면 사용

왼쪽 `Investment opportunity`에서 사례를 선택합니다. 기본 사례는 심화 합성 사례 `Northstar Analytics`입니다. 기존 Foundation의 `ns`와 구별되는 `nb` 자료를 사용합니다. `Manufacturing case`는 제조업 재고 증빙, `Lumen · conflict review`는 반증에 따른 질문 재개를 보여줍니다. 실제 자료 수집이 미완료인 공개 Orion 사례는 완성된 분석 사례로 제공하지 않습니다.

| 화면 메뉴 | 할 수 있는 일 |
|---|---|
| `Deal overview` | 기업 개요, 문서 수, 투자 가설, 열린 질문과 증빙 상태 확인 |
| `Evidence explorer` | 근거와 주장 표에서 행을 선택하고 출처·충족 상태 확인 |
| `Investment thesis` | 가설, 반대 가설, 재무 영향과 남은 검증 요건 확인 |
| `Adaptive DD matrix` | 계산 순위, 점수, 증빙 부족, 중요도, 확보 가능성 및 요청 문서 확인 |
| `Analyst review` | 증빙 이벤트, 승인·반려 기록과 최신 순위 변경 확인 |
| `Adaptive analytics` | 가정에 따른 Bayesian/EIG 계산과 순위 전후 비교 확인 |
| `Screening & export` | 현재 상태를 검토하고 DD 목록·증빙 목록·예비 검토 메모 다운로드 |

현재 Top-3는 중앙 상단 `Priority watchlist`에 표시됩니다. 문서 선택 또는 표의 행 선택으로 오른쪽 `Source inspector`에 출처를 엽니다. 정확한 발췌문과 native locator를 확인하며, 이 화면은 원본 문서 편집기나 PDF 좌표 기반 강조 기능을 제공하지 않습니다.

원본 파일을 열어 보려면 왼쪽 `SOURCE LIBRARY`에서 현재 이용 가능한 문서를 고른 뒤 `Download original source`를 누릅니다. 서버가 원본 해시를 확인한 파일을 내려받습니다. 아직 승인되지 않아 현재 작업대에 없는 미래 문서는 이 목록에서 다운로드할 수 없습니다.

표 머리글을 선택하면 화면 정렬을 바꿀 수 있습니다. 열별 필터와 너비 조절은 조회용입니다. `Rank` 열은 여전히 엔진의 계산 순위이며 점수나 증빙을 셀에서 직접 수정할 수 없습니다. Tab으로 주요 조작 영역을 이동하고, 표 안에서는 방향키로 이동합니다. 화면이 좁거나 확대되어 있으면 아래쪽에 배치된 출처·검토 영역까지 스크롤합니다.

## 4. 증빙 검토와 순위 비교

1. `Analyst review`를 선택하고 오른쪽 `Synthetic evidence event`의 다음 이벤트를 확인합니다.
2. 이벤트 설명과 `Original source`를 펼쳐 해당 발췌문·원문 위치를 읽습니다. 미리보기는 아직 승인된 결과가 아닙니다.
3. `Review note`에 판단 이유를 기록합니다.
4. 반영하려면 `Approve update`, 반려하려면 `Reject update`를 누릅니다.
5. `Latest committed ranking comparison`과 `Immutable review history`에서 결과를 확인합니다. 상단 Top-3와 `Adaptive DD matrix`도 같은 승인된 상태를 사용합니다.

반려 또는 승인 전 미리보기는 현재 순위를 바꾸지 않습니다. 순위가 그대로여도 증빙 상태나 충족한 요건이 바뀔 수 있으므로 변경 이유를 함께 읽습니다. 같은 이벤트를 반복 클릭해도 두 번 적용되지 않습니다. 오래된 상태 오류가 표시되면 최신 Snapshot을 확인한 뒤 다시 검토합니다. 순차 이벤트를 반려하면 그 진행 경로는 종료되므로, 다른 결정을 시도하려면 `Reset demo`를 사용합니다.

검토·감사 이력의 시각은 각 합성 이벤트의 기준 시각으로부터 정해진 재생 시각입니다. 같은 진행을 재현하기 위한 값이며 실제 사용자가 클릭하거나 서명한 시각, 인증된 조직 검토자의 승인 기록을 뜻하지 않습니다.

왼쪽 `Reset demo`는 해당 작업대의 진행을 초기 상태로 되돌립니다. 새로고침도 메모리에 있던 진행을 초기화합니다. 데모는 작업 이력의 장기 저장용이 아니므로 필요한 보고서는 종료 전에 내보냅니다. 서로 다른 탭과 브라우저 세션은 독립적인 데모 진행을 갖습니다.

## 5. 결과 내보내기

`Screening & export`에서 현재 질문과 미확인 사항을 확인한 뒤 다음 순서로 진행합니다.

1. `Document format`에서 파일 형식을 선택합니다.
2. `I reviewed this snapshot and approve this export.`를 체크합니다.
3. 표시된 revision의 승인이 준비되었다는 `Ready to download` 안내를 확인합니다.
4. `Approve & download`를 누릅니다.
5. 브라우저가 받은 파일의 Snapshot과 검토 상태를 확인합니다.

| 형식 선택 | 결과 |
|---|---|
| `DD Request List · Excel` | `.xlsx` 실사 요청 목록 |
| `DD Request List · CSV` | `.csv` 실사 요청 목록 |
| `Evidence Register · CSV` | `.csv` 증빙 목록 |
| `Screening Memo · Word` | `.docx` 예비 투자 검토 메모 |
| `Screening Memo · Markdown` | `.md` 예비 투자 검토 메모 |

내보내기 승인은 화면에 표시된 Snapshot과 출력 선택에 적용됩니다. 화면이 갱신 중이면 승인이 만들어지지 않으므로 갱신을 마친 결과를 읽고 체크를 다시 수행합니다. 증빙 상태나 형식을 변경한 뒤에도 변경된 결과를 다시 검토하고 승인합니다. 화면의 표 정렬·필터를 별도 Export 선택 기능으로 간주하지 않습니다. 파일은 서버의 검증된 상태로 생성하며 외부 LLM을 호출하지 않습니다. 내보내기 승인도 최종 투자 승인을 뜻하지 않습니다.

파일명에는 사례와 revision이 들어갑니다. 예를 들어 Northstar revision 2의 Excel은 `deal_nb_dd_xlsx_r2.xlsx`입니다. 브라우저가 같은 이름의 파일에 번호를 덧붙일 수 있으므로, 파일 안의 Snapshot과 승인 정보를 기준으로 구별합니다.

## 6. 화면의 숫자와 상태 읽기

| 표시 | 의미 |
|---|---|
| DD 우선순위 점수 | 기존 제품 공식 `9 × 증빙 부족(G) + 8 × 중요도(M) + 3 × 확보 가능성(O)`으로 계산합니다. |
| 계산 순위 | 서버의 현재 승인된 Snapshot에 저장된 순위입니다. 표의 정렬이나 필터는 이를 변경하지 않습니다. |
| EIG | 가상의 확률 가정에서 계산한 기대 정보 획득량입니다. 단위는 bits이며 제품 우선순위 점수와 별개입니다. |
| Prior / Posterior | 명시된 이진 시나리오와 가능도 가정에 대한 사전·사후 확률입니다. 실제 투자 성공확률이 아닙니다. |
| Supported / Partial / Missing / Contradicted | 질문 또는 주장의 정의된 증빙 요건을 얼마나 충족하는지 나타냅니다. |
| Approved / Rejected | 분석가의 검토 결정입니다. 문서 내용 자체의 현실 진실성을 보증하지 않습니다. |
| Document only | 문서에 해당 내용이 있음을 확인한 상태입니다. 독립적인 사실 확인과 구별합니다. |
| Unavailable | 계산에 필요한 가정이나 입력이 없습니다. 0이나 완료 결과로 해석하지 않습니다. |

PDF는 페이지·추출 단위, PPTX는 슬라이드·도형·문단, DOCX는 문단 또는 표 셀의 구조 위치로 원문을 확인합니다. DOCX에 존재하지 않는 페이지 번호를 만들지 않습니다. 추출 문장의 강조와 원본 파일의 시각적 위치 강조는 다릅니다.

## 7. 테스트 실행

프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python -m pytest -q --strict-markers
```

브라우저 테스트에는 Playwright용 Chromium이 추가로 필요합니다. 최초 다운로드에는 인터넷 연결이 필요합니다.

```powershell
.\.venv\Scripts\python -m playwright install chromium
$env:ORION_REQUIRE_BROWSER = "1"
.\.venv\Scripts\python -m pytest tests/web/test_browser.py -q --strict-markers
```

브라우저 테스트는 임시 loopback 포트에서 자체 서버를 시작합니다. `ORION_REQUIRE_BROWSER=1`은 Chromium이 없을 때 조용히 건너뛰지 않고 실패하게 합니다. 테스트의 통과·실패·미실행 결과는 실제 출력으로 확인합니다. 예전 Chunk의 테스트 개수나 smoke 테스트만으로 이번 UI 검증 완료를 판단하지 않습니다.

## 8. 문제 해결

| 증상 | 확인 및 조치 |
|---|---|
| `py -3.12`를 찾지 못함 | Python 3.12 설치 여부와 Windows Python Launcher를 확인합니다. 다른 버전으로 우회하지 않습니다. |
| `No module named orion` | 프로젝트 루트에서 위의 editable 설치 명령을 실행했는지, 가상환경 Python을 사용했는지 확인합니다. |
| Dash 또는 AG Grid 모듈 없음 | 해당 운영체제의 전체 hash lock 설치와 `pip check`를 다시 확인합니다. |
| 해시 불일치 또는 설치 실패 | 오류에 표시된 패키지·버전·네트워크 문제를 확인합니다. `--require-hashes`를 지우거나 lock을 임의 수정하지 않습니다. |
| 브라우저 연결 안 됨 | 서버 터미널이 종료되지 않았는지와 출력된 주소를 확인합니다. 앱이 실행되기 전 브라우저만 열면 접속되지 않습니다. |
| 8050 포트가 이미 사용 중 | 같은 앱을 두 번 실행했는지 확인하고 기존 서버를 종료한 뒤 다시 실행합니다. |
| 자료 또는 원문 검증 오류 | ZIP을 부분 복사하지 않았는지 확인합니다. `spec`, `data`, `chunk3_synthetic_evaluation`을 포함한 전체 폴더를 유지합니다. |
| 브라우저 테스트가 Chromium을 찾지 못함 | 같은 가상환경에서 Playwright Chromium 설치 명령을 실행합니다. |
| Live 모드 또는 업로드가 차단됨 | 이번 웹 데모의 지원 범위를 벗어납니다. Demo 모드로 실행합니다. |

## 9. 제공 범위

데모 자료는 허구의 기업·고객·문서이며, 문서와 검토 결과는 예비 투자 검토 교육용입니다. 실제 FDD 완료 보고서나 투자 승인으로 표현하지 않습니다. 실제 LLM 실행과 B0–B3 모델 성능 실험은 이 결정론적 데모 실행과 별개입니다.

GitHub 반영은 별도 로컬 환경에서 수행합니다. 이 사용 절차는 GitHub push, Pull Request 또는 merge를 실행하지 않습니다.

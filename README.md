# Orion Deal Intelligence — 규칙 기반 Adaptive DD MVP

현재 기본 화면은 **자료 분석 → 가설 검토·확정 → 질문 생성 → 중요도 평가 → 새 증거 반영**의 5단계입니다. 한국어 질문 라이브러리와 Python 규칙으로 동작하며 OpenAI API·로컬 LLM·API 키가 필요하지 않습니다. 등록 원본과 검토 기록은 이 PC의 `.local/orion-rules/projects.sqlite3`에 저장합니다.

기존 환경이 설치되어 있다면 다음 명령으로 시작합니다.

```powershell
.\.venv\Scripts\python -m orion.app
```

브라우저에서 **http://127.0.0.1:8050**을 엽니다. 새 프로젝트에 자료를 올리거나 **합성 검증 사례 열기**로 계산 예시를 확인하세요. 실제 프로젝트의 확률·EIG·EVSI는 근거와 가정을 직접 설정할 때만 계산합니다.

- [새 MVP의 사용 방법·계산 정책·지원 범위](docs/RULE_BASED_MVP_20261118.md)
- [익명화 딜 사례 열기·EIG/EVSI 실습](docs/CASE_STUDIES.md)
- [원래 MVP 설계안](docs/ORION_ADAPTIVE_DD_MVP_BLUEPRINT_20261118.md)

기존 FDD 화면과 차트는 보존했습니다. 아래 명령으로 별도 포트에서 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python -m orion.app --legacy --port 8051
```

아래 Chunk 4 설명은 **보존된 기존 Dash 앱**의 설명입니다. 해당 앱은 합성 자료 검토용이며 새 MVP와 데이터 저장소가 다릅니다.

## 보존된 Chunk 4 Dash Workbench

Python 3.12 기반 Chunk 1–3에 **Dash + Dash AG Grid 분석 화면, 증빙 승인·반려, 전후 순위 비교, Bayesian/EIG 설명, 승인 후 보고서 내보내기**를 연결했습니다. 사용자 제공 `orion-deal-intelligence-main.zip`만 코드 기준본으로 사용합니다. 실제 LLM 호출, 공개 배포, 실제 B0–B3 모델 성능 측정은 이번 구현에 포함되지 않습니다.

## 웹 앱 시작

Windows PowerShell에서 이 README가 있는 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-win.lock
.\.venv\Scripts\python -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python -m orion.app --legacy --port 8051
```

브라우저에서 **http://127.0.0.1:8051**을 엽니다. Linux는 아래 기존 설치 절차 후 `.venv/bin/python -m orion.app --legacy --port 8051`을 실행합니다. 최초 패키지 설치 후 Demo는 API key 없이 오프라인으로 동작합니다. 웹 앱은 이 전체 소스 트리의 합성 원문 파일을 사용하므로 프로젝트 폴더를 유지해야 합니다. 과거 `artifacts/` wheel은 Chunk 1–3 보존 자료입니다.

- [한국어 설치·사용 안내](docs/ORION_WEBAPP_USER_GUIDE.md)
- [5–7분 시연 순서](docs/ORION_DEMO_WALKTHROUGH.md)
- [구조와 상태 관리](docs/UI_ARCHITECTURE.md)
- [구현·실행 검증 보고](implementation_evidence/CHUNK_04.md)

Northstar 심화 사례(`nb`)의 T1–T4, 제조업(`mf`), Lumen의 상충 증빙 사례를 사용할 수 있습니다. Demo의 검토자는 모의 역할이며, 기존 기관의 실제 권한이나 투자 승인을 뜻하지 않습니다. 브라우저 탭마다 서명된 행동 이력을 메모리에 보관하고 기존 엔진으로 재현합니다. 새로고침·초기화·서버 재시작 시 Demo 작업은 유지되지 않을 수 있습니다. Local Live 문서 업로드와 외부 AI 실행은 활성화하지 않습니다.

## 전체 회귀·브라우저 검증

```powershell
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python scripts/validate_chunk04.py --require-browser
```

브라우저 설치 없이 `python -m pytest -q --strict-markers`도 실행할 수 있으나, 이 경우 브라우저 시험이 생략되면 전체 UI 검증 통과로 해석하지 마세요. 검증 스크립트는 실제 명령·종료 코드·JUnit·원본 파일 보존 결과를 `implementation_evidence/`에 기록합니다. Windows 명령은 실행 안내이며 이번 작업의 실제 검증 운영체제는 보고서를 참조하세요.

## 기존 Chunk 1–3 설명과 CLI

아래는 기존 코드·CLI·데이터 계약에 관한 설명입니다. 과거 Chunk 보고서의 미구현 상태는 당시 기준이며, 현재 웹 기능 상태는 위 Chunk 4 보고서가 우선합니다.

기준은 `spec/`에 원본 그대로 보존한 Handoff 1.0.0입니다. Scoring Formula, Data Contracts, State Transition 및 기대값은 변경하지 않았습니다. Chunk 2 실행 결과와 한계는 [CHUNK_02.md](implementation_evidence/CHUNK_02.md), 기존 Foundation 증빙은 [CHUNK_01.md](implementation_evidence/CHUNK_01.md)에 있습니다. Chunk 3는 첨부 Chunk 2 코드에서 만든 로컬 `feature/chunk-03-synthetic-evaluation` 브랜치입니다. 원격 GitHub 접근·commit·push는 수행하지 않았습니다. [Chunk 3 기술 보고서](implementation_evidence/CHUNK_03.md)와 [통합 결정](implementation_evidence/CHUNK_03_INTEGRATION_DECISIONS.md)을 확인하세요.

## 설치와 실행

지원 Python은 **3.12**입니다. 프로젝트 폴더에서 실행합니다. 가상환경과 로컬 DB는 ZIP에 포함하지 않습니다. 최초 의존성 설치에는 패키지 저장소 연결이 필요하며, 아래 검증 명령은 API key 없이 실행됩니다.

Ubuntu / Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-linux.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -m orion.cli validate-fixture spec/EXAMPLES/initial_state.json
.venv/bin/python -m orion.cli seed-demo --case ns
.venv/bin/python -m pytest -q --strict-markers
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --require-hashes -r requirements-win.lock
.\.venv\Scripts\python -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m orion.cli validate-fixture spec/EXAMPLES/initial_state.json
.\.venv\Scripts\python -m orion.cli seed-demo --case ns
.\.venv\Scripts\python -m pytest -q --strict-markers
```

Windows용 lock은 별도 target으로 생성하고 wheel 확보를 검증했습니다. **이 작업 환경에서 Windows Python/pytest를 실행한 것은 아닙니다.** `.github/workflows/ci.yml`에 Windows/Ubuntu Python 3.12 검증이 준비되어 있으며 원격 CI 실행은 별도로 필요합니다.

## 구현한 기능

| 파일 | 역할 |
|---|---|
| `src/orion/domain/models.py` | 모든 계약 객체·envelope의 strict Pydantic 모델, 타입 변환·unknown field·비정상 값 차단 |
| `src/orion/domain/grounding.py` | ID/Deal/버전/참조, native locator, text-v1, 원문 SHA-256, code-point offset와 quote 검증 |
| `src/orion/adapters/parsers/` | bounded native PDF/DOCX/PPTX parsing, timeout worker, 원본 bytes 기반 locator 검증 |
| `src/orion/adapters/sqlite_repo.py` | WAL·FK, entity history, 원자적 revision, 중복 요청 처리, rollback, append-only snapshot/audit |
| `src/orion/config.py` | Demo 기본값, 업로드/Live/영속 상태 차단, Local loopback·Host/Origin 정책, 비용 설정 검증 |
| `src/orion/demo.py` | 합성 입력 allowlist, 요청별 독립 상태, 최대 32개 행동 검증, reset |
| `src/orion/domain/scoring.py`, `transitions.py` | Decimal 우선순위, 승인 요구조건, 충돌·해결·재개, canonical digest |
| `src/orion/services/review.py`, `workspace.py` | 서버 ActorContext, staging/승인/반려, 현재 Snapshot 검증 |
| `src/orion/cli.py` | fixture 검증, Demo seed, rank/replay, Local DB 초기화 |
| `tests/` | 계약·인용·실제 SQLite·Demo 보안·CLI·최소 Dash/Grid smoke |
| `requirements-*.lock`, `.github/workflows/ci.yml` | OS별 hash lock, 검사 도구 lock, CI |

`validate-fixture`는 `initial_state.json`, `staged_evidence_update.json`, `expected_top3_transition.json`을 지원합니다. 후자의 두 파일은 같은 폴더의 초기 상태와 staging 파일을 참조하며, `--base`와 `--update`로 명시할 수도 있습니다. **ExpectedTransition의 구조·참조만 검사하며 결과 순위를 실행하거나 제품 입력으로 사용하지 않습니다.**

```bash
.venv/bin/python -m orion.cli validate-fixture spec/DATASET_SPECS/lm/staged_evidence_update.json
.venv/bin/python -m orion.cli validate-fixture spec/DATASET_SPECS/cd/expected_top3_transition.json
.venv/bin/python scripts/verify_spec.py
```

오류는 종료 코드 `2`와 안전한 JSON 오류 코드로 반환합니다. 원문이나 키를 오류 출력에 포함하지 않습니다.

## 보안 및 검증의 의미

- 기본 Demo는 키가 환경에 있어도 Live adapter를 생성하지 않습니다. 업로드와 방문자 SQLite를 거절합니다. 서버가 받는 것은 합성 사례와 허용 event ID/행동뿐입니다.
- `seed-demo`와 기존 `replay_demo()`는 Foundation 호환성을 위해 seed/reset 전용 경계를 유지합니다. **승인/반려 엔진의 진입점은 `replay_reviewed_demo()`와 CLI `replay`입니다.** 양쪽 모두 영속 방문자 상태를 만들지 않습니다. 변경된 함수와 기존 fail-closed 테스트를 동시에 보존하기 위한 명시적 API 분리입니다.
- 예시 자료의 `fixture_text_only`는 계약 예시 텍스트입니다. 실제 PDF/DOCX/PPTX 인용 검증을 통과했다는 뜻이 아닙니다. Local 검증은 원본 bytes와 독립적인 native unit resolver를 요구하며 fixture를 거부합니다.
- `SourceResolver`는 서버 소유 parser/index adapter를 위한 인터페이스입니다. 브라우저가 돌려준 텍스트나 파일 경로를 resolver로 신뢰하면 안 됩니다.
- `SQLiteRepository`는 신뢰된 application service용 adapter입니다. actor 권한, 승인 결정 및 결정론적 상태 전이를 대신하지 않습니다. 원본 DB 파일의 소유자 변조까지 방지하는 공증 원장이 아닙니다.
- Local DB 초기화는 명시적 `ORION_MODE=local_live`에서만 허용합니다. 이 설정만으로 provider나 파일 업로드 기능이 활성화되지는 않습니다. 임의 사용자 업로드나 Live provider 실행은 아직 구현하지 않았습니다.
- 예산 값 검증은 구현했습니다. 실제 요청별 reserve/settle와 API 실행은 미구현이며, 우회 실행 대신 차단합니다.

## Core Engine 실행

```bash
.venv/bin/python -m orion.cli rank --state spec/EXAMPLES/initial_state.json
.venv/bin/python -m orion.cli replay --case ns --event staged --approve --output build/ns_after.json
.venv/bin/python -m orion.cli replay --case cd --event staged --approve --output build/cd_after.json
.venv/bin/python -m orion.cli replay --case lm --event staged --approve --output build/lm_after.json
.venv/bin/python -m pytest tests/core tests/transitions tests/integration -q --strict-markers
```

`replay`는 상태 JSON을 지정 경로에 저장하고 실제 변경 설명을 stdout JSON으로 반환합니다. `--reject` 또는 승인 옵션 없는 실행은 현재 순위를 유지합니다. 출력은 합성 fixture 텍스트 검증 결과이며 native parser 검증 결과가 아닙니다. `rank`는 현재 Snapshot의 digest·파생 상태·순위가 일치하는지 검사하며, 이 오프라인 명령은 Demo 상태만 받습니다.

| 사례 | 초기 Top-3 점수 | 승인 후 Top-3 점수 |
|---|---|---|
| Northstar | 100 / 97 / 89 | 97 / 89 / 86 |
| Cedar | 100 / 94 / 89 | 94 / 89 / 86 |
| Lumen | 92 / 89 / 84 | 97 / 92 / 89 |

`ReviewService(repo, ActorContext(...))`는 서버에서 생성합니다. 브라우저가 `actor_id`, `actor_role`, 점수·원문을 보내 승인을 위조할 수 없도록 `execute()`의 엄격한 DTO는 action/deal_id/event_id/expected_revision/idempotency_key/reason만 받습니다. `stage()`는 신뢰된 ingestion 경계이며 원본 검증을 다시 수행합니다. Local Live는 기존처럼 신뢰된 `SourceResolver`와 원본 bytes를 요구하고 fixture를 거부합니다.

기존 SQLite v1 DB를 `initialize()`하면 `staged_updates`, `staged_resolutions` 및 append-only trigger가 추가됩니다. 기존 entity, Snapshot, audit를 다시 쓰지 않습니다. staging/반려는 audit-only transaction으로 revision과 현재 Snapshot을 보존합니다. 승인은 하나의 `BEGIN IMMEDIATE`에서 entity versions, decision, Snapshot, audit, idempotency 결과를 함께 저장합니다. 예외 시 전부 롤백합니다.

`spec/`, 기존 680개 테스트, dependency lock은 원본 그대로 보존합니다. `artifacts/`의 0.1.0 wheel은 이전 Foundation 산출물이며, Chunk 2 사용은 소스 설치 또는 새 0.2.0 wheel을 사용하세요. 루트 CHECKSUMS/DELIVERY_FILES는 통합 패키지 기준으로 갱신되며 이전 파일은 Git baseline과 원본 ZIP에 남습니다.

Windows에서 반영할 때는 [WINDOWS_APPLY_CHUNK_02.md](implementation_evidence/WINDOWS_APPLY_CHUNK_02.md)를 참고하세요. GitHub commit/push는 사용자가 개인 PC에서 직접 수행합니다.

후속 범위: Live API·비용 예약, 공개 배포, 실제 모델 B0–B3 비교. 단위테스트 및 authored-fixture 성공은 학술 목표의 실제 모델 성능이 아닙니다. Dash·export·브라우저 격리는 Chunk 4 보고서를, Windows 실제 실행 여부는 해당 보고서의 한계를 참조하세요.


## Chunk 3 전체 실행

설치 후 프로젝트 루트에서 한 번에 재생성·검증·평가·전체 테스트를 실행합니다.

```bash
python scripts/validate_chunk03.py
```

개별 명령은 다음과 같습니다. 모든 명령은 합성 자료만 처리하며 API key가 필요 없습니다.

```bash
python -m orion.cli generate-synthetic --output data/synthetic
python -m orion.cli ingest --case all --mode demo
python -m orion.cli generate-dataset --output chunk3_synthetic_evaluation
python -m orion.cli validate-dataset
python -m orion.cli replay-scenario --case nb --output build/northstar.json
python -m orion.cli replay-scenario --case mf --output build/manufacturing.json
python -m orion.cli audit-model-inputs --cases all
python -m orion.cli evaluate --arms B0 B1 B2 B3 B1-R --cases all --mode cached
python -m pytest -q --strict-markers
```

| 경로 | 내용 |
|---|---|
| `data/synthetic/`, `data/parsed/` | 기존 세 사례의 12개 native 원본과 실제 파서 runtime pack |
| `chunk3_synthetic_evaluation/data/` | Northstar 심화 및 제조업 원문·structured 기록·업데이트, 공개 Orion pending manifest |
| `chunk3_synthetic_evaluation/gold/` | 평가 전용 정답·세계 가정·예상 전이. 모델 context에서 제외 |
| `src/orion/synthetic/` | 결정론 생성·금액 대사·단계별 입력·승인 시나리오 |
| `src/orion/quant/` | 가정 출처가 있는 Bayesian/EIG·중복 방지·별도 연구 순위·민감도 |
| `src/orion/evaluation/`, `evaluation/` | baseline 인터페이스·분모가 명확한 지표·prompt dump·fixture replay 결과 |
| `implementation_evidence/CHUNK_03.md` | 한국어 기술 보고서, 실제 결과와 미실행 항목 |

제품 점수는 `P = 9G + 8M + 3O`인 scoring 1.0.0을 그대로 사용합니다. Bayesian/EIG는 명시된 가상 확률 가정의 계산이며 실증 투자 성공확률이 아닙니다. 별도 연구 정책의 EIG 가중 결과를 제품 점수로 바꾸거나 EVSI로 부르지 않습니다.

`--mode live`는 모델 adapter가 준비되지 않았으므로 실제 호출하지 않습니다. 캐시의 provenance는 `authored-fixture`이고 실시간 extraction·독립 전문가 검증을 뜻하지 않습니다. Gold와 미래 원문은 단계별 source allowlist에 포함하지 않습니다. ZIP 전체를 LLM에 넣는 방식은 이 경계를 무너뜨리므로 `agent_visible_bundle`과 저장된 prompt dump를 사용하세요.

새 runtime dependency는 추가하지 않았습니다. 기존 Pydantic와 parser extras, Python 표준 라이브러리로 계산·생성을 수행합니다. NumPy/pandas 없이도 이 크기의 자료를 재현할 수 있도록 구성했습니다. 원본 OS별 hash lock은 그대로 보존합니다. 최신 코드는 소스 설치 또는 `artifacts/orion_deal_intelligence-0.3.0-py3-none-any.whl`을 사용하고, 0.1.0/0.2.0 wheel은 과거 호환성 증빙으로만 사용하세요.

Chunk 4의 실행 가능한 웹 진입점은 `python -m orion.app`입니다. 기존 source index·승인 전이·정량 엔진을 사용하며, 원래의 Core Engine과 평가 명령은 계속 사용할 수 있습니다.

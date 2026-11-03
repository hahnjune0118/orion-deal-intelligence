# Orion Deal Intelligence 2.0 — Chunk 1 + Chunk 2

Python 3.12 기반 Foundation에 Adaptive DD Core Engine을 통합했습니다. 승인된 증빙의 요구조건 충족·충돌·우선순위와 승인/반려 트랜잭션을 구현했습니다. **Chunk 3 이후의 native parser, 전체 Dash 앱, 평가·배포는 이번 범위에 포함하지 않습니다.**

기준은 `spec/`에 원본 그대로 보존한 Handoff 1.0.0입니다. Scoring Formula, Data Contracts, State Transition 및 기대값은 변경하지 않았습니다. Chunk 2 실행 결과와 한계는 [CHUNK_02.md](implementation_evidence/CHUNK_02.md), 기존 Foundation 증빙은 [CHUNK_01.md](implementation_evidence/CHUNK_01.md)에 있습니다. 첨부 코드에서 만든 로컬 `feature/chunk-02-core-engine` 브랜치이며 원격 GitHub 접근·commit·push는 수행하지 않았습니다.

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
| `src/orion/adapters/parsers/base.py` | parser interface와 미구현 시 명시적 차단 |
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
- Local DB 초기화는 명시적 `ORION_MODE=local_live`에서만 허용합니다. 이 설정만으로 provider나 파일 업로드 기능이 활성화되지는 않습니다. 아직 해당 기능이 구현되지 않았습니다.
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

미구현: native parser, 전체 Dash UI, export 승인·파일, Live API·비용 예약, 공개 배포, B0–B3 평가, 선택 Bayesian 패널. 단위테스트 성공은 학술 목표의 실측 성능이 아닙니다. 실제 두 브라우저 탭 검증과 Windows 실행은 이후 환경에서 별도 확인해야 합니다.

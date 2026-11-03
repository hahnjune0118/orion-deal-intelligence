# Orion Deal Intelligence 2.0 — Chunk 1 Foundation

실행 가능한 Python 3.12 Foundation 프로젝트입니다. 데이터 계약·원문 위치 검증·SQLite 저장·Demo 보안 경계를 구현했습니다. **전체 Dash 앱이나 순위 엔진은 아직 없습니다. Chunk 2 이후는 시작하지 않았습니다.**

기준은 `spec/`에 원본 그대로 보존한 Handoff 1.0.0입니다. Scoring Formula, Data Contracts, State Transition 및 기대값은 변경하지 않았습니다. 이번 실행 결과, 미검증 범위와 다음 작업은 [CHUNK_01.md](implementation_evidence/CHUNK_01.md)를 먼저 확인하세요.

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
| `src/orion/cli.py` | fixture 검증, Demo seed 로딩, Local DB 초기화 |
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
- `seed-demo`는 매번 새 seed를 읽고 검증합니다. 영속 상태를 만들지 않습니다. 현재 승인/반려 행동은 검증한 뒤 `FEATURE_NOT_IMPLEMENTED`로 차단합니다. **실제 승인·재순위 replay는 Chunk 2가 구현할 기능입니다.**
- 예시 자료의 `fixture_text_only`는 계약 예시 텍스트입니다. 실제 PDF/DOCX/PPTX 인용 검증을 통과했다는 뜻이 아닙니다. Local 검증은 원본 bytes와 독립적인 native unit resolver를 요구하며 fixture를 거부합니다.
- `SourceResolver`는 서버 소유 parser/index adapter를 위한 인터페이스입니다. 브라우저가 돌려준 텍스트나 파일 경로를 resolver로 신뢰하면 안 됩니다.
- `SQLiteRepository`는 신뢰된 application service용 adapter입니다. actor 권한, 승인 결정 및 결정론적 상태 전이를 대신하지 않습니다. 원본 DB 파일의 소유자 변조까지 방지하는 공증 원장이 아닙니다.
- Local DB 초기화는 명시적 `ORION_MODE=local_live`에서만 허용합니다. 이 설정만으로 provider나 파일 업로드 기능이 활성화되지는 않습니다. 아직 해당 기능이 구현되지 않았습니다.
- 예산 값 검증은 구현했습니다. 실제 요청별 reserve/settle와 API 실행은 미구현이며, 우회 실행 대신 차단합니다.

## 다음 개발에 사용할 경계

`validate_envelope(data)` → `validate_grounding(state, draft, mode=...)` → trusted service → `SQLiteRepository.transact(...)` 순서로 연결합니다. `transact` callback 안에서 상태를 읽고, 다음 Chunk의 엔진이 완전한 변경을 계산한 다음 entity/snapshot/decision/audit를 함께 씁니다. 성공한 같은 idempotency key/payload는 revision 검사보다 먼저 최초 결과를 반환합니다.

현재 `transact`는 Snapshot을 동반한 **revision 변경용**입니다. Snapshot을 유지하는 staging/반려의 audit-only 저장 경계, reviewer service, approved-record selection, derived status 및 head input digest 대조는 Chunk 2에서 완성해야 합니다. Foundation의 참조 검증 통과를 순위·상태 전이의 정당성 검증으로 해석하지 마세요.

미구현: scoring/Top-3 변화, 승인 상태 전이, native parser, 전체 Dash UI, export 승인·파일, Live API·비용 예약, 공개 배포, B0–B3 평가. 단위테스트 성공은 학술 목표의 실측 성능이 아닙니다.

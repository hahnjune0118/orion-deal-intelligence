# Chunk 1 Foundation 구현 프롬프트

공통 Orchestrator를 적용하고 **Foundation만** 구현하라. 예산은 8시간이다.

## 정확한 입력

`spec/00_READ_FIRST.md`, `01_MASTER_SPECIFICATION.md`, `02_PRD_AND_ACCEPTANCE_TESTS.md`, `03_SYSTEM_ARCHITECTURE.md`, `04_DATA_CONTRACTS.md`, `SCHEMAS/models.schema.json`, `SCHEMAS/FIELD_REFERENCE.md`, `EXAMPLES/initial_state.json`, `EXAMPLES/staged_evidence_update.json`, `EXAMPLES/expected_top3_transition.json`, `DATASET_SPECS/cd/*.json`, `DATASET_SPECS/lm/*.json`, `CONFIG/requirements-candidate.txt`, `QA/dependency_metadata.json`, `09_SECURITY_COST_DEPLOYMENT.md`.

## 구현과 출력

- `pyproject.toml`, src layout, Python3.12 설정, README, .gitignore, `.env.example`(key 값 없음), `pytest.ini` 또는 pyproject marker 등록.
- `src/orion/domain/models.py`: 모든 Schema entity와 envelope의 strict Pydantic 모델. JSON Schema와 허용/거절 케이스의 parity를 시험한다. 생성 Schema의 metadata 차이와 semantic 차이를 구별한다.
- `src/orion/domain/grounding.py`: ID/Deal/버전/참조 무결성과 text-v1 normalization/hash/quote 검사. 문서 native parser는 interface만 만들고 실제 3-format 구현은 Chunk3로 남긴다.
- `src/orion/adapters/sqlite_repo.py`: 초기화, entity version 저장, processed_commands, revision transaction, rollback, snapshot/audit append-only 경계. 이 단계에서는 rank 알고리즘을 만들지 않는다.
- `src/orion/config.py`: Demo default, public upload/live adapter deny, Local loopback 정책, budget config 검증.
- `tests/contracts/`, `tests/repository/`, `tests/security/test_demo_boundary.py`; `python -m orion.cli validate-fixture <path>` 구현.
- Windows/Ubuntu용 exact transitive hash locks, 의존성 메타데이터와 라이선스 notices. pin 후보의 compatibility·취약점을 확인하고 변경 시 로그를 남긴다.
- `.github/workflows/ci.yml`: Python3.12 Win/Ubuntu, install, pip check, contract/repository tests. live API key 없이 동작.

## 실행 순서와 명령

먼저 기존 사용자 작업을 읽고 보존한다. 아래 install은 후보 검증용이며 성공 후 환경별 hash lock을 생성하고 clean venv에서 재설치한다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r spec/CONFIG/requirements-candidate.txt
.\.venv\Scripts\python -m pip install --no-deps -e .
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m orion.cli validate-fixture spec/EXAMPLES/initial_state.json
.\.venv\Scripts\python -m pytest tests/contracts tests/repository tests/security/test_demo_boundary.py -q --strict-markers
```

lock 생성 도구 자체도 version pin하라. Windows/Linux resolver 결과가 다르면 하나의 lock으로 합쳐 설치 성공을 가장하지 마라. CI와 로컬 command가 같은 환경 계약을 사용하게 하라. Dash+Grid 최소 component serialization/import smoke는 이 단계에 허용하지만 제품 UI 전체를 만들지 않는다.

## G1 Acceptance Gate

정상 9 envelope 예시, unknown field, invalid enum/date/ID, document mismatch, 잘못된 quote/offset, cross-deal reference가 올바르게 통과/거절되어야 한다. DB rollback·동일 idempotency payload·다른 payload 충돌·WAL reconnect를 실제 SQLite로 검증한다. fixture_text_only를 Local file_verified로 오인하지 않아야 한다. Demo는 key가 있더라도 Live adapter를 생성하지 않아야 한다. AT01 준비, AT04–07/14–16/20–23의 Foundation 범위를 기록한다.

`implementation_evidence/CHUNK_01.md`에 실행 결과와 git diff를 남기고 아직 미구현인 scoring/native parsing/UI/export는 명확히 적는다. G1이 실패하면 Chunk2로 넘어가지 않는다. 이전 계약 파일을 임의로 수정하지 마라.

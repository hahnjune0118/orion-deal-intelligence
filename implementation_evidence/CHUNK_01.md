# Chunk 01 — Foundation 실행·인수인계 보고

작성일: 2026-11-03 (한국시간). 실제 검증 시각은 아래 UTC 로그를 기준으로 합니다.

## 결과와 Gate 상태

**실행 가능한 Python 3.12 프로젝트를 구현했고, 최종 wheel 설치 환경에서 680개 pytest가 모두 통과했습니다.** 실패 0, 오류 0, skip 0. Chunk 2 이후는 구현하지 않았습니다.

G1의 Linux 기능 검증은 통과했습니다. **G1 전체의 교차 플랫폼 실행 조건은 Windows native 실행이 `not_run`이므로 미완료입니다.** Windows target lock·wheel hash 검증과 CI 정의는 완료했지만 Windows 실행 성공으로 간주하지 않습니다. 후속 구현자는 Windows CI 결과를 확인해 G1을 닫은 다음 Chunk 2를 시작해야 합니다.

원본 `spec/` 47개 파일은 첨부 ZIP과 동일하며, 원본 checksum manifest의 46개 항목도 통과했습니다. 최우선 사용자 첨부는 `reference_inputs/01_FINAL_DECISIONS.md`에 보존했습니다. Contract/scoring version은 모두 **1.0.0**이며 formula, enum, 상태 전이와 expected 결과를 변경하지 않았습니다.

## 실제 환경과 재현 정보

- OS: `Linux-6.18.57-x86_64-with-glibc2.39`
- Python: CPython 3.12.14, x86_64
- 최종 pytest: 9.0.3 / Pydantic: 2.11.7
- 테스트된 구현 Git SHA: `996627961f2145b85453f3d6f8334b56b7110917`
- 원본 기준 commit: `14d2436` (첨부 명세 보존)
- 최종 pytest 시작 UTC: `2026-11-03T05:59:07.022258+00:00`
- pytest 출력: `680 passed in 7.37s`; 종료 코드 `0`
- clean 환경: `.venv-release`에 Linux hash lock 설치 후, editable 설치를 제거하고 실제 wheel을 설치하여 시험
- import 경로: `site-packages/orion/__init__.py` 확인. 저장소 밖 cwd에서도 세 Demo CLI 실행 성공

| Lock | SHA-256 |
|---|---|
| `requirements-linux.lock` | `5cbdfc3fcd8e5215664e248128454114ad918313a214c7f81e3fb86197af3f0a` |
| `requirements-tooling.lock` | `b21d90818cd078df19f897d0feee726df1ab78ff6f46fc0efa461c8707cd1c1a` |
| `requirements-win.lock` | `42a560139504b5838dc379352e4a53c9306a8461744e284dbb7cc96223eb9b0d` |

## 실행한 검사

| 검사 | 실제 결과 | 증빙 |
|---|---|---|
| 계약·Schema parity·원문/참조·CLI | 597 passed | `final-pytest.xml`, `logs/final-pytest.log` |
| 실제 SQLite 저장·롤백·동시성 | 42 passed | 동일 pytest 로그 |
| Demo·설정·보안 경계 | 40 passed | 동일 pytest 로그 |
| Dash/Grid import·serialization·Flask layout | 1 passed | 동일 pytest 로그; 실제 browser 시험 아님 |
| 설치된 wheel 전체 pytest | **680 passed / 0 failed / 0 skipped** | `logs/final-pytest.log` |
| 정상 9 envelope CLI | 9개 모두 exit 0 | `logs/final-cli-*.log` |
| 세 사례 Demo seed CLI | 모두 exit 0; 영속 상태 없음 | `logs/final-demo-*.log` |
| 원본 명세 checksum / Git spec diff | PASS / 변경 없음 | `logs/final-spec-integrity.log`, `logs/final-spec-diff.log` |
| `pip check`, compileall | exit 0 | `logs/final-pip-check.log`, `logs/final-compile.log` |
| Linux/Windows lock audit | 각각 63개 패키지, 알려진 취약점 0건 보고 | `dependency-audit-linux.json`, `dependency-audit-win.json` |
| Windows wheel 확보·SHA 검사 | PASS | `logs/windows-final-wheel-download.log` |
| native Windows pytest / 원격 GitHub Actions | **not_run** | Linux 실행 환경이며 원격 저장소 미사용 |
| 실제 브라우저·native parser·공개 배포·Live API | **not_run** | 이후 Chunk 범위 |

최종 명령·시각·exit code·실행 경로는 `final-validation.json`에 20건을 기록했습니다. 핵심 명령은 다음과 같습니다.

```bash
python -m pip install --require-hashes -r requirements-linux.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip wheel --no-deps --no-build-isolation --wheel-dir dist .
python -m pip install --no-deps --force-reinstall dist/orion_deal_intelligence-0.1.0-py3-none-any.whl
python -m pip check
python -m pytest tests/contracts tests/repository tests/security tests/smoke -q --strict-markers --junitxml=implementation_evidence/final-pytest.xml
python -m orion.cli validate-fixture spec/EXAMPLES/initial_state.json
python scripts/verify_spec.py
```

첫 설치·보안 검사에서 발견한 문제는 숨기지 않고 초기 로그도 보존했습니다. pytest/pytest-playwright/python-dotenv/Playwright 구현용 pin을 근거에 따라 수정했고 재설치·재검사했습니다. `DEPENDENCIES.md`와 `DEPENDENCY_SECURITY_REVIEW.md`에 변경 이유를 기록했습니다. 취약점 0건 보고는 모든 취약점 부재의 보증이나 브라우저/JavaScript 전체 감사를 뜻하지 않습니다.

## 구현 파일 목록

| 주요 파일 | 구현 내용 |
|---|---|
| `src/orion/domain/models.py` | 24개 named schema 객체 + 2개 inline 객체, 12개 persisted entity, 4개 Locator와 3개 Envelope |
| `src/orion/domain/grounding.py` | ID/Deal/문서 버전, 참조·원문 해시·quote·offset·native locator·관계·audit 검증 |
| `src/orion/adapters/parsers/base.py` | parser interface. 실제 parser는 명시적으로 차단 |
| `src/orion/adapters/sqlite_repo.py` | 9개 최소 테이블, FK/WAL, append-only, entity versions, atomic revision, idempotency, rollback |
| `src/orion/config.py` | Demo 기본, 외부 provider·업로드·방문자 DB 차단, loopback·Host/Origin, budget config |
| `src/orion/demo.py` | 고정 합성 입력 allowlist, 독립 request 상태, 행동 검증·reset; 승인 실행은 차단 |
| `src/orion/cli.py` | validate-fixture / seed-demo / init-db |
| `tests/contracts/`, `tests/repository/`, `tests/security/`, `tests/smoke/` | 실행 검증 및 회귀 테스트 |
| `scripts/generate_models.py`, `scripts/verify_spec.py` | 모델 재생성 및 명세 무결성 검사 |
| `scripts/lock_dependencies.py`, `scripts/dependency_inventory.py` | 고정 도구로 lock·metadata·notice 관리 |
| `pyproject.toml`, `.python-version`, `.env.example`, `.gitignore`, `.gitattributes` | 설치·Python·설정·소스 보존 기준 |
| `requirements-linux.lock`, `requirements-win.lock`, `requirements-tooling.lock` | OS별 전체 hash lock 및 도구 lock |
| `.github/workflows/ci.yml` | Ubuntu/Windows Python3.12 검사 정의 |
| `artifacts/orion_deal_intelligence-0.1.0-py3-none-any.whl` | 실제 설치하고 검증한 배포 wheel |
| `THIRD_PARTY_NOTICES.md`, `third_party_licenses/` | 사용 패키지 라이선스·NOTICE |
| `implementation_evidence/` | 실제 로그, JUnit XML, 명세 비교, dependency audit, diff와 인수인계 |

전체 파일은 루트 `DELIVERY_FILES.txt`, 각 파일 해시는 `CHECKSUMS.sha256`에 있습니다. venv, 원문 사용자 DB, 개인 key, 임시 다운로드 파일은 포함하지 않습니다.

## Acceptance Test 연결

| ID | Foundation에서 실제 검증한 범위 | 남은 범위 |
|---|---|---|
| AT01 | domain이 UI/provider/SQLite를 import하지 않음 | rank 결정론 실행 |
| AT04–06 | DOCX 구조 locator, quote/offset/hash 변조 차단, 파싱 상태 경계, file resolver 계약 | 실제 PDF/DOCX/PPTX와 source viewer |
| AT07 | 인용 검증이 truth를 승격하지 않음, 독립 확인 근거/결정/반증 guard | 승인 엔진에서의 파생 상태 |
| AT14–16 | 실제 DB idempotency·stale revision·concurrency·중간 실패 rollback | reviewer 승인 서비스 결합 |
| AT20–22 | API key가 있어도 provider 생성 차단, socket 호출 0, 업로드/임의 입력 차단, 요청별 동시 상태 분리 | 전체 Demo flow·두 브라우저 탭 |
| AT23 | config/CLI에서 secret 미보유·오류 원문 비출력, Local 요청 정책 | Live UI/HTML/export 통합 검사 |
| AT29 | SQLite reconnect·Demo seed/reset의 Foundation 경계 | 실제 app restart·브라우저 reload |
| AT30 | 명령·로그·실패/미실행·diff 기록 | 후속 Chunk별 반복 |

## 현재 한계·미구현 사항

1. **순위/승인 엔진:** `P=9G+8M+3O` 계산, tie/null 처리, derived support/workflow, reviewer 승인/반려, 재개, Top-3 전이는 미구현입니다. 예시의 결과를 제품 기능으로 재생하지 않습니다.
2. **Digest 책임:** `input_digest` helper는 세 초기 예시 hash와 일치합니다. 승인 평가에 사용할 record set 선택과 head digest freshness 대조는 다음 엔진 책임입니다. Foundation 참조 검증을 파생 상태의 정당성 검사로 표현하지 않습니다.
3. **저장 경계:** 현재 `transact`는 새 Snapshot을 수반하는 revision 변경용입니다. Snapshot을 바꾸지 않는 staging/반려의 audit-only transaction과 immutable staged-event archive/service는 다음 단계에서 필요합니다.
4. **Demo:** 독립 seed 로딩·허용 행동 검증·reset은 동작합니다. 승인/반려 replay는 `FEATURE_NOT_IMPLEMENTED`로 차단합니다. 서버가 결과 점수/actor/경로를 client 입력으로 받는 우회 경로는 없습니다.
5. **Native 파일:** fixture_text_only는 예시 텍스트일 뿐입니다. file_verified는 원본 bytes·hash·독립 source unit resolver가 필요합니다. 실제 3-format parser와 합성 원문 생성은 Chunk 3입니다.
6. **Live·Budget:** 비용 설정과 ledger 테이블만 준비했습니다. 실행/예약/정산/timeout 보존·가격 확인·OpenAI adapter는 미구현이며 실행을 차단합니다.
7. **UI·export·평가·배포:** Dash 전체 화면, 승인 export, B0–B3, 공개 배포는 미구현입니다. 실제 인용 정확도95%/Top-3 coverage80% 등 학술 성능은 `not_measured`입니다.
8. **Windows:** lock 생성·wheel hash 확보만 통과했습니다. native 실행과 원격 CI는 `not_run`이며 G1 전체 통과를 선언하지 않습니다.

## 다음 Chunk 인수인계

- 먼저 `.github/workflows/ci.yml`의 실제 Windows Python3.12 검사로 남은 G1 조건을 닫습니다. Linux와 Windows 결과를 하나로 합쳐 성공이라고 보고하지 않습니다.
- 이후 사용자가 Chunk 2를 요청하면 `spec/PROMPTS/02_CORE_ENGINE.md`를 읽고 시작합니다. 현재 세션에서는 실행하지 않았습니다.
- `validate_envelope` → `validate_grounding`을 통과한 server-owned 객체만 service에 전달합니다. `SourceResolver`를 브라우저 JSON/텍스트로 대체하지 않습니다.
- 서버 ActorContext에서 reviewer를 결정하고, `repo.transact(..., expected_revision=..., idempotency_key=..., request_payload=..., mutate=...)` callback 안에서 승인 record selection·상태 파생·rank·Snapshot·decision·audit를 계산/저장합니다.
- `processed_commands`는 동일 payload replay를 revision 검사보다 먼저 처리합니다. 단순 payload 변경은 `IDEMPOTENCY_CONFLICT`, stale 새 명령은 `REVISION_CONFLICT`입니다.
- 기존 Snapshot/audit/created_at을 수정하지 않습니다. entity version은 1씩 증가하며, source bytes/파싱 기준 변경은 document version 및 새로운 SourceSpan ID가 필요합니다.
- 현재 seed/fixture는 제품 API 입력과 evaluation gold를 섞지 않습니다. `resources/demo/`에는 세 initial_state와 staged update만 있고 gold/expected 파일이 없습니다.
- 기대 fixture·formula를 테스트에 맞춰 바꾸지 않습니다. 기존 테스트와 다음 Chunk 테스트를 함께 실행한 뒤 실제 결과를 기록합니다.

## Diff 검토와 보존

구현 소스 patch와 전체 변경 목록은 `implementation-source.patch`, `implementation-diff-stat.txt`, `implementation-diff-name-status.txt`에 보존했습니다. `git diff --cached --check`는 통과했습니다. upstream license와 raw execution log는 원본 공백을 보존하도록 `.gitattributes`에서 whitespace 검사를 제외했으며, 구현 Python과 테스트 소스는 검사 대상입니다. 문서/명세는 원본 bytes를 보존합니다.

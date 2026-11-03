# Chunk 02 — Adaptive DD Core Engine 구현·검증 보고

2026-11-03 (한국시간). 이번 작업은 **Chunk 2까지만** 수행했습니다.

## 결과

**설치한 package 0.2.0 wheel 환경에서 전체 823개 테스트가 통과했습니다.** 기존 Foundation 680개를 수정·삭제하지 않았으며 신규 143개를 추가했습니다. 실패 0, 오류 0, skip 0. G2의 Linux 기능 및 service boundary 검증을 통과했습니다.

GitHub 인증·원격 저장소 조회·remote commit/push는 수행하지 않았습니다. 사용자의 지시에 따라 첨부 Chunk 1을 로컬 baseline으로 사용했습니다. 원격 저장소 HEAD와의 동일성을 확인했다고 주장하지 않습니다. 로컬 브랜치는 `feature/chunk-02-core-engine`입니다. 실제 GitHub commit/push는 개인 Windows PC에서 사용자가 수행합니다.

기존 G1의 **native Windows 실행 미검증**은 해소하지 못했습니다. Linux에서 현재 Foundation 전체를 다시 실행했고 통과했지만, Windows/원격 CI는 `not_run`입니다. G2 Linux 통과를 전체 제품 출시나 모든 플랫폼의 G1 종료로 표현하지 않습니다.

## 환경과 재현성

- OS: `Linux-6.18.57-x86_64-with-glibc2.39`
- Python: `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`
- dependency lock: 기존 Linux hash lock 전체를 별도 venv에 설치, `pip check` 통과
- Pydantic 2.11.7 / pytest 9.0.3, package 0.2.0; contract/scoring **1.0.0 유지**
- 로컬 baseline Git SHA: `842efcfd23841826650b23c97da39ae85ca4403c` — 첨부 ZIP에서 복원한 초기 commit이며 원격 Git SHA가 아님
- 구현 commit: 없음; baseline 위 working tree로 보존
- 테스트한 source/test tree SHA-256: `300e63d7496518b477ca7f6f23d1e85351b0b1546a0b8853bed6d584f233f6ca`
- 최종 전체 테스트 시작 UTC: `2026-11-03T06:39:40.197611+00:00`
- 최종 전체 테스트 종료 UTC: `2026-11-03T06:40:08.041633+00:00`
- 실제 전체 테스트 시간: 26.500초; 종료 코드 0
- 실행 로그: `logs/chunk02-final-full-pytest.log`, JUnit: `chunk02-pytest.xml`

| Lock | SHA-256 |
|---|---|
| `requirements-linux.lock` | `5cbdfc3fcd8e5215664e248128454114ad918313a214c7f81e3fb86197af3f0a` |
| `requirements-tooling.lock` | `b21d90818cd078df19f897d0feee726df1ab78ff6f46fc0efa461c8707cd1c1a` |
| `requirements-win.lock` | `42a560139504b5838dc379352e4a53c9306a8461744e284dbb7cc96223eb9b0d` |

전체 명령, UTC 시각, 종료 코드, pass/failed/not_run, 파일별 hash는 `chunk02-validation.json`에 있습니다. 초기 baseline 실행은 `logs/chunk02-baseline-pytest.log`(680 pass)에 보존했습니다. wheel을 설치해 실제 `site-packages/orion`에서 import된 것을 확인한 뒤 전체 테스트를 실행했습니다.

## 구현

| 파일 | 동작 |
|---|---|
| `domain/scoring.py` | 원자적 requirement credit, 최소 reliability/독립 확인 조건, 반증 conflict, Decimal formula·raw tie, null/0, 해결 질문 제외, canonical digest |
| `domain/transitions.py` | 승인된 draft만 활성화, scoped full supersession, 반증 보존, claim support/truth 분리, 해결·재개, stale head 차단, 실제 before/after 이유 |
| `services/workspace.py` | 서버 소유 ActorContext 및 검증된 현재 workspace 읽기 |
| `services/review.py` | immutable staging, 승인/반려, strict command DTO, reviewer 권한, 최초 결과 재전송, changed questions/reasons |
| `adapters/sqlite_repo.py` | 기존 저장 구조 유지 + staged_updates/staged_resolutions 추가, audit-only transaction, 기존 revision transaction 활용 |
| `demo.py` | 매 요청 allowlisted synthetic event log 재생, 고정 synthetic reviewer/time, 무DB·무네트워크·독립 상태 |
| `cli.py` | `rank --state` 및 `replay --case --event staged --approve/--reject --output` |
| `tests/core`, `tests/transitions`, `tests/integration` | 143개 신규 검증; 기존 테스트 680개 보존 |
| CI / README / pyproject | 기존 CI Foundation 검사 유지 + Core 검사, 새 명령 안내, package version 0.2.0 |

기존 `replay_demo()`의 Foundation seed/reset 및 `FEATURE_NOT_IMPLEMENTED` 계약을 그대로 보존했습니다. 새 승인 replay는 `replay_reviewed_demo()`이며 CLI `replay`가 이 엔진을 호출합니다. 기존 test를 바꿔 삭제하지 않기 위한 호환 API 분리입니다. 서버 actor·점수·원문을 client JSON으로 받는 경로는 없습니다.

SQLite 기존 v1 DB는 시작 시 두 archive table과 append-only trigger만 추가합니다. 기존 version/history/snapshot/audit는 재작성하지 않습니다. 실제 첨부 0.1.0 wheel로 DB를 생성하고 새 adapter로 열어 승인까지 수행한 테스트가 포함됩니다. 스키마 계약·enum·점수 공식·expected fixture를 수정하지 않았습니다.

## 실제 전이

| 사례 | Before Top-3 | After Top-3 | 핵심 결과 |
|---|---|---|---|
| Northstar | 100 / 97 / 89 | 97 / 89 / 86 | A 계약만 해결. Birch 계약·두 고객 검수/수금·독립성은 미해결. 주장은 partial/document_only |
| Cedar | 100 / 94 / 89 | 94 / 89 / 86 | cut-off 해결 후 warranty/inventory/receivable 상대 승격 |
| Lumen | 92 / 89 / 84 | 97 / 92 / 89 | renewal 재개. 기존 지지와 새 반증을 함께 보존, contradicted/disputed |

`chunk02-artifacts/before_after.json`은 **실제 엔진 출력**의 question별 이전/이후 순위·점수·상태·이유입니다. `ns_after.json`, `cd_after.json`, `lm_after.json`은 전체 committed synthetic 상태입니다. 기대값 파일을 실행 입력으로 로딩하거나 QA reference arithmetic을 구현으로 복사하지 않았습니다.

## 검증과 AT 연결

| 검사 | 실제 결과 | AT |
|---|---|---|
| 기존 Foundation 전체 | 680 passed, 원본 테스트 byte 보존 | 기존 G1 회귀 |
| Core scoring | 46 passed | AT01,09–12 |
| Transition | 36 passed | AT07–08,11–13,17 |
| Review SQLite service | 37 passed | AT13–16,21 |
| Demo replay / CLI | 23 passed | AT01,08,17,20–22 service boundary |
| 실제 Chunk 1 DB upgrade | 1 passed | AT14–16,29 관련 호환성 |
| 전체 설치 wheel pytest | **823 passed / 0 failed / 0 errors / 0 skipped** | AT30 |
| 명세 원본 checksum | 46개 항목 일치, spec 47개 파일 변경 없음 | 계약 불변 |
| lock / 기존 테스트 Git diff | 변경 없음 | 회귀 보존 |
| pip check / compile / CLI rank와 3개 replay 및 validate | 모두 exit 0 | 재현성 |
| Git whitespace / patch 적용 검증 | `review/` 검토 자료 참조 | 변경 전달 |

100회 entity collection 셔플, fractional gap, 같은 표시점수의 다른 raw 값, 정확한 점수 동점의 M/G/O/key/ID 정렬을 검사했습니다. 독립 리뷰에서 반복소수 중간 반올림이 정확한 동점을 깨는 경우를 발견하여, 동일 공식의 분자 결합 후 마지막 나눗셈으로 수정하고 회귀 테스트를 추가했습니다.

미승인·반려·중복·무관한 증빙은 각 사례에서 순위를 바꾸지 않습니다. invalid locator, unauthorized, stale revision, cross-Deal, self/cycle 관계, 부분 supersession을 차단합니다. 반복 idempotency와 동시 승인, 이후 revision에서의 최초 명령 재전송도 audit를 중복 추가하지 않습니다. snapshot/audit 쓰기 중 강제 예외, staging 실패 시 모든 관련 테이블의 롤백을 확인했습니다.

이미 independently_verified인 주장에 반증이 들어오면 disputed로 전환할 수 있도록 상태 파생 순서를 교정했습니다. 반증을 낮은 reliability·다른 claim으로 바꾸어 지우는 우회도 차단하며, 명시적 full supersession을 요구합니다. 원문 quote 일치와 독립 진실 확인은 분리합니다.

## 실행 명령

```bash
python -m pytest -q --strict-markers
python -m pytest tests/core tests/transitions tests/integration/test_review_commit.py -q --strict-markers
python -m orion.cli rank --state spec/EXAMPLES/initial_state.json
python -m orion.cli replay --case ns --event staged --approve --output build/ns_after.json
python -m orion.cli replay --case cd --event staged --approve --output build/cd_after.json
python -m orion.cli replay --case lm --event staged --approve --output build/lm_after.json
python scripts/verify_spec.py
git diff --check
git diff --stat
git diff --name-status
```

위 Python 명령은 설치한 venv에서 실행합니다. 실제 실행에서는 replay JSON을 증빙 보존을 위해 `implementation_evidence/chunk02-artifacts/` 경로에 저장했습니다. 상세 절대 실행 명령은 validation JSON에 기록했습니다.

## 전달 및 Git diff

통합 ZIP은 **Chunk 1 전체 소스·기존 증빙·원본 wheel을 포함하고 Chunk 2를 추가한 전체 코드**입니다. `.git`, venv, cache, 사용자 DB/비밀정보는 포함하지 않습니다. 원본 0.1.0 wheel은 이전 버전 증빙으로 보존하고 새 0.2.0 wheel도 제공합니다.

ZIP 최상위 `review/`에 `CHUNK_02.patch`(binary 포함 전체 diff), `DIFF_STAT.txt`, `CHANGED_FILES.txt`, `PATCH_VALIDATION.json`이 있습니다. diff 기준은 첨부 Chunk 1이며 untracked 신규 파일도 모두 포함합니다. patch는 원본 복사본에 실제 `git apply --check`·`git apply` 후 파일별 byte 비교로 검증합니다. Windows 안내는 `WINDOWS_APPLY_CHUNK_02.md`입니다.

## 한계와 이후 단계

- **not_run:** native Windows pytest, GitHub Actions, 두 실제 브라우저 탭, native PDF/DOCX/PPTX parsing, Live API, 공개 배포, B0–B3 평가.
- AT20–22는 무네트워크/무DB, 임의 입력 차단, 동시 요청별 상태 독립의 **서비스 경계** 검증입니다. 브라우저 UI 검증으로 확대 주장하지 않습니다.
- fixture_text_only는 작성된 계약 예시 텍스트입니다. 인용 위치 정확도 95%, 허위 인용 0건, Top-3 coverage 80% 같은 학술 성능은 `not_measured`입니다.
- 선택 Bayesian/EIG는 구현하지 않았습니다. 제품 순위와 연결하지 않았습니다.
- Chunk 3의 native 합성 문서·평가, Chunk 4 UI, Chunk 5 export/Live/배포는 **시작하지 않았습니다**. 다음 단계 전 Windows 검증을 확인하고 별도 요청 범위에서 진행해야 합니다.

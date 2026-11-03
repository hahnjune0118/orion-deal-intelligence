# Chunk 2 Core Engine 구현 프롬프트

Orchestrator와 G1 증빙을 읽고 deterministic evidence update vertical slice를 구현하라. 예산 10시간.

## 정확한 입력

`implementation_evidence/CHUNK_01.md`, `src/orion/domain/models.py`, `src/orion/domain/grounding.py`, `src/orion/adapters/sqlite_repo.py`, `spec/04_DATA_CONTRACTS.md`, `spec/05_SCORING_AND_ADAPTIVE_ENGINE.md`, `spec/02_PRD_AND_ACCEPTANCE_TESTS.md`, `spec/EXAMPLES/*.json`, `spec/DATASET_SPECS/cd/*.json`, `spec/DATASET_SPECS/lm/*.json`, `spec/SCHEMAS/models.schema.json`.

## 구현과 출력

- `domain/scoring.py`: requirement credit, conflict, Decimal formula, null policy, raw tie-break, resolved exclusion, canonical digest.
- `domain/transitions.py`: approved atom만 활성화, duplicate origin, scoped relations, claim support와 question reopen/resolution. 원문 존재와 진실 확인 분리.
- `services/review.py`, `services/workspace.py`: 서버 ActorContext, staging/approve/reject, revision/idempotency/transaction, immutable Snapshot과 AuditEvent.
- `demo.py`: allowlisted synthetic event log replay. Client가 점수·역할·raw evidence를 제출하면 거절한다.
- CLI `replay --case {ns,cd,lm} --event staged --approve --output <path>`와 `rank --state <path>`.
- `tests/core/`, `tests/transitions/`, `tests/integration/test_review_commit.py`.
- Bayesian 모듈은 시간이 남을 때만: bounded inputs, impossible outcome, entropy/EIG worked example. rank와 연결하지 않는다.

## 명령

```bash
python -m orion.cli rank --state spec/EXAMPLES/initial_state.json
python -m orion.cli replay --case ns --event staged --approve --output build/ns_after.json
python -m orion.cli replay --case cd --event staged --approve --output build/cd_after.json
python -m orion.cli replay --case lm --event staged --approve --output build/lm_after.json
python -m pytest tests/core tests/transitions tests/integration/test_review_commit.py -q --strict-markers
git diff --check
```

현재 fixtures는 native parsing 완료를 뜻하지 않는다. source token matching만으로 독립 사실 검증을 선언하지 않는다. QA reference arithmetic 코드를 그대로 테스트 대상 구현으로 복사하여 자기 자신과 비교하지 마라.

## G2 Gate

Northstar 100/97/89→97/89/86, Cedar 100/94/89→94/89/86, Lumen 92/89/84→97/92/89를 정확히 재현하라. Northstar 계약A가 검수·수금·Birch 계약을 충족하지 않아야 한다. Lumen 반증은 renewal을 reopen하고 source conflict를 보존한다.

각 pack에서 duplicate/unrelated/unapproved/rejected는 rank를 바꾸지 않아야 한다. invalid locator/unauthorized/stale approval은 commit 차단. 관계 cycle/self-reference, 다른 Deal, 부분 supersession, unknown reliability, null/zero score, fractional gap, 동일 표시점수의 raw tie를 테스트하라. 같은 상태를 entity collection 순서만 바꾸어도 digest/순위가 동일해야 한다. repeated idempotency는 audit를 중복 추가하지 않는다. audit/snapshot 중간 오류는 모든 쓰기를 rollback한다. AT08–17 및 AT20–22 service 경계를 입증하라.

종료 시 `implementation_evidence/CHUNK_02.md`, 실제 before/after diff, pytest 로그와 git diff를 남겨라. 점수·expected 값의 계약 변경은 별도 변경관리 없이 하지 않는다.

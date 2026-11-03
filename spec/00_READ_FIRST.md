# Orion Deal Intelligence 2.0 개발 인수인계

명세 버전 **1.0.0** · 기준일 **2026-11-03** · 대상 독자: 단독 개발자와 후속 구현 GPT 세션

이 패키지는 구현을 시작하기 위한 계약이다. 완성 애플리케이션, 성능평가 결과 또는 배포 완료 보고서가 아니다. **증빙을 검토·승인한 뒤 질문의 Top-3가 정당하게 바뀌는 한 흐름**을 먼저 완성한다. 이번 산출물에는 앱 코드 대신 JSON Schema, 계산 가능한 예시, 검증 스크립트, 구현 단계별 프롬프트가 있다.

## 읽는 순서

1. [Master Specification](01_MASTER_SPECIFICATION.md)으로 범위와 불변조건을 확인한다.
2. [Architecture](03_SYSTEM_ARCHITECTURE.md), [Data Contracts](04_DATA_CONTRACTS.md), [Scoring](05_SCORING_AND_ADAPTIVE_ENGINE.md)을 함께 읽는다.
3. [UI Design System](06_DASH_UI_UX_DESIGN_SYSTEM.md)과 [Acceptance Tests](02_PRD_AND_ACCEPTANCE_TESTS.md)를 구현 계약으로 사용한다.
4. [Orchestrator](PROMPTS/00_ORCHESTRATOR.md)를 새 구현 세션에 먼저 전달하고 [Foundation](PROMPTS/01_FOUNDATION.md)부터 실행한다.
5. 매 Chunk 종료 시 실제 실행 로그와 git diff를 남긴다. 다음 Chunk를 통과시키기 위해 실패한 테스트나 기대값을 바꾸지 않는다.

## 우선순위

`01_FINAL_DECISIONS.md` > 최초 학술 기획안 > 2차 피드백 보완 > 1차 피드백 보완. `02_FIRST_PROMPT.md`는 이 패키지의 제작·검증 요구사항이다. 원본들은 본 패키지에 재배포하지 않고 [결정·출처 기록](11_DECISION_LOG_AND_SOURCES.md)에 이름, 해시, 구조상 위치를 남겼다. 구버전 스토리보드의 상장사·DCF 수치는 이 제품의 예시 데이터가 아니다.

## 버전과 파일의 역할

| 대상 | 규칙 |
|---|---|
| Product | Orion Deal Intelligence 2.0 |
| Contract / scoring | `1.0.0` / `1.0.0` |
| Entity | `entity_version`는 같은 ID의 수정 시 1 증가 |
| Deal state | 승인된 원자적 변경마다 `state_revision` 증가 |
| Input / gold | `EXAMPLES`, `DATASET_SPECS`와 `EVAL_GOLD`를 분리. 기대값 파일도 모델 입력 금지 |
| Source fixtures | 현재 JSON은 추출 텍스트 계약 예시. `fixture_text_only`, `file_sha256=null`은 의도적이다. 실제 PDF/DOCX/PPTX 파싱을 검증했다는 뜻이 아니다 |
| QA | `QA/validate_package.py`는 명세의 산술·계약 검사 도구. 제품 엔진으로 복사하지 않고 구현을 독립 검증할 참고자료로만 사용 |

## 이 패키지 검증 재실행

Python 3.12 환경에서 패키지 루트 기준:

```powershell
py -3.12 -m venv .qa-venv
.\.qa-venv\Scripts\python -m pip install jsonschema==4.25.1
.\.qa-venv\Scripts\python QA/validate_package.py
```

실제 실행 결과는 [QA/VALIDATION_REPORT.md](QA/VALIDATION_REPORT.md)에 있다. 제품 인용 정확도 95%, 허위 인용 0건, Top-3 coverage 80%는 **미검증 목표**이며 이 계약 검사의 통과율로 대체할 수 없다.

## 첫 개발 세션의 완료 범위

Foundation은 Pydantic 모델, 참조·원문 검사기, 로컬 SQLite 저장소, Demo 무네트워크 경계, 의존성 잠금·CI 골격까지다. UI 전체나 LLM 성능 실험부터 시작하지 않는다. 다음 단계는 Core Engine → Synthetic Data & Evaluation → Dash UI → Integration & Release 순서다. 상세 시간표는 [구현 계획](10_IMPLEMENTATION_PLAN.md)에 있다.

변경이 필요하면 계약 변경안을 명시하고 영향 파일·마이그레이션·테스트를 함께 수정한다. 범위를 줄일 때도 승인, 근거검증, 재현성, 공개 Demo의 무API 원칙은 유지한다.

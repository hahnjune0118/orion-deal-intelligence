# Delivery Manifest

Orion Deal Intelligence 2.0 · Contract 1.0.0 · 2026-11-03

필수 산출물 **23개 전부**와 보완 자료를 포함한 총 **47개 파일**이다. ZIP의 최상위에서 00_READ_FIRST.md부터 읽는다. 전체 애플리케이션은 이번 산출물에 포함하지 않는다.

## 전달 파일

- `ORION_GPT_PRO_HANDOFF.zip`: 아래 파일 전체를 담은 압축파일.
- `01_MASTER_SPECIFICATION.md`: ZIP 내부와 byte-identical인 별도 Markdown 사본. 단독 사본의 상대 링크는 ZIP을 풀었을 때 해당 동반 문서로 연결된다.

## 현재 검증 범위

[명세 검증 결과](QA/VALIDATION_REPORT.md)는 JSON Schema, 참조·원문 텍스트 무결성, 루브릭·Bayes/EIG 산술, 세 예시 전이, 음성 입력, 필수 파일과 내부 링크를 검사한 기록이다. 제품 실행·실제 문서 파서·브라우저·Live API·hosting·학술 성능 결과가 아니다.
직접 dependency 17개 release metadata와 Linux CPython3.12 resolver dry-run(총63개)을 확인했다. 설치·취약점·Windows 통합 시험은 후속 Chunk1 Gate다. 두 SVG wireframe을 PNG로 렌더하여 내용·배치·승인 전후 상태 표기를 시각 확인했다. 이는 실제 앱의 접근성 통과 보고가 아니다.

## 파일 목록

| File | Required | Purpose |
|---|---|---|
| [00_READ_FIRST.md](00_READ_FIRST.md) | 필수 | Master Specification의 구성 문서 |
| [01_MASTER_SPECIFICATION.md](01_MASTER_SPECIFICATION.md) | 필수 | Master Specification의 구성 문서 |
| [02_PRD_AND_ACCEPTANCE_TESTS.md](02_PRD_AND_ACCEPTANCE_TESTS.md) | 필수 | Master Specification의 구성 문서 |
| [03_SYSTEM_ARCHITECTURE.md](03_SYSTEM_ARCHITECTURE.md) | 필수 | Master Specification의 구성 문서 |
| [04_DATA_CONTRACTS.md](04_DATA_CONTRACTS.md) | 필수 | Master Specification의 구성 문서 |
| [05_SCORING_AND_ADAPTIVE_ENGINE.md](05_SCORING_AND_ADAPTIVE_ENGINE.md) | 필수 | Master Specification의 구성 문서 |
| [06_DASH_UI_UX_DESIGN_SYSTEM.md](06_DASH_UI_UX_DESIGN_SYSTEM.md) | 필수 | Master Specification의 구성 문서 |
| [07_SYNTHETIC_DEAL_DATASET_SPEC.md](07_SYNTHETIC_DEAL_DATASET_SPEC.md) | 필수 | Master Specification의 구성 문서 |
| [08_EVALUATION_PROTOCOL.md](08_EVALUATION_PROTOCOL.md) | 필수 | Master Specification의 구성 문서 |
| [09_SECURITY_COST_DEPLOYMENT.md](09_SECURITY_COST_DEPLOYMENT.md) | 필수 | Master Specification의 구성 문서 |
| [10_IMPLEMENTATION_PLAN.md](10_IMPLEMENTATION_PLAN.md) | 필수 | Master Specification의 구성 문서 |
| [11_DECISION_LOG_AND_SOURCES.md](11_DECISION_LOG_AND_SOURCES.md) | 필수 | Master Specification의 구성 문서 |
| [CHECKSUMS.sha256](CHECKSUMS.sha256) | 보완 | 각 파일의 SHA-256 무결성 목록 |
| [CONFIG/live_pricing.example.json](CONFIG/live_pricing.example.json) | 보완 | 의존성 후보와 fail-closed Live 가격 설정 |
| [CONFIG/requirements-candidate.txt](CONFIG/requirements-candidate.txt) | 보완 | 의존성 후보와 fail-closed Live 가격 설정 |
| [CONFIG/requirements-linux-resolved.lock](CONFIG/requirements-linux-resolved.lock) | 보완 | 의존성 후보와 fail-closed Live 가격 설정 |
| [DATASET_SPECS/cd/expected_top3_transition.json](DATASET_SPECS/cd/expected_top3_transition.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DATASET_SPECS/cd/initial_state.json](DATASET_SPECS/cd/initial_state.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DATASET_SPECS/cd/staged_evidence_update.json](DATASET_SPECS/cd/staged_evidence_update.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DATASET_SPECS/financial_truth.json](DATASET_SPECS/financial_truth.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DATASET_SPECS/lm/expected_top3_transition.json](DATASET_SPECS/lm/expected_top3_transition.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DATASET_SPECS/lm/initial_state.json](DATASET_SPECS/lm/initial_state.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DATASET_SPECS/lm/staged_evidence_update.json](DATASET_SPECS/lm/staged_evidence_update.json) | 보완 | 추가 합성 사례와 재무 일치 기준 |
| [DELIVERY_MANIFEST.md](DELIVERY_MANIFEST.md) | 필수 | 제출 범위와 전체 파일 목록 |
| [DESIGN/update-review-wireframe.svg](DESIGN/update-review-wireframe.svg) | 보완 | 독립적인 UI 배치와 승인 전후 wireframe |
| [DESIGN/workspace-wireframe.svg](DESIGN/workspace-wireframe.svg) | 보완 | 독립적인 UI 배치와 승인 전후 wireframe |
| [EVAL_GOLD/cd_gold.json](EVAL_GOLD/cd_gold.json) | 보완 | 모델 입력에서 제외할 잠정 평가 기준 |
| [EVAL_GOLD/lm_gold.json](EVAL_GOLD/lm_gold.json) | 보완 | 모델 입력에서 제외할 잠정 평가 기준 |
| [EVAL_GOLD/ns_gold.json](EVAL_GOLD/ns_gold.json) | 보완 | 모델 입력에서 제외할 잠정 평가 기준 |
| [EXAMPLES/expected_top3_transition.json](EXAMPLES/expected_top3_transition.json) | 필수 | Northstar 초기 상태·단일 이벤트·기대 전이 |
| [EXAMPLES/initial_state.json](EXAMPLES/initial_state.json) | 필수 | Northstar 초기 상태·단일 이벤트·기대 전이 |
| [EXAMPLES/staged_evidence_update.json](EXAMPLES/staged_evidence_update.json) | 필수 | Northstar 초기 상태·단일 이벤트·기대 전이 |
| [PROMPTS/00_ORCHESTRATOR.md](PROMPTS/00_ORCHESTRATOR.md) | 필수 | 후속 구현용 단계별 작업 지시와 실행 Gate |
| [PROMPTS/01_FOUNDATION.md](PROMPTS/01_FOUNDATION.md) | 필수 | 후속 구현용 단계별 작업 지시와 실행 Gate |
| [PROMPTS/02_CORE_ENGINE.md](PROMPTS/02_CORE_ENGINE.md) | 필수 | 후속 구현용 단계별 작업 지시와 실행 Gate |
| [PROMPTS/03_SYNTHETIC_DATA_EVAL.md](PROMPTS/03_SYNTHETIC_DATA_EVAL.md) | 필수 | 후속 구현용 단계별 작업 지시와 실행 Gate |
| [PROMPTS/04_DASH_UI.md](PROMPTS/04_DASH_UI.md) | 필수 | 후속 구현용 단계별 작업 지시와 실행 Gate |
| [PROMPTS/05_INTEGRATION_RELEASE.md](PROMPTS/05_INTEGRATION_RELEASE.md) | 필수 | 후속 구현용 단계별 작업 지시와 실행 Gate |
| [QA/VALIDATION_REPORT.md](QA/VALIDATION_REPORT.md) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [QA/dependency_metadata.json](QA/dependency_metadata.json) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [QA/dependency_resolution_summary.json](QA/dependency_resolution_summary.json) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [QA/package_release.py](QA/package_release.py) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [QA/source_inventory.json](QA/source_inventory.json) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [QA/validate_package.py](QA/validate_package.py) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [QA/validation_results.json](QA/validation_results.json) | 보완 | 실행한 명세 검증, 근거 기록, 재검증 도구 |
| [SCHEMAS/FIELD_REFERENCE.md](SCHEMAS/FIELD_REFERENCE.md) | 보완 | 기계 판독 모델 계약과 필드 사전 |
| [SCHEMAS/models.schema.json](SCHEMAS/models.schema.json) | 필수 | 기계 판독 모델 계약과 필드 사전 |

## 무결성 재확인

`CHECKSUMS.sha256`은 자신을 제외한 모든 파일의 SHA-256을 포함한다. `QA/package_release.py`는 실제 검증 스크립트 실행 후 manifest/checksum을 생성하고 ZIP CRC, 모든 member bytes/hash, JSON 구문, 내부 링크, 별도 Master 사본 일치를 확인한다.
검증 보고서를 재실행하면 실행시각이 바뀌므로 기존 checksum과 다를 수 있다. 수정 후에는 package_release.py로 새 패키지를 만들고 기존 배포 파일과 구분한다.

## 의도적으로 포함하지 않은 것

원본 DOCX/업로드 자료의 재배포본, 실제 기업 비공개 데이터, API key, venv, 임시 파일, 앱 구현 코드, native 합성 source 파일은 포함하지 않는다. 현재 source 예시는 fixture_text_only이며 native PDF/DOCX/PPTX 생성과 parsing 검증은 Chunk3의 명시된 산출물이다.

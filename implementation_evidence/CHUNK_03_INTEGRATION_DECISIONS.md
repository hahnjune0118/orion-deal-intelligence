# Chunk 3 통합 기준과 명세 차이

현재 사용자가 제공한 Chunk 3 실행 지시문을 구현 범위로 삼고, 첨부된 통합 Chunk 2 `0.2.0`을 기술 기준으로 사용합니다. 원본 Chunk 1 ZIP과 비교하여 기존 파일의 보존 여부와 버전을 확인했습니다. GitHub 원격 저장소는 조회하지 않았습니다.

| 항목 | 적용한 결정 | 호환성 |
|---|---|---|
| Blueprint의 Streamlit 또는 Next.js | 최종 확정된 Dash + Dash AG Grid 유지 | Chunk 4 UI 구현은 하지 않음 |
| Python 3.11 이상이라는 새 지시 | 기존 검증 환경 Python 3.12 유지 | 3.11을 검증 없이 지원한다고 선언하지 않음 |
| Bayesian/EIG와 B3 | 가정 출처가 있는 독립 계산·연구 정책을 추가 | 기존 scoring 1.0.0의 45% Gap / 40% Materiality / 15% Obtainability는 불변 |
| B3의 비교 의미 | 기존 B3는 승인 후 adaptive reranking이며 Bayesian 계산을 별도 기록 | Bayesian을 끈 기본 순위는 동일해야 함. EIG 연구 순위는 별도 정책명 사용 |
| 기존 세 사례와 새 Deal B/C | 기존 ns/cd/lm 계약 사례 보존. 심화 Northstar(nb)와 제조업(mf) 데이터셋 추가 | 기존 expected 결과와 fixture는 수정하지 않음 |
| Orion 공개기업 | 공개 원문 수집·검증 요구사항과 pending manifest | 검증하지 않은 공개 사실·문서를 만들지 않음 |
| Hypothesis / BeliefSnapshot 등 | 기존 Claim(binary_hypothesis)·Evidence·DDQuestion 위에 확장 모델 사용 | 기존 JSON schema 및 enum을 바꾸지 않음 |
| B0–B3 실행 | 인터페이스, 작성된 fixture, 실제 deterministic engine 측정 | 실시간 LLM 모델 성능 비교는 not_run |
| Gold | 문서의 내용과 합성 세계의 사실을 분리하고 감사 | 작성자 정의·잠정 라벨이며 외부 전문가 검증 아님 |
| 원본 Blueprint | 설계 참고만 수행 | 고용주 식별 내용은 신규 데이터·배포 ZIP에 복사하지 않음 |

기존 계약 모델·점수 공식·기대값을 수정하는 breaking change는 없습니다. 추가 모듈은 선택적이며 기존 API와 SQLite 데이터를 그대로 유지합니다. 세부 실제 파일 변경은 `review/CHANGED_FILES.txt`, diff는 `review/CHUNK_03.patch`에 기록합니다.

새 합성 데이터는 일반적인 상업·재무 원리에서 독립적으로 작성하며 실제 사람·계좌·로고·비공개 거래를 포함하지 않습니다. Northstar의 계약·청구·수금은 서로 다른 사건입니다. 회사가 작성한 원문의 인용 일치 여부는 독립적인 경제적 진실 확인과 구분합니다.

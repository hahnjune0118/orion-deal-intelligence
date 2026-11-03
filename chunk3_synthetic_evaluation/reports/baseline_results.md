# Baseline Results — interpretation

실제 B0–B3 LLM benchmark는 **not_run**입니다. API 호출, 실제 모델 응답, 모델 간 우열 검증을 수행하지 않았습니다.

`evaluation/results/report.json`은 기존 3개 사례 및 확장된 Northstar/제조업 시나리오의 **작성된 fixture·결정론적 엔진 기능 실행 결과**입니다. B0/B1은 공통 질문 fixture로 평가 파이프라인을 검증하며, B0의 인용 생략은 결측 처리 검사용입니다. 이를 실제 일반 LLM의 성능으로 해석하면 안 됩니다. B2는 초기 순위를 유지하고, B3는 같은 초기 객체에서 승인된 증빙에 따라 기존 Chunk 2 엔진으로 순위·질문 상태를 갱신합니다. B1-R은 인터페이스만 있으며 결과는 not_run입니다.

지표별 실제 분자·분모, stage별 Top-3, 금지된 입력 감사, negative control, no-Bayesian/가중치 ablation, 원문·출력·gold checksum은 생성된 JSON 보고서에 기록됩니다. 실행 실패는 successful row에서 제외하지 않고 명시합니다. 정답은 self-authored/provisional이며 외부 독립 검토, 실제 모델 비교, 비공개 held-out 검증은 후속 과제입니다.

## 이번 실행에서 확인한 기능 결과

- 5개 사례의 13개 상태 × 5개 arm = 65개 평가 행을 생성했습니다. B1-R 13개 행은 명시적으로 not_run입니다.
- 기존 3개 승인 전이 및 확장 Northstar 4개·제조업 1개 전이를 실행했습니다.
- 기존 15개 negative control은 실제 중복·무관·잘못된 원문 위치·미승인·이전 revision 재전송을 검사했습니다.
- 확장 7개 상태의 독립 작성 Top-3, 점수, hypothesis support/truth, 해결 질문 목록이 실행 결과와 일치했습니다.
- Bayesian 모듈 활성/비활성으로 확장 7개 상태를 각각 재생했으며 production 순위와 상태가 동일했습니다.
- 독립 Fraction/entropy 계산 기준: 양성 posterior 0.6315789474, 음성 posterior 0.0967741935, EIG 0.2361139273 bits. 실행된 sequential posterior MAE는 약 5.55×10⁻¹⁷, EIG 오차는 약 1.67×10⁻¹⁶이었습니다.

위 결과는 코드·시나리오의 결정론적 기능 검증입니다. 실제 LLM 추출·질문 생성 능력, 투자 성과 예측, 외부 분석가의 gold 타당성 검증으로 확대하지 않습니다. 최종 실행의 정확한 숫자와 시각은 JSON 보고서 및 통합 테스트 로그를 우선합니다.

# Evaluation Protocol

Protocol 1.0.0 · 상태: **사전 설계, 제품 평가 미실행**. Contract QA 통과율을 논문 성능으로 쓰지 않는다.

## 연구 질문과 비교 조건

근거 연결·구조화된 실사 workflow·새 증빙의 결정론적 반영을 순서대로 추가했을 때 핵심 질문의 선택과 갱신이 개선되는지 본다. Bayesian/EIG는 별도 optional 계산이므로 B3의 이름이나 성과로 그 효과를 주장하지 않는다. 이는 최신 확정사항에 따른 기존 기획안의 실험 정의 변경이다.

| Arm | 초기 분석 | 신규 증빙 처리 | 주된 비교 |
|---|---|---|---|
| B0 static generic LLM | 같은 source text를 plain context로 주고 일반 DD checklist·Top-3 생성 | 초기 순위 고정 | 정적 일반 생성 baseline |
| B1 grounded citations | 동일 corpus, locator/quote를 포함한 답변; citation validator 사용 | 초기 질문 순위 고정, 새로운 source inspector는 가능 | grounding 추가 |
| B2 structured workflow | Thesis/Claim/Evidence/requirements, reviewer 고정 입력, deterministic initial rank | 신규 증빙은 보여주되 initial ranking 동결 | 구조화 추가 |
| B3 adaptive | B2와 동일 초기 객체·점수·review budget | 한 이벤트를 검증·승인 후 결정론 갱신 | 순수 adaptive re-ranking 효과 |

B0–B2가 새 사건에 응답할 기회가 없는 것만으로 B3가 우수하다고 일반화하지 않는다. 추가 **B1-R** control은 같은 새 증빙과 token budget으로 grounded LLM을 한 번 재실행한다. B3 vs B2는 adaptive 처리의 효과, B3 vs B1-R은 단순 재질문 대비 구조적 이점을 비교한다. B1-R은 본 4-arm 표와 구분하여 보고한다.

## 입력 통제와 비용

같은 native document text, task wording, model snapshot, temperature(지원 시 0), 출력 token ceiling, 실행 시점·provider 설정을 기록한다. B0도 source text에 접근하게 하여 정보량 차이를 줄인다. B1–B3는 동일 retrieval candidates를 사용한다. Reviewer input/승인 목록은 arm마다 유리하게 바꾸지 않고 사전 고정한다. B3의 초기 상태는 B2를 복사하며 별도의 더 좋은 LLM 호출을 허용하지 않는다.

각 실행 manifest는 case_id, arm, seed 또는 seed 미지원, model_id, prompt version/hash, contract/scoring version, source hashes, input token/output token, cache/live, run duration, cost, reviewer time, error를 담는다. 반복 3회는 stochastic output variation을 보기 위한 최소 권장값이며 seed 미지원 시 동일 조건 재호출로 표시한다. budget 부족으로 횟수를 줄이면 미리 기록한다. 재시도·실패도 비용과 denominator에 포함한다.

공개 Demo의 저자 작성 cached output은 모델 성능 측정이 아니다. 후속 실제 LLM 실행 결과를 캐시할 때에만 해당 run manifest와 함께 model-generated cache라고 부른다. `authored-fixture` 캐시와 구분한다.

## Gold와 판정 절차

Gold는 모델 실행 전에 freeze하고 hash와 작성일을 기록한다. claim ID, 원문 locator/quote, support/contradiction, 허용 request family, 각 상태의 critical set(최대3), fulfillment/reopen criteria, expected transition reason을 포함한다. 문장 일치가 아니라 요청 대상·범위·기간·증빙 유형이 같으면 동일 family로 매핑한다. 한 output 질문을 여러 critical family에 중복 매칭하지 않는다.

가능하면 독립 평가자 2명이 arm을 가린 output을 판정한다. 불일치·조정 과정을 보관한다. 범주 판정의 Cohen's kappa 또는 raw agreement를 함께 보고하되 표본이 작은 한계를 적는다. 단독 개발자가 gold까지 작성하면 `self-authored, single-rater`로 표시하고 독립 검증이라고 주장하지 않는다. 모델을 유일한 심판으로 사용하지 않는다.

Northstar는 개발용, Cedar/Lumen은 frozen-rule 평가용이다. 세 사례 합계도 공개하되 개발 사례 포함 지표와 heldout-only 지표를 따로 표시한다. 현 패키지의 gold는 author-proposed 상태다.

## 지표와 정확한 분모

| 지표 | 계산 | 실패·예외 |
|---|---|---|
| Location citation accuracy | 올바른 document/version/locator와 exact quote를 가진 citation 수 / 제출된 전체 citation 수 | citation 0개는 NA, 100% 아님 |
| Fabricated citations | 존재하지 않는 document/locator/quote를 가리킨 citation 절대 개수 | 0건 목표; 다른 문장의 실재 citation 오용은 entailment 실패로 추가 기록 |
| Citation completeness | citation이 필요한 factual claim 중 검증 가능한 citation을 가진 claim 수 / citation 필요한 factual claim 전체 | 근거 없는 사실 진술을 분모에서 제외하지 않음 |
| Entailment accuracy | 제출 citation이 실제로 해당 주장·기간·대상을 지지하는 claim 수 / citation 있는 factual claim 전체 | exact quote 검사와 별도 인간 판정 |
| Critical Top-3 coverage | `|matched Top3 ∩ gold critical| / |gold critical|` | 각 state gold는 1–3개. output<3은 채우지 않음 |
| Top-3 precision | `|matched Top3 ∩ gold critical| / |output Top3|` | output=0은 0; coverage와 함께 보고 |
| Transition exact match | before/after family order와 해결/재개 reason 모두 맞는 event 수 / 유효 승인 평가 event 수 | 무변화 event는 기대 무변화와 비교 |
| Negative-control stability | 기대하는 no-change/reject를 보인 negative 수 / 전체 negative 수 | 잘못된 source를 받아도 rank 같다고 성공 처리하지 않음 |
| Duplicate rate | 중복 request family 수(첫 항목 제외) / 출력 질문 수 | output0이면 NA, generation failure 별도 |
| Request actionability | 대상/자료유형/기간/criterion 네 요소가 모두 있는 질문 수 / 전체 질문 수 | 사람 0/1 checklist |
| Review correction rate | analyst가 의미·source·criterion을 수정해야 한 초안 수 / 전체 초안 수 | 수정 전·후 결과를 별도 저장 |
| Reproducibility | 같은 승인 상태·정책으로 동일 order/score/digest를 낸 반복 수 / 반복 전체 | timestamp-dependent audit hash는 이 지표 제외 |

citation accuracy≥95%, fabricated citations=0, critical Top-3 coverage≥80%는 **미검증 목표**다. 각 case×state×arm의 분자/분모를 먼저 공개하고 macro average(각 state 동일 가중)와 micro numerator/denominator를 나란히 제시한다. 제품 실패로 유효 output이 없으면 coverage/actionability를 0으로 처리하고 citation accuracy는 NA+failure flag로 기록한다. 좋은 출력만 골라 분모를 축소하지 않는다.

원문 snippet이 있는 것과 질문이 올바른 것의 차이를 보이기 위해 location·completeness·entailment를 분리한다. 추출기 오류로 읽지 못한 문서도 ingest failure율로 전체 문서 수를 분모로 보고한다.

## 표본과 불확실성

기본 자료는 3 Deal×2 state=6 positive state, event transition 3건, negative controls 15건이다. Case 내부 state·질문·citation은 서로 독립 표본이 아니다. 두 heldout Deal과 3 transition으로 통계적 유의성이나 일반적 우월성을 주장하지 않는다. 80%는 이 작은 transition 표본에서 2/3로는 충족되지 않고 3/3이어야 하므로 coverage와 transition을 혼동하지 않는다.

각 비율은 numerator/denominator와 Wilson 95% interval을 설명용으로 보고하되 의존성 때문에 모집단 CI로 해석하지 않는다고 명시한다. Deal 단위 평균·최솟값·case별 실패를 주요 요약으로 한다. 두 heldout case에 대한 bootstrap으로 정밀한 CI를 제시하지 않는다. 0 fabricated 관측도 모집단 0위험을 증명하지 않는다.

## Ablation과 negative controls

A1 no-adaptive는 B2, A2 no-gap, A3 no-materiality, A4 no-obtainability로 하나씩 제거한다. scoring 가중치 재정규화는 [05](05_SCORING_AND_ADAPTIVE_ENGINE.md)의 규칙을 사용하고 나머지 입력·승인·resolved exclusion은 고정한다. Bayesian 패널은 기본 rank와 독립이므로 패널 on/off에서 ranking이 **동일해야 한다**. 이 불변 테스트를 EIG 성능 향상이라고 보고하지 않는다.

기본 5개 negative와 추가 source conflict, prompt injection, unauthorized export를 수행한다. duplicate/no-evidence/unapproved 입력이 rank를 바꾼다면 adaptive 효과가 아니라 구현 결함으로 기록한다.

## 재현 실행 절차

1. source bytes와 gold를 freeze하고 hashes를 `evaluation/run_manifest.json`에 기록한다.
2. 모델 input allowlist audit를 실행하고 gold/expected 문자열 유출이 없음을 검사한다.
3. B0/B1 초안을 동일 예산으로 생성하고 B2/B3가 공유하는 구조화 초안을 생성한다. 수작업 수정을 기록한다.
4. 모든 arm의 initial Snapshot과 output을 저장한다.
5. 매 event는 baseline state로 reset한 뒤 하나씩 제공한다. B3 reviewer 승인과 B1-R 재질문을 별도 log로 기록한다.
6. 블라인드 가능한 평가자가 question family·citation correctness를 판정한다.
7. metric, 비용, 실패, 시간, ablation, negative 결과를 집계하고 raw annotations와 report를 보관한다.

후속 CLI 계약: `python -m orion.cli evaluate --arms B0 B1 B2 B3 B1-R --cases all --mode cached`는 **기능적 replay**이며 `--mode live --budget-usd 5`의 실제 모델 실험과 구분한다. 비용 초과 시 일부 결과를 미측정으로 남긴다. output report의 요약 열은 case/arm/state/N_citations/N_correct/N_fabricated/Top3_hits/gold_N/coverage/transition_pass/cost/status다.

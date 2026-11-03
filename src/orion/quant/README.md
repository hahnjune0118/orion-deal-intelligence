# Bayesian / EIG 및 선택형 연구 점수

이 모듈은 **명시적으로 작성된 합성 시나리오**의 계산기다. 실제 투자 성공확률을 추정하거나 실증적으로 보정하지 않는다. 문서에 주장이 쓰여 있다는 사실과 그 주장의 진실성은 다르다. 승인·반려·원문 검증은 기존 Chunk 2 서비스가 담당한다. 이 모듈은 승인 권한을 부여하지 않는다.

기존 `orion.domain.scoring.rank_state`와 scoring contract `1.0.0`은 변경하지 않았다. Bayesian/EIG를 켜고 꺼도 기존 질문 순위는 동일하다. `orion.quant.priority.rank_research`는 호출자가 별도로 선택하는 연구 실험이며 기존 제품 순위와 혼합하지 않는다. 연구 점수도 **EVSI가 아니다**.

## 1. 수식과 독립 계산

`posterior(p,a,b)`는 다음 식을 사용한다.

\[
P(H\mid E)=\frac{ap}{ap+b(1-p)}
\]

Blueprint의 합성 가정 `p=0.30, a=0.80, b=0.20`에 대해 실제 코드 결과는 다음과 같다.

| 항목 | 계산 | 결과 |
|---|---|---:|
| Positive predictive probability | `0.8×0.3 + 0.2×0.7` | 0.38 |
| Positive posterior | `0.24 / 0.38` | 0.631578947368421 |
| Negative predictive probability | `0.2×0.3 + 0.8×0.7` | 0.62 |
| Negative posterior | `0.06 / 0.62` | 0.096774193548387 |
| Prior entropy | `−p log₂p − (1−p) log₂(1−p)` | 0.881290899230693 bits |
| Expected posterior entropy | `0.38×H(12/19)+0.62×H(3/31)` | 0.645176971891755 bits |
| EIG | `H(0.3) − expected posterior entropy` | **0.236113927338937 bits** |

관측된 positive answer의 posterior entropy는 0.949452 bits로 prior보다 높다. 하나의 실현 결과는 불확실성을 늘릴 수 있다. EIG는 가능한 답변 전체에 대한 **관측 전 기대값**이므로 이 경우에도 양수다. 실현 정보 변화와 EIG를 혼동하지 않는다.

음성 결과의 likelihood는 양성 likelihood의 **여집합**이다. 양성의 두 likelihood를 서로 교환하는 방식이 아니다. 0 또는 1 prior는 허용하지만 predictive probability가 0인 관측은 `ValueError`다. exhaustive answer model 안에서 확률이 0인 답변의 posterior는 `None`이고 기대 entropy 기여는 0이다. NaN, Infinity, bool, 문자열, [0,1] 밖의 확률은 거절한다.

`tests/quant/test_bayes.py`는 별도의 60자리 Decimal 계산으로 posterior를 검증한다. EIG 테스트는 posterior/entropy 구현을 다시 호출해 기대값을 만드는 대신 2×2 joint probability table의 mutual-information/KL 식으로 교차 검증한다.

## 2. API와 필수 가정 출처

```python
from dataclasses import asdict
from orion.quant import binary_posteriors, binary_eig

posteriors = binary_posteriors(0.30, 0.80, 0.20)
information = binary_eig(
    0.30, 0.80, 0.20,
    "Blueprint illustrative binary scenario; analyst-authored, not empirical",
)
assert information is not None
print(asdict(information))
```

`binary_eig` 또는 `expected_information_gain`에 필요한 probability나 assumption source가 없으면 결과는 `None`이다. 임의 수치를 채우지 않는다. 확률을 명시했지만 분포가 잘못되면 `None`으로 조용히 감추지 않고 오류를 낸다. 다지선다 `AnswerLikelihood` 목록은 `H`와 `not H` 각각의 conditional likelihood 합이 1이어야 하며, answer label이 중복되어서는 안 된다. 계산 시간에 답변들이 실제로 상호배타적·완전한지는 Analyst가 검토해야 한다.

`ProbabilityAssumptions`는 `assumption_id`, `version`, `assumption_source`, `author_id`, `as_of`, `prior`, `likelihood_h`, `likelihood_not_h`를 보존한다. `interpretation`은 `synthetic_scenario_not_empirical`로 고정된다.

## 3. 중복·상관 증거와 순차 갱신

`BayesianLedger`는 hypothesis별로 다음을 확인한다.

- 승인되지 않은 증거와 probability 누락은 belief를 바꾸지 않는다.
- 같은 evidence ID 또는 동일 원문 fingerprint를 다시 제출하면 재계산하지 않는다.
- 동일 `evidence_group_id`나 선언된 상관 group은 기본적으로 추가 likelihood multiplication을 차단한다.
- 상관 관계는 대칭으로 보관한다. A→B 또는 B→A 순서 모두 차단하고, 선언된 관계의 전이 연결도 보수적으로 차단한다.
- 동일 원문을 새 group 이름으로 재제출해도 그 alias를 기존 group에 연결한다.
- 변경된 입력으로 이미 적용한 evidence ID를 재사용하거나, 새 evidence에 오래된 prior를 사용하면 오류다.
- 이미 독립으로 계산한 두 group 사이의 새로운 상관 관계가 나중에 드러나면 명시적 conditional model 없이 계속 갱신하지 않고 replay를 요구한다.

`source_fingerprint`는 승인된 source excerpt의 SHA-256이어야 한다. 독립성 group과 dependency는 source registry/Analyst 검토에서 정해야 한다. LLM이 자기 판단으로 새 group을 만들도록 허용하는 보안 경계는 이 계산기에 없다. 표현을 바꾼 의미상 중복은 해시만으로 찾을 수 없으므로 group 검토가 필요하다.

## 4. 명시적 conditional likelihood 경로

같은 고객의 계약과 검수·수금은 무조건 독립이라고 가정할 수 없다. 다음 관측에 대해 `P(E₂|H,E₁)`와 `P(E₂|not H,E₁)`를 직접 정의한 **검토된 합성 joint scenario**가 있을 때만 chain rule 경로를 선택할 수 있다.

```python
from hashlib import sha256
from orion.quant import BayesianLedger, ConditionalLikelihoodModel, ProbabilityAssumptions

ledger = BayesianLedger()
first = ProbabilityAssumptions(
    assumption_id="h1-contract-v1", assumption_source="Authored synthetic first-contract test",
    author_id="synthetic-analyst", as_of="2026-11-03",
    prior=.30, likelihood_h=.80, likelihood_not_h=.20,
)
event1 = ledger.update(
    hypothesis_id="h1", evidence_id="e_contract", evidence_group_id="customer-a",
    source_fingerprint=sha256(b"Synthetic signed contract excerpt").hexdigest(),
    assumptions=first, approved=True,
)
second = ProbabilityAssumptions(
    assumption_id="h1-execution-v1",
    assumption_source="P(execution|H,contract)=.75; P(execution|not H,contract)=.30; hypothetical",
    author_id="synthetic-analyst", as_of="2026-11-03",
    prior=event1.posterior, likelihood_h=.75, likelihood_not_h=.30,
)
conditional = ConditionalLikelihoodModel(
    model_id="h1-joint-contract-execution-v1", hypothesis_id="h1", evidence_id="e_execution",
    assumption_id="h1-execution-v1", conditioning_evidence_ids=["e_contract"],
    likelihood_h=.75, likelihood_not_h=.30,
    conditioning_group_ids=["customer-a"],
    assumption_source="Reviewed illustrative joint scenario; likelihoods conditional on signed contract",
    reviewer_id="synthetic-reviewer", reviewed_at="2026-11-03", review_status="approved",
)
event2 = ledger.update(
    hypothesis_id="h1", evidence_id="e_execution", evidence_group_id="customer-a",
    source_fingerprint=sha256(b"Distinct synthetic acceptance and collection record").hexdigest(),
    assumptions=second, approved=True, conditional_model=conditional,
)
assert abs(event2.posterior - 30 / 37) < 1e-12
```

이 모델은 현재 hypothesis, 새로운 evidence ID, probability assumption ID/version과 정확한 likelihood 값에 결합된다. conditioning evidence/group 목록은 해당 hypothesis에서 **이미 적용된 전체 history와 정확히 같아야 한다**. 누락·미래·다른 hypothesis·임의 group·미승인 모델이면 거절한다. identical source나 동일 evidence ID의 재사용은 conditional model로도 우회할 수 없다. 선언된 likelihood가 실제로 타당한지는 이 계산기가 입증하지 않으며, 합성 시나리오의 명시적 가정으로만 사용한다. retrospective correlation이 발견되었을 때는 이전 history를 적절한 joint model로 재작성하여 replay하는 것이 필요하다.

이 예의 합성 joint 계산은 `(.3×.8×.75) / (.3×.8×.75 + .7×.2×.30) = 30/37`이다. 두 번째 `.75/.30`은 독립 likelihood가 아니라 첫 사건을 조건으로 한 likelihood다. snapshot은 실제 likelihood, assumption author/date, conditional model source/reviewer/date와 conditioning ID를 모두 남긴다. JSON 직렬화는 `ledger.snapshot()`으로 가능하다. 기존 SQLite 도메인이나 ranking snapshot 계약은 바꾸지 않는다.

## 5. 선택형 연구 priority와 sensitivity

`ResearchPriorityPolicy`의 기본 가중치는 다음과 같다.

| 요소 | 가중치 | 정규화 |
|---|---:|---|
| Financial materiality | 0.30 | Analyst score / 5 |
| Evidence gap | 0.25 | Requirement gap / 5 |
| EIG | 0.20 | Binary entropy 기준 0–1 bits |
| Obtainability | 0.15 | Analyst score / 5 |
| Time/cost | 0.10 | `1 / (1 + days/10 + external_cost_minor/100000)` |

`score = 100 × (1 − evidence_overlap) × Σ(weight × normalized component)`.

- `external_cost_minor`는 USD cents다. 기본 비용 scale 100000은 $1,000이며 정책에서 공개적으로 변경할 수 있다.
- EIG·time/cost가 없으면 해당 가중치를 제외하고 나머지를 합계 1로 다시 정규화한다. EIG 누락은 probability를 0으로 만들지 않으며 정성적인 materiality/gap/obtainability fallback이다.
- materiality/obtainability 누락은 기존 기본값 3/2를 쓰고 provisional 표시한다.
- obtainability에 이미 시간·비용이 반영되었으면 `obtainability_includes_cost_time=True`로 time/cost 항을 제외한다.
- `evidence_overlap`은 명시적 Analyst 입력이다. 중복 group은 posterior 갱신 차단과 별도로 관리한다.
- draft/rejected 또는 resolved 질문은 research ranking에서 제외한다. 동점은 materiality, gap, question ID 순서로 정렬한다.

`sensitivity_analysis()`는 balanced, financial_materiality, information_first, no_bayesian_eig 정책의 전체 입력·점수·순위·rank delta를 반환한다. 다음 두 합성 질문의 실행 결과는 economic relevance와 information quantity가 다른 개념임을 보여준다.

공통 gap=4, obtainability=4, days=5, cost=$500이고, information 질문은 materiality=2/EIG=.9, financial 질문은 materiality=5/EIG=.1이다.

| 정책 | 1위 | Information 점수 | Financial 점수 |
|---|---|---:|---:|
| Balanced | Financial | 67.0 | 69.0 |
| Financial materiality | Financial | 60.5 | 75.5 |
| Information first | Information | 73.0 | 53.0 |
| No Bayesian/EIG | Financial | 61.25 | 83.75 |

이는 임의 설계 가중치에 대한 민감도 예시다. 보편적으로 최적인 투자 질문이라는 의미가 아니다. 정책별 누락 항 재정규화가 있으므로 다른 정책의 score 절댓값을 성과처럼 비교하지 않는다.

`eig_sensitivity([.1,.3,.5], .8, .2, source)` 결과 EIG는 각각 0.1048183, 0.2361139, 0.2780719 bits다. prior 선택에 따라 정보량이 바뀌며, 이 수치도 실증 추정이 아니다.

## 6. 실행

```bash
python -m pytest tests/quant -q --strict-markers
```

새 외부 라이브러리는 필요 없다. Python 표준 라이브러리와 기존 Pydantic을 사용한다. 모든 테스트는 합성 수학·승인 경계·의존성·누락·불가능 관측의 결정론적 테스트다. LLM 벤치마크 결과나 투자 성과로 해석하지 않는다.

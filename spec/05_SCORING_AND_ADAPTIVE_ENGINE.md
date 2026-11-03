# Scoring과 Adaptive Engine

Contract / scoring 1.0.0 · **분석가가 이해할 수 있는 휴리스틱 우선순위**다. Deal 성공확률·손실확률·EVSI가 아니다.

## 1 계산 대상과 Evidence Gap

입력은 승인된 question, 승인된 active evidence, validated SourceSpan, reviewer가 확정한 requirement·M·O다. draft/rejected/duplicate 질문은 제외한다. requirement가 하나도 없는 question은 invalid다. 승인 전 evidence는 현재 순위에서 보이지 않는다.

Evidence가 condition을 충족하려면 같은 claim과 criterion key, `stance=supports`, `source_reliability≥min_reliability`, 유효한 span, 필요한 경우 `verification_level=independent_check`가 모두 맞아야 한다. 여러 증빙이 같은 조건을 만족해도 조건은 1회만 센다. source_reliability=null은 자동 충족으로 인정하지 않는다. LLM은 reliability 등급을 확정하지 못한다.

관련 key에 유효·승인된 refutes evidence가 있고 reliability가 최소치 이상이면 unresolved conflict다. 반증을 발견하는 데 independent_check를 필수로 요구하지 않지만, 이를 곧 독립적인 사실 판정으로 표현하지 않는다. 명시적인 supersedes 승인 없이 반증을 제거하지 않는다.

전체 조건 `n`, 충족 조건 `k`에 대해:

\[
G=\begin{cases}5 & \text{unresolved contradiction}\\5(1-k/n)&\text{otherwise}\end{cases}
\]

`k=n`이고 충돌이 없으면 resolved로 먼저 제외한다. 나머지 질문만 점수 계산한다. SourceSpan의 존재, provenance, reliability, truth verification, 업무상 fulfillment는 각기 다른 개념이다.

## 2 Financial Materiality M

사용 가능한 금액이 있으면 같은 통화·기간의 exposure/연간 revenue 비율로 등급을 정한다. 손실 기대값을 계산하지 않는다. exposure는 검증할 거래/고객/잔액의 규모이며 실제 조정액으로 단정하지 않는다.

| 비율 r | M |
|---|---:|
| 0≤r<1% | 0 |
| 1%≤r<3% | 1 |
| 3%≤r<5% | 2 |
| 5%≤r<10% | 3 |
| 10%≤r<20% | 4 |
| r≥20% | 5 |

`basis=objective_ratio`는 exposure/denominator와 원문 참조를 저장하고 코드는 bin을 검사한다. 매출이 0·음수·미확보이면 그 방식을 쓰지 않는다. EBITDA가 작거나 음수일 때도 분모를 임의 바꾸지 않는다.

금액으로 표현하기 어려운 중요도는 `analyst_rubric`: 0=현재 screening 판단에 영향 없음, 1=부수적 설명, 2=국소 operating assumption, 3=주요 driver의 민감도, 4=중대한 driver/고객 의존, 5=핵심 thesis 성립 또는 screening 중단을 좌우함. 선택 이유·대상·기간을 적고 reviewer가 승인한다. 예시는 이 주관 루브릭을 사용하며 검증된 재무 위험모형이라고 부르지 않는다. basis=unknown이면 score=null → M=3, provisional.

## 3 Obtainability O와 시간·비용

요청하면 검토 가능한 문서를 확보하는 데 드는 예상 영업일과 외부 직접비를 사용한다. 비용은 USD cents로 저장한다. 시간과 비용을 각각 다음 bin으로 바꾸고 `O=min(O_days,O_cost)`로 결정한다.

| O | 예상 영업일 상한 | 외부 직접비 상한 USD |
|---:|---:|---:|
| 5 | 1 | 0 |
| 4 | 3 | 100 |
| 3 | 7 | 500 |
| 2 | 14 | 1,500 |
| 1 | 30 | 5,000 |
| 0 | 30 초과 | 5,000 초과 |

각 축은 독립적으로 첫 충족 bin을 찾는다. 예: 2일·$600이면 `min(4,2)=2`다. 두 값이 있어야 `derived_cost_time`을 쓴다. 수치를 알 수 없지만 analyst가 등급을 판단하면 `analyst_estimate`, score, rationale를 기록한다. 둘 다 확정할 수 없으면 unknown/null → O=2, provisional. 높은 O는 획득이 쉬움을 뜻한다. 시간/비용에 대한 별도 감점은 없으므로 이중 계산하지 않는다.

## 4 최종 점수와 동점

\[
P=20(0.45G+0.40M+0.15O)=9G+8M+3O
\]

가중치는 연구 설계의 고정값이며 학습된 계수가 아니다. raw Decimal 점수 내림차순 → M 내림차순 → G 내림차순 → O 내림차순 → canonical_key ASCII 오름차순 → question_id ASCII 오름차순으로 정렬한다. 화면 반올림값으로 tie를 결정하지 않는다. 순위는 연속 1부터, Top-3는 가능한 첫 min(3,N)개다. 세 질문 미만이면 가짜 질문으로 채우지 않는다.

정확한 null, 0, 범위 초과를 구별한다. M/O가 범위 밖이거나 무효 비율이면 오류이지 clamp 대상이 아니다. ScoreRow.provisional은 M/O default가 사용되었음을 뜻하며 증빙 정확도나 확률을 뜻하지 않는다.

## 5 Worked transition

| Northstar 질문 | 초기 G/M/O | 초기 점수·순위 | A 계약 승인 후 |
|---|---|---|---|
| Aster 유료 계약 | 5/5/5 | 100 · 1 | 조건 충족, resolved, score/rank=null |
| Birch 독립 유료 계약 | 5/5/4 | 97 · 2 | 97 · 1 |
| 두 고객 검수·수금 | 5/4/4 | 89 · 3 | 89 · 2 |
| 고객 소유관계 독립성 | 5/4/3 | 86 · 4 | 86 · 3 |
| 반복매출 gross margin bridge | 5/3/3 | 78 · 5 | 78 · 4 |

입력 증빙은 계약A 한 건이며 수금 증빙이 아니다. 주 가설의 7조건(계약2·검수2·수금2·독립성1) 중 1조건만 충족하여 partial/document_only다. 반복매출 margin은 별도 claim이며 missing으로 남는다. 순위 상승은 미해결 질문의 **상대 승격**이다. 점수가 올랐다고 기록하지 않는다.

Cedar는 100점 cut-off 질문 해결 후 `[warranty 94, inventory 89, receivable 86]`이 Top-3다. Lumen은 기존 해결 renewal 질문에 반증이 생겨 `97`점으로 재개되고 `[renewal 97, labor 92, margin 89]`가 된다. JSON의 before/after와 실제 산술 검사는 QA 보고서에서 확인한다.

## 6 승인 commit 순서

1. reviewer·현재 Deal·payload hash를 검증한다. 이미 처리된 동일 명령이면 기존 결과만 반환한다.
2. expected revision, 문서·span·criterion·관계 무결성을 검증한다.
3. 새 evidence/relation을 approved로 저장한다. 중복 origin은 union하여 같은 key 충족을 한 번만 센다.
4. Claim support를 파생하고, 질문 resolved/open을 계산한다. conflict는 supersession 승인 없이는 유지한다.
5. 새 Snapshot을 계산한다. Top-3가 같아도 이유와 점수 변화를 비교한다.
6. before/after revision·decision·snapshot·audit를 한 트랜잭션에서 commit한다.

무관한 업로드는 관련 criterion이 없으므로 rank unchanged다. duplicate 업로드는 새 출처 숫자로 가산하지 않는다. 잘못된 locator·미승인 증빙은 승인 commit 자체가 차단된다. 기존 증빙 철회·부분 대체는 별도 reviewer decision과 새 버전이 필요하다. overwrite로 감사 이력을 없애지 않는다.

## 7 Bayesian와 EIG 선택 패널

MVP 순위에는 이 패널 값이 **0% 영향**을 준다. 정해진 기간과 판정 기준의 이진 H, 가상 prior p, positive likelihood a=P(E+|H), b=P(E+|¬H)를 analyst가 입력한 경우에만 계산한다.

\[
P(H|E+)=\frac{ap}{ap+b(1-p)},\quad P(E+)=ap+b(1-p)
\]

negative outcome은 a−=1−a, b−=1−b를 사용한다. 두 outcome은 mutually exclusive/exhaustive라는 가정을 표시한다. 불완전한 답변 공간에서는 EIG를 계산하지 않는다. entropy는 base-2 Shannon entropy, `H(0)=H(1)=0`으로 연속 확장한다.

\[
EIG=H(p)-[P(E+)H(p_+)+(1-P(E+))H(p_-)]
\]

예시 p=.30, a=.80, b=.20이면 P(E+)=.38, p+=.6315789474, p−=.0967741935이며 EIG는 약 .2361 bits다. 정확한 실행값은 QA 보고서에 기록한다. 수치는 모두 교육용 입력이며 실제 성공확률이 아니다. 관측 전 EIG와 관측 후 surprisal/entropy change를 혼동하지 않는다.

입력 누락·확률 범위 밖·관측된 outcome의 확률 0이면 계산 불가를 표시한다. 예상 EIG에서 확률 0 outcome 항은 0으로 처리하고 해당 posterior는 null이다. 독립성 가정 없이 여러 증거의 likelihood를 곱하지 않는다. 동일 origin/중복 증거를 반복 업데이트하지 않는다. calibration data와 utility가 없으므로 calibrated probability·EVSI라는 명칭을 쓰지 않는다.

## 8 민감도와 실패 공개

평가의 ablation은 Gap 제거, M 제거, O 제거, adaptive update 제거를 한 번에 하나씩 수행한다. 제거한 항은 0으로 놓고 나머지 가중치를 원래 총합으로 다시 정규화하며 resolved exclusion·승인 경계는 유지한다. 이는 별도 실험 scoring version이고 제품 Snapshot과 섞지 않는다. 가중치를 gold 성능에 맞추어 변경한 뒤 같은 gold로 평가하지 않는다.

중요하지만 매우 획득하기 어려운 질문은 O로 다소 내려갈 수 있다. 그래서 각 요소와 Top-3 밖의 중대한 질문도 확인할 수 있도록 전체 grid를 제공한다. 이 루브릭의 한계를 숨기기 위해 확률이나 예상손실 숫자를 덧붙이지 않는다.

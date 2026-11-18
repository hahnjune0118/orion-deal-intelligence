from copy import deepcopy
import math
import pytest

from orion.rules import engine as e
from orion.rules.library import RULES


def example():
    s=e.initial('검증 기업','2025년','subscription')
    s['documents']=[dict(id='d_1',filename='source.txt',sha256='a'*64,version=1,group='company',
                        spans=[dict(id='s1',text='반복매출 구독 갱신 매출 수금 고객 성장',location='1행')])]
    e.analyze(s)
    for h in s['hypotheses']:
        h.update(approved=True,prior=.3,prior_source='합성 확률 가정')
    s['demo']=True
    e.generate(s)
    return s


def evidence(question='recurring.definition',outcome='support',**overrides):
    return dict(question=question,outcome=outcome,response='계약 원문에 따른 검토 결과입니다.',note='원문과 정의의 연결을 검토함',
                group='group-1',independent=False,**overrides)


def test_real_project_has_no_fabricated_probabilities_or_evsi():
    s=example();s['models']={}
    for h in s['hypotheses']:h['prior']=None
    v=e.view(s)
    assert all(q['eig'] is None and q['evsi'] is None for q in v['questions'])
    assert all(h['probability'] is None for h in v['hypotheses'])
    assert all(q['provisional'] for q in v['questions'])


def test_rule_selection_no_saas_metrics_for_plain_manufacturer():
    s=e.initial('기계 기업','2025','manufacturing')
    s['documents']=[dict(spans=[dict(id='s1',text='설비 투자 유지보수 원가 매출',location='1행')])]
    e.analyze(s)
    assert 'recurring' not in {h['id'] for h in s['hypotheses']}
    assert 'capex' in {h['id'] for h in s['hypotheses']}
    assert all(not h['approved'] for h in s['hypotheses'])


def test_generation_requires_approval_and_preserves_ids_and_edits():
    s=e.initial('기업','기간','general')
    with pytest.raises(ValueError):e.generate(s)
    s=example();q=s['questions'][0];q['title']='검토자가 수정한 질문'
    ids=[q['id'] for q in s['questions']]
    e.generate(s)
    assert [q['id'] for q in s['questions']]==ids
    assert s['questions'][0]['title']=='검토자가 수정한 질문'


def test_positive_update_matches_independent_decimal_arithmetic_and_activates_followup():
    s=example();before=e.snapshot(s)
    event=e.evidence_apply(s,evidence())
    p,applied=e.replay(s)
    assert p['recurring']==pytest.approx(24/38)
    assert '반영' in applied[event['id']]
    after=e.snapshot(s)
    assert before['questions']['recurring.cohort']['active'] is False
    assert after['questions']['recurring.cohort']['active'] is True
    assert 'recurring.definition' not in after['ranks']
    assert before['ranks'] != after['ranks']


def test_contradiction_opens_different_followup_and_rejection_changes_no_recommendation():
    s=example();before=e.snapshot(s)
    e.evidence_apply(s,evidence(outcome='contradict'),reject=True)
    assert e.snapshot(s)['ranks']==before['ranks']
    assert e.replay(s)[0]['recurring']==.3
    e.evidence_apply(s,evidence(outcome='contradict'))
    assert e.replay(s)[0]['recurring']==pytest.approx(.06/.62)
    assert e.snapshot(s)['questions']['recurring.correct']['active']
    assert not e.snapshot(s)['questions']['recurring.cohort']['active']


def test_insufficient_keeps_probability_and_question_open():
    s=example();e.evidence_apply(s,evidence(outcome='insufficient'))
    assert e.replay(s)[0]['recurring']==.3
    q=next(q for q in e.view(s)['questions'] if q['id']=='recurring.definition')
    assert q['eligible'] and q['status']=='보완 필요'


def test_duplicate_quote_rejected_even_if_group_renamed():
    s=example();e.evidence_apply(s,evidence())
    other=evidence('recurring.contracts');other['group']='alias'
    with pytest.raises(ValueError,match='동일 원문'):e.evidence_apply(s,other)


@pytest.mark.parametrize('same_group,independent,expected',[(True,True,24/38),(False,False,24/38),(False,True,48/55)])
def test_dependent_evidence_is_not_multiplied(same_group,independent,expected):
    s=example();e.evidence_apply(s,evidence())
    second=evidence('recurring.contracts');second.update(response='다른 계약의 구체적인 원문 증거입니다.',group='group-1' if same_group else 'bank',independent=independent)
    e.evidence_apply(s,second)
    assert e.replay(s)[0]['recurring']==pytest.approx(expected)


def test_revocation_replays_and_reopens_question():
    s=example();event=e.evidence_apply(s,evidence());event['status']='revoked'
    assert e.replay(s)[0]['recurring']==.3
    q=next(q for q in e.view(s)['questions'] if q['id']=='recurring.definition')
    assert q['eligible'] and q['status']=='검토 대기'


def test_evsi_is_decision_value_not_eig_and_cost_is_separate():
    model=dict(a=.8,b=.2,source='계산 예시')
    decision=dict(utilities=[[100,-100],[0,0]],cost=5,delay=2,unit='점수',source='시나리오')
    value=e.evsi(.3,model,decision)
    assert value['gross']==pytest.approx(10)
    assert value['net']==pytest.approx(3)
    assert value['evpi']==pytest.approx(30)
    decision['utilities']=[[100,100],[0,0]]
    assert e.evsi(.3,model,decision)['gross']==pytest.approx(0)
    assert e.evsi(.3,{**model,'a':.5,'b':.5},decision)['gross']==0


def test_eig_is_bounded_and_not_added_in_money_units():
    s=example()
    for q in e.view(s)['questions']:
        assert 0<=q['eig']<=1
        assert q['score']<=100
        assert q['evsi'] is None
    s['models'].pop('recurring.definition')
    q=next(q for q in e.view(s)['questions'] if q['id']=='recurring.definition')
    assert q['eig'] is None
    assert q['score']==pytest.approx(100*(.35+.25*.8+.15*.6)/.75)


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,-.1,1.1])
def test_invalid_probability_is_rejected(bad):
    with pytest.raises(ValueError):e.number(bad,'確率')


def test_evidence_is_bound_to_immutable_likelihood_at_application():
    s=example();e.evidence_apply(s,evidence())
    before=e.replay(s)[0]['recurring']
    s['models']['recurring.definition']['a']=.1
    assert e.replay(s)[0]['recurring']==before


def test_unrelated_evidence_does_not_change_other_hypothesis():
    s=example();before=e.replay(s)[0]
    e.evidence_apply(s,evidence('customer.terms'))
    after=e.replay(s)[0]
    assert before['recurring']==after['recurring']
    assert before['cash']==after['cash']
    assert before['customer']!=after['customer']


def test_manual_question_and_missing_numeric_inputs():
    s=example();e.custom_question(s,dict(topic='cash',title='원문에 없는 위험을 추가 검증합니까?',request='검증 자료',criterion='확인 기준'))
    q=s['questions'][-1]
    assert q['id'].startswith('custom.')
    row=next(qr for qr in e.view(s)['questions'] if qr['id']==q['id'])
    assert row['eig'] is None

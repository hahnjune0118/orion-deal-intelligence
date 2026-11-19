"""Finance signs, classification boundaries and scenario isolation."""
from copy import deepcopy
import pytest
from orion.rules import engine, deal_visuals as v
from orion.web.rules_app import create_rules_app


def state():
    return engine.initial('합성 거래','2025','service')


def test_flow_gap_never_creates_an_invented_balancing_flow():
    m=v.sample();assert v.calculate(m)['flow']['gap']=='0'
    m['flows'].pop();d=v.calculate(m)
    assert d['flow']['gap']=='20' and len(m['flows'])==7
    assert d['warnings']


def test_cb_split_rcps_classification_and_other_issuers():
    m=v.sample();a=v.calculate(m)['capital']
    assert a['liability']=='170' and a['equity']=='130' and a['balance_gap']=='0'
    m['instruments'][3]['classification']='unknown'
    a=v.calculate(m)['capital'];assert a['unknown']=='20' and a['balance_gap'] is None
    m['instruments'][0]['issuer']='다른 법인'
    a=v.calculate(m)['capital'];assert a['equity']=='10' and a['excluded_issuers']==1


def test_fdd_status_and_equity_value_signs_are_exact():
    m=v.sample();before=deepcopy(m);a=v.calculate(m);p=v.calculate(m,True)
    assert a['bridges']['qoe']['end']=='32' and a['bridges']['nwc']['end']=='22'
    assert a['bridges']['net_debt']['end']=='55'
    assert a['price']['start']=='193' and a['price']['end']=='201'
    assert [r['amount'] for r in a['price']['rows']]==['16','-3','-5']
    assert p['bridges']['qoe']['end']=='31' and p['price']['end']=='193'
    assert m==before
    m.update(ev_mode='fixed',enterprise_value='240')
    assert v.calculate(m)['price']['end']=='185'
    assert v.calculate(m)['price']['rows'][0]['amount']=='0'


def test_duplicate_nwc_debt_item_blocks_price_preview_only():
    m=v.sample();m['adjustments'][4].update(economic_key='old_ar',stream='net_debt',category='기타')
    assert v.calculate(m)['price']['available']
    d=v.calculate(m,True)
    assert not d['price']['available'] and any('중복' in w for w in d['warnings'])


def test_missing_base_is_not_zero_and_net_cash_is_supported():
    m=v.empty();m['bases']['net_debt']='-20';d=v.calculate(m)
    assert not d['bridges']['qoe']['available']
    assert d['bridges']['net_debt']['end']=='-20' and not d['price']['available']


def test_missing_economic_key_and_scope_do_not_produce_a_price():
    m=v.sample();m['adjustments'][3]['economic_key']=''
    assert not v.calculate(m)['price']['available']
    m=v.sample();m['scope']=''
    assert not v.calculate(m)['price']['available']


@pytest.mark.parametrize('bad',[True,'NaN','Infinity','-1'])
def test_invalid_source_amount_is_rejected(bad):
    with pytest.raises(ValueError):v.update(state(),dict(operation='save',section='flows',side='source',label='합성 조달',note='합성',amount=bad,refs=[]))


def test_invalid_split_foreign_refs_and_unit_changes_are_rejected():
    s=state();data=dict(operation='save',section='instruments',label='CB',note='계약 미검토',kind='CB',issuer='SPC',classification='split',book=100,liability_part=120,refs=[])
    with pytest.raises(ValueError,match='복합'):v.update(s,data)
    with pytest.raises(ValueError,match='원문'):v.update(s,{**data,'refs':['foreign-source']})
    s['deal_visuals']['assets']='100'
    with pytest.raises(ValueError,match='단위'):v.update(s,dict(operation='settings',unit='USD'))


def test_negative_retained_equity_is_numeric_not_a_negative_liability():
    s=state();data=dict(operation='save',section='instruments',label='누적 손실',kind='기타 자본',classification='equity',issuer='인수 주체 / SPC',book='-10',note='합성 자본 손실',refs=[])
    v.update(s,data)
    assert v.view(s)['accepted']['capital']['equity']=='-10'
    with pytest.raises(ValueError):v.update(s,{**data,'classification':'liability'})


def test_budget_import_reconciles_without_inventing_financing_terms():
    s=state();s['case_study']=dict(waterfall=dict(values=[100,-40,-30,30],labels=['재원','매매대금','상환','잔여 현금'],refs=[],note='합성 예산'))
    v.import_budget(s);d=v.view(s)
    assert d['accepted']['flow']['gap']=='0' and not d['model']['instruments']
    assert d['model']['flows'][0]['label'].endswith('조달자 미분류')
    with pytest.raises(ValueError,match='중복'):v.import_budget(s)


def test_case_budget_preview_is_read_only_and_becomes_editable_on_save():
    s=state();s['case_study']=dict(waterfall=dict(values=[100,-60,40],labels=['재원','대금','유보'],refs=[],note='합성 예산'))
    original=deepcopy(s);view=v.view(s)
    assert s==original and view['model']['linked_preview']
    row=view['model']['flows'][1]
    v.update(s,dict(operation='save',section='flows',item_id=row['id'],side='use',label=row['label'],amount='61',note='합성 수정',refs=[]))
    assert not v.view(s)['model']['linked_preview']
    assert v.view(s)['accepted']['flow']['gap']=='-1'


def test_visual_saves_are_versioned_and_isolated_from_evidence(tmp_path):
    app=create_rules_app(tmp_path);app.testing=True;c=app.test_client();headers={'Origin':'http://localhost'}
    p=c.post('/api/example',json={},headers=headers).get_json();pid=p['id'];before=p['state']
    body=dict(version=p['version'],operation='save',section='adjustments',stream='qoe',category='일회성 비용',status='accepted',amount='1.2',label='검토 가정',note='합성 조정',refs=[],question_id='recurring.definition')
    r=c.post(f'/api/projects/{pid}/actions/visual',json=body,headers=headers)
    assert r.status_code==200,r.get_json()
    saved=r.get_json();assert saved['version']==p['version']+1
    for key in ('evidence','hypotheses','recommendations'):assert saved['state'][key]==before[key]
    assert saved['state']['visual_workspace']['accepted']['bridges']['qoe']['end']=='33.2'
    history=c.get(f'/api/projects/{pid}/history').get_json()
    assert history[-1]['deal_visuals']['adjustments'][-1]['amount']=='1.2'
    assert c.post(f'/api/projects/{pid}/actions/visual',json=body,headers=headers).status_code==409
    # Derived-value validation must happen before commit, not in the response after saving.
    body.update(version=saved['version'],amount='1000000000000000000')
    assert c.post(f'/api/projects/{pid}/actions/visual',json=body,headers=headers).status_code==400
    assert c.get(f'/api/projects/{pid}').get_json()['version']==saved['version']

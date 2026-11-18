from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from orion.rules.case_studies import CaseStudies,apply_scenario
from orion.rules.store import Store
from orion.rules import engine
from orion.web.rules_app import create_rules_app


def write_case(root):
    span=dict(id='s_case',location='시트 입력 · B2',text='거래대금 100억원. 전환 조건은 미합의.',sha256=sha256('거래대금 100억원. 전환 조건은 미합의.'.encode()).hexdigest())
    content=(span['location']+'\n'+span['text']).encode()
    doc=dict(id='d_case',filename='대상사_구조.xlsx',key='model',masked=True,group='advisor',origin='analyst',version=1,spans=[span],
             sha256=sha256(content).hexdigest(),warnings=['마스킹 텍스트. 원본 제공 없음.'],parsed_units=1,total_units=1,status='검토 필요')
    h=dict(id='control',label='지배권',title='지배권 유지가 가능하다.',counter='지배권을 유지할 수 없다.',refs=['s_case'],approved=True,prior=None,prior_source='',prior_version=0)
    q=dict(id='case.cb',topic='control',title='전환 조건을 확인했습니까?',request='체결 계약',criterion='계약 대사',importance=5,obtainability=3,mandatory=True,parent=None,answer=None,source_refs=['s_case'])
    follow={**q,'id':'case.follow','title':'보호조항 대안은 무엇입니까?','parent':'case.cb','answer':'contradict'}
    source='확률·효용·비용은 원문에서 추정하지 않은 실습 가정'
    case=dict(id='test-case',title='익명화 거래',description='익명화 사례',schema='orion-anonymized-case-1',period='2025',industry='service',documents=[doc],hypotheses=[h],questions=[q,follow],
       case_study=dict(description='익명화 실제 딜. 검토 초안',note='규정의 현재 유효성은 미검증',masking='식별 정보 마스킹',metrics=[dict(label='거래대금',value='100억원',basis='자료 기재',refs=['s_case'])],
       versions=[dict(label='초안',detail='미확정',refs=['s_case'])],issues=[dict(title='전환 조건은?',question='case.cb',detail='미합의',refs=['s_case'])],scenario_enabled=False,
       waterfall=dict(title='단순 자금 연결',labels=['총액','구주','현금','잔여'],values=[100,-10,-40,50],note='비용 차감 전',refs=['s_case']),
       dilution=dict(title='지분 민감도',labels=['전환 전','전환 후'],values=[70,45],note='가정별 지분',refs=['s_case']),
       practice_assumptions=dict(source=source,priors={'control':.3},models={q['id']:dict(a=.8,b=.2),follow['id']:dict(a=.8,b=.2)},
          decisions={q['id']:dict(go_h=100,go_not=-100,hold_h=0,hold_not=0,cost=5,delay=2,unit='실습 효용점수')}),
       evidence_samples=[dict(label='가상 후속 증거 · 보호조항 미수용',question=q['id'],response='[가상 증거 · 실제 자료 아님] 보호조항을 수용하지 않았다고 가정.',note='실습용 입력이며 실제 협의 결과가 아닙니다.',group='practice',outcome='contradict',simulated=True)]))
    dest=Path(root)/'case-studies';dest.mkdir(parents=True,exist_ok=True)
    (dest/'test-case.json').write_text(json.dumps(case,ensure_ascii=False),encoding='utf-8')
    return case


def test_case_catalog_open_is_atomic_persistent_and_idempotent(tmp_path):
    write_case(tmp_path);cases=CaseStudies(tmp_path/'case-studies');store=Store(tmp_path/'db.sqlite3')
    assert cases.catalog()[0]['id']=='test-case'
    row=cases.open(store,'test-case');state=row['state']
    assert not state['demo'] and all(h['prior'] is None for h in state['hypotheses'])
    assert len(state['questions'])==2
    assert all(q['eig'] is None for q in engine.view(state)['questions'])
    name,data=store.file(row['id'],'d_case')
    assert name.endswith('_마스킹텍스트.txt') and not data.startswith(b'PK')
    assert cases.open(store,'test-case')['id']==row['id']
    assert cases.open(store,'test-case',copy=True)['id']!=row['id']
    assert len(Store(tmp_path/'db.sqlite3').list())==2


def test_practice_assumptions_are_explicit_and_have_independent_math(tmp_path):
    write_case(tmp_path);cases=CaseStudies(tmp_path/'case-studies');store=Store(tmp_path/'db.sqlite3')
    state=cases.open(store,'test-case')['state'];apply_scenario(state)
    q=engine.view(state)['questions'][0]
    assert q['eig']==pytest.approx(.236113927338937,abs=1e-10)
    assert q['evsi']['gross']==pytest.approx(10)
    assert q['evsi']['net']==pytest.approx(3)
    assert q['provisional']
    with pytest.raises(ValueError):apply_scenario(state)
    event=engine.evidence_apply(state,dict(question=q['id'],outcome='contradict',response='가상 답변',note='연습입니다.',practice=True))
    assert event['practice']
    view=engine.view(state)
    assert view['hypotheses'][0]['probability']==pytest.approx(.06/.62)
    assert view['questions'][1]['active']
    ids=[q['id'] for q in view['questions']]
    engine.analyze(state);engine.generate(state)
    assert [q['id'] for q in state['questions']]==ids
    assert len(state['hypotheses'])==1


@pytest.mark.parametrize('broken',['hash','refs','probability','unmasked'])
def test_invalid_case_never_creates_partial_project(tmp_path,broken):
    p=write_case(tmp_path)
    if broken=='hash':p['documents'][0]['sha256']='0'*64
    if broken=='refs':p['questions'][0]['source_refs']=['absent']
    if broken=='probability':p['hypotheses'][0]['prior']=.99
    if broken=='unmasked':p['documents'][0]['masked']=False
    (tmp_path/'case-studies/test-case.json').write_text(json.dumps(p),encoding='utf-8')
    store=Store(tmp_path/'db.sqlite3')
    with pytest.raises(ValueError):CaseStudies(tmp_path/'case-studies').open(store,'test-case')
    assert store.list()==[]


def test_case_routes_keep_origin_boundary_and_never_offer_original_binary(tmp_path):
    write_case(tmp_path);app=create_rules_app(tmp_path);app.testing=True;c=app.test_client()
    assert c.get('/api/cases').status_code==200
    assert c.post('/api/cases/test-case/open',json={}).status_code==403
    opened=c.post('/api/cases/test-case/open',json={},headers={'Origin':'http://localhost'}).get_json()
    text=c.get('/api/projects/'+opened['id']+'/files/d_case')
    assert text.headers['Content-Type'].startswith('text/plain')
    assert b'application/vnd' not in text.data and b'PK'!=text.data[:2]
    assert c.get('/.local/case-prep/raw.json').status_code==404
    assert c.get('/assets/../../.local/case-prep/raw.json').status_code==404
    with pytest.raises(ValueError):CaseStudies(tmp_path/'case-studies').read('../anything')


def test_two_cases_keep_evidence_files_and_assumptions_separate(tmp_path):
    original=write_case(tmp_path)
    second=json.loads(json.dumps(original).replace('test-case','second-case').replace('d_case','d_second').replace('s_case','s_second'))
    second['title']='다른 업종 사례'
    (tmp_path/'case-studies/second-case.json').write_text(json.dumps(second),encoding='utf-8')
    cases=CaseStudies(tmp_path/'case-studies');store=Store(tmp_path/'db.sqlite3')
    assert len(cases.catalog())==2
    first=cases.open(store,'test-case');other=cases.open(store,'second-case')
    store.update(other['id'],other['version'],apply_scenario)
    assert all(h['prior'] is None for h in store.get(first['id'])['state']['hypotheses'])
    with pytest.raises(ValueError):store.file(first['id'],'d_second')
    with pytest.raises(ValueError):store.file(other['id'],'d_case')
    assert cases.open(store,'test-case')['id']==first['id']


def test_practice_profile_accepts_zero_prior_and_keeps_custom_question_unmodeled(tmp_path):
    pack=write_case(tmp_path);pack['case_study']['practice_assumptions']['priors']['control']=0
    (tmp_path/'case-studies/test-case.json').write_text(json.dumps(pack),encoding='utf-8')
    store=Store(tmp_path/'db.sqlite3')
    state=CaseStudies(tmp_path/'case-studies').open(store,'test-case')['state']
    engine.custom_question(state,dict(topic='control',title='추가 검토 질문',request='추가 원문',criterion='원문 검토'))
    custom=state['questions'][-1]['id']
    apply_scenario(state)
    assert state['hypotheses'][0]['prior']==0
    assert custom not in state['models']
    assert engine.view(state)['questions'][-1]['eig'] is None

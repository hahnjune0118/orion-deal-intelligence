"""Source quality, conservative reconciliation and read-only decision experiments."""
from copy import deepcopy
import io
import json
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from openpyxl import Workbook

from orion.rules import engine, financial, retrieval, analysis, benchmark, reporting
from orion.rules.parsing import parse
from orion.web.rules_app import create_rules_app


def workbook(value=100,unit='억원',period='2025년',scope='별도',basis='실적'):
    wb=Workbook();ws=wb.active;ws.title='손익'
    ws.append(['항목','값','단위','기간','범위','구분'])
    ws.append(['매출',value,unit,period,scope,basis])
    buf=io.BytesIO();wb.save(buf);wb.close();return buf.getvalue()


def doc(raw,name,identifier):
    return dict(id=identifier,filename=name,version=1,group=identifier,origin='company',**parse(raw,name))


def state_with_facts(value=90,unit='억원',**kwargs):
    s=engine.initial('합성 기업','2025년','general')
    s['documents']=[doc(workbook(),'a.xlsx','a'),doc(workbook(value,unit,**kwargs),'b.xlsx','b')]
    engine.analyze(s)
    for h in s['hypotheses']:h.update(approved=True,prior=.3,prior_source='합성 가정')
    engine.generate(s)
    return s


def review(s):
    for f in list(s['financial_facts']):engine.fact_update(s,{**f,'reviewed':True,'review_note':'원문 셀과 단위·기간·범위를 대조한 합성 검토'})


def test_xlsx_cells_formula_cache_and_location_remain_distinct():
    raw=workbook('=SUM(40,60)')
    result=parse(raw,'formula.xlsx')
    cell=next(s for s in result['spans'] if s.get('cell',{}).get('address')=='B2')
    assert cell['text']=='=SUM(40,60)'
    assert cell['cell']['formula']=='=SUM(40,60)' and cell['cell']['cached'] is None
    assert 'fact' not in cell['cell']
    assert '시트 손익 · 셀 B2' in cell['location']
    assert any('계산값 없음' in x for x in result['warnings'])
    # A cached value belongs to the saved workbook; the parser does not execute SUM.
    buf=io.BytesIO()
    with ZipFile(io.BytesIO(raw)) as z,ZipFile(buf,'w',ZIP_DEFLATED) as out:
        for item in z.infolist():
            body=z.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':body=body.replace(b'<f>SUM(40,60)</f><v></v>',b'<f>SUM(40,60)</f><v>100</v>')
            out.writestr(item,body)
    cached=parse(buf.getvalue(),'cached.xlsx')
    cell=next(s for s in cached['spans'] if s.get('cell',{}).get('address')=='B2')
    assert cell['cell']['cached']==100 and cell['cell']['fact']['value']=='100'


def test_error_and_oversized_excel_do_not_become_facts_or_partial_success():
    result=parse(workbook('#DIV/0!'),'error.xlsx')
    assert any('Excel 오류' in w for w in result['warnings'])
    assert not any(s.get('cell',{}).get('fact') for s in result['spans'])
    wb=Workbook();wb.active['Z3000']=1;buf=io.BytesIO();wb.save(buf)
    with pytest.raises(ValueError,match='한도'):parse(buf.getvalue(),'large.xlsx')


def test_no_unrelated_text_is_called_a_data_grounded_hypothesis():
    s=engine.initial('합성 기업','2025','general')
    s['documents']=[doc('오늘의 날씨는 맑습니다.'.encode(),'weather.txt','d')]
    engine.analyze(s)
    assert len(s['hypotheses'])==3
    assert all(not h['refs'] and h['origin_kind'].startswith('기본 점검') for h in s['hypotheses'])


def test_bm25_retrieves_financial_synonyms_and_never_foreign_project_text():
    documents=[dict(id='d',filename='a.txt',spans=[dict(id='r',text='Revenue contract sales'),dict(id='x',text='오늘 날씨와 운동')])]
    found=retrieval.search(documents,'매출')
    assert found[0]['id']=='r' and found[0]['retrieval']=='local-bm25-1'
    assert retrieval.search(documents,'해당없음')==[]


def test_differences_require_review_and_do_not_mean_accounting_error():
    s=state_with_facts()
    assert s['reconciliations']==[]
    review(s)
    assert s['reconciliations'][0]['status']=='대사 차이 · 원인 미판정'
    assert s['reconciliations'][0]['difference']=='1000000000'
    q=next(q for q in engine.view(s)['questions'] if q.get('reconciliation_signature'))
    assert q['eligible'] and len(q['refs'])==2
    # A change of basis must deactivate the stale question rather than preserve its assertion.
    f=s['financial_facts'][1];engine.fact_update(s,{**f,'period':'2026년','reviewed':True,'review_note':'기간 재확인'})
    assert not next(x for x in engine.view(s)['questions'] if x['id']==q['id'])['active']


@pytest.mark.parametrize('kwargs',[dict(period='2026년'),dict(scope='연결'),dict(basis='계획')])
def test_different_financial_bases_are_never_compared(kwargs):
    s=state_with_facts(**kwargs);review(s)
    assert s['reconciliations']==[]


def test_same_value_in_different_units_reconciles_to_zero():
    s=state_with_facts(value=10000,unit='백만원');review(s)
    assert s['reconciliations'][0]['status']=='일치'
    assert not any(q.get('reconciliation_signature') for q in s['questions'])


def test_snapshot_preserves_evsi_assumptions_and_old_snapshot_is_not_rewritten():
    s=state_with_facts();key=s['questions'][0]['id']
    s['models'][key]=dict(a=.8,b=.2,source='합성 우도')
    s['decisions'][key]=dict(utilities=[[100,-100],[0,0]],cost=5,delay=2,unit='점수',source='합성 효용')
    snap=engine.snapshot(s);s['decisions'][key]['cost']=50
    assert snap['decisions'][key]['cost']==5
    assert snap['questions'][key]['evsi']['net']==pytest.approx(3)
    assert engine.snapshot(s)['questions'][key]['evsi']['net']==pytest.approx(-42)


def test_tree_sensitivity_and_comparison_are_pure_and_respect_answer_mass():
    s=state_with_facts();key=s['questions'][0]['id']
    s['models'][key]=dict(a=.8,b=.2,source='합성 우도')
    s['decisions'][key]=dict(utilities=[[100,-100],[0,0]],cost=5,delay=2,unit='점수',source='합성 효용')
    before=deepcopy(s);d=analysis.inspect(s,key)
    assert s==before
    assert sum(a['mass'] for a in d['tree']['answers'])==pytest.approx(1)
    assert d['tree']['answers'][0]['posterior']==pytest.approx(24/38)
    assert d['tree']['answers'][0]['action']['actions']==['진행']
    assert d['tree']['current_action']['actions']==['보류']
    assert len(d['scenarios'])==9
    assert all(set(row['top3'])<=set(q['id'] for q in s['questions']) for row in d['scenarios'] if not row['error'])


def test_evidence_trace_matches_replay_and_does_not_apply_a_rejected_answer():
    s=state_with_facts();key=s['questions'][0]['id'];s['models'][key]=dict(a=.8,b=.2,source='합성')
    data=dict(question=key,outcome='support',response='합성 검증 답변',note='근거 대조',group='a')
    engine.evidence_apply(s,data,reject=True);engine.evidence_apply(s,data)
    trace=engine.evidence_trace(s)
    assert trace[0]['before']==trace[0]['after']==.3
    assert trace[-1]['likelihood_ratio']==4
    assert trace[-1]['after']==pytest.approx(24/38)


def test_synthetic_evaluation_is_reproducible_and_explicit_about_limits():
    a,b=benchmark.evaluate(),benchmark.evaluate()
    assert a==b and len(a['rows'])==12
    assert all(0<=r['ndcg']<=1 and r['minutes']==15 for r in a['rows'])
    assert any(r['first_evsi']<0 for r in a['rows'])
    assert any('미실행' in v for v in a['limitations'])


def test_report_escapes_text_and_includes_net_cost_assumptions():
    s=state_with_facts();s['company']='<script>alert(1)</script>'
    report=reporting.report(s,3)
    assert '<script>' not in report and '&lt;script&gt;' in report
    assert '비용 차감 후' in report and '원문 근거 명세' in report


def test_registering_an_existing_cell_reuses_the_observation():
    s=state_with_facts()
    before=deepcopy(s['financial_facts'])
    engine.fact_add(s,dict(span=before[0]['span']))
    assert s['financial_facts']==before


def test_new_api_exports_and_research_do_not_modify_database(tmp_path):
    app=create_rules_app(tmp_path);app.testing=True;c=app.test_client()
    p=c.post('/api/example',json={},headers={'Origin':'http://localhost'}).get_json();pid=p['id']
    assert c.get(f'/api/projects/{pid}/analysis?question=recurring.definition').status_code==200
    assert c.get('/api/evaluation').get_json()['scope'].startswith('작성된 합성')
    assert c.get('/api/templates/financial.xlsx').data.startswith(b'PK')
    assert b'<!doctype html>' in c.get(f'/api/projects/{pid}/export/html').data
    csv=c.get(f'/api/projects/{pid}/export/csv').data.decode('utf-8-sig')
    assert 'EVSI 비용 차감 후' in csv and '효용 가정 출처' in csv
    assert c.get(f'/api/projects/{pid}').get_json()['version']==p['version']

"""Real browser acceptance of the persistent five-step MVP and local cases."""
from hashlib import sha256
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from orion.web.rules_app import create_rules_app
from test_case_studies import write_case

pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    root=tmp_path_factory.mktemp('rules-browser');pack=write_case(root)
    import json
    pack['id']='revenue-case';pack['title']='매출 귀속 비교 사례'
    pack['case_study']['comparison']=dict(title='매출 인식 대안',labels=['총액','사용료'],values=[1273.8,290.16],unit='억 원',scaleMax=1400,note='회계 인식 대안의 계획값',refs=['s_case'])
    (root/'case-studies/revenue-case.json').write_text(json.dumps(pack),encoding='utf-8')
    app=create_rules_app(root)
    http=make_server('127.0.0.1',0,app,threaded=True)
    app.config['RULES_PORT']=http.server_port
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{http.server_port}'
    http.shutdown();thread.join(timeout=5)


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as p:
        if not Path(p.chromium.executable_path).is_file():
            message='Chromium is not installed; run python -m playwright install chromium'
            if os.environ.get('ORION_REQUIRE_BROWSER')=='1':
                pytest.fail(message)
            pytest.skip(message)
        b=p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def ui(browser,server):
    context=browser.new_context(base_url=server,viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();page.set_default_timeout(10000)
    errors=[];external=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:external.append(r.url) if urlsplit(r.url).hostname not in {'127.0.0.1','localhost'} else None)
    page.goto(server);expect(page.locator('#r-busy')).to_be_hidden()
    yield page
    assert errors==[]
    assert external==[]
    context.close()


def nav(page,n):
    page.locator(f'#r-nav [data-step="{n}"]').click()
    expect(page.locator('#r-step-kicker')).to_have_text(f'STEP {n:02d} / 05')


def sample(page):
    page.locator('#r-example').click()
    expect(page.locator('#r-busy')).to_be_hidden()
    expect(page.locator('#r-project-heading')).to_contain_text('합성 검증 사례')
    return page.locator('#r-project').input_value()


def record(page,pid):
    return page.request.get('/api/projects/'+pid).json()


def test_real_upload_hypothesis_question_and_no_invented_math(ui):
    page=ui
    page.locator('#r-new-project summary').click()
    page.locator('#r-create [name=company]').fill('브라우저 실제 입력 검증')
    page.locator('#r-create [name=period]').fill('2025년')
    page.get_by_role('button',name='프로젝트 만들기',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('프로젝트를 만들었습니다')
    pid=page.locator('#r-project').input_value()
    source='2025년 매출 125억원. 구독 반복매출 정의와 갱신 계약을 검토한다. 고객 A 채권의 후속 수금 확인. <script>window.injected=true</script>'.encode()
    page.locator('#r-upload [name=file]').set_input_files({'name':'계약_검토.txt','mimeType':'text/plain','buffer':source})
    page.get_by_role('button',name='자료 등록·텍스트 추출',exact=True).click()
    expect(page.locator('#r-files')).to_contain_text('계약_검토.txt')
    page.get_by_role('button',name='자료 분석·가설 초안 구성',exact=True).click()
    expect(page.locator('#r-content')).to_contain_text('125억원')
    page.locator('#r-files .r-file').click()
    page.locator('#r-detail .r-source-button').first.click()
    expect(page.locator('#r-detail .r-quote')).to_contain_text('<script>window.injected=true</script>')
    assert page.evaluate('window.injected') is None
    with page.expect_download() as download:
        page.get_by_role('link',name='원본 파일 다운로드').click()
    assert sha256(open(download.value.path(),'rb').read()).digest()==sha256(source).digest()
    nav(page,2)
    page.get_by_role('button',name='가설·확률 가정 검토').first.click()
    page.locator('#r-hypothesis-form [name=approved]').check()
    page.get_by_role('button',name='가설 검토 저장',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('저장했습니다')
    page.get_by_role('button',name='확정 가설로 질문 구성 →',exact=True).click()
    expect(page.locator('#r-step-kicker')).to_have_text('STEP 03 / 05')
    assert record(page,pid)['state']['questions']
    nav(page,4)
    expect(page.locator('#r-content')).to_contain_text('EIG 미계산')
    assert all(h['probability'] is None for h in record(page,pid)['state']['hypotheses'])
    page.reload();expect(page.locator('#r-busy')).to_be_hidden()
    expect(page.locator('#r-files')).to_contain_text('계약_검토.txt')
    assert page.locator('#r-project').input_value()==pid


def test_information_dashboard_matches_calculation_and_keeps_recommendations(ui):
    page=ui;pid=sample(page)
    before=record(page,pid)
    nav(page,4)
    dashboard=page.locator('#r-information-dashboard')
    expect(dashboard.get_by_role('heading',name='EIG · 기대정보이득',exact=True)).to_be_visible()
    expect(dashboard.get_by_role('heading',name='EVSI · 표본정보의 기대가치',exact=True)).to_be_visible()
    expect(dashboard).to_contain_text('EIG가 높아도 모든 답변에서 같은 행동이 최선이면 EVSI는 0')
    rows=before['state']['questions']
    for q in [q for q in rows if q['eligible']]:
        row=dashboard.locator('tbody tr').filter(has_text=q['id'])
        expect(row).to_have_count(1)
        expect(row.locator('td').nth(1)).to_contain_text(f"{q['eig']:.4f}" if q['eig'] is not None else 'EIG 미계산')
        expect(row.locator('td').nth(2)).to_contain_text(f"{q['evsi']['gross']:.2f}" if q['evsi'] else 'EVSI 미계산')
    after=record(page,pid)
    assert after['version']==before['version']
    assert after['state']['recommendations']==before['state']['recommendations']
    assert after['state']['models']==before['state']['models']
    # A metric selection opens the existing assumptions editor.
    dashboard.locator('tbody tr').filter(has_text='recurring.definition').get_by_role('button',name='평가 가정 열기').click()
    expect(page.locator('#r-question-form')).to_be_visible()
    page.locator('#r-content').evaluate('e=>e.scrollTop=0')
    capture=Path('build/information-metrics');capture.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(capture/'desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(capture/'mobile.png'),full_page=True)


def test_information_charts_keep_negative_zero_and_distinct_units(ui):
    page=ui;pid=sample(page)
    # Use reviewed synthetic models; do not change company data or ranking logic.
    source='동일 비교 기준 합성 가정'
    candidates=[q for q in record(page,pid)['state']['questions'] if q['eligible'] and q['eig'] is not None][:3]
    assert len(candidates)==3
    for i,q in enumerate(candidates):
        body=dict(id=q['id'],go_h=100 if i!=1 else 0,go_not=-100 if i!=1 else 0,
                  hold_h=0,hold_not=0,cost=100 if i==0 else 0,delay=0,
                  unit='효용점수' if i<2 else '원',source=source,
                  version=record(page,pid)['version'])
        result=page.request.post('/api/projects/'+pid+'/actions/decision',data=body,
                                 headers={'Origin':page.url.rstrip('/')})
        assert result.ok,result.text()
    page.reload();expect(page.locator('#r-busy')).to_be_hidden();nav(page,4)
    chart=page.get_by_role('group',name='비용 차감 후 EVSI 비교 그래프',exact=True)
    # Two utility scales share a unit but have different sources; keep them separate.
    expect(chart).to_have_count(3)
    expect(page.locator('.r-negative-fill')).to_have_count(1)
    expect(chart.filter(has_text='비용 차감 후 0.00 효용점수')).to_have_count(1)
    expect(chart.filter(has_text='효용점수').first).not_to_contain_text('0.00 원')
    dashboard=page.locator('#r-information-dashboard')
    expect(dashboard).to_contain_text('EVSI 미계산')
    # Zero bars remain zero width; negative values extend left of the zero line.
    assert page.locator('.r-negative-fill').evaluate('e=>parseFloat(e.style.width)')>0


def test_preview_review_apply_followup_history_and_revoke(ui):
    page=ui;pid=sample(page);nav(page,5)
    picker=page.locator('#r-content select[name=question]')
    picker.select_option('recurring.definition')
    form=page.locator('#r-evidence-form')
    form.locator('[name=response]').fill('계약 원문에서 반복매출 정의와 제외 조건을 확인한 합성 답변')
    form.locator('[name=note]').fill('판정 기준과 계약 범위를 대조한 합성 검토')
    form.get_by_role('button',name='적용 전 미리보기',exact=True).click()
    expect(page.locator('#r-preview')).to_contain_text('30.0% → 63.2%')
    assert record(page,pid)['version']==2
    page.get_by_role('button',name='검토 결과 적용',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('확인을 선택')
    form.locator('[name=reviewed]').check()
    page.get_by_role('button',name='검토 결과 적용',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('다시 계산했습니다')
    data=record(page,pid)
    assert next(h for h in data['state']['hypotheses'] if h['id']=='recurring')['probability']==pytest.approx(24/38)
    assert next(q for q in data['state']['questions'] if q['id']=='recurring.cohort')['active']
    page.get_by_text('이전 저장 버전 선택·비교',exact=True).click()
    page.get_by_role('button',name='저장 버전 불러오기',exact=True).click()
    expect(page.locator('select[name=before]')).to_be_visible()
    page.locator('select[name=before]').select_option('2')
    expect(page.locator('#r-content')).to_contain_text('63.2%')
    page.once('dialog',lambda d:d.accept())
    page.get_by_role('button',name='적용 철회·이력 재생',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('저장했습니다')
    data=record(page,pid)
    assert next(h for h in data['state']['hypotheses'] if h['id']=='recurring')['probability']==.3
    assert not next(q for q in data['state']['questions'] if q['id']=='recurring.cohort')['active']


def test_excel_fact_review_reconciliation_and_report_download(ui):
    import io
    from openpyxl import Workbook
    page=ui
    page.locator('#r-new-project summary').click()
    page.locator('#r-create [name=company]').fill('합성 Excel 검토')
    page.locator('#r-create [name=period]').fill('2025년')
    page.get_by_role('button',name='프로젝트 만들기',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('프로젝트를 만들었습니다')
    for filename,value in [('공시.xlsx',100),('관리.xlsx',90)]:
        wb=Workbook();wb.active.append(['항목','값','단위','기간','범위','구분'])
        wb.active.append(['매출',value,'억원','2025년','별도','실적']);buf=io.BytesIO();wb.save(buf)
        page.locator('#r-upload [name=file]').set_input_files({'name':filename,'mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':buf.getvalue()})
        page.get_by_role('button',name='자료 등록·텍스트 추출',exact=True).click()
        expect(page.locator('#r-files')).to_contain_text(filename)
    page.get_by_role('button',name='자료 분석·가설 초안 구성',exact=True).click()
    expect(page.locator('#r-content')).to_contain_text('100 억원')
    for i in range(2):
        page.get_by_role('button',name='기준 검토',exact=True).first.click()
        form=page.locator('#r-fact-form');form.locator('[name=review_note]').fill('합성 원천과 기간·단위·범위를 대조함')
        form.locator('[name=reviewed]').check()
        form.get_by_role('button',name='재무 관측치 검토 저장',exact=True).click()
        expect(page.locator('#r-busy')).to_be_hidden()
    expect(page.locator('#r-content')).to_contain_text('대사 차이 · 원인 미판정')
    assert record(page,page.locator('#r-project').input_value())['state']['reconciliations'][0]['difference']=='1000000000'
    with page.expect_download() as download:
        page.get_by_role('link',name='검토 보고서 HTML',exact=True).click()
    report=Path(download.value.path()).read_text(encoding='utf-8')
    assert '1000000000' in report and '대사 차이 · 원인 미판정' in report
    assert '원문 근거 명세' in report and '재무 관측치' in report


def test_decision_tree_sensitivity_and_synthetic_evaluation_ui(ui):
    page=ui;pid=sample(page);nav(page,4)
    page.locator('[name=research_question]').select_option('recurring.definition')
    before=record(page,pid)
    page.get_by_role('button',name='계산 과정과 민감도 보기',exact=True).click()
    expect(page.locator('#r-research-output')).to_contain_text('답변별 의사결정 경로')
    expect(page.locator('#r-research-output')).to_contain_text('63.2%')
    page.get_by_text('과제 검증 · 공유 가능한 합성 비교 실험',exact=True).click()
    page.get_by_role('button',name='합성 비교 실험 실행',exact=True).click()
    expect(page.locator('#r-evaluation-output')).to_contain_text('nDCG@3')
    expect(page.locator('#r-evaluation-output')).to_contain_text('독립 검토')
    assert record(page,pid)['version']==before['version']


def test_deal_map_funding_fdd_preview_edit_and_price_bridge(ui,tmp_path):
    page=ui;pid=sample(page)
    before=record(page,pid)
    page.locator('#r-deal-map').click()
    expect(page.locator('#r-title')).to_have_text('거래 구조·FDD 시각화')
    expect(page.locator('#r-content')).to_contain_text('300.00')
    expect(page.get_by_role('img',name='Sources와 Uses 자금 흐름',exact=True)).to_be_visible()
    page.get_by_role('tab',name='조달·BS 대변',exact=True).click()
    expect(page.locator('.dv-balance-board')).to_contain_text('170.00 억원')
    expect(page.locator('.dv-balance-board')).to_contain_text('130.00 억원')
    page.get_by_role('tab',name='QoE·NWC·Net Debt',exact=True).click()
    expect(page.get_by_role('img',name='QoE · 정상화 EBITDA',exact=True)).to_be_visible()
    expect(page.get_by_role('img',name='NWC · 영업운전자본',exact=True)).to_be_visible()
    expect(page.get_by_role('img',name='Net Debt · 순차입금',exact=True)).to_be_visible()
    page.locator('#dv-preview-toggle').click()
    expect(page.locator('#r-content')).to_contain_text('제안과 검토 반영 항목을 함께 계산한 미리보기')
    row=page.locator('#r-content tbody tr').filter(has_text='장기 미수채권 제외')
    row.get_by_role('button',name='수정',exact=True).click()
    form=page.locator('form[data-section=adjustments]')
    expect(form.locator('[name=category]')).to_have_value('매출채권')
    form.locator('[name=amount]').fill('-4')
    form.get_by_role('button',name='시각화 항목 저장',exact=True).click()
    expect(page.locator('#r-busy')).to_be_hidden()
    after=record(page,pid)
    assert after['state']['visual_workspace']['accepted']['price']['end']=='200'
    assert after['state']['hypotheses']==before['state']['hypotheses']
    page.get_by_role('tab',name='지분가치 연결',exact=True).click()
    expect(page.locator('#r-content')).to_contain_text('192.00 억원')
    page.locator('#dv-preview-toggle').click()
    expect(page.locator('#r-content')).to_contain_text('200.00 억원')
    with page.expect_download() as download:
        page.get_by_role('button',name='그래프 SVG 저장',exact=True).click()
    assert '<svg' in Path(download.value.path()).read_text(encoding='utf-8')
    page.screenshot(path=str(tmp_path/'deal-price.png'))
    nav(page,4)
    expect(page.locator('#r-title')).to_have_text('중요도 평가')


@pytest.mark.parametrize('width',[1920,1440,390])
def test_deal_charts_keep_frame_and_mobile_page_within_viewport(ui,width,tmp_path):
    page=ui;page.set_viewport_size({'width':width,'height':1000});sample(page)
    original=page.locator('.r-right').bounding_box()
    page.locator('#r-deal-map').click()
    for name in ['자금 흐름','조달·BS 대변','QoE·NWC·Net Debt','지분가치 연결']:
        page.get_by_role('tab',name=name,exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        if width>1024:
            now=page.locator('.r-right').bounding_box()
            assert all(abs(now[k]-original[k])<1 for k in ('x','y','width','height'))
        if name=='QoE·NWC·Net Debt':page.screenshot(path=str(tmp_path/f'deal-waterfalls-{width}.png'),full_page=True)


def test_question_editor_and_evsi_scenario(ui):
    page=ui;pid=sample(page);nav(page,3)
    page.get_by_role('button',name='반복매출의 정의와 단발성·해지·미서명 계약 제외 기준은 무엇입니까?',exact=True).click()
    form=page.locator('#r-question-form')
    form.locator('[name=title]').fill('반복매출 산식과 제외 조건을 확인해 주십시오.')
    form.locator('[name=importance]').fill('4')
    form.get_by_role('button',name='질문·평가 설정 저장',exact=True).click()
    expect(page.locator('#r-detail h3').first).to_have_text('반복매출 산식과 제외 조건을 확인해 주십시오.')
    page.get_by_text('의사결정 가치 EVSI (선택)',exact=True).click()
    decision=page.locator('#r-decision-form')
    decision.locator('[name=delay]').fill('2')
    decision.get_by_role('button',name='EVSI 시나리오 저장',exact=True).click()
    expect(page.locator('#r-detail')).to_contain_text('비용 차감 후 3.00 효용점수')
    nav(page,5)
    page.locator('#r-content select[name=question]').select_option('recurring.definition')
    form=page.locator('#r-evidence-form')
    form.locator('[name=response]').fill('채택하지 않은 합성 답변')
    form.locator('[name=note]').fill('원문과 연결되지 않아 반려')
    form.locator('[name=reviewed]').check()
    form.get_by_role('button',name='적용 전 미리보기',exact=True).click()
    page.get_by_role('button',name='반려하고 현재 추천 유지',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('반려 기록')
    data=record(page,pid)
    assert all(h['probability']==.3 for h in data['state']['hypotheses'])
    assert data['state']['evidence'][0]['status']=='rejected'


def test_anonymized_case_source_math_and_practice_evidence(ui):
    page=ui
    page.locator('#r-case').select_option('test-case')
    page.locator('#r-open-case').click()
    expect(page.locator('#r-notice')).to_contain_text('익명화 사례를 열었습니다')
    pid=page.locator('#r-project').input_value()
    expect(page.locator('#r-content')).to_contain_text('단순 자금 연결')
    expect(page.locator('#r-content')).to_contain_text('지분 민감도')
    assert record(page,pid)['state']['hypotheses'][0]['probability'] is None
    page.locator('#r-files .r-file').first.click()
    expect(page.locator('#r-detail')).to_contain_text('마스킹 텍스트 다운로드')
    assert page.locator('#r-files img').first.get_attribute('src').endswith('file-excel.svg')
    with page.expect_download() as download:
        page.get_by_role('link',name='마스킹 텍스트 다운로드').click()
    assert download.value.suggested_filename.endswith('.txt')
    assert not open(download.value.path(),'rb').read().startswith(b'PK')
    nav(page,4)
    page.get_by_role('button',name='편집 가능한 실습 가정 적용',exact=True).click()
    expect(page.locator('#r-content')).to_contain_text('실습 가정 적용 중')
    expect(page.locator('#r-content')).to_contain_text('EIG 0.2361 bits')
    expect(page.locator('#r-content')).to_contain_text('비용 차감 후 3.00')
    nav(page,5)
    page.get_by_role('button',name='가상 후속 증거 · 보호조항 미수용',exact=True).click()
    expect(page.locator('#r-evidence-form [name=response]')).to_have_value('[가상 증거 · 실제 자료 아님] 보호조항을 수용하지 않았다고 가정.')
    page.locator('#r-evidence-form [name=reviewed]').check()
    page.get_by_role('button',name='적용 전 미리보기',exact=True).click()
    expect(page.locator('#r-preview')).to_contain_text('실습용 가상 증거')
    expect(page.locator('#r-preview')).to_contain_text('30.0% → 9.7%')
    page.get_by_role('button',name='검토 결과 적용',exact=True).click()
    expect(page.locator('#r-notice')).to_contain_text('다시 계산했습니다')
    data=record(page,pid)
    assert data['state']['evidence'][0]['practice']
    assert data['state']['questions'][1]['active']
    assert data['state']['recommendations']==['case.follow']
    assert page.locator('#r-project').input_value()==pid


def test_comparison_chart_uses_money_units_and_preserves_legacy_percent_chart(ui):
    page=ui
    page.locator('#r-case').select_option('revenue-case');page.locator('#r-open-case').click()
    expect(page.locator('#r-notice')).to_contain_text('익명화 사례를 열었습니다')
    expect(page.locator('.r-dilution-row').first).to_contain_text('1,273.80억 원')
    assert page.locator('.r-dilution-track.r-no-threshold').count()==2
    page.locator('#r-case').select_option('test-case');page.locator('#r-open-case').click()
    expect(page.locator('.r-dilution-row').first).to_contain_text('70.00%')
    assert page.locator('.r-dilution-track.r-no-threshold').count()==0
    pid=page.locator('#r-project').input_value()
    page.reload();expect(page.locator('#r-busy')).to_be_hidden()
    assert page.locator('#r-project').input_value()==pid


@pytest.mark.parametrize('size',[(1280,800),(1440,900),(1920,1080),(2560,1440),(1024,900),(720,900),(390,844)])
def test_all_steps_have_stable_readable_panels_and_no_page_overflow(ui,size,tmp_path):
    page=ui;page.set_viewport_size({'width':size[0],'height':size[1]});sample(page)
    selectors=['.r-header','.r-left','#r-main','.r-right','.r-detail','.r-library','#r-content']
    expected=None
    for n in range(1,6):
        nav(page,n)
        expect(page.locator('.r-library')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        boxes={s:page.locator(s).bounding_box() for s in selectors}
        if size[0]>1024:
            if expected is None:expected=boxes
            for s in selectors:
                for prop in ('x','y','width','height'):
                    assert abs(boxes[s][prop]-expected[s][prop])<1,(n,s,prop,boxes[s],expected[s])
            assert boxes['.r-right']['width']>=370
        assert page.locator('#r-nav button').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')>=15
    page.locator('#r-files .r-file').first.click()
    page.locator('#r-detail .r-source-button').first.click()
    assert page.locator('#r-detail .r-quote').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')>=16
    page.screenshot(path=str(tmp_path/f'rules-{size[0]}.png'),full_page=True)

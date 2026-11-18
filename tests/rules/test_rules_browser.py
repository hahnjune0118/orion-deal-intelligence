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

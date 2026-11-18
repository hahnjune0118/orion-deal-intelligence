"""Browser acceptance checks for the persistent FDD shell and source library."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_browser import chromium_browser, live_url, _navigate, _fw_navigate, _fw_option, _fw_field, _choose_case
from orion.web.layout import SUPPORT_TOOLS

pytestmark = pytest.mark.integration
OUT = Path(__file__).resolve().parents[2] / 'build/frame-implementation/acceptance'
REGIONS = ['.global-header', '.navigation-pane', '.main-pane', '.right-rail', '.frame-detail', '#project-library', '#frame-content']


def geometry(page):
    return page.evaluate('''selectors => Object.fromEntries(selectors.map(s => {const b=document.querySelector(s).getBoundingClientRect();return [s,{x:b.x,y:b.y,width:b.width,height:b.height}]}))''', REGIONS)


def same_geometry(expected, actual):
    for selector in REGIONS:
        for prop in ['x','y','width','height']:
            assert abs(expected[selector][prop] - actual[selector][prop]) <= 1, (selector, prop, expected[selector], actual[selector])


@pytest.mark.parametrize('size', [(1280,800), (1440,900), (1920,1080), (2560,1440)])
def test_frame_is_stable_on_every_page(chromium_browser, live_url, size):
    context = chromium_browser.new_context(viewport={'width':size[0], 'height':size[1]})
    page=context.new_page();page.set_default_timeout(30000)
    errors=[];page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(live_url)
    expect(page.locator('#fw-content .fw-metric').first).to_be_visible(timeout=60000)
    expected=geometry(page);records=[]
    OUT.mkdir(parents=True,exist_ok=True)
    for route in list(range(1,9)) + [key for key,_ in SUPPORT_TOOLS]:
        if isinstance(route,int):_fw_navigate(page,route)
        else:
            if route == 'fdd':
                _fw_navigate(page,8)
                page.locator('#stage-view label').get_by_text('참고 수동 조서',exact=True).click()
            else:_navigate(page,route)
            expect(page.locator('#fw-title')).to_have_text(dict(SUPPORT_TOOLS)[route])
        page.wait_for_timeout(100)
        actual=geometry(page);same_geometry(expected,actual)
        expect(page.locator('#project-library')).to_be_visible()
        expect(page.locator('#studio-source-search')).to_be_visible()
        expect(page.locator('#studio-source-list .studio-file')).to_have_count(4)
        expect(page.locator('#finance-source-list .studio-file')).to_have_count(8)
        assert page.locator('#fw-role').bounding_box()['x'] < expected['.main-pane']['x']
        assert page.locator('#inspector-toggle, .fw-stage-nav, .studio-stepper').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
        for selector in ['#frame-content','#inspector-pane','#frame-file-list','.frame-navigation']:
            page.locator(selector).evaluate('(e) => {e.scrollTop = e.scrollHeight; e.scrollLeft = 0;}')
        page.evaluate('window.scrollTo(0,300)')
        same_geometry(expected,geometry(page))
        for selector in ['#frame-content','#inspector-pane','#frame-file-list','.frame-navigation']:
            page.locator(selector).evaluate('(e) => {e.scrollTop = 0;}')
        page.screenshot(path=str(OUT/f'{size[0]}-{route}.png'))
        records.append({'route':route,'geometry':actual})
    _fw_navigate(page,4)
    for label in ['과거 실적','QoE','운전자본','순차입금','현금흐름·CAPEX','전망']:
        page.locator('#fw-area label').get_by_text(label,exact=True).click()
        expect(page.locator('#fw-content .main-svg').first).to_be_visible()
        same_geometry(expected,geometry(page))
    if size[0] == 1920:
        for role in ['PE · 이익·현금','IB · 거래·쟁점','Big 4 · 조서·대사']:
            _fw_option(page.locator('#fw-role'),role)
            for route in range(1,9):
                _fw_navigate(page,route);same_geometry(expected,geometry(page))
    for width in [1024,720,390]:
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), width
        expect(page.locator('#project-library')).to_be_visible()
        assert page.locator('.right-rail').bounding_box()['y'] >= page.locator('.main-pane').bounding_box()['y']
        for field in ['deal-selector','fw-role','fw-period']:
            label=page.locator(f'.frame-settings label[for="{field}"]').bounding_box()
            control=page.locator('#'+field).bounding_box()
            assert control['x'] > label['x'], (width,field)
            assert abs(label['y']+label['height']/2-control['y']-control['height']/2) <= 1, (width,field)
    assert not errors,errors
    (OUT/f'{size[0]}-geometry.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    context.close()


def test_library_keeps_context_and_downloads_exact_sources(chromium_browser, live_url, tmp_path):
    context=chromium_browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();page.set_default_timeout(30000);page.goto(live_url)
    expect(page.locator('#finance-source-list .studio-file')).to_have_count(8,timeout=60000)
    page.locator('#studio-source-search').fill('monthly')
    expect(page.locator('#finance-source-list .studio-file')).to_have_count(1)
    _fw_navigate(page,5)
    expect(page.locator('#studio-source-search')).to_have_value('monthly')
    page.locator('#finance-source-list .studio-file').click()
    expect(page.locator('#fw-detail')).to_contain_text('monthly_financials.csv')
    expect(page.locator('#fw-title')).to_contain_text('5.')
    with page.expect_download() as info:page.locator('#frame-finance-download').click()
    result=tmp_path/info.value.suggested_filename;info.value.save_as(result)
    from orion.services.fdd_finance import demo_pack
    assert result.read_bytes()==demo_pack()['documents']['monthly_financials']['text'].encode('utf-8')
    _navigate(page,'studio')
    page.locator('#finance-source-list .studio-file').click()
    expect(page.locator('#finance-inspector')).to_be_visible()
    expect(page.locator('#fw-detail')).to_contain_text('monthly_financials.csv')
    expect(page.locator('#studio-center')).to_be_visible()
    page.locator('#studio-source-search').fill('financial.docx')
    page.locator('#studio-source-list .studio-file').click()
    expect(page.locator('.legacy-inspector')).to_be_visible()
    expect(page.locator('#source-inspector')).to_contain_text('nb_doc_financial.docx')
    _fw_option(page.locator('#studio-source-type'),'PDF')
    expect(page.locator('#studio-source-list')).to_contain_text('검색 결과가 없습니다')
    _choose_case(page,'제조업')
    expect(page.locator('#studio-source-search')).to_have_value('')
    expect(page.locator('#studio-source-type')).to_contain_text('전체 형식')
    expect(page.locator('#finance-source-list')).to_contain_text('표시할 재무 원천표가 없습니다')
    expect(page.locator('#source-inspector')).not_to_contain_text('nb_doc_financial.docx', timeout=30000)
    context.close()


def test_unsaved_case_switch_and_saved_role_switch(chromium_browser,live_url):
    context=chromium_browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page();page.set_default_timeout(30000);page.goto(live_url)
    expect(page.locator('#fw-title')).to_contain_text('1.',timeout=60000)
    page.get_by_text('실사 범위 수정',exact=True).click()
    _fw_field(page,'scope_entity').fill('입력 중인 실사 대상')
    expect(page.locator('#frame-unsaved')).to_contain_text('미저장')
    page.locator('#deal-selector').click()
    page.once('dialog',lambda dialog: dialog.dismiss())
    page.locator('#deal-selector .Select-menu-outer').get_by_text('제조업 사례',exact=True).click()
    expect(page.locator('#deal-selector')).to_contain_text('Northstar')
    expect(_fw_field(page,'scope_entity')).to_have_value('입력 중인 실사 대상')
    page.locator('#fw-title').click()
    page.locator('button[id*=\'"action":"scope"\']').click()
    expect(page.locator('#fw-message')).to_contain_text('저장했습니다')
    _fw_option(page.locator('#fw-role'),'PE · 이익·현금')
    expect(page.locator('#fw-context')).to_contain_text('입력 중인 실사 대상')
    context.close()

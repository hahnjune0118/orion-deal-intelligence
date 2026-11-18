"""Real Chromium checks; skip only when the optional browser is not installed.

Capture reviewed UI evidence with ORION_SCREENSHOT_DIR=implementation_evidence/screenshots.
The server runs on a random loopback port; no API keys or external services are used.
"""
from __future__ import annotations

import os
import json
from hashlib import sha256
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit
from zipfile import ZipFile

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def live_url():
    from orion.app import create_app
    from orion.config import Settings
    app = create_app(project_root=ROOT, settings=Settings(), secret_key="browser-test-only-secret-32-characters")
    server = make_server("127.0.0.1", 0, app.server, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def chromium_browser():
    with sync_playwright() as p:
        if not Path(p.chromium.executable_path).is_file():
            message = "Chromium is not installed; run python -m playwright install chromium"
            if os.environ.get("ORION_REQUIRE_BROWSER") == "1":
                pytest.fail(message)
            pytest.skip(message)
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        browser.close()


def _open(browser, url, *, size=(1440, 900), studio=False):
    context = browser.new_context(viewport={"width": size[0], "height": size[1]}, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(30000)
    page.outbound_requests = []
    page.on("request", lambda request: page.outbound_requests.append(request.url)
            if urlsplit(request.url).hostname not in {None, "127.0.0.1", "localhost"} else None)
    page.goto(url)
    _revision(page, 1)
    _navigate(page, "studio" if studio else "overview")
    return context, page


def _revision(page, revision):
    expect(page.locator("#snapshot-summary strong")).to_contain_text(
        re.compile(rf"리비전\s*[:·]?\s*{revision}\b", re.IGNORECASE), timeout=60000
    )


def _navigate(page, name):
    if page.locator('#support-tools-drawer').get_attribute('open') is None:
        page.locator('#support-tools-drawer > summary').click()
    page.locator(f'.fw-tools-menu button[id*=\'"page":"{name}"\']').click()
    titles = {"overview": "투자 건 개요", "evidence": "증빙 탐색", "thesis": "투자 가설 검토판", "questions": "맞춤형 실사 질문표", "review": "분석가 검토 및 증빙 업데이트", "analytics": "맞춤형 분석", "export": "예비 심사 메모 및 실사 자료 내보내기"}
    if name == 'studio':
        expect(page.locator('#studio-center')).to_be_visible(timeout=60000)
    else:
        expect(page.locator("#page-content h2").first).to_have_text(titles[name], timeout=60000)


def _choose_case(page, text):
    control = page.locator("#deal-selector")
    control.click()
    control.locator(".Select-menu-outer").get_by_text(re.compile(text, re.I)).click()
    _revision(page, 1)
    expect(control).to_contain_text(re.compile(text, re.I))


def _shot(page, filename, fallback):
    folder = Path(os.environ.get("ORION_SCREENSHOT_DIR", str(fallback)))
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / filename), full_page=True)


def test_northstar_full_approved_flow_and_exports(chromium_browser, live_url, tmp_path):
    context, page = _open(chromium_browser, live_url)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    before = page.locator("#top3-list").inner_text()
    _shot(page, "01_overview_1440.png", tmp_path)
    with page.expect_download() as source_info:
        page.locator("#source-download-button").click()
    original = tmp_path / source_info.value.suggested_filename
    source_info.value.save_as(original)
    expected_source = ROOT / "chunk3_synthetic_evaluation/data/synthetic_northstar/documents/nb_doc_cim.docx"
    assert sha256(original.read_bytes()).digest() == sha256(expected_source.read_bytes()).digest()
    _navigate(page, "evidence")
    expect(page.locator("#evidence-grid .ag-row").first).to_be_visible()
    expect(page.locator('#evidence-grid .ag-header-cell[col-id="review_status"]')).to_contain_text("검토")
    expect(page.locator('#evidence-grid .ag-row [col-id="review_status"]').first).to_have_text("승인")
    page.locator('#evidence-grid .ag-row [col-id="review_status"]').first.hover()
    expect(page.locator(".ag-tooltip")).to_have_text("승인")
    page.mouse.move(0, 0)
    first_row = page.locator("#evidence-grid .ag-row").first
    evidence_id = first_row.get_attribute("row-id")
    initial = json.loads((ROOT / "chunk3_synthetic_evaluation/data/synthetic_northstar/structured/initial_state.json").read_text())
    record = next(e for e in initial["evidence"] if e["id"] == evidence_id)
    span = next(s for s in initial["source_spans"] if s["id"] == record["source_span_ids"][0])
    first_row.click()
    expect(page.locator("#source-inspector")).to_contain_text(span["quote"])
    expect(page.locator("#source-inspector .locator").first).to_contain_text("word/document.xml")
    page.locator("#source-library-drawer > summary").click()
    document_search = page.locator("#studio-source-search")
    document_search.fill("no-matching-source-document")
    expect(page.locator("#studio-source-list")).to_contain_text("검색 결과가 없습니다")
    document_search.fill("")
    page.locator("#source-library-drawer > summary").click()
    _shot(page, "02_evidence_1440.png", tmp_path)
    _navigate(page, "thesis")
    expect(page.locator("#thesis-grid .ag-row").first).to_be_visible()
    _shot(page, "03_thesis_1440.png", tmp_path)
    _navigate(page, "questions")
    expect(page.locator("#question-grid .ag-row").first).to_be_visible()
    assert page.locator('#question-grid .ag-header-cell[col-id="issue"]').bounding_box()["width"] >= 220
    _shot(page, "04_dd_matrix_1440.png", tmp_path)
    _navigate(page, "review")
    _shot(page, "05_review_preview_1440.png", tmp_path)
    for revision in range(2, 6):
        prior_top3 = page.locator("#top3-list").inner_text()
        page.locator("#review-reason").fill(f"Browser reviewer checked the original source for stage {revision - 1}.")
        page.locator("#review-approve").click()
        _revision(page, revision)
        if revision == 4:  # The real T3 cost event changes evidence, not the Top 3.
            assert page.locator("#top3-list").inner_text() == prior_top3
    assert page.locator("#top3-list").inner_text() != before
    _navigate(page, "analytics")
    expect(page.locator("#page-content")).to_contain_text("사후확률")
    expect(page.locator("#page-content")).to_contain_text("비트")
    _shot(page, "06_analytics_1440.png", tmp_path)
    _navigate(page, "export")
    _shot(page, "07_export_1440.png", tmp_path)
    for label, member in [("실사 요청 목록 · Excel", "xl/workbook.xml"), ("예비 심사 메모 · Word", "word/document.xml")]:
        control = page.locator("#export-format")
        control.click()
        control.locator(".Select-menu-outer").get_by_text(label, exact=True).click()
        expect(page.locator('#export-confirm input')).not_to_be_checked(timeout=60000)
        page.locator('#export-confirm input').check()
        expect(page.locator("#export-approval-status")).to_contain_text("다운로드할 수 있습니다", timeout=60000)
        with page.expect_download() as info:
            page.locator("#export-button").click()
        download = info.value
        artifact = tmp_path / download.suggested_filename
        download.save_as(artifact)
        assert artifact.stat().st_size > 100
        assert ".." not in download.suggested_filename
        with ZipFile(artifact) as archive:
            assert member in archive.namelist()
    assert errors == []
    assert page.outbound_requests == [], "Demo must use local assets and no external provider calls"
    context.close()


def test_rejection_reset_context_and_tab_isolation(chromium_browser, live_url):
    first, page = _open(chromium_browser, live_url)
    second, other = _open(chromium_browser, live_url)
    new_tab = first.new_page()
    new_tab.goto(live_url)
    _revision(new_tab, 1)
    _navigate(new_tab, "overview")
    before = page.locator("#top3-list").inner_text()
    def tamper_approval(route):
        body = route.request.post_data_json
        if "review-approve.n_clicks" in body.get("changedPropIds", []):
            for item in body.get("state", []):
                if item.get("id") == "workspace-token":
                    item["value"] += "tampered"
            route.continue_(post_data=json.dumps(body))
        else:
            route.continue_()
    page.route("**/_dash-update-component", tamper_approval)
    page.locator("#review-approve").click()
    expect(page.locator("#status-live-region")).to_contain_text("INVALID_TOKEN", timeout=60000)
    _revision(page, 1)
    assert page.locator("#top3-list").inner_text() == before
    page.unroute("**/_dash-update-component", tamper_approval)
    page.locator("#review-reason").fill("Reject this draft; source does not justify acceptance in this branch.")
    page.locator("#review-reject").click()
    expect(page.locator("#status-live-region")).to_contain_text("반려", timeout=60000)
    _revision(page, 1)
    assert page.locator("#top3-list").inner_text() == before
    page.locator("#reset-demo").click()
    expect(page.locator("#status-live-region")).to_contain_text("초기")
    expect(page).to_have_title("Orion · FDD 작업 공간", timeout=60000)
    expect(page.locator("#event-preview .badge-preview-approval-required")).to_be_visible()
    page.locator("#review-reason").fill("Checked original source; approve synthetic event.")
    page.locator("#review-approve").click()
    _revision(page, 2)
    _revision(other, 1)
    _revision(new_tab, 1)
    assert other.locator("#top3-list").inner_text() == before
    assert new_tab.locator("#top3-list").inner_text() == before
    page.locator("#reset-demo").click()
    _revision(page, 1)
    assert page.locator("#top3-list").inner_text() == before
    first.close()
    second.close()


def test_secondary_cases_keyboard_and_responsive_views(chromium_browser, live_url, tmp_path):
    context, page = _open(chromium_browser, live_url)
    _choose_case(page, "제조업")
    _navigate(page, "analytics")
    expect(page.locator("#page-content")).to_contain_text("분석 불가")
    page.locator("#review-reason").fill("Checked inventory evidence.")
    page.locator("#review-approve").click()
    _revision(page, 2)
    _choose_case(page, "Lumen")
    old = page.locator("#top3-list").inner_text()
    page.locator("#review-reason").fill("Checked contradictory side letter.")
    page.locator("#review-approve").click()
    _revision(page, 2)
    assert page.locator("#top3-list").inner_text() != old
    _navigate(page, "questions")
    grid = page.locator("#question-grid")
    expected_question = grid.locator('.ag-row[row-index="1"]').first.get_attribute("row-id")
    grid.locator('[role="gridcell"]').first.focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator("#source-inspector .identifier").first).to_have_text(expected_question, timeout=60000)
    page.keyboard.press("Escape")
    assert page.evaluate("document.activeElement !== document.body")
    for width, height, name in [(1280, 720, "08_questions_1280.png"), (1024, 768, "09_questions_1024.png"), (720, 450, "10_questions_200percent_reflow.png")]:
        page.set_viewport_size({"width": width, "height": height})
        expect(page.locator("#workspace-tabs")).to_be_visible()
        _shot(page, name, tmp_path)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), "Whole-page horizontal overflow"
        assert page.locator("#review-approve").is_visible()
    context.close()


def test_dashboard_charts_and_inspector_toggle(chromium_browser, live_url, tmp_path):
    context, page = _open(chromium_browser, live_url)
    expect(page.locator('#dashboard-metrics')).to_contain_text('미해결 실사 질문')
    for chart_id in ['overview-priority-chart', 'overview-coverage-chart']:
        chart = page.locator('#' + chart_id)
        expect(chart.locator('.main-svg').first).to_be_visible()
        assert chart.bounding_box()['height'] >= 250
    _shot(page, '11_dashboard_refresh_1440.png', tmp_path)
    page.locator('#inspector-toggle').click()
    expect(page.locator('#inspector-pane')).not_to_be_visible()
    expect(page.locator('#inspector-toggle')).to_have_attribute('aria-expanded', 'false')
    page.locator('#inspector-toggle').click()
    expect(page.locator('#inspector-pane')).to_be_visible()
    expect(page.locator('#inspector-toggle')).to_have_attribute('aria-expanded', 'true')
    for size in [(1440, 900), (1024, 768), (720, 900), (390, 844)]:
        page.set_viewport_size({'width': size[0], 'height': size[1]})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), (size, page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e => e.getBoundingClientRect().right > innerWidth+2).map(e => [e.tagName,e.id,e.className,e.getBoundingClientRect().right]).slice(0,12)"))
    _choose_case(page, '제조업')
    expect(page.locator('#overview-coverage-chart .main-svg').first).to_be_visible()
    context.close()


def test_visuals_across_all_workspace_pages(chromium_browser, live_url, tmp_path):
    context, page = _open(chromium_browser, live_url)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for name in ['evidence', 'thesis', 'questions', 'review', 'analytics', 'export']:
        _navigate(page, name)
        expect(page.locator('#page-content .visual-panel').first).to_be_visible()
        expect(page.locator('#page-content .page-visuals .main-svg').first).to_be_visible()
        expect(page).to_have_title('Orion · FDD 작업 공간', timeout=60000)
        _shot(page, 'visual_' + name + '_1440.png', tmp_path)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), name
        page.set_viewport_size({'width': 1440, 'height': 900})
    _navigate(page, 'questions')
    control = page.locator('#score-question-selector')
    control.click()
    control.locator('.Select-menu-outer').get_by_text(re.compile(r'^Q02')).click()
    expect(control).to_contain_text('Q02')
    expect(page).to_have_title('Orion · FDD 작업 공간', timeout=60000)
    _navigate(page, 'review')
    page.locator('#review-approve').click()
    _revision(page, 2)
    expect(page.locator('#review-score-comparison .main-svg').first).to_be_visible()
    expect(page.locator('#review-stage-combo .main-svg').first).to_be_visible()
    _navigate(page, 'analytics')
    expect(page.locator('#belief-waterfall .main-svg').first).to_be_visible()
    _shot(page, 'visual_analytics_approved_1440.png', tmp_path)
    assert errors == []
    assert page.outbound_requests == []
    context.close()


def test_studio_document_review_edit_and_exports(chromium_browser, live_url, tmp_path):
    context, page = _open(chromium_browser, live_url, studio=True)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    expect(page.locator('#studio-center')).to_be_visible()
    expect(page.locator('#studio-settings')).to_be_visible()
    expect(page.locator('#studio-question-selection input').first).to_be_visible()
    expect(page.locator('#studio-result-count')).to_contain_text('13 / 13')
    assert page.locator('#inspector-pane').bounding_box()['width'] >= 410
    assert page.locator('.studio-question-body strong').first.evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)') >= 15
    page.set_viewport_size({'width': 2560, 'height': 1260})
    assert page.locator('#inspector-pane').bounding_box()['width'] >= 500
    _shot(page, 'studio_workspace_2560.png', tmp_path)
    page.set_viewport_size({'width': 1440, 'height': 900})
    _shot(page, 'studio_workspace_1440.png', tmp_path)
    canonical = page.locator('#top3-list').inner_text()
    page.locator('#source-library-drawer > summary').click()
    page.locator('#studio-source-search').fill('financial')
    expect(page.locator('.studio-file')).to_have_count(1)
    page.locator('.studio-file').click()
    expect(page.locator('.legacy-inspector')).to_be_visible()
    expect(page.locator('#source-inspector')).to_contain_text('nb_doc_financial.docx')
    page.locator('#source-library-drawer > summary').click()
    page.locator('#studio-source-search').fill('')
    expect(page.locator('.studio-file')).to_have_count(4)
    page.locator('#source-library-drawer > summary').click()
    page.locator('#studio-question-selection input').first.check()
    page.locator('#studio-review-selection').click()
    expect(page.locator('#studio-editor')).to_be_visible()
    expect(page.locator('#studio-edit-issue')).not_to_have_value('')
    page.locator('#studio-edit-issue').fill('서명 계약과 수금 증빙을 추가로 확인해 주세요.')
    page.locator('#studio-save').click()
    expect(page.locator('#studio-message')).to_contain_text('수정 초안을 저장')
    expect(page.locator('#studio-question-selection')).to_contain_text('서명 계약과 수금 증빙을 추가로 확인해 주세요.')
    page.locator('#studio-export-reviewed').click()
    expect(page.locator('#studio-message')).to_contain_text('모든 질문을 검토 완료')
    page.locator('#studio-edit-note').fill('합성 자료의 요청 범위를 검토했습니다.')
    page.locator('#studio-approve').click()
    expect(page.locator('#studio-message')).to_contain_text('검토 완료로 표시')
    with page.expect_download() as info:
        page.locator('#studio-export-reviewed').click()
    path = tmp_path / info.value.suggested_filename
    info.value.save_as(path)
    exported = path.read_text(encoding='utf-8-sig')
    assert '서명 계약과 수금 증빙을 추가로 확인해 주세요.' in exported
    assert 'Aster executed paid contract' in exported
    assert 'file' not in info.value.suggested_filename or '..' not in info.value.suggested_filename
    assert page.locator('#top3-list').inner_text() == canonical
    _revision(page, 1)
    expect(page.locator('#studio-view label')).to_have_count(1)
    expect(page.locator('#studio-question-selection')).to_have_class(re.compile('mode-list'))
    expect(page.locator('.studio-request-text').first).to_be_visible()
    page.locator('#studio-question-search').fill('impossible-no-matching-question')
    expect(page.locator('#studio-list-empty')).to_contain_text('표시할 질문이 없습니다')
    page.locator('#studio-question-search').fill('')
    page.locator('#studio-clear-selection').click()
    expect(page.locator('#studio-selection-count')).to_contain_text('0개 선택')
    page.locator('#studio-memo').fill('추가 수금 증빙 검토 필요')
    page.locator('#studio-save-memo').click()
    expect(page.locator('#studio-message')).to_contain_text('메모를 저장')
    for width in [1440, 1024, 720, 390]:
        page.set_viewport_size({'width': width, 'height': 900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), width
    page.set_viewport_size({'width': 1440, 'height': 900})
    _shot(page, 'studio_reviewed_1440.png', tmp_path)
    _choose_case(page, '제조업')
    expect(page.locator('#studio-result-count')).to_contain_text('9 / 9')
    expect(page.locator('#studio-memo')).to_have_value('')
    expect(page.locator('#studio-question-selection')).not_to_contain_text('서명 계약과 수금 증빙을 추가로 확인해 주세요.')
    expect(page.locator('#studio-selection-count')).to_contain_text('0개 선택')
    assert errors == []
    assert page.outbound_requests == []
    context.close()


def _fw_field(page, name):
    identifier = json.dumps({'type': 'fw-field', 'name': name}, sort_keys=True, separators=(',', ':'))
    return page.locator("[id='" + identifier + "']")


def _fw_command(page, action):
    return page.locator("button[id*='\"type\":\"fw-command\"'][id*='\"action\":\"" + action + "\"']")


def _fw_navigate(page, number):
    page.locator('#workspace-tabs label').filter(has_text=re.compile(rf'^{number}\.')).click()
    expect(page.locator('#fw-title')).to_contain_text(re.compile(rf'^{number}\.'))


def _fw_option(control, label):
    control.click()
    if control.locator('input').count():
        control.locator('input').first.fill(label)
    control.locator('.Select-menu-outer').get_by_text(label, exact=True).click()


def test_fdd_financial_workflow_and_workpaper_exports(chromium_browser, live_url, tmp_path):
    context = chromium_browser.new_context(viewport={'width': 1680, 'height': 1080}, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(30000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(live_url)
    expect(page.locator('#fw-content .fw-metric').first).to_be_visible(timeout=60000)
    expect(page.locator('#workspace-tabs label')).to_have_count(8)
    _shot(page, 'fdd_01_deal_1680.png', tmp_path)
    _fw_navigate(page, 4)
    page.locator('#fw-area label').get_by_text('QoE', exact=True).click()
    expect(page.locator('#fw-content')).to_contain_text('2,264.4')
    expect(page.locator('#fw-detail')).to_contain_text('GL-001')
    # Move to a different record, then use an actual Plotly mark to navigate back.
    _fw_option(page.locator('#fw-inspection'), 'ADJ-002 · 주주 개인 비용 가산')
    expect(_fw_field(page, 'edit_id')).to_have_value('ADJ-002')
    page.locator('#fw-content .waterfalllayer .point path').nth(1).click(force=True)
    expect(_fw_field(page, 'edit_id')).to_have_value('ADJ-001')
    expect(page.locator('#fw-detail')).to_contain_text('2행')
    _fw_field(page, 'edit_amount').fill('40')
    _fw_command(page, 'adjustment').click()
    expect(page.locator('#fw-message')).to_contain_text('저장했습니다')
    expect(page.locator('#fw-content')).to_contain_text('2,269.4')
    _shot(page, 'fdd_04_qoe_1680.png', tmp_path)
    _fw_navigate(page, 3)
    expect(page.locator('#fw-detail')).to_contain_text('관리–TB 원차이')
    _fw_field(page, 'edit_adjustment_tb').fill('12')
    _fw_field(page, 'edit_explanation').fill('검증 사례: 관리 매출과 전기 시점 차이 12를 별도 대사 조정으로 기록합니다.')
    _fw_option(_fw_field(page, 'edit_source_id'), 'monthly_financials.csv · v1')
    _fw_field(page, 'edit_source_row').fill('25')
    _fw_field(page, 'edit_source_column').fill('revenue')
    _fw_command(page, 'reconciliation').click()
    expect(page.locator('#fw-message')).to_contain_text('저장했습니다')
    expect(page.locator('#fw-content')).to_contain_text('조정 대사')
    _fw_navigate(page, 5)
    for label in ['ISS-001 · 관리매출과 시산표의 12월 차이', 'ISS-003 · 현금·차입잔액의 외부 확인 미수령']:
        _fw_option(page.locator('#fw-inspection'), label)
        _fw_option(_fw_field(page, 'edit_status'), '범위 제한')
        _fw_field(page, 'edit_conclusion').fill('검증 사례의 외부 확인 미수령을 보고서 제한사항으로 남깁니다.')
        _fw_command(page, 'issue').click()
        expect(page.locator('#fw-message')).to_contain_text('저장했습니다')
    _fw_navigate(page, 7)
    _fw_field(page, 'prepare_preparer').fill('작성 담당자')
    _fw_command(page, 'prepare').click()
    expect(page.locator('#fw-status-pills')).to_contain_text('작성 제출')
    _fw_field(page, 'approve_reviewer').fill('검토 담당자')
    _fw_command(page, 'approve').click()
    expect(page.locator('#fw-status-pills')).to_contain_text('검토 기록 확정')
    _fw_navigate(page, 8)
    with page.expect_download() as info:
        page.get_by_role('button', name='Excel 데이터북', exact=True).click()
    artifact = tmp_path / info.value.suggested_filename
    info.value.save_as(artifact)
    from openpyxl import load_workbook
    book = load_workbook(artifact, data_only=True)
    values = list(book['거래영향'].values)
    assert dict(zip(values[0], values[1]))['adjusted_ebitda'] == 2269.4
    assert '검토 기록 확정' in str(list(book['산출물정보'].values))
    with page.expect_download() as info:
        page.get_by_role('button', name='FDD 검토 보고서 · Markdown', exact=True).click()
    report = tmp_path / info.value.suggested_filename
    info.value.save_as(report)
    assert '2,269.40' in report.read_text(encoding='utf-8')
    _fw_navigate(page, 6)
    _fw_field(page, 'transaction_ev').fill('10000')
    _fw_command(page, 'transaction').click()
    expect(page.locator('#fw-content')).to_contain_text('9,337.0')
    expect(page.locator('#fw-status-pills')).to_contain_text('작성 중')
    _revision(page, 1)  # Financial changes do not modify canonical DD evidence.
    assert errors == []
    context.close()


def test_fdd_all_pages_sources_panel_and_mobile_layout(chromium_browser, live_url, tmp_path):
    context = chromium_browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(live_url)
    expect(page.locator('#fw-content .fw-card').first).to_be_visible(timeout=60000)
    for number in range(1, 9):
        _fw_navigate(page, number)
        expect(page.locator('#finance-inspector')).to_be_visible()
        assert page.locator('#inspector-pane').bounding_box()['width'] >= 410
        assert page.locator('#finance-inspector p').first.evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)') >= 15
        _shot(page, f'fdd_page_{number}_1440.png', tmp_path)
    _fw_navigate(page, 4)
    for label in ['과거 실적', 'QoE', '운전자본', '순차입금', '현금흐름·CAPEX', '전망']:
        page.locator('#fw-area label').get_by_text(label, exact=True).click()
        expect(page.locator('#fw-content .main-svg').first).to_be_visible()
    page.locator('#fw-area label').get_by_text('운전자본', exact=True).click()
    page.set_viewport_size({'width': 2560, 'height': 1260})
    assert page.locator('#inspector-pane').bounding_box()['width'] >= 500
    _shot(page, 'fdd_nwc_2560.png', tmp_path)
    page.set_viewport_size({'width': 1440, 'height': 1000})
    # The global document library also opens original Word evidence inside FDD.
    page.locator('#source-library-drawer > summary').click()
    page.locator('#studio-source-search').fill('financial')
    expect(page.locator('.studio-file')).to_have_count(1)
    page.locator('.studio-file').click()
    expect(page.locator('#fw-detail')).to_contain_text('nb_doc_financial.docx')
    assert page.locator('#fw-detail .source-excerpt').first.evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)') >= 15
    for width in [1440, 1024, 720, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.wait_for_function("Array.from(document.querySelectorAll('#fw-content .fw-chart')).every(e => {const p=e.querySelector('.js-plotly-plot'); return p && p._fullLayout && p._fullLayout.width <= e.clientWidth+2 && p._fullLayout.height >= 240;})")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), width
    _shot(page, 'fdd_nwc_mobile.png', tmp_path)
    page.set_viewport_size({'width': 1440, 'height': 1000})
    _choose_case(page, '제조업')
    expect(page.locator('#fw-content')).to_contain_text('재무자료가 아직 연결되지 않았습니다')
    _choose_case(page, 'Northstar')
    expect(page.locator('#fw-content')).to_contain_text('월별 운전자본 구성')
    assert errors == []
    context.close()


def test_fdd_financial_csv_and_request_entry(chromium_browser, live_url, tmp_path):
    from orion.services.fdd_finance import DATASETS, csv_text, demo_pack
    context = chromium_browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(30000)
    page.goto(live_url)
    expect(page.locator('#fw-content .fw-card').first).to_be_visible(timeout=60000)
    _fw_navigate(page, 2)
    page.get_by_text('재무 표 입력 · CSV 붙여넣기', exact=True).click()
    with page.expect_download() as info:
        page.get_by_role('button', name='선택한 표의 CSV 템플릿', exact=True).click()
    template = tmp_path / info.value.suggested_filename
    info.value.save_as(template)
    assert template.read_text(encoding='utf-8-sig').strip() == ','.join(DATASETS['monthly'][1])
    _fw_option(_fw_field(page, 'dataset_kind'), '시산표')
    _fw_field(page, 'dataset_filename').fill('reviewed_trial.csv')
    _fw_field(page, 'dataset_text').fill(csv_text(demo_pack()['data']['trial'], DATASETS['trial'][1]))
    _fw_command(page, 'dataset').click()
    expect(page.locator('#fw-message')).to_contain_text('저장했습니다')
    expect(page.locator('#fw-content')).to_contain_text('reviewed_trial.csv')
    _fw_option(page.locator('#fw-inspection'), 'IRL-002 · 시산표·총계정원장 집계')
    expect(_fw_field(page, 'edit_status')).to_contain_text('보완 요청')
    expect(_fw_field(page, 'edit_source_id')).to_contain_text('reviewed_trial.csv')
    page.get_by_role('button', name='+ 자료 요청 등록', exact=True).click()
    expect(_fw_field(page, 'edit_id')).to_have_value('')
    _fw_field(page, 'edit_title').fill('추가 은행 확인서 요청')
    _fw_field(page, 'edit_owner').fill('실사 담당자')
    _fw_field(page, 'edit_due').fill('2026-11-25')
    _fw_option(_fw_field(page, 'edit_status'), '요청')
    _fw_command(page, 'request').click()
    expect(page.locator('#fw-status-pills')).to_contain_text('조서 v3')
    _fw_option(page.locator('#fw-inspection'), 'IRL-009 · 추가 은행 확인서 요청')
    expect(_fw_field(page, 'edit_owner')).to_have_value('실사 담당자')
    _fw_navigate(page, 1)
    page.get_by_text('실사 범위 수정', exact=True).click()
    _fw_field(page, 'scope_currency').fill('KRW')
    _fw_command(page, 'scope').click()
    expect(page.locator('#fw-message')).to_contain_text('통화·단위만 변경할 수 없습니다')
    _choose_case(page, '제조업')
    _fw_navigate(page, 2)
    page.get_by_text('재무 표 입력 · CSV 붙여넣기', exact=True).click()
    row = {key: None for key in DATASETS['monthly'][1]}
    row.update(period='2025-12', revenue='100', cogs='40', opex='20', da='5')
    _fw_field(page, 'dataset_text').fill(csv_text([row], DATASETS['monthly'][1]))
    _fw_command(page, 'dataset').click()
    expect(page.locator('#fw-message')).to_contain_text('저장했습니다')
    _fw_navigate(page, 4)
    expect(page.locator('#fw-content .fw-metric').first).to_contain_text('100.0')
    page.locator('#fw-area label').get_by_text('운전자본', exact=True).click()
    expect(page.locator('#fw-content .fw-metric').first).to_contain_text('미제공')
    _choose_case(page, 'Northstar')
    _fw_navigate(page, 2)
    _fw_option(page.locator('#fw-inspection'), 'IRL-009 · 추가 은행 확인서 요청')
    expect(_fw_field(page, 'edit_owner')).to_have_value('실사 담당자')
    context.close()

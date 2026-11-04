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


def _open(browser, url, *, size=(1440, 900)):
    context = browser.new_context(viewport={"width": size[0], "height": size[1]}, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(30000)
    page.outbound_requests = []
    page.on("request", lambda request: page.outbound_requests.append(request.url)
            if urlsplit(request.url).hostname not in {None, "127.0.0.1", "localhost"} else None)
    page.goto(url)
    _revision(page, 1)
    return context, page


def _revision(page, revision):
    expect(page.locator("#snapshot-summary strong")).to_contain_text(
        re.compile(rf"revision\s*[:·]?\s*{revision}\b", re.IGNORECASE), timeout=60000
    )


def _navigate(page, name):
    order = ["overview", "evidence", "thesis", "questions", "review", "analytics", "export"]
    page.locator("#workspace-tabs label").nth(order.index(name)).click()
    titles = {"overview": "Deal overview", "evidence": "Evidence explorer", "thesis": "Investment thesis board", "questions": "Adaptive DD matrix", "review": "Analyst review & evidence updates", "analytics": "Adaptive analytics", "export": "Screening memo & DD export"}
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
    first_row = page.locator("#evidence-grid .ag-row").first
    evidence_id = first_row.get_attribute("row-id")
    initial = json.loads((ROOT / "chunk3_synthetic_evaluation/data/synthetic_northstar/structured/initial_state.json").read_text())
    record = next(e for e in initial["evidence"] if e["id"] == evidence_id)
    span = next(s for s in initial["source_spans"] if s["id"] == record["source_span_ids"][0])
    first_row.click()
    expect(page.locator("#source-inspector")).to_contain_text(span["quote"])
    expect(page.locator("#source-inspector .locator").first).to_contain_text("word/document.xml")
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
    expect(page.locator("#page-content")).to_contain_text(re.compile("posterior", re.I))
    expect(page.locator("#page-content")).to_contain_text(re.compile("bits", re.I))
    _shot(page, "06_analytics_1440.png", tmp_path)
    _navigate(page, "export")
    _shot(page, "07_export_1440.png", tmp_path)
    for label, member in [("DD Request List · Excel", "xl/workbook.xml"), ("Screening Memo · Word", "word/document.xml")]:
        control = page.locator("#export-format")
        control.click()
        control.locator(".Select-menu-outer").get_by_text(label, exact=True).click()
        expect(page.locator('#export-confirm input')).not_to_be_checked(timeout=60000)
        page.locator('#export-confirm input').check()
        expect(page.locator("#export-approval-status")).to_contain_text("Ready to download", timeout=60000)
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
    expect(page.locator("#status-live-region")).to_contain_text(re.compile("reject", re.I), timeout=60000)
    _revision(page, 1)
    assert page.locator("#top3-list").inner_text() == before
    page.locator("#reset-demo").click()
    expect(page.locator("#status-live-region")).to_contain_text(re.compile("reset|initial", re.I))
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
    _choose_case(page, "manufacturing")
    _navigate(page, "analytics")
    expect(page.locator("#page-content")).to_contain_text(re.compile("unavailable|not parameterized|not_parameterized", re.I))
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

"""Financial invariants and source/review boundaries, independent expected figures."""
from copy import deepcopy
from decimal import Decimal as D
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from orion.services.fdd_finance import (DATASETS, FinanceError, calculations, csv_text, demo_pack, parse_csv,
                                        resolve_ref)
from orion.services.fdd_workpapers import (FDDWorkpapers, content_hash, databook_bytes, initial_state,
                                           report_markdown, review_blockers, review_status, source_bundle_bytes)


@pytest.fixture
def state():
    return initial_state('nb', 'Northstar', 'test-binding')


@pytest.fixture
def service():
    return FDDWorkpapers('financial-test-only-key-32-characters')


def test_complete_case_financial_bridges_and_units(state, service):
    c = calculations(state, '2025')
    # Independently derived from 12 months of revenue 900 + 16*i + seasonality,
    # 48% cost, 220 + 18% operating cost, and the two recorded one-off costs.
    assert c['revenue'] == D('14460')
    assert c['prior_revenue'] == D('12156')
    assert c['reported_ebitda'] == D('2223.40')
    assert c['qoe_sum'] == D('41')
    assert c['adjusted_ebitda'] == D('2264.40')
    assert c['opening_nwc'] == D('248')
    assert c['reported_nwc'] == D('307')
    assert c['adjusted_nwc'] == D('287')
    assert c['pegs']['12'] == D('280')
    assert c['base_net_debt'] == D('633')
    assert c['net_debt'] == D('670')  # 785 + 120 - 272 + 25 + 12, restricted cash excluded.
    assert c['cash']['operating_cash'] == D('1840.40')
    assert c['cash_residual'] == D('0')
    assert c['fcf'] == D('1456.40')
    assert c['equity'] is None  # No invented enterprise valuation.
    updated = service.update(state, 'transaction', dict(ev='10000', peg_method='12', peg_manual=None,
                             mechanism='Completion accounts', note='입력 가격 시나리오'))
    assert calculations(updated)['equity'] == D('9337')
    updated = service.update(updated, 'transaction', dict(ev='10000', peg_method='12', peg_manual=None, mechanism='Locked box', note=''))
    assert calculations(updated)['equity'] == D('9330')
    assert state['transaction']['ev'] is None


def test_reconciliation_mapping_and_source_locators(state, service):
    c = calculations(state)
    row = next(r for r in c['reconciliations'] if r['metric'] == 'revenue')
    assert row['management'] == D('14460')
    assert row['trial'] == row['gl'] == row['statutory'] == D('14448')
    assert row['residual_tb'] == D('12') and row['status'] == '미대사'
    ref = resolve_ref(c['pack'], state['adjustments'][0]['source'])
    assert ref['record']['id'] == 'GL-001' and ref['row'] == 2 and ref['value'] == '35'
    assert ref['sha256'] == sha256(c['pack']['documents'][ref['document']]['text'].encode()).hexdigest()
    wrong = service.update(state, 'mapping', dict(account_code='4000', metric='opex', multiplier='-1'))
    assert next(r for r in calculations(wrong)['reconciliations'] if r['metric'] == 'revenue')['gl'] is None
    assert '미대사·미제공 재무 계정' in review_blockers(wrong)


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '1e16', '1.0000001', 'True'])
def test_invalid_csv_financial_amounts_fail_closed(bad):
    columns = DATASETS['trial'][1]
    text = csv_text([dict(period='2025-01', revenue=bad, cogs='0', opex='0', da='0')], columns)
    with pytest.raises(FinanceError):
        parse_csv('trial', text)


def test_missing_values_gaps_and_period_filters_never_become_zero(state, service):
    rows = deepcopy(demo_pack()['data']['monthly'])
    rows[-1]['ar'] = None
    changed = service.update(state, 'dataset', dict(kind='monthly', filename='entered.csv', text=csv_text(rows, DATASETS['monthly'][1])))
    c = calculations(changed)
    assert c['reported_nwc'] is None and c['cash_expected'] is None and c['equity'] is None
    assert c['revenue'] == D('14460')
    assert calculations(state, '2024')['qoe_sum'] == 0
    assert calculations(state, 'LTM')['adjusted_ebitda'] == D('2264.40')
    rows.pop(14)  # Missing March observation is not an observed zero.
    changed = service.update(state, 'dataset', dict(kind='monthly', filename='gap.csv', text=csv_text(rows, DATASETS['monthly'][1])))
    assert calculations(changed)['reported_ebitda'] is None
    with pytest.raises(FinanceError):
        parse_csv('monthly', csv_text(rows + [rows[0]], DATASETS['monthly'][1]))
    scope = dict(state['scope'], end='2024-12', as_of='2024-12-31')
    restricted = service.update(state, 'scope', scope)
    assert calculations(restricted)['period'] == '2024'
    assert calculations(restricted)['revenue'] == D('12156')
    partial = service.update(state, 'scope', dict(state['scope'], start='2025-02'))
    assert calculations(partial, 'LTM')['revenue'] is None
    assert calculations(partial)['pegs']['12'] is None


def test_duplicate_nwc_and_net_debt_economic_item_or_source_rejected(state, service):
    nwc = state['adjustments'][3]
    values = {k: v for k, v in nwc.items() if k not in {'id', 'source'}}
    values.update(area='Net debt', economic_key='different-name-same-cell', source_id='adjustment_ledger', source_row=5, source_column='amount')
    with pytest.raises(FinanceError, match='중복'):
        service.update(state, 'adjustment', values)
    values.update(source_id='monthly_financials', source_row=25, source_column='ap')
    with pytest.raises(FinanceError, match='기준 NWC'):
        service.update(state, 'adjustment', values)
    values.update(source_id='adjustment_ledger', source_row=2, source_column='description')
    with pytest.raises(FinanceError):
        service.update(state, 'adjustment', values)


def test_source_replacement_invalidates_adoption_and_preserves_history(state, service):
    source = demo_pack()['data']['ledger']
    changed = service.update(state, 'dataset', dict(kind='ledger', filename='new_ledger.csv', text=csv_text(source, DATASETS['ledger'][1])))
    assert {r['decision'] for r in changed['adjustments']} == {'검토 후보'}
    assert calculations(changed)['adjusted_ebitda'] == calculations(changed)['reported_ebitda']
    assert resolve_ref(calculations(changed)['pack'], changed['adjustments'][0]['source']) is None
    assert changed['history'][0]['before'] == content_hash(state)
    assert state['adjustments'][0]['decision'] == '분석 반영'


def test_signed_drafts_bound_to_session_and_project(service):
    state = service.read(None, 'nb', 'session-a', 'Northstar')
    token = service.sign(state)
    assert service.read(token, 'nb', 'session-a')['case_id'] == 'nb'
    for args in [(token, 'nb', 'session-b'), (token, 'mf', 'session-a'), (token[:-2] + 'aa', 'nb', 'session-a')]:
        with pytest.raises(FinanceError):
            service.read(*args)
    other = service.read(None, 'mf', 'session-a', '제조업 사례')
    assert calculations(other)['revenue'] is None and not other['demo_pack']
    oversized = deepcopy(state)
    oversized['history'] = [{'note': 'x' * 180_000}]
    with pytest.raises(FinanceError, match='한도'):
        service.sign(oversized)
    with pytest.raises(FinanceError, match='140KB'):
        parse_csv('monthly', '한' * 50_000)


def test_review_gates_distinct_names_and_changes_invalidate_signoff(state, service):
    prepared = service.update(state, 'prepare', dict(preparer='작성자'))
    with pytest.raises(FinanceError, match='다른 검토자'):
        service.update(prepared, 'approve', dict(reviewer='작성자'))
    with pytest.raises(FinanceError, match='미대사'):
        service.update(prepared, 'approve', dict(reviewer='검토자'))
    resolved = service.update(state, 'reconciliation', dict(id='2025-revenue', adjustment_tb='12', adjustment_fs='0',
        explanation='관리 매출과 미전기 금액의 기간 차이 12를 대사 조정으로 기록 (검증용 예시)', source_id='monthly_financials', source_row=25, source_column='revenue'))
    for issue in list(resolved['issues']):
        if issue['priority'] == '높음':
            resolved = service.update(resolved, 'issue', {**issue, 'status': '범위 제한', 'conclusion': '추가 원천 미수령을 범위 제한으로 명시'})
    assert review_blockers(resolved) == []
    prepared = service.update(resolved, 'prepare', dict(preparer='작성자'))
    approved = service.update(prepared, 'approve', dict(reviewer='검토자'))
    assert review_status(approved) == '검토 기록 확정'
    updated = service.update(approved, 'transaction', dict(ev='10000', peg_method='12', peg_manual=None, mechanism='Completion accounts', note=''))
    assert updated['review']['approved_hash'] is None and review_status(updated) == '작성 중'
    commented = service.update(prepared, 'comment', dict(author='검토자', workpaper='QOE', note='반복성 근거 보완'))
    with pytest.raises(FinanceError, match='미해결 검토 의견'):
        service.update(commented, 'approve', dict(reviewer='검토자'))
    closed = service.update(commented, 'resolve_comment', dict(id='RC-001', response='보완 자료와 산정 근거를 확인'))
    signed = service.update(closed, 'approve', dict(reviewer='검토자'))
    edited_response = service.update(signed, 'resolve_comment', dict(id='RC-001', response='해소 근거를 다시 수정'))
    assert review_status(edited_response) != '검토 기록 확정'


def test_databook_report_and_downloaded_sources_share_values_and_hashes(state):
    workbook = load_workbook(BytesIO(databook_bytes(state)), data_only=True)
    rows = list(workbook['거래영향'].values)
    values = dict(zip(rows[0], rows[1]))
    assert values['adjusted_ebitda'] == 2264.4 and isinstance(values['adjusted_ebitda'], float)
    assert values['net_debt'] == 670 and values['ev'] is None
    assert workbook['산출물정보']['B2'].value == content_hash(state)
    report = report_markdown(state)
    assert '2,264.40' in report and '미제공 / 미정량' in report and '외부확인 제외' in report
    with ZipFile(BytesIO(source_bundle_bytes(state))) as archive:
        manifest = json.loads(archive.read('source_manifest.json'))
        for source in manifest:
            assert sha256(archive.read('sources/' + source['id'] + '.csv')).hexdigest() == source['sha256']
    injected = deepcopy(state)
    injected['issues'][0]['title'] = '=HYPERLINK("https://evil.invalid")'
    book = load_workbook(BytesIO(databook_bytes(injected)), data_only=False)
    assert not any(cell.data_type == 'f' for sheet in book for row in sheet for cell in row)

"""Dash wiring for signed financial workpapers; no browser-supplied totals."""
from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from flask import session

from orion.services.fdd_finance import DATASETS, FinanceError, calculations, csv_text, pack_for
from orion.services.fdd_workpapers import (FDDWorkpapers, databook_bytes, report_markdown,
                                           review_status, source_bundle_bytes)
from . import fdd_workspace as ui


def register_finance(app, workspace):
    service = FDDWorkpapers(app.server.secret_key)
    app.clientside_callback("""function(page, area, selection) {
        const trigger = dash_clientside.callback_context.triggered[0];
        window.requestAnimationFrame(function() {
            const pane = document.getElementById('inspector-pane');
            if (pane) pane.scrollTop = 0;
            if (trigger && !trigger.prop_id.startsWith('fw-inspection.')) {
                const main = document.getElementById('main-workspace');
                if (main) main.scrollTop = 0;
                window.scrollTo({top:0, behavior:'instant'});
            }
        });
        return window.dash_clientside.no_update;
    }""", Output('finance-scroll', 'data'), Input('workspace-tabs', 'value'), Input('fw-area', 'value'), Input('fw-inspection', 'value'))

    def current(workspace_token, finance_token=None):
        sid = session['orion_session']
        view = workspace.view(workspace_token, sid)
        state = service.read(finance_token, view['case_id'], sid, view['deal']['name'])
        return view, state

    def fields(ids, values):
        return {identifier['name']: value for identifier, value in zip(ids or [], values or [])}

    @app.callback(Output('finance-registry', 'data'), Output('finance-token', 'data'), Output('fw-message', 'children'),
                  Input('workspace-token', 'data'), Input({'type': 'fw-command', 'action': ALL}, 'n_clicks'),
                  State('finance-registry', 'data'), State('finance-token', 'data'), State('fw-inspection', 'value'),
                  State({'type': 'fw-field', 'name': ALL}, 'id'), State({'type': 'fw-field', 'name': ALL}, 'value'))
    def mutate(workspace_token, clicks, registry, finance_token, selection, field_ids, field_values):
        if not workspace_token:
            return no_update, no_update, no_update
        try:
            view, _ = current(workspace_token)
            case = view['case_id']
            registry = dict(registry or {})
            trigger = ctx.triggered_id
            if trigger is None or trigger == 'workspace-token':
                _, state = current(workspace_token, registry.get(case))
                token = service.sign(state)
                registry[case] = token
                return registry, token, ''
            if not isinstance(trigger, dict) or not any(item.get('value') for item in ctx.triggered):
                return no_update, no_update, no_update
            action = trigger['action']
            if action in {'reset_finance', 'blank_finance'}:
                _, state = current(workspace_token)
                if action == 'blank_finance':
                    # Clear only the additive financial draft. Original documents,
                    # question rankings and canonical snapshots are untouched.
                    state.update(demo_pack=False, pack_hash=None, datasets={}, adjustments=[], requests=[], issues=[],
                                 reconciliations={}, mapping=[])
                    state['scope'].update(entity=view['deal']['name'], currency='KRW', unit='백만원', gaap='K-IFRS',
                                          business_scope='입력 필요', exclusions='공개자료 기반 예비 검토. 미제공 자료·제외 범위를 기록하세요.')
                message = '재무 조서를 초기화했습니다.' if action == 'reset_finance' else '빈 재무 조서를 시작했습니다. 범위와 기간을 저장하고 자료를 입력하세요.'
            else:
                _, state = current(workspace_token, finance_token)
                values = fields(field_ids, field_values)
                prefix = {'scope': 'scope_', 'transaction': 'transaction_', 'dataset': 'dataset_', 'prepare': 'prepare_',
                          'approve': 'approve_', 'comment': 'comment_', 'resolve_comment': 'resolve_comment_'}.get(action, 'edit_')
                values = {k[len(prefix):]: v for k, v in values.items() if k.startswith(prefix)}
                if action in {'request', 'adjustment', 'issue', 'reconciliation'}:
                    identifier = values.get('id') or 'new'
                    if selection != action + ':' + identifier:
                        raise FinanceError('선택한 상세 항목을 불러온 뒤 저장하세요. 이전 항목은 변경하지 않았습니다.')
                state = service.update(state, action, values, original_documents=[d['id'] for d in view['documents']])
                message = '저장했습니다. 재무 수치·근거·판단 변경 시 이전 작성 제출과 검토 확정은 해제됩니다.'
            token = service.sign(state)
            registry[case] = token
            return registry, token, html.Div(message, className='fw-notice fw-notice-ok')
        except FinanceError as error:
            return no_update, no_update, html.Div(str(error), className='fw-notice fw-notice-error')
        except (TypeError, ValueError):
            return no_update, no_update, html.Div('입력 형식과 현재 프로젝트를 확인하세요. 변경은 저장되지 않았습니다.', className='fw-notice fw-notice-error')

    @app.callback(Output('fw-title', 'children'), Output('fw-context', 'children'), Output('fw-content', 'children'),
                  Output('fw-status-pills', 'children'), Output('fw-area-wrap', 'style'),
                  Output('fw-period', 'options'), Output('fw-period', 'value'),
                  Input('workspace-token', 'data'), Input('finance-token', 'data'), Input('workspace-tabs', 'value'),
                  Input('fw-area', 'value'), Input('fw-role', 'value'), Input('fw-period', 'value'))
    def render(workspace_token, finance_token, page, area, role, period):
        if not workspace_token or not finance_token or page not in ui.PAGES:
            return (no_update,) * 7
        try:
            view, state = current(workspace_token, finance_token)
            rows = pack_for(state)['data']['monthly']
            years = sorted({r['period'][:4] for r in rows if state['scope']['start'] <= r['period'] <= state['scope']['end']})
            allowed = years + (['LTM'] if rows else [])
            period = period if period in allowed else (years[-1] if years else None)
            c = calculations(state, period)
            s = state['scope']
            context = f"{s['entity']} · {s['currency']} {s['unit']} · 기준일 {s['as_of']}"
            period_text = f"{c['periods'][0]} → {c['periods'][-1]} · {len(c['periods'])}개월" if c['periods'] else '재무자료 미제공'
            pills = [ui.pill(period_text), ui.pill(review_status(state), 'blue'), ui.pill('조서 v' + str(state['revision']))]
            content = ui.render_page(state, page, c, area or 'historical', role or 'Big 4', view['documents'])
            if state['demo_pack']:
                content.insert(0, html.Div('합성 재무 검증팩 · 기존 투자 문서와 별개의 수치입니다. 실제 기업의 재무자료가 아닙니다.', className='fw-demo-note'))
            # Different pages must not reuse native <details> open state or an
            # editor DOM node simply because it occupied the same list position.
            content = html.Div(content, key=page + ':' + (area if page == 'financial' else 'page'))
            return ui.TITLES[page], context, content, pills, {'display': 'block' if page == 'financial' else 'none'}, [
                {'label': ('최근 12개월 · LTM' if y == 'LTM' else y + '년 · 제공 월 기준'), 'value': y} for y in allowed], period
        except FinanceError as error:
            return '재무 조서 확인 필요', '', html.Div(str(error), className='fw-empty'), [], {}, [], None

    @app.callback(Output('fw-inspection', 'options'), Output('fw-inspection', 'value'), Output('fw-detail', 'children'),
                  Input('workspace-token', 'data'), Input('finance-token', 'data'), Input('workspace-tabs', 'value'),
                  Input('fw-area', 'value'), Input('fw-period', 'value'), Input('fw-inspection', 'value'))
    def inspect(workspace_token, finance_token, page, area, period, selection):
        if not workspace_token or not finance_token or page not in ui.PAGES:
            return (no_update,) * 3
        try:
            view, state = current(workspace_token, finance_token)
            c = calculations(state, period)
            options = ui.inspection_options(state, c, page, area)
            # A navigation transition picks the current page's default; a chart
            # click may add any valid source cell from this project's active pack.
            native_id = selection.split(':', 1)[1] if selection and selection.startswith('native:') else None
            is_native = native_id in {d['id'] for d in view['documents']}
            if ctx.triggered_id in {'workspace-tabs', 'fw-area'} or not (is_native or ui.valid_selection(state, c, selection)):
                selection = options[0]['value'] if options else None
                is_native = False
            if selection and selection not in {o['value'] for o in options}:
                label = {'request:new': '새 자료 요청', 'adjustment:new': '새 조정 후보', 'issue:new': '새 발견사항', 'mapping:new': '계정 매핑 추가'}.get(selection, selection)
                if is_native:
                    label = next(d.get('filename', native_id) for d in view['documents'] if d['id'] == native_id)
                options.append({'value': selection, 'label': label})
            if is_native:
                from .layout import render_inspection
                detail = render_inspection(workspace.inspect(workspace_token, session['orion_session'], 'document', native_id))
            else:
                detail = ui.render_detail(state, c, selection, view['documents'], area)
            if selection and selection.startswith('request:'):
                request_id = selection.split(':', 1)[1]
                record = next((r for r in state['requests'] if r['id'] == request_id), {})
                doc_id = record.get('source_id')
                if doc_id in {d['id'] for d in view['documents']}:
                    from .layout import render_inspection
                    detail.append(render_inspection(workspace.inspect(workspace_token, session['orion_session'], 'document', doc_id)))
            return options, selection, detail
        except FinanceError as error:
            return [], None, html.P(str(error))

    @app.callback(Output('workspace-tabs', 'value', allow_duplicate=True),
                  Input({'type': 'fw-route', 'page': ALL, 'key': ALL}, 'n_clicks'), prevent_initial_call=True)
    def navigate(clicks):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or not any(item.get('value') for item in ctx.triggered):
            return no_update
        return trigger['page'] if trigger['page'] in ui.PAGES | {'studio', 'evidence', 'thesis', 'questions', 'review', 'analytics', 'export', 'overview', 'fdd'} else no_update

    @app.callback(Output('fw-inspection', 'value', allow_duplicate=True),
                  Input({'type': 'fw-select', 'target': ALL}, 'n_clicks'),
                  Input({'type': 'fw-chart', 'kind': ALL}, 'clickData'),
                  Input({'type': 'fw-grid', 'kind': ALL}, 'cellClicked'),
                  State('workspace-token', 'data'), State('finance-token', 'data'), State('fw-period', 'value'), prevent_initial_call=True)
    def select(clicks, chart_clicks, grid_clicks, workspace_token, finance_token, period):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or not any(item.get('value') for item in ctx.triggered):
            return no_update
        view, state = current(workspace_token, finance_token)
        c = calculations(state, period)
        selection = None
        if trigger['type'] == 'fw-select':
            selection = trigger['target']
        elif trigger['type'] == 'fw-chart':
            event = next((v for v in chart_clicks or [] if v and v.get('points')), None)
            # Use the event for the actual triggering graph (not another graph's
            # retained clickData) when multiple charts share the pattern input.
            entries = ctx.inputs_list[1]
            event = next((v['value'] for v in entries if v['id'] == trigger), event)
            if event:
                selection = event['points'][0].get('customdata')
        else:
            entries = ctx.inputs_list[2]
            event = next((v['value'] for v in entries if v['id'] == trigger), None)
            if not event:
                return no_update
            kind = trigger['kind']
            row_id = event.get('rowId')
            selection = {'requests': 'request:', 'adjustments': 'adjustment:', 'issues': 'issue:',
                         'reconciliation': 'reconciliation:', 'mapping': 'mapping:'}.get(kind, '') + str(row_id)
            if kind == 'monthly':
                row = next((r for i, r in enumerate(c['pack']['data']['monthly']) if str(i) == str(row_id)), None)
                if row and event.get('colId') in DATASETS['monthly'][1]:
                    selection = ui.source_key(c['pack'], 'monthly', c['pack']['data']['monthly'].index(row), event['colId'])
        return selection if ui.valid_selection(state, c, selection) else no_update

    @app.callback(Output('finance-download', 'data'),
                  Input({'type': 'fw-download', 'kind': ALL}, 'n_clicks'),
                  State('workspace-token', 'data'), State('finance-token', 'data'), State('fw-period', 'value'),
                  State({'type': 'fw-field', 'name': ALL}, 'id'), State({'type': 'fw-field', 'name': ALL}, 'value'), prevent_initial_call=True)
    def export(clicks, workspace_token, finance_token, period, field_ids, field_values):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or not any(item.get('value') for item in ctx.triggered):
            return no_update
        try:
            _, state = current(workspace_token, finance_token)
            kind = trigger['kind']
            name = f"Orion_FDD_{state['case_id']}_v{state['revision']}"
            if kind == 'xlsx':
                return dcc.send_bytes(databook_bytes(state, period), name + '_databook.xlsx')
            if kind == 'report':
                return dcc.send_string(report_markdown(state, period), name + '_draft.md')
            if kind == 'sources':
                return dcc.send_bytes(source_bundle_bytes(state), name + '_sources.zip')
            if kind == 'template':
                kind = fields(field_ids, field_values).get('dataset_kind', 'monthly')
                if kind in DATASETS:
                    return dcc.send_string('\ufeff' + csv_text([], DATASETS[kind][1]), f'Orion_FDD_{kind}_template.csv')
        except FinanceError:
            return no_update
        return no_update

"""FDD-first presentation: the same calculated workpapers feed UI and exports."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D
from datetime import date
import json
import hashlib

from dash import dcc, html
import dash_ag_grid as dag
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from orion.services.fdd_finance import (DATASETS, LABELS, calculations, decimal, ebitda, nwc,
                                        ratio, resolve_ref, serial, source_ref)
from orion.services.fdd_workpapers import (AREAS, ADJUSTMENT_DECISIONS, ISSUE_STATES, REQUEST_STATES,
                                            review_blockers, review_status, content_hash)
from .i18n import GRID_LOCALE
from .file_icons import file_icon

NAVIGATION = [("deal", "1. 거래 개요·실사 범위"), ("dataroom", "2. 자료실·자료 요청"),
              ("reconciliation", "3. 재무 데이터·대사"), ("financial", "4. 재무 실사 분석"),
              ("issues", "5. 쟁점·실사 질문·경영진 Q&A"), ("adjustments", "6. 조정사항·거래 영향"),
              ("quality", "7. 작성·검토 관리"), ("deliverables", "8. 보고서·산출물")]
PAGES = {k for k, _ in NAVIGATION}
ANALYSES = [("historical", "과거 실적"), ("qoe", "QoE"), ("nwc", "운전자본"),
            ("debt", "순차입금"), ("cash", "현금흐름·CAPEX"), ("forecast", "전망")]
TITLES = dict(NAVIGATION)
BLUE, TEAL, ORANGE, PURPLE, NAVY = "#4664e8", "#0c9288", "#d98035", "#8b6bd1", "#243958"
DATASET_LABELS = {"monthly": "월별 관리재무", "trial": "시산표", "gl": "원장 계정별 월 잔액", "statutory": "연간 재무제표",
                  "segments": "부문 매출", "ledger": "조정 원장 발췌", "aging": "연령 분석", "budget": "경영계획"}


def fmt(value, percent=False, digits=1):
    if value is None:
        return "미제공"
    value = D(str(value))
    return f"{value * 100:,.1f}%" if percent else f"{value:,.{digits}f}"


def plot_number(value):
    return None if value is None or value == '' else float(value)


def pill(text, kind="neutral"):
    return html.Span(text, className="fw-pill fw-" + kind)


def command(label, action, primary=False):
    return html.Button(label, id={"type": "fw-command", "action": action}, n_clicks=0,
                       className="button button-primary" if primary else "button button-secondary")


def route(label, page):
    return html.Button(label, id={"type": "fw-route", "page": page, "key": hashlib.sha1(label.encode()).hexdigest()[:10]}, n_clicks=0, className="fw-route-link")


def select_button(label, target):
    return html.Button(label, id={"type": "fw-select", "target": target}, n_clicks=0, className="button button-secondary")


def download(label, kind):
    return html.Button(label, id={"type": "fw-download", "kind": kind}, n_clicks=0, className="button button-secondary")


def field(name, label, value="", *, options=None, multiline=False, numeric=False, readonly=False):
    identifier = {"type": "fw-field", "name": name}
    if options is not None:
        component = dcc.Dropdown(id=identifier, options=[{"label": label_, "value": key} for key, label_ in options],
                                 value=value, clearable=False, searchable=True, disabled=readonly)
    elif multiline:
        component = dcc.Textarea(id=identifier, value=value or "", maxLength=140_000 if name == "dataset_text" else 2000,
                                 readOnly=readonly, className="fw-textarea fw-csv" if name == "dataset_text" else "fw-textarea")
    else:
        component = dcc.Input(id=identifier, value=value, type="number" if numeric else "text", readOnly=readonly,
                              className="fw-input", debounce=True, maxLength=2000 if not numeric else None)
    return html.Div([html.Label(label, htmlFor=json.dumps(identifier, separators=(",", ":"), sort_keys=True)), component], className="fw-field")


def card(title, children, note=None, className=""):
    return html.Section([html.Div([html.H3(title), html.Span(note, className="fw-note") if note else None], className="fw-section-heading"),
                         *children], className="fw-card " + className)


def metrics(items):
    return html.Div([html.Div([html.Span(label), html.Strong(value), html.Small(note)], className="fw-metric")
                     for label, value, note in items], className="fw-metrics")


def table(kind, rows, columns, max_height=410):
    rows = serial(rows)
    fields = []
    for definition in columns:
        key, name, *numeric = definition
        is_number = bool(numeric and numeric[0])
        col = dict(field=key, headerName=name, tooltipField=key, minWidth=130 if is_number else 150,
                   flex=1, wrapText=False, autoHeight=False)
        if key == 'id':
            col.update(minWidth=100, maxWidth=115, flex=0)
        if key in {'status', 'area', 'priority', 'decision', 'agreed', 'owner', 'period', 'due'}:
            col.update(minWidth=110, width=120, flex=0)
        if key in {"name", "title", "explanation", "judgment"}:
            col.update(minWidth=240, flex=2)
        if is_number:
            col.update(type="numericColumn", valueFormatter={"function": "fwNumber(params)"}, cellClass="fw-number",
                       cellClassRules={"fw-difference": "params.value !== null && Number(params.value) !== 0"} if "residual" in key else {})
        if key in {"status", "decision", "priority"}:
            col["cellClassRules"] = {"fw-state-open": "['未','미대사','추가 확인','보완 요청','높음','미해결'].includes(params.value)",
                                     "fw-state-ok": "['일치','조정 대사','수령','해결','분석 반영'].includes(params.value)"}
        fields.append(col)
    for i, row in enumerate(rows):
        row.setdefault("id", str(i))
    return dag.AgGrid(id={"type": "fw-grid", "kind": kind}, rowData=rows, columnDefs=fields,
                      getRowId="params.data.id", defaultColDef={"resizable": True, "sortable": True, "filter": True,
                                                                 "wrapHeaderText": True, "autoHeaderHeight": True},
                      dashGridOptions={"localeText": GRID_LOCALE, "animateRows": False, "rowHeight": 52, "headerHeight": 46,
                                       "enableCellTextSelection": True, "tooltipShowDelay": 250, "ensureDomOrder": True},
                      className="ag-theme-alpine fw-grid", style={"width": "100%", "height": min(max_height, max(150, 52 * len(rows) + 66))})


def chart(identifier, fig, height=325):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Segoe UI, Malgun Gothic, sans-serif", size=14, color=NAVY),
                      margin=dict(l=52, r=26, t=34, b=50), height=height,
                      legend=dict(orientation="h", y=1.15, x=0), hoverlabel=dict(font_size=15))
    fig.update_xaxes(showgrid=False, automargin=True)
    fig.update_yaxes(gridcolor="#e9eef5", zerolinecolor="#a8b4c5", automargin=True)
    return dcc.Graph(id={"type": "fw-chart", "kind": identifier}, figure=fig,
                     config={"displayModeBar": False, "responsive": True, "locale": "ko"}, responsive=True,
                     style={'width': '100%', 'height': height, 'minWidth': 0}, className="fw-chart")


def waterfall(identifier, labels, movements, *, refs=None, totals=None, focus=False):
    if any(value is None for value in movements):
        return html.Div("계산에 필요한 원천 금액이 미제공입니다. 자료를 입력하면 bridge를 표시합니다.", className="fw-empty")
    measures = ["absolute"] + ["relative"] * (len(movements) - 2) + ["total"]
    if totals:
        for index in totals:
            measures[index] = "total"
    running, texts, levels = D(0), [], []
    for value, measure in zip(movements, measures):
        running = value if measure == "absolute" else running if measure == "total" else running + value
        texts.append(fmt(running if measure == "total" else value))
        levels.append(running)
    fig = go.Figure(go.Waterfall(x=labels, y=[float(v) for v in movements], measure=measures,
        increasing=dict(marker_color=BLUE), decreasing=dict(marker_color=ORANGE), totals=dict(marker_color=NAVY),
        connector=dict(line_color="#bcc6d5"), text=texts, textposition="outside", customdata=refs or [""] * len(labels),
        hovertemplate="%{x}<br>%{text}<extra></extra>"))
    if focus and levels:
        low, high = min(levels), max(levels)
        pad = max(D(20), (high - low) * D('.5'))
        fig.update_yaxes(range=[float(low - pad), float(high + pad)], title_text='금액 · 확대 축')
    fig.update_xaxes(tickvals=labels, ticktext=[label.replace(' ', '<br>', 1) for label in labels])
    return chart(identifier, fig, 345)


def source_key(pack, kind, row, column):
    ref = source_ref(pack, kind, row, column)
    return f"cell:{ref['document']}:{ref['row']}:{ref['column']}" if ref else ""


def display_months(c):
    """Leave an explicit chart gap for missing months; never create source rows."""
    if not c['selected']:
        return []
    lookup = {r['period']: r for r in c['selected']}
    start, end = c['selected'][0]['period'], c['selected'][-1]['period']
    first = int(start[:4]) * 12 + int(start[5:]) - 1
    last = int(end[:4]) * 12 + int(end[5:]) - 1
    return [lookup.get(f'{i // 12}-{i % 12 + 1:02}', {'period': f'{i // 12}-{i % 12 + 1:02}'}) for i in range(first, last + 1)]


def root():
    return html.Div([
        html.Div(id="fw-message", role="status", **{"aria-live": "polite"}),
        html.Div(id="fw-content"),
        html.Details([html.Summary('재무 조서 새로 시작'),
                      html.P('현재 재무 조서를 덮어씁니다. 필요한 데이터북·보고서를 먼저 내려받으세요. 기존 원문·질문 엔진의 상태는 별도로 유지됩니다.'),
                      html.Div([command('기본 재무 조서 다시 시작', 'reset_finance'), command('빈 재무 조서로 시작', 'blank_finance')], className='fw-actions')], className='fw-reset-controls'),
        html.P("조서는 현재 브라우저 탭에 저장됩니다. 앱 재시작 전 데이터북을 내려받으세요. 금액은 합성 재무팩 또는 사용자 입력이며, 자료 수령·분석 반영·검토 기록·경영진 합의는 별도 상태입니다.", className="fw-storage-note"),
    ], id="finance-workspace", className="fw-workspace")


def inspector_root():
    return html.Div([
                     html.P('선택 항목의 금액·원천·판단을 함께 확인합니다.', className='fw-inspector-help'),
                     html.Label("선택한 항목", htmlFor="fw-inspection"),
                     dcc.Dropdown(id="fw-inspection", options=[], clearable=False, placeholder="표의 행·차트 막대를 선택"),
                     html.Div(id="fw-detail")], id="finance-inspector")


def trend(c):
    rows = display_months(c)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    packrows = c["pack"]["data"]["monthly"]
    refs = [source_key(c["pack"], "monthly", packrows.index(r) if r in packrows else None, "revenue") for r in rows]
    fig.add_trace(go.Bar(x=[r["period"] for r in rows], y=[plot_number(r.get("revenue")) for r in rows], name="매출", marker_color=BLUE, customdata=refs,
                        hovertemplate="%{x}<br>매출 %{y:,.1f}<extra></extra>"), secondary_y=False)
    margins = [ratio(ebitda(r), decimal(r.get("revenue"))) for r in rows]
    fig.add_trace(go.Scatter(x=[r["period"] for r in rows], y=[None if m is None else float(m) for m in margins], name="EBITDA 마진", mode="lines+markers", line_color=TEAL, connectgaps=False), secondary_y=True)
    fig.update_yaxes(tickformat=".0%", secondary_y=True, title_text="마진")
    fig.update_yaxes(rangemode='tozero', secondary_y=False)
    ticks = list(dict.fromkeys([r['period'] for r in rows[::3]] + ([rows[-1]['period']] if rows else [])))
    fig.update_xaxes(type='category', tickvals=ticks, ticktext=[p.replace('-', '.') for p in ticks])
    return chart("trend", fig)


def qoe_chart(c):
    adjustments = c["qoe"]
    return waterfall("qoe", ["보고 EBITDA"] + [a["name"] for a in adjustments] + ["조정 EBITDA"],
                     [c["reported_ebitda"]] + [decimal(a["amount"]) for a in adjustments] + [D(0)],
                     refs=["metric:ebitda"] + ["adjustment:" + a["id"] for a in adjustments] + ["metric:adjusted_ebitda"], focus=True)


def adjustment_table(state, area=None):
    rows = [a for a in state["adjustments"] if area is None or a["area"] == area]
    return table("adjustments", rows, [("id", "조정 ID"), ("area", "영역"), ("name", "조정 설명"), ("period", "해당 월"),
                                       ("amount", "증감 금액", True), ("decision", "분석 상태"), ("agreed", "경영진 합의")])


def render_deal(state, c, role):
    s = state["scope"]
    blockers = review_blockers(state)
    cards = metrics([("보고 EBITDA", fmt(c["reported_ebitda"]), "원천 관리손익 기준"),
                     ("분석 반영 EBITDA", fmt(c["adjusted_ebitda"]), "검토·합의 상태와 별도"),
                     ("순차입금", fmt(c["net_debt"]), "기준일 잔액 + debt-like"),
                     ("미해결 검토 조건", str(len(blockers)), "자료·분석·판단 확인 항목")])
    focus = card("검토 우선 항목", [html.Div([pill("확인 필요", "orange"), html.Strong(" · ".join(blockers) or "현재 등록된 차단 조건 없음")], className="fw-focus"),
                   html.Div([route("재무 대사 확인 →", "reconciliation"), route("미해결 쟁점 확인 →", "issues")], className="fw-actions")])
    if role == "PE":
        focus = card("지속 이익·현금 창출력", [qoe_chart(c), html.P(f"보고 EBITDA 대비 영업현금흐름 전환율 {fmt(c['cash_conversion'], True)}. 조정 채택과 가격 시나리오는 별도로 검토합니다.")])
    elif role == "IB":
        focus = card("거래 의사결정 전달사항", [html.P(state["transaction"]["note"] or "가격·계약상 전달사항을 아직 작성하지 않았습니다."),
                    table("issues", state["issues"], [("id", "쟁점 ID"), ("title", "주요 발견사항"), ("priority", "중요도"), ("status", "상태")]), route("거래 영향 작성 →", "adjustments")])
    scope_fields = [("entity", "대상 법인"), ("side", "실사 관점"), ("transaction_type", "거래 구조"),
                    ("business_scope", "대상 사업·법인 범위"), ("start", "검토 시작 월"), ("end", "검토 종료 월"),
                    ("as_of", "기준일"), ("gaap", "회계기준"), ("currency", "통화"), ("unit", "금액 단위"), ("exclusions", "제외·제한 범위")]
    return [cards, html.Div([card("실사 범위", [html.Dl([html.Div([html.Dt(label), html.Dd(s[key])]) for key, label in
                     [("entity", "대상"), ("side", "관점"), ("as_of", "기준일"), ("gaap", "회계기준")]], className="fw-definition"),
                     html.Details([html.Summary('사업 범위·제한사항'), html.P(s['business_scope']), html.P(s['exclusions'])])]), focus], className="fw-two-col"),
            card("월별 실적", [trend(c)], f"{s['currency']} {s['unit']}"),
            html.Details([html.Summary("실사 범위 수정"), html.Div([field("scope_" + key, label, s[key],
                        options=[(v, v) for v in ("매수자", "매도자", "투자·금융기관")] if key == "side" else None,
                        multiline=key in {"business_scope", "exclusions"}) for key, label in scope_fields], className="fw-form-grid"),
                        command("범위 저장", "scope", True)], className="fw-card fw-edit-scope")]


def render_dataroom(state, c, original_docs):
    rows = state["requests"]
    counts = {status: sum(r["status"] == status for r in rows) for status in REQUEST_STATES}
    sources = c["pack"]["documents"]
    source_cards = []
    for doc in sources.values():
        source_cards.append(html.Button([file_icon(doc["filename"]),
                            html.Div([html.Strong(doc["filename"]), html.Small(f"v{doc['version']} · {DATASET_LABELS[doc['kind']]}" )]),
                            pill("합성" if doc["classification"] == "synthetic" else "직접 입력", "blue")],
                            id={"type": "fw-select", "target": "source:" + doc["id"]}, n_clicks=0, className="fw-source-tile"))
    late = sum(bool(r["due"] and r["due"] < date.today().isoformat() and r["status"] != "수령") for r in rows)
    return [metrics([(status, str(count), "자료 요청 건수") for status, count in counts.items()]),
            card("자료 요청 목록 · IRL", [html.Div([select_button("+ 자료 요청 등록", "request:new"), pill(f"기한 경과 {late}건", "orange")], className="fw-actions"),
                 table("requests", rows, [("id", "요청 ID"), ("title", "요청 자료"), ("status", "수령 상태"), ("owner", "담당자"), ("due", "기한"),
                       ("area", "영역"), ("source_id", "수령 자료"), ("version", "버전"), ("followup", "보완 사유")])], "수령은 분석·검토 완료와 별도"),
            card("재무 원천 자료", [html.Div(source_cards, className="fw-source-grid"), download("재무 원천 CSV 묶음", "sources"),
                  html.P("기존 투자 문서와 인용문은 오른쪽 아래 프로젝트 자료에서 모든 화면에서 확인할 수 있습니다.")]),
            html.Details([html.Summary("재무 표 입력 · CSV 붙여넣기"),
                  html.P("템플릿의 열 이름·순서를 유지하세요. 빈칸은 미제공이며 0으로 바뀌지 않습니다. 자료 교체 시 관련 조정과 검토를 다시 확인합니다."),
                  html.Div([field("dataset_kind", "자료 종류", "monthly", options=[(key, label) for key, label in DATASET_LABELS.items()]),
                            field("dataset_filename", "자료 이름", "entered_financials.csv")], className="fw-form-grid"),
                  download("선택한 표의 CSV 템플릿", "template"), field("dataset_text", "CSV 내용", "", multiline=True),
                  command("재무 표 검증·반영", "dataset", True)], className="fw-card")]


def render_reconciliation(state, c):
    revenue = next((r for r in c["reconciliations"] if r["metric"] == "revenue"), {})
    rows = [{**r, "metric_label": LABELS[r["metric"]]} for r in c["reconciliations"]]
    diff = go.Figure(go.Bar(x=[r["metric_label"] for r in rows], y=[r["residual_tb"] for r in rows], marker_color=ORANGE,
                           customdata=["reconciliation:" + r["id"] for r in rows], hovertemplate="%{x}<br>미대사 차이 %{y:,.2f}<extra></extra>"))
    monthly = [{**r, "_index": i, 'id': str(i)} for i, r in enumerate(c["pack"]["data"]["monthly"]) if r["period"] in c["periods"]]
    return [metrics([("관리 매출", fmt(revenue.get("management")), "관리손익 합계"), ("시산표 매출", fmt(revenue.get("trial")), "시산표 동일 기간"),
                     ("재무제표 매출", fmt(revenue.get("statutory")), "온전한 연간 기간만 대사"),
                     ("미대사 계정", str(sum(r["status"] not in {"일치", "조정 대사"} for r in rows)), "계정 수 · 금액 영향과 별도")]),
            card("관리손익 ↔ 시산표 ↔ 원장 ↔ 재무제표", [table("reconciliation", rows, [("metric_label", "계정"), ("management", "관리손익", True),
                 ("trial", "시산표", True), ("gl", "매핑 원장", True), ("statutory", "재무제표", True), ("residual_tb", "관리–TB 잔여차이", True),
                 ("residual_gl", "TB–원장 차이", True), ("residual_fs", "TB–FS 잔여차이", True), ("status", "대사 상태")]),
                 html.P("행을 누르면 원천 자료와 대사 조정·설명을 기록합니다. 차이 설명만으로 미대사 금액을 제거하지 않습니다.")]),
            html.Div([card("대사 차이", [chart("reconciliation", diff, 270)]),
                      card("원장 계정 매핑", [pill(f"미매핑 {len(c['unmapped'])}개" if c['pack']['data']['gl'] else '원장 미제공', "orange" if c["unmapped"] or not c['pack']['data']['gl'] else "teal"),
                          table("mapping", [{**r, "id": r["account_code"], "metric_label": LABELS[r["metric"]]} for r in state["mapping"]],
                              [("account_code", "원장 계정"), ("metric_label", "재무 계정"), ("multiplier", "차대변 부호")], 300),
                          select_button("계정 매핑 추가·수정", "mapping:new")])], className="fw-two-col"),
            html.Details([html.Summary("월별 입력 재무표 · 셀별 출처"), table("monthly", monthly,
                         [("period", "월"), *[(k, LABELS[k], True) for k in ("revenue", "cogs", "opex", "da", "ar", "inventory", "ap", "cash", "borrowings")]])], className="fw-card")]


def render_financial(state, c, area):
    if not c["selected"]:
        return [html.Div([html.H3("재무자료가 아직 연결되지 않았습니다"), html.P("자료실에서 기간·통화·단위를 정한 뒤 재무 표를 입력하세요."), route("자료실로 이동 →", "dataroom")], className="fw-card fw-empty")]
    if area == "historical":
        groups = defaultdict(lambda: [D(0), D(0)])
        for r in c["segments"]:
            if r.get("revenue") is not None and r.get("cogs") is not None:
                groups[r["segment"]][0] += decimal(r["revenue"])
                groups[r["segment"]][1] += decimal(r["cogs"])
        fig = go.Figure(go.Bar(y=list(groups), x=[v[0] for v in groups.values()], orientation="h", marker_color=PURPLE,
                              hovertemplate="%{y}<br>매출 %{x:,.1f}<extra></extra>"))
        return [metrics([("매출", fmt(c["revenue"]), "선택 기간"), ("전년 동기간 대비", fmt(c["revenue_growth"], True), "동일 월이 모두 있을 때 계산"),
                         ("보고 EBITDA", fmt(c["reported_ebitda"]), "매출 − 원가 − 영업비용"), ("EBITDA 마진", fmt(c["ebitda_margin"], True), "보고 EBITDA / 매출")]),
                card("월별 매출·이익률", [trend(c)]),
                html.Div([card("사업 부문별 매출", [chart("segments", fig, 280) if c['segments'] else html.Div('사업 부문별 매출 자료 미제공', className='fw-empty'), html.P(f"부문 합계와 관리매출 차이: {fmt(c['segment_residual'])}")]),
                          card("동기간 비교", [table("historical", [dict(id="rev", name="매출", current=c["revenue"], previous=c["prior_revenue"]),
                                dict(id="ebitda", name="보고 EBITDA", current=c["reported_ebitda"], previous=c["prior_ebitda"])], [("name", "항목"), ("previous", "전년 동기간", True), ("current", "현재 기간", True)])])], className="fw-two-col")]
    if area == "qoe":
        return [metrics([("보고 EBITDA", fmt(c["reported_ebitda"]), "원천 관리손익"), ("분석 반영 조정", fmt(c["qoe_sum"]), "+ 가산 / − 차감"),
                         ("조정 EBITDA", fmt(c["adjusted_ebitda"]), "검토 확정·경영진 합의와 별도"), ("조정 항목", str(len(c["qoe"])), "선택 기간에 반영된 항목")]),
                card("QoE · EBITDA bridge", [qoe_chart(c), html.P("막대를 누르면 조정 근거와 원장 행·열을 확인합니다. 분석 반영은 경영진 합의나 독립 검증을 뜻하지 않습니다.")]),
                card("정상화 조정 조서", [select_button("+ QoE 조정 등록", "adjustment:new"), adjustment_table(state, "QoE")])]
    if area == "nwc":
        fig = go.Figure()
        monthly = display_months(c)
        dates = [r['period'] for r in monthly]
        for key, color, sign in [("ar", PURPLE, 1), ("inventory", BLUE, 1), ("other_assets", TEAL, 1), ("ap", ORANGE, -1), ("other_liabilities", "#aab5c7", -1)]:
            packrows = c['pack']['data']['monthly']
            refs = [source_key(c['pack'], 'monthly', packrows.index(r) if r in packrows else None, key) for r in monthly]
            fig.add_trace(go.Bar(name=LABELS[key], x=dates, y=[None if r.get(key) is None else float(decimal(r[key])) * sign for r in monthly], marker_color=color, customdata=refs))
        fig.add_trace(go.Scatter(name="순운전자본", x=dates, y=[nwc(r) for r in monthly], line_color=NAVY, mode="lines+markers", connectgaps=False))
        fig.update_layout(barmode="relative")
        ticks = list(dict.fromkeys(dates[::3] + [dates[-1]]))
        fig.update_xaxes(type='category', tickvals=ticks, ticktext=[p.replace('-', '.') for p in ticks])
        buckets = list(dict.fromkeys(r["bucket"] for r in c["aging"]))
        heat = go.Figure(go.Heatmap(x=buckets, y=[LABELS[k] for k in ("ar", "inventory", "ap")],
                     z=[[plot_number(next((r["amount"] for r in c["aging"] if r["account"] == account and r["bucket"] == bucket), None)) for bucket in buckets] for account in ("ar", "inventory", "ap")],
                     colorscale=[[0, "#f0f4ff"], [1, BLUE]], texttemplate="%{z:,.1f}", hovertemplate="%{y} · %{x}<br>%{z:,.2f}<extra></extra>", showscale=False))
        return [metrics([("기말 보고 NWC", fmt(c["reported_nwc"]), "영업자산 − 영업부채"), ("기말 조정 NWC", fmt(c["adjusted_nwc"]), "기말 대상 조정만 반영"),
                         ("12개월 평균", fmt(c["pegs"]["12"]), "12개 연속 월 필요"), ("Peg 후보", fmt(c["peg"]), "거래 영향에서 방식 선택")]),
                card("월별 운전자본 구성", [chart("nwc", fig, 355) if any(r.get(k) is not None for r in monthly for k in ('ar','inventory','other_assets','ap','other_liabilities')) else html.Div('월별 운전자본 자료 미제공', className='fw-empty'), html.P("NWC = 매출채권 + 재고 + 기타 영업자산 − 매입채무 − 기타 영업부채. 현금·차입·리스는 제외합니다.")]),
                html.Div([card("기말 연령 분석", [chart("aging", heat, 260) if c['aging'] else html.Div('기말 연령 분석 자료 미제공', className='fw-empty'), html.P("연령 합계 대사: " + " · ".join(f"{LABELS[r['account']]} {fmt(r['residual'])}" for r in c["aging_checks"]))]),
                          card("정상 수준·peg 비교", [table("pegs", [dict(id=k, method=k + "개월 평균", amount=v) for k, v in c["pegs"].items() if k != "manual"], [("method", "방식"), ("amount", "금액", True)]),
                              html.P("평균은 후보값입니다. 계절성·성장·제외 계정·합의 조건을 검토해 선택합니다. 기말 충당금 조정을 과거 월에 자동 소급하지 않습니다.")])], className="fw-two-col"),
                card("NWC 조정사항", [adjustment_table(state, "NWC")])]
    if area == "debt":
        row = c["current"]
        adjustments = c["debt_adjustments"]
        wf = waterfall("debt", ["차입금", "리스부채", "사용가능 현금"] + [a["name"] for a in adjustments] + ["순차입금"],
                        [decimal(row.get("borrowings")), decimal(row.get("lease_liability")), None if row.get("cash") is None else -decimal(row["cash"])] + [decimal(a["amount"]) for a in adjustments] + [D(0)],
                        refs=["balance:borrowings", "balance:lease_liability", "balance:cash"] + ["adjustment:" + a["id"] for a in adjustments] + ["metric:net_debt"])
        return [metrics([("기준 순차입금", fmt(c["base_net_debt"]), "차입 + 리스 − 사용가능 현금"),
                         ("분석 반영 순차입금", fmt(c["net_debt"]), "debt-like 조정 포함"), ("제한성 현금", fmt(row.get("restricted_cash")), "현금 차감에서 제외"),
                         ("기준 월", row["period"], "잔액·계약 정의 확인 필요")]),
                card("순차입금 bridge", [wf, html.P("리스·미지급 항목의 포함 범위는 거래 정의에 따라 달라집니다. 기본 분석 정의는 리스 포함, 제한성 현금 제외입니다.")]),
                card("Debt-like 조정사항", [select_button("+ 부채성 항목 등록", "adjustment:new"), adjustment_table(state, "Net debt")])]
    if area == "cash":
        v = c["cash"]
        neg = lambda x: None if x is None else -x
        movements = [c["reported_ebitda"], neg(v["interest_paid"]), neg(v["tax_paid"]), neg(c["delta_nwc"]), v["noncash"], v["other_operating"], D(0), neg(v["maintenance_capex"]), neg(v["growth_capex"]), D(0)]
        wf = waterfall("cash", ["보고 EBITDA", "현금 이자", "현금 세금", "NWC 증가", "비현금 가산", "기타 영업", "계산 OCF", "유지 CAPEX", "성장 CAPEX", "계산 FCF"], movements, totals=[6])
        return [metrics([("보고 영업현금흐름", fmt(v["operating_cash"]), "원천 현금흐름표"), ("계산 OCF와 차이", fmt(c["cash_residual"]), "0이어야 대사 일치"),
                         ("FCF", fmt(c["fcf"]), "보고 OCF − 유지·성장 CAPEX"), ("현금 전환율", fmt(c["cash_conversion"], True), "보고 OCF / 보고 EBITDA")]),
                card("EBITDA → 현금흐름 → FCF", [wf, html.P(f"NWC 기초 {fmt(c['opening_nwc'])} → 기말 {fmt(c['reported_nwc'])}. 기초 잔액이 없으면 현금흐름 대사를 계산하지 않습니다.")]),
                card("현금흐름 대사", [table("cash", [dict(id=k, name=LABELS[k], amount=v[k]) for k in v], [("name", "현금흐름 항목"), ("amount", "기간 합계", True)])])]
    if not c['budgets']:
        return [card('경영계획 미제공', [html.Div('전망·계약 커버리지·공급능력 가정 자료가 없습니다.', className='fw-empty'), route('자료 요청으로 이동 →', 'dataroom')])]
    # Forecast is a management plan, distinct from observed financials.
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[r["period"] for r in c["budgets"]], y=[plot_number(r["revenue"]) for r in c["budgets"]], name="경영계획 매출", marker_color=PURPLE))
    fig.add_trace(go.Scatter(x=[r["period"] for r in c["budgets"]], y=[plot_number(r["contracted_revenue"]) for r in c["budgets"]], name="계약 기반 매출", mode="lines+markers", line_color=TEAL))
    fig.add_trace(go.Scatter(x=[r["period"] for r in c["budgets"]], y=[plot_number(r["capacity_revenue"]) for r in c["budgets"]], name="매출 환산 공급능력", mode="lines", line=dict(color=NAVY, dash="dash")))
    fig.update_xaxes(type='category', tickvals=[r['period'] for r in c['budgets'][::3]], ticktext=[r['period'].replace('-', '.') for r in c['budgets'][::3]])
    return [metrics([("경영계획 매출", fmt(c["budget_revenue"]), "계획값 · 실적이 아님"), ("현재 실적 대비", fmt(c["budget_growth"], True), "기간 길이·계절성 확인"),
                     ("계약 커버리지", fmt(c["contracted_coverage"], True), "계약 기반 / 계획 매출"), ("계획 EBITDA", fmt(c["budget_ebitda"]), "경영진 가정")]),
            card("전망 가정 점검", [chart("forecast", fig), html.P("계약·공급능력 값도 원천 가정입니다. 자동 검증·달성 확률이 아니며 생산능력의 금액 환산 기준을 확인해야 합니다.")]),
            card("월별 경영계획", [table("budget", c["budgets"], [("period", "계획 월"), ("revenue", "계획 매출", True), ("ebitda", "계획 EBITDA", True),
                         ("contracted_revenue", "계약 기반 매출", True), ("capacity_revenue", "매출 환산 공급능력", True), ("assumption", "가정·한계")])])]


def render_issues(state, c):
    return [metrics([(status, str(sum(i["status"] == status for i in state["issues"])), "쟁점 건수") for status in ("추가 확인", "경영진 답변", "판단 작성", "해결")]),
            card("발견사항 → 요청 → 답변 → 실사 판단", [html.Div([select_button("+ 쟁점 등록", "issue:new"), route("질문 검토 도구 열기 →", "studio")], className="fw-actions"),
                 table("issues", state["issues"], [("id", "쟁점 ID"), ("title", "발견사항"), ("area", "영역"), ("impact", "금액 영향", True),
                   ("priority", "중요도"), ("status", "상태"), ("request_id", "추가 요청"), ("adjustment_id", "조정 ID"), ("management", "경영진 답변"), ("conclusion", "실사팀 판단")]),
                 html.P("금액이 없는 쟁점은 미정량입니다. 서로 다른 쟁점의 잠재 영향을 합산하지 않습니다. 기존 질문·증빙 도구는 상단에서도 접근할 수 있습니다.")])]


def render_adjustments(state, c):
    transaction = state["transaction"]
    price = waterfall("equity", ["기업가치 EV", "순차입금 차감", "NWC 가격 조정", "지분가치 Equity"],
                      [c["ev"], None if c["net_debt"] is None else -c["net_debt"], c["nwc_price_adjustment"], D(0)])
    return [metrics([("조정 EBITDA", fmt(c["adjusted_ebitda"]), "가격배수 자동 적용 없음"), ("기말 조정 NWC", fmt(c["adjusted_nwc"]), "peg 비교 대상"),
                     ("EV 입력 시나리오", fmt(c["ev"]), "미입력 시 지분가치 계산 안 함"), ("Equity 입력 시나리오", fmt(c["equity"]), "EV − 순차입금 + NWC 가격 조정")]),
            card("EV → Equity bridge", [price, html.P("Completion accounts: 기말 조정 NWC − peg. Locked box: 여기서는 NWC 사후 정산 0으로 표시하며, 누수·기준일 가격 협의는 별도로 검토합니다.")]),
            card("거래 가정·가격 조정 정의", [html.Div([field("transaction_ev", "기업가치 EV · 입력 시나리오", transaction["ev"], numeric=True),
                 field("transaction_peg_method", "Peg 후보 선택", transaction["peg_method"], options=[("3", "3개월 평균"), ("6", "6개월 평균"), ("12", "12개월 평균"), ("manual", "수동 합의 후보")]),
                 field("transaction_peg_manual", "수동 peg", transaction["peg_manual"], numeric=True),
                 field("transaction_mechanism", "가격 조정 방식", transaction["mechanism"], options=[(v, v) for v in ("Completion accounts", "Locked box")])], className="fw-form-grid"),
                 field("transaction_note", "가격·계약·추가 실사 전달사항", transaction["note"], multiline=True), command("거래 가정 저장", "transaction", True)]),
            card("전체 조정 등록부", [select_button("+ 조정 후보 등록", "adjustment:new"), adjustment_table(state),
                 html.P("같은 경제적 항목 키·원천 셀을 NWC와 순차입금에 중복 반영하지 않습니다. 서로 다른 키로 입력한 관련 항목은 실사팀이 추가로 확인해야 합니다.")])]


def render_quality(state, c):
    review = state["review"]
    blockers = review_blockers(state)
    return [card("현재 조서의 검토 조건", [html.Div([pill(review_status(state), "blue"), pill(f"버전 {state['revision']}")], className="fw-actions"),
            html.Ul([html.Li(b) for b in blockers]) if blockers else html.P("현재 등록된 차단 조건이 없습니다."),
            html.P("자료 수령·작성 제출·검토 기록 확정·경영진 합의는 서로 다릅니다. 이름은 직접 기재하는 기록으로 사용자 인증·권한을 대신하지 않습니다.")]),
            html.Div([card("작성 제출", [field("prepare_preparer", "작성자", review["preparer"]), command("현재 버전 작성 제출", "prepare", True)]),
                      card("검토 기록", [field("approve_reviewer", "검토자 · 작성자와 다르게 입력", review["reviewer"]), command("조건 확인 후 검토 기록 확정", "approve", True),
                           html.P("숫자·자료·판단이 변경되면 작성 제출과 검토 확정이 해제됩니다.")])], className="fw-two-col"),
            card("검토 의견", [table("comments", review["comments"], [("id", "의견 ID"), ("author", "작성자"), ("workpaper", "조서"), ("note", "검토 의견"), ("status", "상태"), ("response", "해소 근거")]),
                 html.Div([field("comment_author", "의견 작성자", ""), field("comment_workpaper", "연결 조서 / 쟁점 ID", "")], className="fw-form-grid"),
                 field("comment_note", "검토 의견", "", multiline=True), command("검토 의견 등록", "comment"),
                 html.Div([field("resolve_comment_id", "해소할 의견", "", options=[("", "선택")] + [(r["id"], r["id"] + " · " + r["note"][:40]) for r in review["comments"]]),
                           field("resolve_comment_response", "해소 근거", "", multiline=True)], className="fw-form-grid"), command("의견 해소 기록", "resolve_comment")]),
            html.Details([html.Summary(f"변경 이력 · {len(state['history'])}건"), table("history", [{**r, "id": str(r["revision"])} for r in reversed(state["history"])],
                         [("revision", "버전"), ("timestamp", "기록 시각 UTC"), ("action", "변경"), ("detail", "내용"), ('changes', '변경 전·후 입력'), ("before", "이전 내용 해시"), ("after", "현재 내용 해시")])], className="fw-card")]


def render_deliverables(state, c):
    return [card("같은 조서에서 만드는 산출물", [html.P(f"{review_status(state)} · 조서 v{state['revision']} · 선택 기간 {c['period'] or '미제공'}"),
                 html.Div([download("Excel 데이터북", "xlsx"), download("FDD 검토 보고서 · Markdown", "report"), download("재무 원천 CSV 묶음", "sources")], className="fw-actions"),
                 html.P("데이터북에는 월별 수치, 대사, 조정, NWC, 현금흐름, IRL, 쟁점, 검토 의견, 원천 해시·버전이 함께 저장됩니다. 화면과 같은 계산 결과를 사용합니다."),
                 html.Div([pill("확정 전에는 초안"), pill("합성 / 직접 입력", "orange")], className="fw-actions")]),
            card("보고서 수치 확인", [table("report", [dict(id=k, name=label, amount=c[k]) for k, label in
                         [("revenue", "매출"), ("reported_ebitda", "보고 EBITDA"), ("adjusted_ebitda", "조정 EBITDA"),
                          ("adjusted_nwc", "기말 조정 NWC"), ("net_debt", "순차입금"), ("fcf", "FCF"), ("equity", "Equity 입력 시나리오")]], [("name", "수치"), ("amount", "금액", True)]),
                         html.P("범위 제한: " + state["scope"]["exclusions"])]),
            card("기존 증빙·질문 산출물", [html.Div([route("질문 검토·초안 CSV →", "studio"), route("증빙 기반 예비 심사 문서 →", "export")], className="fw-actions"),
                         html.P("공식 질문 순위·원문 인용과 재무 조정 조서는 서로 다른 산출물입니다.")])]


def render_page(state, page, c, area="historical", role="Big 4", original_docs=()):
    if page == "deal":
        return render_deal(state, c, role)
    if page == "dataroom":
        return render_dataroom(state, c, original_docs)
    if page == "reconciliation":
        return render_reconciliation(state, c)
    if page == "financial":
        result = render_financial(state, c, area)
        if c['selected'] and not c['continuous']:
            result.insert(0, html.Div('기간에 빠진 월이 있거나 LTM 12개월을 충족하지 않습니다. 합계를 제한하고 시계열의 누락 월은 공백으로 표시합니다.', className='fw-notice fw-notice-error'))
        return result
    if page == "issues":
        return render_issues(state, c)
    if page == "adjustments":
        return render_adjustments(state, c)
    if page == "quality":
        return render_quality(state, c)
    return render_deliverables(state, c)


def valid_selection(state, c, selection):
    if not isinstance(selection, str) or len(selection) > 250:
        return False
    parts = selection.split(':')
    if len(parts) < 2:
        return False
    kind, identifier = parts[:2]
    if kind == 'cell' and len(parts) == 4:
        try:
            return resolve_ref(c['pack'], dict(document=identifier, row=int(parts[2]), column=parts[3])) is not None
        except ValueError:
            return False
    if kind == 'source':
        return identifier in c['pack']['documents']
    if kind in {'request', 'adjustment', 'issue'}:
        return identifier == 'new' or identifier in {r['id'] for r in state[{'request': 'requests', 'adjustment': 'adjustments', 'issue': 'issues'}[kind]]}
    if kind == 'mapping':
        return identifier == 'new' or identifier in {r['account_code'] for r in state['mapping']}
    if kind == 'reconciliation':
        return identifier in {r['id'] for r in c['reconciliations']}
    if kind == 'balance':
        return identifier in LABELS and c['current'] is not None
    if kind == 'metric':
        return identifier in {'revenue', 'ebitda', 'adjusted_ebitda', 'nwc', 'net_debt', 'cash', 'equity'}
    return False


def inspection_options(state, c, page, area):
    pairs = []
    if page == 'dataroom':
        pairs = [('request:' + r['id'], r['id'] + ' · ' + r['title']) for r in state['requests']]
        pairs += [('source:' + d['id'], d['filename']) for d in c['pack']['documents'].values()]
    elif page == 'reconciliation':
        pairs = [('reconciliation:' + r['id'], r['year'] + ' · ' + LABELS[r['metric']]) for r in c['reconciliations']]
    elif page == 'issues':
        pairs = [('issue:' + r['id'], r['id'] + ' · ' + r['title']) for r in state['issues']]
    elif page == 'adjustments' or (page == 'financial' and area in {'qoe', 'debt'}):
        target_area = {'qoe': 'QoE', 'debt': 'Net debt'}.get(area) if page == 'financial' else None
        pairs = [('adjustment:' + r['id'], r['id'] + ' · ' + r['name']) for r in state['adjustments'] if not target_area or r['area'] == target_area]
    elif page == 'financial' and area == 'nwc':
        pairs = [('balance:' + k, LABELS[k]) for k in ('ar', 'inventory', 'other_assets', 'ap', 'other_liabilities')]
    if not pairs:
        pairs = [('metric:ebitda', '보고 EBITDA'), ('metric:revenue', '매출'), ('metric:net_debt', '순차입금'), ('metric:equity', 'Equity 입력 시나리오')]
    return [{'value': key, 'label': label} for key, label in pairs]


def render_source(c, ref):
    resolved = resolve_ref(c['pack'], ref)
    if not resolved:
        return html.Div('원천 버전이 변경됐거나 연결되지 않았습니다. 새 자료로 근거를 다시 지정하세요.', className='fw-empty')
    return html.Div([
        html.H3('원천·계산 추적'),
        html.Div([file_icon(resolved['filename']), html.Strong(resolved['filename'])], className='fw-actions'),
        html.P(f"v{resolved['version']} · {resolved['row']}행 · {resolved['column']} 열"),
        html.Blockquote([html.Strong(str(resolved['value']) if resolved['value'] is not None else '미제공'),
                         html.Small('원천 셀 값 · ' + ('합성 자료' if resolved['classification'] == 'synthetic' else '사용자 직접 입력'))], className='fw-source-value'),
        html.Dl([html.Div([html.Dt(LABELS.get(key, {'period': '기간', 'id': '원장 ID', 'account': '원장 계정', 'description': '원장 설명'}.get(key, key))), html.Dd(str(value) if value is not None else '미제공')]) for key, value in resolved['record'].items()], className='fw-definition fw-source-record'),
        html.Details([html.Summary('원천 무결성 · SHA256'), html.P(resolved['sha256'], className='fw-hash')])
    ], className='fw-source-detail')


def ref_fields(c, ref):
    ref = ref or {}
    return [field('edit_source_id', '원천 재무 파일', ref.get('document', ''), options=[('', '선택')] + [(d['id'], d['filename'] + f" · v{d['version']}") for d in c['pack']['documents'].values()]),
            html.Div([field('edit_source_row', '원천 행 번호', ref.get('row'), numeric=True),
                      field('edit_source_column', '원천 열 이름', ref.get('column', 'amount'))], className='fw-form-grid')]


def render_detail(state, c, selection, original_docs=(), area='historical'):
    if not valid_selection(state, c, selection):
        return html.P('표의 행이나 차트 막대를 선택하면 근거와 판단을 확인할 수 있습니다.')
    kind, identifier, *tail = selection.split(':')
    if kind == 'cell':
        return render_source(c, dict(document=identifier, row=int(tail[0]), column=tail[1]))
    if kind == 'source':
        doc = c['pack']['documents'][identifier]
        return [html.H3(doc['filename']), pill('합성 재무자료' if doc['classification'] == 'synthetic' else '사용자 직접 입력', 'blue'),
                html.P(doc['description']), html.P(f"현재 버전 {doc['version']} · {len(c['pack']['data'][doc['kind']])}행"),
                html.P(doc['sha256'], className='fw-hash'), html.P('원천 CSV는 자료실·산출물 화면에서 내려받을 수 있습니다.'),
                render_source(c, dict(document=identifier, row=2, column=doc['columns'][1]))]
    if kind == 'request':
        row = next((r for r in state['requests'] if r['id'] == identifier), {})
        docs = [(d['id'], d['filename']) for d in c['pack']['documents'].values()] + [(d['id'], d.get('filename', d['id'])) for d in original_docs]
        return [html.H3(row.get('id', '새 자료 요청')), field('edit_id', '요청 ID', row.get('id', ''), readonly=True),
                field('edit_title', '요청 자료', row.get('title', ''), multiline=True),
                field('edit_area', '업무 영역', row.get('area', '과거 실적'), options=[(v, v) for v in AREAS]),
                html.Div([field('edit_owner', '담당자', row.get('owner', '')), field('edit_due', '기한 · YYYY-MM-DD', row.get('due', ''))], className='fw-form-grid'),
                field('edit_status', '수령 상태', row.get('status', '미요청'), options=[(v, v) for v in REQUEST_STATES]),
                field('edit_source_id', '수령 자료·버전 연결', row.get('source_id', ''), options=[('', '미제공')] + docs),
                field('edit_workpaper', '연결 조서', row.get('workpaper', '')),
                field('edit_followup', '보완 요청 사유', row.get('followup', ''), multiline=True), command('자료 요청 저장', 'request', True)]
    if kind == 'adjustment':
        default_area = {'nwc': 'NWC', 'debt': 'Net debt'}.get(area, 'QoE')
        row = next((r for r in state['adjustments'] if r['id'] == identifier), {})
        source = resolve_ref(c['pack'], row.get('source'))
        mismatch = bool(source and source['value'] is not None and abs(decimal(source['value'])) != abs(decimal(row['amount'])))
        return [html.H3(row.get('id', '새 조정 후보')), field('edit_id', '조정 ID', row.get('id', ''), readonly=True),
                html.P('입력 조정액이 원천 셀 금액과 다릅니다. 부분 반영·계산식·추가 근거를 실사팀 판단에 기록하세요.', className='fw-notice fw-notice-error') if mismatch else None,
                field('edit_name', '조정 설명', row.get('name', '')),
                field('edit_area', '분석 영역', row.get('area', default_area), options=[(v, v) for v in ('QoE', 'NWC', 'Net debt')]),
                html.Div([field('edit_amount', '증감 금액 · + / −', row.get('amount'), numeric=True), field('edit_period', '해당 월 · YYYY-MM', row.get('period', c['current']['period'] if c['current'] else ''))], className='fw-form-grid'),
                field('edit_economic_key', '경제적 항목 키 · 중복 확인용', row.get('economic_key', '')),
                field('edit_management', '경영진 설명', row.get('management', ''), multiline=True),
                field('edit_judgment', '실사팀 판단·산정 근거', row.get('judgment', ''), multiline=True),
                html.Div([field('edit_recurring', '반복성', row.get('recurring', '추가 확인'), options=[(v, v) for v in ('반복', '비반복', '추가 확인')]),
                          field('edit_cash', '현금성', row.get('cash', '추가 확인'), options=[(v, v) for v in ('현금', '비현금', '추가 확인')])], className='fw-form-grid'),
                field('edit_decision', '분석 반영 상태', row.get('decision', '검토 후보'), options=[(v, v) for v in ADJUSTMENT_DECISIONS]),
                field('edit_agreed', '경영진 합의 상태', row.get('agreed', '미합의'), options=[(v, v) for v in ('미합의', '경영진 동의', '경영진 이견')]),
                *ref_fields(c, row.get('source')), command('조정 조서 저장', 'adjustment', True),
                render_source(c, row.get('source')) if row else None]
    if kind == 'issue':
        row = next((r for r in state['issues'] if r['id'] == identifier), {})
        return [html.H3(row.get('id', '새 발견사항')), field('edit_id', '쟁점 ID', row.get('id', ''), readonly=True),
                field('edit_title', '발견사항', row.get('title', ''), multiline=True),
                field('edit_area', '영역', row.get('area', '과거 실적'), options=[(v, v) for v in AREAS]),
                field('edit_impact', '금액 영향 · 미정량이면 빈칸', row.get('impact'), numeric=True),
                field('edit_priority', '중요도', row.get('priority', '보통'), options=[(v, v) for v in ('높음', '보통', '낮음')]),
                field('edit_status', '쟁점 상태', row.get('status', '추가 확인'), options=[(v, v) for v in ISSUE_STATES]),
                field('edit_request_id', '연결 자료 요청', row.get('request_id', ''), options=[('', '연결 없음')] + [(r['id'], r['id'] + ' · ' + r['title']) for r in state['requests']]),
                field('edit_adjustment_id', '연결 조정사항', row.get('adjustment_id', ''), options=[('', '미정량 / 연결 없음')] + [(r['id'], r['id'] + ' · ' + r['name']) for r in state['adjustments']]),
                field('edit_management', '경영진 답변', row.get('management', ''), multiline=True),
                field('edit_conclusion', '실사팀 결론·후속 절차', row.get('conclusion', ''), multiline=True), command('쟁점·Q&A 저장', 'issue', True)]
    if kind == 'reconciliation':
        row = next(r for r in c['reconciliations'] if r['id'] == identifier)
        saved = state['reconciliations'].get(identifier, {})
        source_docs = [doc for doc in c['pack']['documents'].values() if doc['kind'] in {'monthly', 'trial', 'gl', 'statutory'}]
        return [html.H3(row['year'] + ' · ' + LABELS[row['metric']]), pill(row['status'], 'orange' if row['status'] == '미대사' else 'blue'),
                html.Dl([html.Div([html.Dt(label), html.Dd(fmt(row[key]))]) for key, label in [('management', '관리손익'), ('trial', '시산표'), ('gl', '매핑 원장'), ('statutory', '재무제표'), ('difference_tb', '관리–TB 원차이'), ('difference_fs', 'TB–FS 원차이')]], className='fw-definition'),
                html.P('원차이에서 근거가 있는 대사 조정을 차감한 잔여 차이가 0이어야 합니다. 원천 금액은 그대로 보존합니다.'),
                field('edit_id', '대사 ID', identifier, readonly=True),
                field('edit_adjustment_tb', '관리–TB 대사 조정', saved.get('adjustment_tb', '0'), numeric=True),
                field('edit_adjustment_fs', 'TB–FS 대사 조정', saved.get('adjustment_fs', '0'), numeric=True),
                field('edit_explanation', '대사 조정 설명·차이 원인', saved.get('explanation', ''), multiline=True),
                *ref_fields(c, saved.get('source')), command('대사 설명·조정 저장', 'reconciliation', True),
                html.H3('비교 원천'), *[html.Div([html.Strong(doc['filename']), html.P(f"v{doc['version']} · {doc['sha256']}", className='fw-hash')]) for doc in source_docs]]
    if kind == 'mapping':
        row = next((r for r in state['mapping'] if r['account_code'] == identifier), {})
        codes = sorted({r['account_code'] for r in c['pack']['data']['gl']})
        return [html.H3('원장 계정 매핑'), field('edit_account_code', '원장 계정 코드', row.get('account_code', codes[0] if codes else ''), options=[(k, k) for k in codes]),
                field('edit_metric', '매핑 재무 계정', row.get('metric', 'revenue'), options=[(k, LABELS[k]) for k in ('revenue', 'cogs', 'opex', 'da')]),
                field('edit_multiplier', '차대변 부호 전환', row.get('multiplier', '1'), options=[('1', '× 1 · 차변 양수'), ('-1', '× −1 · 대변 매출 전환')]),
                html.P('원장 잔액 × 부호를 재무 계정별로 합산합니다. 매핑 변경 시 기존 대사 조정을 다시 검토합니다.'), command('계정 매핑 저장', 'mapping', True)]
    if kind == 'balance':
        rows = c['pack']['data']['monthly']
        return render_source(c, source_ref(c['pack'], 'monthly', rows.index(c['current']), identifier))
    definitions = {
        'revenue': ('매출', c['revenue'], '선택 기간의 관리손익 매출 합계. 기간이 끊기거나 값이 비어 있으면 계산하지 않습니다.'),
        'ebitda': ('보고 EBITDA', c['reported_ebitda'], '매출 − 매출원가 − 영업비용(D&A 제외). 감가상각비는 별도 항목입니다.'),
        'adjusted_ebitda': ('조정 EBITDA', c['adjusted_ebitda'], '보고 EBITDA + 선택 기간에 분석 반영한 QoE 조정. 검토 확정·경영진 합의는 별도입니다.'),
        'nwc': ('기말 조정 NWC', c['adjusted_nwc'], '채권 + 재고 + 기타 영업자산 − 채무 − 기타 영업부채 + 기말 NWC 조정.'),
        'net_debt': ('순차입금', c['net_debt'], '차입금 + 리스부채 − 사용가능 현금 + 기말 debt-like 조정. 제한성 현금은 차감에서 제외.'),
              'cash': ('보고 영업현금흐름', c['cash']['operating_cash'], '선택 기간 원천 operating_cash 합계. EBITDA bridge와 별도로 대사합니다.'),
        'equity': ('Equity 입력 시나리오', c['equity'], 'EV 입력 − 순차입금 + NWC 가격 조정. EV 미입력 시 산출하지 않습니다. Locked box 선택 시 NWC 사후 정산은 0입니다.')}
    title, value, description = definitions[identifier]
    return [html.H3(title), html.Div(fmt(value), className='fw-detail-number'), html.P(description),
            html.P(state['scope']['currency'] + ' · ' + state['scope']['unit']),
            html.P('분석 기간: ' + (' → '.join([c['periods'][0], c['periods'][-1]]) if c['periods'] else '미제공')),
            pill(review_status(state), 'blue'),
            html.H3('현재 연결된 원천'), *[html.Details([html.Summary(d['filename'] + f" · v{d['version']}"), html.P(d['sha256'], className='fw-hash')]) for d in c['pack']['documents'].values() if d['kind'] in {'monthly', 'ledger'}],
            html.P('자료 수령이나 원천 셀 연결만으로 재무 수치의 외부 검증을 의미하지 않습니다.')]

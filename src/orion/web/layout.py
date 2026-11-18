"""Accessible document-centered Dash layout; no authoritative business logic."""
from __future__ import annotations

from dash import dcc, html
import dash_ag_grid as dag
import plotly.graph_objects as go
from .i18n import GRID_LOCALE, LABELS, text
from .visuals import page_visuals
from . import studio, fdd
from . import fdd_workspace as finance

NAVIGATION = finance.NAVIGATION
SUPPORT_TOOLS = [("studio", "질문 검토 작업 공간"), ("evidence", "원문·증빙 탐색"), ("thesis", "투자 가설"),
                 ("questions", "질문 중요도 평가"), ("review", "새 증거 반영"), ("analytics", "증빙 요청 분석 · Bayesian/EIG"),
                 ("export", "예비 심사 문서"), ("overview", "기존 증빙 개요"), ("fdd", "기존 수동 FDD 조서")]
CASE_OPTIONS = [
    {"label": "Northstar Analytics", "value": "nb"},
    {"label": "제조업 사례", "value": "mf"},
    {"label": "Lumen · 상충 증빙 검토", "value": "lm"},
]
FORMAT_OPTIONS = [
    {"label": "실사 요청 목록 · Excel", "value": "dd_xlsx"},
    {"label": "실사 요청 목록 · CSV", "value": "dd_csv"},
    {"label": "증빙 목록 · CSV", "value": "evidence_csv"},
    {"label": "예비 심사 메모 · Word", "value": "memo_docx"},
    {"label": "예비 심사 메모 · Markdown", "value": "memo_md"},
]


def human(value):
    if value is None:
        return "확인 불가"
    if isinstance(value, (list, tuple)):
        return "; ".join(human(x) for x in value) or "없음"
    if isinstance(value, dict):
        return "; ".join(f"{human(k)}: {human(v)}" for k, v in value.items())
    return ", ".join(text(part) for part in str(value).split(", "))


def metadata_value(key, value):
    """Translate typed status fields, preserving identifiers and free source text."""
    if value is None:
        return "확인 불가"
    if isinstance(value, dict):
        return "; ".join(f"{text(k)}: {metadata_value(k, v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "; ".join(metadata_value(key, item) for item in value) or "없음"
    if key in {"kind", "format", "asset_status", "parse_status", "source_origin", "locator_status",
               "extraction_method", "review_status", "claim_kind", "support_status", "truth_status",
               "stance", "provenance", "verification_level", "lifecycle", "relation_type", "basis",
               "financial_driver", "workflow_status", "actor_role", "target_type", "action", "event_type"}:
        return text(value)
    return str(value)


def badge(value, prefix=""):
    text = human(value)
    status = str(value or "unknown").replace("_", "-")
    return html.Span(f"{prefix}{text}", className=f"badge badge-{status}")


def empty(message):
    return html.Div(message, className="empty-state")


def grid(identifier, rows, columns, *, identity="id", height=440):
    return dag.AgGrid(
        id=identifier, rowData=rows, columnDefs=columns,
        getRowId=f"params.data.{identity}", enableEnterpriseModules=False,
        defaultColDef={"sortable": True, "filter": True, "resizable": True,
                       "minWidth": 110, "wrapHeaderText": True, "autoHeaderHeight": True},
        dashGridOptions={"rowSelection": {"mode": "singleRow", "enableClickSelection": True,
                                          "checkboxes": False},
                         "animateRows": False, "rowHeight": 52, "headerHeight": 46,
                         "tooltipShowDelay": 250, "ensureDomOrder": True,
                         "localeText": GRID_LOCALE,
                         "context": {"displayLabels": LABELS},
                         "suppressCellFocus": False},
        style={"height": f"{min(height, max(150, 52 * len(rows) + 70))}px", "width": "100%"}, className="ag-theme-alpine orion-grid",
    )


def column(field, name, width=None, flex=None, **extra):
    result = {"field": field, "headerName": name, "tooltipField": field, **extra}
    if field in {"issue", "stance", "provenance", "verification_level", "review_status", "lifecycle",
                 "support_status", "truth_status", "claim_kind", "evidence_status", "financial_drivers",
                 "financial_driver", "workflow_status", "before_status", "after_status", "reason_codes"}:
        # Format cells and tooltips without rewriting raw row data or filter values.
        formatted = "orionKoreanValue(params)"
        result["valueFormatter"] = {"function": formatted}
        result["tooltipValueGetter"] = {"function": formatted}
    if field == "source_refs":
        result["valueFormatter"] = {"function": "orionSourceReferences(params)"}
        result["tooltipValueGetter"] = {"function": "orionSourceReferences(params)"}
    if "tooltipValueGetter" in result:
        # AG Grid gives tooltipField precedence over tooltipValueGetter.
        result.pop("tooltipField", None)
        result["useValueFormatterForExport"] = False
    if width is not None:
        result["width"] = width
    if flex is not None:
        result["flex"] = flex
        if width is not None:
            result.setdefault("minWidth", width)
    return result


def layout():
    return html.Div([
        dcc.Store(id="workspace-token", storage_type="memory"),
        dcc.Store(id="workspace-revision", storage_type="memory"),
        dcc.Store(id="workspace-snapshot", storage_type="memory"),
        dcc.Store(id="rendered-workspace-token", storage_type="memory"),
        dcc.Store(id="export-approval", storage_type="memory"),
        dcc.Store(id="studio-draft-token", storage_type="memory"),
        dcc.Store(id="fdd-store", storage_type="session"), dcc.Download(id="fdd-download"),
        dcc.Store(id="finance-registry", storage_type="session"), dcc.Store(id="finance-token", storage_type="memory"),
        dcc.Download(id="finance-download"),
        dcc.Store(id='finance-scroll', storage_type='memory'),
        dcc.Download(id="studio-download"),
        dcc.Download(id="export-download"),
        dcc.Download(id="source-download"),
        html.A("작업 영역으로 건너뛰기", href="#main-workspace", className="skip-link"),
        html.Header([
            html.Div([html.Span("O", className="brand-mark"), html.Div([
                html.Strong("ORION", className="brand"), html.Span("Deal Intelligence · FDD", className="brand-subtitle")])], className="brand-group"),
            html.Details([html.Summary("자료 목록", title="모든 작업 화면에서 프로젝트 자료 검색·원문 확인"),
                          html.Div(studio.sidebar(), className="source-library-content")], id="source-library-drawer", className="source-library-drawer"),
            html.Div([html.Details([html.Summary("질문·증빙 도구"), html.Div([finance.route(label, page) for page, label in SUPPORT_TOOLS], className="fw-tools-menu")], id='support-tools-drawer', className="fw-tools-drawer"),
                      html.Button("원문 패널 접기", id="inspector-toggle", n_clicks=0, className="button button-quiet"),
                      html.Span("합성 자료 데모", className="mode-pill", id="mode-banner"),
                      html.Span("재무 실사 작업 공간", className="header-caption")], className="header-right"),
        ], className="global-header"),
        html.Div([
            html.Aside([
                html.Div("작업 영역", className="eyebrow"),
                html.Label("투자 대상", htmlFor="deal-selector", className="control-label"),
                dcc.Dropdown(id="deal-selector", options=CASE_OPTIONS, value="nb", clearable=False, searchable=False),
                html.Div("FDD WORKFLOW", className="eyebrow nav-eyebrow"),
                dcc.RadioItems(id="workspace-tabs", options=[{"label": label, "value": value} for value, label in NAVIGATION],
                               value="deal", className="workspace-nav", labelClassName="nav-item", inputClassName="nav-radio"),
                html.Div(className="sidebar-divider"),
                html.Label("원문 자료실", htmlFor="document-selector", className="eyebrow"),
                dcc.Dropdown(id="document-selector", options=[], placeholder="검토할 문서 선택", clearable=False),
                html.Button("원문 다운로드", id="source-download-button", n_clicks=0, className="button button-quiet source-download-button"),
                html.Div(id="source-download-status", role="status", className="sidebar-copy"),
                html.Div(id="document-summary", className="sidebar-copy"),
                html.Div([html.Strong("원문 무결성"), html.P("기존 엔진이 원문 위치와 해시를 검증합니다. 인용은 문서에 해당 내용이 기재되어 있음을 확인합니다.")], className="sidebar-note"),
                html.Button("데모 초기화", id="reset-demo", n_clicks=0, className="button button-quiet reset-button"),
                html.P("세션별 독립 실행 · API 키 불필요", className="sidebar-copy"),
            ], className="navigation-pane", **{"aria-label": "투자 건 및 작업 영역 탐색"}),
            html.Main([
                html.Div([html.Div([html.Div("투자 분석 작업대", className="eyebrow"),
                                    html.H1("투자 대상을 불러오는 중…", id="deal-heading"),
                                    html.P(id="deal-description", className="subtitle")]),
                          html.Div(id="snapshot-summary", className="snapshot-summary")], className="workspace-heading"),
                html.Div(id="dashboard-metrics"),
                html.Section([html.Div([html.H2("우선 검토 질문"), html.Span("공식 상위 3개", className="muted")], className="section-bar"),
                              html.Div(id="top3-list")], className="top3-panel", **{"aria-label": "현재 우선순위 상위 실사 질문 3개"}),
                html.Div(id="status-live-region", role="status", **{"aria-live": "polite", "aria-atomic": "true"}, className="status-line"),
                finance.root(), html.Div(studio.workspace(None), id="studio-center"), fdd.layout(),
                dcc.Loading(html.Div(id="page-content"), type="circle", color="#145e63", delay_show=200),
                html.Section([
                    html.Div([html.H2("예비 심사 문서 내보내기 승인"), html.Span("현재 스냅샷에만 적용", className="muted")], className="section-bar"),
                    html.P("이 예비 문서를 승인하기 전에 질문과 미해결 증빙 공백을 검토하세요. 내보내기 승인은 투자 승인을 의미하지 않습니다.", className="muted"),
                    html.Label("문서 형식", htmlFor="export-format", className="control-label"),
                    dcc.Dropdown(id="export-format", options=FORMAT_OPTIONS, value="dd_xlsx", clearable=False, searchable=False),
                    dcc.Checklist(id="export-confirm", options=[{"label": " 현재 스냅샷을 검토했으며 내보내기를 승인합니다.", "value": "approved"}], value=[], className="export-confirm"),
                    html.Div(id="export-approval-status", role="status", **{"aria-live": "polite"}, className="status-line"),
                    html.Button("승인 후 다운로드", id="export-button", n_clicks=0, className="button button-primary"),
                    html.Div(id="export-status", role="status", **{"aria-live": "polite"}, className="status-line"),
                ], id="export-controls", className="panel", style={"display": "none"}),
                html.Footer("IB · Big 4 · PE 재무 실사 지원 / 합성 자료 검증 환경", className="workspace-footer"),
            ], id="main-workspace", className="main-pane", tabIndex=-1),
            html.Aside([
                finance.inspector_root(),
                dcc.RadioItems(id="studio-side-tabs", options=[{"label": "질문 설정", "value": "settings"}, {"label": "질문 편집", "value": "editor"}, {"label": "원문·증빙", "value": "source"}],
                               value="settings", className="studio-side-tabs mode-settings", inline=True),
                html.Div(id="studio-message", role="status", **{"aria-live": "polite"}, className="studio-message"),
                studio.settings(), studio.editor(),
                html.Div([
                html.Div([html.H2("원문 검토"), html.Div([html.A("업데이트 검토", href="#review-panel", className="text-link"),
                           html.A("분석으로 돌아가기", href="#main-workspace", className="text-link")], className="inspector-links")], className="section-bar inspector-header"),
                html.Div(id="source-inspector", children=empty("문서, 주장, 증빙 기록 또는 실사 질문을 선택해 원문을 확인하세요.")),
                html.Section([
                    html.Div("담당자 검토", className="eyebrow"), html.H2("증빙 업데이트"),
                    html.Label("합성 증빙 이벤트", htmlFor="event-selector", className="control-label"),
                    dcc.Dropdown(id="event-selector", options=[], clearable=False, searchable=False, placeholder="이벤트 선택"),
                    html.Div(id="event-preview", className="event-preview"),
                    html.Label("검토 의견", htmlFor="review-reason", className="control-label"),
                    dcc.Textarea(id="review-reason", value="합성 원문과 제안된 영향을 검토했습니다.", className="review-note", maxLength=1000),
                    html.Div([
                        html.Button("업데이트 반려", id="review-reject", n_clicks=0, className="button button-secondary"),
                        html.Button("업데이트 승인", id="review-approve", n_clicks=0, className="button button-primary"),
                    ], className="review-actions"),
                    html.P("승인한 경우에만 확정된 증빙 상태가 변경됩니다. 반려하면 순위가 유지됩니다.", className="muted"),
                ], id="review-panel", className="review-panel", tabIndex=-1),
                ], className="legacy-inspector"),
            ], id="inspector-pane", className="inspector-pane", **{"aria-label": "원문 확인 및 분석가 검토"}),
        ], id="workbench", className="workbench"),
    ], className="orion-app")


def render_top3(view):
    rows = view.get("top3", [])
    if not rows:
        return empty("검토 대상인 미해결 질문이 없습니다. 임의의 우선순위를 추가하지 않습니다.")
    return html.Ol([html.Li([
        html.Span(str(row.get("rank", index + 1)).zfill(2), className="rank-number"),
        html.Div([html.Strong(text(row.get("issue", row.get("request_text", row.get("id", ""))))),
                  html.Span(human(row.get("financial_driver", "")), className="watchlist-driver")], className="watchlist-question"),
        html.Strong(f'{row.get("score", "—"):g}' if isinstance(row.get("score"), (int, float)) else str(row.get("score", "—")), className="score-number"),
    ]) for index, row in enumerate(rows)], className="watchlist")


def metrics(view):
    summary = view.get("summary", {})
    data = [("원문 문서", summary.get("documents", 0), "현재 투자 건의 등록 문서", "documents"),
            ("투자 가설", summary.get("theses", 0), "증빙과 연결된 검토 가설", "theses"),
            ("미해결 실사 질문", summary.get("open_questions", 0), "추가 확인이 필요한 요청", "questions"),
            ("미해결 위험", summary.get("unresolved_risks", 0), "증빙 누락 · 부분 충족 · 상충", "risks")]
    return html.Div([html.Div([html.Span(label), html.Strong(str(value)), html.Small(note)],
                             className=f"metric metric-{kind}") for label, value, note, kind in data], className="metrics")


def overview_charts(view):
    """Visual summaries of existing snapshot values, never new engine inputs."""
    questions = [q for q in view.get("questions", []) if q.get("workflow_status") == "open"]
    ranked = sorted(questions, key=lambda q: q.get("rank", 9999))[:6]
    if ranked:
        chart = go.Figure(go.Bar(
            x=[float(q.get("score", 0)) for q in reversed(ranked)],
            y=[f"Q{q.get('rank', i + 1):02}" for i, q in reversed(list(enumerate(ranked)))],
            orientation="h", customdata=[q.get("issue", "") for q in reversed(ranked)],
            text=[f"{float(q.get('score', 0)):g}" for q in reversed(ranked)], textposition="outside",
            marker_color=["#b8c3dc" if i < len(ranked) - 3 else "#5264d9" for i in range(len(ranked))],
            hovertemplate="%{customdata}<br>공식 우선순위 점수: %{x}<extra></extra>"))
        figure_layout(chart, height=255)
        chart.update_layout(margin={"l": 42, "r": 42, "t": 10, "b": 38}, showlegend=False)
        chart.update_xaxes(title_text="공식 우선순위 점수", range=[0, max(1, max(float(q.get("score", 0)) for q in ranked)) * 1.18], gridcolor="#edf0f5")
        chart.update_yaxes(title_text=None, type="category")
        priority = dcc.Graph(id="overview-priority-chart", figure=chart, style={"height": "255px"}, config={"displayModeBar": False, "responsive": True})
    else:
        priority = empty("미해결 질문이 없습니다.")
    counts = {}
    for claim in view.get("claims", []):
        label = claim.get("support_status", "unknown")
        counts[label] = counts.get(label, 0) + 1
    if counts:
        donut = go.Figure(go.Pie(labels=[human(label) for label in counts], values=list(counts.values()), hole=.76,
                                sort=False, textinfo="none", marker={"colors": [{"missing": "#c0c8dd", "partial": "#e8b45b", "supported": "#53a49a", "contradicted": "#cf7f83"}.get(label, "#929bb1") for label in counts]},
                                hovertemplate="%{label}: %{value}개<extra></extra>"))
        figure_layout(donut, height=255)
        donut.update_layout(margin={"l": 12, "r": 12, "t": 12, "b": 30},
                            legend={"orientation": "h", "y": -.05, "x": .5, "xanchor": "center"},
                            annotations=[{"text": f"<b>{len(view.get('claims', []))}</b><br>검토 주장", "showarrow": False, "font": {"size": 17}}])
        coverage = dcc.Graph(id="overview-coverage-chart", figure=donut, style={"height": "255px"}, config={"displayModeBar": False, "responsive": True})
    else:
        coverage = empty("검토할 주장이 없습니다.")
    return html.Div([
        html.Section([html.Div([html.H3("질문별 우선순위"), html.Span("상위 6개 · 현재 스냅샷", className="muted")], className="section-bar"),
                      priority, html.P("막대에 마우스를 올리면 질문을 확인할 수 있습니다. 엔진의 공식 순위를 그대로 표시합니다.", className="chart-caption")], className="panel"),
        html.Section([html.Div([html.H3("증빙 충족 현황"), html.Span("주장 기준", className="muted")], className="section-bar"),
                      coverage, html.P("증빙 충족은 독립적인 사실 검증이나 투자 성공확률을 의미하지 않습니다.", className="chart-caption")], className="panel"),
    ], className="overview-charts")


def render_overview(view):
    summary = view.get("summary", {})
    return html.Div([
        html.Div([html.H2("투자 건 개요"), badge("synthetic")], className="section-bar"),
        overview_charts(view),
        html.Div([
            html.Section([html.H3("증빙 준비 현황"),
                          html.P(f"증빙 충족률: {human(summary.get('evidence_coverage'))}%의 주장이 완전히 뒷받침됨"),
                          html.P(f"현재 검토: {human(summary.get('review_status'))}"),
                          html.P(f"최근 증빙 업데이트: {human(summary.get('last_update'))}"),
                          html.P("증빙 뒷받침 여부와 독립 검증 여부는 별개입니다. 회사가 보고한 주장은 출처 구분을 유지합니다.", className="muted")], className="panel"),
            html.Section([html.H3("증빙에 따른 검토 절차"), html.Ol([
                html.Li("투자 가설과 원문 증빙을 확인하세요."), html.Li("다음 검토 가능한 증빙 이벤트를 확인하세요."),
                html.Li("제안된 업데이트를 승인하거나 반려하세요."), html.Li("확정된 우선순위를 비교한 뒤 내보내세요.")]),
                html.P("새 증빙은 요청을 해결하거나 상충 상태를 다시 열 수 있으며, 상위 3개 질문은 유지될 수도 있습니다.", className="muted")], className="panel"),
        ], className="two-column"),
        html.Section([html.Div([html.H3("원문 자료실"), html.Span("왼쪽 자료실에서 문서 선택 · 원문 확인", className="muted")], className="section-bar"),
                      html.Div(html.Table([html.Thead(html.Tr([html.Th("문서"), html.Th("추출 상태"), html.Th("출처"), html.Th("버전")])),
                          html.Tbody([html.Tr([html.Td([html.Span(str(d.get("filename", d.get("title", ""))).rsplit(".", 1)[-1].upper()[:4] or "FILE", className="file-icon file-" + studio.file_family(d.get("filename", ""))), html.Strong(d.get("title", d.get("filename", d["id"])))]),
                                              html.Td(badge(d.get("parse_status"))), html.Td(badge(d.get("source_origin"))),
                                              html.Td(f"v{d.get('document_version', 1)}")]) for d in view.get("documents", [])])], className="document-matrix"), className="table-scroll")
                      if view.get("documents") else empty("등록된 문서가 없습니다.")], className="panel"),
        html.Details([html.Summary("범위 및 한계 · 합성 자료 데모 안내"), html.Ul([html.Li(text(item)) for item in view.get("limitations", [])])], className="panel quiet-panel"),
    ])


def render_evidence(view):
    return html.Div([
        html.H2("증빙 탐색"), html.P("행을 선택해 원문, 문서 내 위치, 관련 주장과 검증 상태를 확인하세요.", className="muted"),
        grid("evidence-grid", view.get("evidence", []), [column("statement", "증빙 / 주장", 280, 2), column("stance", "증빙 입장", 120),
             column("provenance", "출처 구분", 180), column("verification_level", "검증", 160), column("review_status", "검토", 120),
             column("source_refs", "원문 참조", 200), column("lifecycle", "활성 상태", 120)]),
        html.H3("주장 검토표"), grid("claim-grid", view.get("claims", []), [column("statement", "주장", 280, 2),
             column("support_status", "증빙 뒷받침", 150), column("truth_status", "사실 검증 상태", 160), column("claim_kind", "주장 유형", 170),
             column("review_status", "검토", 120), column("thesis_title", "투자 가설", 220)], height=330),
    ])


def render_thesis(view):
    rows = view.get("theses", [])
    return html.Div([html.H2("투자 가설 검토판"), html.P("원문이 뒷받침하는 진술도 독립적으로 검증되었다는 뜻은 아닙니다. 투자 가설을 선택해 주장과 질문을 확인하세요.", className="muted"),
        grid("thesis-grid", rows, [column("title", "투자 가설", 260, 2), column("counter_thesis", "반대 가설", 280),
             column("evidence_status", "증빙 상태", 180), column("materiality", "중요도", 120), column("financial_drivers", "재무 영향 요인", 180), column("claims_summary", "뒷받침하는 주장", 300),
             column("verification_requirements", "미완료 검증", 300), column("review_status", "검토", 120)], height=460),
        html.Div("재무 영향 요인 연결은 정성적 노출을 나타냅니다. 기업가치 평가나 DCF 계산을 의미하지 않습니다.", className="callout"),
    ])


def render_questions(view):
    return html.Div([html.Div([html.H2("맞춤형 실사 질문표"), badge("read_only")], className="section-bar"),
        html.P("공식 우선순위 = 9 × 증빙 공백 + 8 × 중요도 + 3 × 확보 가능성. 표 정렬은 표시 순서만 바꾸며, 순위 열은 엔진이 산출한 순위를 유지합니다.", className="callout"),
        html.Details([html.Summary("추가 표시 열"), dcc.Checklist(id="question-columns", options=[
            {"label": " 질문 ID", "value": "id"}, {"label": " 요청 자료", "value": "request_text"}, {"label": " 투자 가설", "value": "thesis_title"},
            {"label": " 재무 영향 요인", "value": "financial_driver"}, {"label": " 기대 정보 이득 (비트)", "value": "eig_bits"},
            {"label": " 연결 증빙 ID", "value": "evidence_ids"}, {"label": " 검토 상태", "value": "review_status"},
        ], value=[], className="column-chooser")], className="column-options"),
        grid("question-grid", view.get("questions", []), question_columns(), height=500),
        html.P("기대 정보 이득이 비어 있으면 필요한 확률 가정이 없다는 뜻입니다. 기대 정보 이득은 분석용 비교 지표이며 우선순위 점수에 더하지 않습니다.", className="muted"),
    ])


def question_columns(selected=()):
    columns = [column("rank", "순위", 96, minWidth=96, filter=False), column("issue", "실사 질문", 290, 2),
            column("score", "우선순위", 120), column("gap", "증빙 공백", 140), column("materiality_score", "중요도", 140), column("obtainability_score", "확보 가능성", 150),
            column("workflow_status", "상태", 130), column("request_text", "검증 요청 자료", 300), column("thesis_title", "투자 가설", 240),
            column("financial_driver", "재무 영향 요인", 180), column("eig_bits", "기대 정보 이득 (비트)", 120), column("evidence_ids", "연결 증빙", 220), column("review_status", "검토", 120), column("id", "질문 ID", 220)]
    optional = {"id", "request_text", "thesis_title", "financial_driver", "eig_bits", "evidence_ids", "review_status"}
    for col in columns:
        if col["field"] in optional:
            col["hide"] = col["field"] not in selected
    return columns


def change_grid(view):
    rows = [{**row, "reason_codes": row.get("reason", row.get("reason_codes", row.get("reasons", [])))} for row in view.get("changes", [])]
    if not rows:
        return empty("아직 확정된 업데이트가 없습니다. 현재 순위는 초기 상태를 유지합니다.")
    return grid("change-grid", rows, [column("issue", "질문", 280, 2), column("before_rank", "변경 전 순위", 110), column("after_rank", "변경 후 순위", 110),
         column("before_score", "변경 전 점수", 110), column("after_score", "변경 후 점수", 110), column("before_status", "변경 전 상태", 140),
         column("after_status", "변경 후 상태", 140), column("reason_codes", "변경 사유", 240)], identity="question_id", height=340)


def render_review(view):
    return html.Div([html.H2("분석가 검토 및 증빙 업데이트"),
        html.P("결정 전에 검토 패널에서 다음 원문 이벤트를 확인하세요. 미리보기는 확정된 스냅샷을 변경하지 않습니다.", className="muted"),
        html.Div([html.Div([html.Span(f"T{e.get('stage', '')}", className="event-step"), html.Div([html.Strong(text(e.get("label", e["id"]))),
            html.Div(e["id"], className="identifier"), badge(e.get("status", "pending"))])], className="event-card") for e in view.get("events", [])], className="event-timeline"),
        html.H3("최근 확정 순위 비교"), change_grid(view),
        html.H3("변경 불가 검토 이력"), html.P(text(view.get("timestamp_basis", "결정론적 합성 자료 재현 시각이며, 실제 분석가의 승인 시각이 아닙니다.")), className="muted"),
        html.Div([html.Div([badge(a.get("event_type")), html.Strong(f"리비전 {a.get('before_revision')} → {a.get('after_revision')}"),
                  html.P(text(a.get("reason", "")) if a.get("event_type") == "update_staged" else a.get("reason", "")), html.Div(a.get("created_at", ""), className="muted"),
                  html.Details([html.Summary("감사 기록 ID 및 해시"), html.Code(a.get("id", "")), html.P(a.get("event_hash", ""), className="hash-value")])], className="audit-card") for a in reversed(view.get("audit", []))]) or empty("아직 검토 결정이 없습니다."),
    ])


def figure_layout(figure, *, height=300):
    figure.update_layout(template="plotly_white", height=height, margin={"l": 48, "r": 20, "t": 28, "b": 50},
                         font={"family": "Segoe UI, Arial, sans-serif", "size": 14, "color": "#172b3a"},
                         legend={"orientation": "h", "y": 1.15}, paper_bgcolor="white", plot_bgcolor="white")
    return figure


def render_analytics(view):
    analysis = view.get("analytics", {})
    beliefs = analysis.get("belief_snapshots", [])
    content = [html.H2("맞춤형 분석"), html.Div("공식 실사 우선순위, 기대 정보 이득, 재무 중요도는 별개입니다. 아래 베이지안 결과는 명시된 합성 시나리오 가정을 사용하며 실증적 투자 성공확률이 아닙니다.", className="callout")]
    if beliefs:
        chart = go.Figure()
        labels = [f"T{x.get('stage', i + 1)} · {x.get('hypothesis_id', '')}" for i, x in enumerate(beliefs)]
        chart.add_bar(name="사전확률", x=labels, y=[x.get("prior") for x in beliefs], marker_color="#91a7bb")
        chart.add_bar(name="사후확률", x=labels, y=[x.get("posterior") for x in beliefs], marker_color="#145e63")
        chart.update_yaxes(range=[0, 1], tickformat=".0%", title_text="시나리오 확률")
        content += [html.H3("사전확률 → 사후확률"), dcc.Graph(id="bayes-chart", figure=figure_layout(chart), config={"displayModeBar": False}),
                    html.Div([html.Details([html.Summary(f"T{x.get('stage', i + 1)} · {x.get('evidence_id', '')} · 가정"),
                       html.P(f"사전확률: {x.get('prior', 0):.4f} · 사후확률: {x.get('posterior', 0):.4f}"),
                       html.P(f"H일 때의 우도: {x.get('likelihood_h')} · H가 아닐 때의 우도: {x.get('likelihood_not_h')}"),
                       html.P(x.get("assumption_source", "")), html.P(f"가정: {x.get('assumption_id', '')} · 작성자: {x.get('assumption_author_id', '')} · 기준일: {x.get('assumption_as_of', '')}"),
                       html.P(x.get("conditional_model_source") or "")], className="assumption-card") for i, x in enumerate(beliefs)])]
    else:
        content.append(empty("아직 승인된 베이지안 업데이트가 없습니다." if analysis.get("status") != "not_parameterized" else "베이지안 분석 불가: 이 사례에는 승인된 확률 매개변수가 없습니다."))
    eig = analysis.get("initial_eig")
    content.append(html.H3("기대 정보 이득"))
    prospective = analysis.get("candidate_eig")
    if prospective:
        content.append(html.Section([badge("unapproved", "예상 분석 · "), html.H3("다음 증빙 모형"),
            html.P(f"이벤트: {prospective['event_id']}"), html.Strong(f"{prospective['eig_bits']:.6f} 비트", className="eig-value"),
            html.P("관련 질문: " + "; ".join(prospective.get("question_ids", []))),
            html.P("이 계산은 승인 전 예상 답변을 고려합니다. 확정된 믿음이나 공식 우선순위를 변경하지 않습니다.", className="muted"),
            html.Details([html.Summary("가정 및 예상 답변"), html.P(prospective.get("assumption_source", "")),
                html.Ul([html.Li(f"{text(a['answer'])}: 확률 {a['probability']:.2%}; 사후확률 {a['posterior']:.2%}" if a.get("posterior") is not None else f"{text(a['answer'])}: 사후확률 확인 불가") for a in prospective.get("answers", [])])])], className="panel"))
    if eig:
        content += [html.Div([html.Strong(f"{eig['eig_bits']:.6f} 비트", className="eig-value"), html.P("초기 이진 검증 시나리오 · 점수 가중치에 미반영")], className="panel"),
                    html.P(eig.get("assumption_source", ""), className="muted"),
                    html.Table([html.Thead(html.Tr([html.Th("예상 답변"), html.Th("답변 확률"), html.Th("사후확률")])),
                                html.Tbody([html.Tr([html.Td(text(x["answer"])), html.Td(f"{x['probability']:.2%}"), html.Td(f"{x['posterior']:.2%}" if x.get("posterior") is not None else "확인 불가")]) for x in eig.get("answers", [])])], className="data-table")]
    else:
        content.append(empty("기대 정보 이득 계산 불가: 필요한 확률 매개변수가 제공되지 않았습니다."))
    candidates = analysis.get("eig_candidates", [])
    if len(candidates) > 1:
        chart = go.Figure(go.Bar(x=[text(x["label"]) for x in candidates], y=[x["eig_bits"] for x in candidates], marker_color="#145e63"))
        chart.update_yaxes(title_text="정보 이득 (비트)", rangemode="tozero")
        content += [html.H3("제공된 증빙 모형 비교"),
                    html.P("각 막대는 해당 단계의 사전확률과 명시된 우도를 사용합니다. 증빙 시나리오 모형의 결과이며, 모든 실사 질문에 임의로 부여한 정보 이득이 아닙니다.", className="muted"),
                    dcc.Graph(id="eig-chart", figure=figure_layout(chart, height=340), config={"displayModeBar": False}),
                    html.Div([html.Details([html.Summary(text(x["label"])), html.P(f"기대 정보 이득: {x['eig_bits']:.6f} 비트 · 사전확률: {x['prior']:.4f}"),
                        html.P(x.get("assumption_source", "")),
                        html.Ul([html.Li(f"{text(a['answer'])}: 확률 {a['probability']:.2%}; 사후확률 {a['posterior']:.2%}" if a.get("posterior") is not None else f"{text(a['answer'])}: 확률 {a['probability']:.2%}; 사후확률 확인 불가") for a in x.get("answers", [])])], className="assumption-card") for x in candidates])]
    content += [html.H3("증빙에 따른 순위 비교"), change_grid(view), html.H3("재무 중요도"),
                html.P("정성적 재무 영향 요인은 기존 실사 질문에서 가져옵니다. 임의의 수치로 가치평가 민감도를 만들지 않습니다.", className="muted"),
                html.Div([badge(driver) for driver in sorted({q.get("financial_driver", "") for q in view.get("questions", [])})], className="badge-row")]
    return html.Div(content)


def render_export(view):
    summary = view.get("summary", {})
    return html.Div([html.H2("예비 심사 메모 및 실사 자료 내보내기"),
        html.P("예비 투자 심사를 위한 원문 기반 검토 결과, 미해결 위험 및 검토 이력을 내보냅니다.", className="muted"),
        html.Div([html.H3("승인 범위"), html.P(f"스냅샷: {view.get('snapshot_id')}"),
                  html.P(f"리비전 {view.get('revision')} · {summary.get('open_questions', 0)}개 미해결 실사 질문 · {summary.get('evidence', 0)}개 증빙 기록"),
                  html.P("미승인 검토 결과는 초안 상태를 유지합니다. 이 파일은 합성 자료 기반 예비 심사 문서이며, 완료된 재무 실사 보고서가 아닙니다."),
                  html.P("스냅샷이나 문서 형식을 변경하면 내보내기 승인이 해제됩니다.", className="muted")], className="panel"),
    ])


def render_page(page, view):
    if page in finance.PAGES:
        return html.Div(className="finance-page-marker")
    content = {"fdd": lambda _: html.Div(className="fdd-page-marker"), "studio": lambda _: html.Div(className="studio-page-marker"), "overview": render_overview, "evidence": render_evidence, "thesis": render_thesis,
            "questions": render_questions, "review": render_review, "analytics": render_analytics,
            "export": render_export}.get(page, render_overview)(view)
    visuals = page_visuals(page, view)
    if visuals is not None:
        content.children.insert(1, visuals)
        content.className = "dashboard-page"
    return content


def render_span(span):
    locator = span.get("locator", {})
    quote = span.get("quote", "")
    return html.Div([
        html.Div([html.Strong(span.get("filename", span.get("document_id", ""))), badge(span.get("source_origin", ""))], className="source-heading"),
        html.Div(f"문서 v{span.get('document_version', 1)} · {span.get('id', '')}", className="identifier"),
        html.Div(metadata_value("locator", locator), className="locator"),
        html.Blockquote([span.get("prefix", ""), html.Mark(quote), span.get("suffix", "")], className="source-excerpt"),
        html.Div([badge(span.get("locator_status"), "원문 위치: "), badge(span.get("extraction_method"), "추출 방식: ")], className="badge-row"),
        html.Details([html.Summary("원문 무결성"), html.Div(span.get("text_sha256", ""), className="hash-value")]),
    ], className="source-span")


def render_inspection(detail):
    if not detail:
        return empty("기록을 선택해 원문을 확인하세요.")
    metadata = detail.get("metadata", {})
    spans = detail.get("spans", [])
    source_content = [render_span(spans[0])] if spans else [empty("이 기록에는 원문 구간이 없으므로 검증된 원문 인용으로 제시하지 않습니다.")]
    if len(spans) > 1:
        source_content.append(html.Details([html.Summary(f"추가 원문 구간 ({len(spans) - 1})"), *[render_span(span) for span in spans[1:]]], className="additional-sources"))
    question = next((q for q in detail.get("questions", []) if q.get("id") == detail.get("id")), None)
    score_detail = None
    if question is not None:
        score_detail = html.Div([html.Strong("공식 우선순위 산출 근거"),
            html.P(f"우선순위 {question.get('score', '—')} = 9 × {question.get('gap', '—')} 증빙 공백 + 8 × {question.get('materiality_score', '—')} 중요도 + 3 × {question.get('obtainability_score', '—')} 확보 가능성"),
            html.P(human(question.get("reason_codes", []))), html.Strong("검증 요청 자료"), html.P(question.get("request_text", "")),
            html.Details([html.Summary("입력 근거 및 미충족 요건"), html.P(question.get("materiality", {}).get("rationale", "")),
                html.P(question.get("obtainability", {}).get("rationale", "")), html.Ul([html.Li(item) for item in question.get("outstanding_requirements", [])])])], className="callout")
    return html.Div([
        html.Div(human(detail.get("kind", "source")), className="eyebrow"), html.H3(detail.get("title", detail.get("id", ""))),
        html.Div(detail.get("id", ""), className="identifier"),
        html.Div([badge(metadata[key], human(key) + ": ") for key in ("support_status", "truth_status", "review_status", "verification_level", "provenance") if key in metadata], className="badge-row"),
        score_detail,
        html.Details([html.Summary("기록 상세"), html.Dl([html.Div([html.Dt(text(key)),
            html.Dd(metadata_value(key, value))],
            className="metadata-row") for key, value in metadata.items()])]),
        html.Div(source_content),
        html.Details([html.Summary(f"관련 주장 · {len(detail['claims'])}개"), *[html.P(c.get("statement", c.get("id", ""))) for c in detail.get("claims", [])]], className="related-records") if detail.get("claims") else None,
        html.Details([html.Summary(f"관련 실사 질문 · {len(detail['questions'])}개"), *[html.P(q.get("issue", q.get("id", ""))) for q in detail.get("questions", [])]], className="related-records") if detail.get("questions") else None,
    ])


def render_preview(preview):
    if not preview:
        return empty("검토할 이벤트가 없습니다. 초기화하여 새 검토 분기를 시작하세요.")
    event = preview.get("event", {})
    note = preview.get("note") or event.get("analyst_note", "")
    spans = preview.get("spans", [])
    return html.Div([
        badge("preview_approval_required"), html.P(note),
        html.P(("상위 3개는 유지되며 하위 요청 순위는 변경될 수 있습니다." if not preview.get("top3_changed", preview.get("ranking_changed")) else "승인하면 우선순위 상위 3개가 변경됩니다.") if preview.get("ranking_changed") else "이 증빙으로 순위는 바뀌지 않지만, 기초 증빙 상태는 변경될 수 있습니다.", className="preview-result"),
        html.Details([html.Summary(f"원문 · {len(spans)}개 구간"), *[render_span(span) for span in spans]]),
        html.Details([html.Summary("변경 전후 우선순위 미리보기"),
                      html.Div("변경 전: " + "; ".join(preview.get("before_top3", []))),
                      html.Div("변경 후: " + "; ".join(preview.get("after_top3", [])))]),
    ])

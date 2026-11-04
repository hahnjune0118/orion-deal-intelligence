"""Accessible document-centered Dash layout; no authoritative business logic."""
from __future__ import annotations

import json
from dash import dcc, html
import dash_ag_grid as dag
import plotly.graph_objects as go

NAVIGATION = [
    ("overview", "Deal overview"), ("evidence", "Evidence explorer"),
    ("thesis", "Investment thesis"), ("questions", "Adaptive DD matrix"),
    ("review", "Analyst review"), ("analytics", "Adaptive analytics"),
    ("export", "Screening & export"),
]
CASE_OPTIONS = [
    {"label": "Northstar Analytics", "value": "nb"},
    {"label": "Manufacturing case", "value": "mf"},
    {"label": "Lumen · conflict review", "value": "lm"},
]
FORMAT_OPTIONS = [
    {"label": "DD Request List · Excel", "value": "dd_xlsx"},
    {"label": "DD Request List · CSV", "value": "dd_csv"},
    {"label": "Evidence Register · CSV", "value": "evidence_csv"},
    {"label": "Screening Memo · Word", "value": "memo_docx"},
    {"label": "Screening Memo · Markdown", "value": "memo_md"},
]


def human(value):
    if value is None:
        return "Unavailable"
    if isinstance(value, (list, tuple)):
        return "; ".join(human(x) for x in value) or "None"
    if isinstance(value, dict):
        return "; ".join(f"{human(k)}: {human(v)}" for k, v in value.items())
    return str(value).replace("_", " ")


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
                         "suppressCellFocus": False},
        style={"height": f"{height}px", "width": "100%"}, className="ag-theme-alpine orion-grid",
    )


def column(field, name, width=None, flex=None, **extra):
    result = {"field": field, "headerName": name, "tooltipField": field, **extra}
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
        dcc.Download(id="export-download"),
        dcc.Download(id="source-download"),
        html.A("Skip to workspace", href="#main-workspace", className="skip-link"),
        html.Header([
            html.Div([html.Span("O", className="brand-mark"), html.Div([
                html.Strong("ORION", className="brand"), html.Span("DEAL INTELLIGENCE", className="brand-subtitle")])], className="brand-group"),
            html.Div([html.Span("SYNTHETIC DEMO", className="mode-pill", id="mode-banner"),
                      html.Span("Evidence-grounded preliminary screening", className="header-caption")], className="header-right"),
        ], className="global-header"),
        html.Div([
            html.Aside([
                html.Div("WORKSPACE", className="eyebrow"),
                html.Label("Investment opportunity", htmlFor="deal-selector", className="control-label"),
                dcc.Dropdown(id="deal-selector", options=CASE_OPTIONS, value="nb", clearable=False, searchable=False),
                html.Div("ANALYSIS", className="eyebrow nav-eyebrow"),
                dcc.RadioItems(id="workspace-tabs", options=[{"label": label, "value": value} for value, label in NAVIGATION],
                               value="overview", className="workspace-nav", labelClassName="nav-item", inputClassName="nav-radio"),
                html.Div(className="sidebar-divider"),
                html.Label("SOURCE LIBRARY", htmlFor="document-selector", className="eyebrow"),
                dcc.Dropdown(id="document-selector", options=[], placeholder="Inspect a document", clearable=False),
                html.Button("Download original source", id="source-download-button", n_clicks=0, className="button button-quiet source-download-button"),
                html.Div(id="source-download-status", role="status", className="sidebar-copy"),
                html.Div(id="document-summary", className="sidebar-copy"),
                html.Div([html.Strong("Source integrity"), html.P("Native locators and source hashes are validated by the existing engine. A citation confirms what a document reports.")], className="sidebar-note"),
                html.Button("Reset demo", id="reset-demo", n_clicks=0, className="button button-quiet reset-button"),
                html.P("Session-isolated · no API key", className="sidebar-copy"),
            ], className="navigation-pane", **{"aria-label": "Deal and workspace navigation"}),
            html.Main([
                html.Div([html.Div([html.Div("INVESTMENT WORKBENCH", className="eyebrow"),
                                    html.H1("Loading opportunity…", id="deal-heading"),
                                    html.P(id="deal-description", className="subtitle")]),
                          html.Div(id="snapshot-summary", className="snapshot-summary")], className="workspace-heading"),
                html.Section([html.Div([html.H2("Priority watchlist"), html.Span("Canonical Top 3", className="muted")], className="section-bar"),
                              html.Div(id="top3-list")], className="top3-panel", **{"aria-label": "Current top three due diligence questions"}),
                html.Div(id="status-live-region", role="status", **{"aria-live": "polite", "aria-atomic": "true"}, className="status-line"),
                dcc.Loading(html.Div(id="page-content"), type="circle", color="#145e63", delay_show=200),
                html.Section([
                    html.Div([html.H2("Approve a screening export"), html.Span("Current snapshot only", className="muted")], className="section-bar"),
                    html.P("Review the questions and unresolved gaps before approving this preliminary document. Export approval does not approve an investment.", className="muted"),
                    html.Label("Document format", htmlFor="export-format", className="control-label"),
                    dcc.Dropdown(id="export-format", options=FORMAT_OPTIONS, value="dd_xlsx", clearable=False, searchable=False),
                    dcc.Checklist(id="export-confirm", options=[{"label": " I reviewed this snapshot and approve this export.", "value": "approved"}], value=[], className="export-confirm"),
                    html.Div(id="export-approval-status", role="status", **{"aria-live": "polite"}, className="status-line"),
                    html.Button("Approve & download", id="export-button", n_clicks=0, className="button button-primary"),
                    html.Div(id="export-status", role="status", **{"aria-live": "polite"}, className="status-line"),
                ], id="export-controls", className="panel", style={"display": "none"}),
                html.Footer("Preliminary screening · synthetic information · deterministic analysis", className="workspace-footer"),
            ], id="main-workspace", className="main-pane", tabIndex=-1),
            html.Aside([
                html.Div([html.H2("Source inspector"), html.Div([html.A("Review update", href="#review-panel", className="text-link"),
                           html.A("Back to analysis", href="#main-workspace", className="text-link")], className="inspector-links")], className="section-bar inspector-header"),
                html.Div(id="source-inspector", children=empty("Select a document, claim, evidence record, or DD question to inspect its source.")),
                html.Section([
                    html.Div("HUMAN REVIEW", className="eyebrow"), html.H2("Evidence update"),
                    html.Label("Synthetic evidence event", htmlFor="event-selector", className="control-label"),
                    dcc.Dropdown(id="event-selector", options=[], clearable=False, searchable=False, placeholder="Choose an event"),
                    html.Div(id="event-preview", className="event-preview"),
                    html.Label("Review note", htmlFor="review-reason", className="control-label"),
                    dcc.Textarea(id="review-reason", value="Reviewed the original synthetic source and the proposed implications.", className="review-note", maxLength=1000),
                    html.Div([
                        html.Button("Reject update", id="review-reject", n_clicks=0, className="button button-secondary"),
                        html.Button("Approve update", id="review-approve", n_clicks=0, className="button button-primary"),
                    ], className="review-actions"),
                    html.P("Only approval changes the committed evidence state. Rejection retains the ranking.", className="muted"),
                ], id="review-panel", className="review-panel", tabIndex=-1),
            ], className="inspector-pane", **{"aria-label": "Source inspection and analyst review"}),
        ], className="workbench"),
    ], className="orion-app")


def render_top3(view):
    rows = view.get("top3", [])
    if not rows:
        return empty("No eligible open questions. No synthetic priority is added.")
    return html.Ol([html.Li([
        html.Span(str(row.get("rank", index + 1)).zfill(2), className="rank-number"),
        html.Div([html.Strong(row.get("issue", row.get("request_text", row.get("id", "")))),
                  html.Span(human(row.get("financial_driver", "")), className="watchlist-driver")], className="watchlist-question"),
        html.Strong(f'{row.get("score", "—"):g}' if isinstance(row.get("score"), (int, float)) else str(row.get("score", "—")), className="score-number"),
    ]) for index, row in enumerate(rows)], className="watchlist")


def metrics(view):
    summary = view.get("summary", {})
    data = [("Documents", summary.get("documents", 0)), ("Investment theses", summary.get("theses", 0)),
            ("Open DD questions", summary.get("open_questions", 0)), ("Unresolved risks", summary.get("unresolved_risks", 0))]
    return html.Div([html.Div([html.Span(label), html.Strong(str(value))], className="metric") for label, value in data], className="metrics")


def render_overview(view):
    summary = view.get("summary", {})
    return html.Div([
        html.Div([html.H2("Deal overview"), badge("synthetic")], className="section-bar"), metrics(view),
        html.Div([
            html.Section([html.H3("Evidence readiness"),
                          html.P(f"Evidence coverage: {human(summary.get('evidence_coverage'))}% of claims fully supported"),
                          html.P(f"Current review: {human(summary.get('review_status'))}"),
                          html.P(f"Last evidence update: {human(summary.get('last_update'))}"),
                          html.P("Support status and independent verification are separate. Company-reported claims retain their provenance.", className="muted")], className="panel"),
            html.Section([html.H3("Adaptive review workflow"), html.Ol([
                html.Li("Inspect the thesis and its source evidence."), html.Li("Review the next available evidence event."),
                html.Li("Approve or reject the proposed update."), html.Li("Compare the committed priorities, then export.")]),
                html.P("New evidence can resolve a request, reopen a conflict, or leave the Top 3 unchanged.", className="muted")], className="panel"),
        ], className="two-column"),
        html.Section([html.H3("Source library"),
                      html.Div([html.Div([html.Strong(d.get("title", d.get("filename", d["id"]))),
                                          html.Div([badge(d.get("parse_status")), badge(d.get("source_origin")), html.Span(f"v{d.get('document_version', 1)}", className="muted")], className="badge-row")], className="document-card") for d in view.get("documents", [])])], className="panel"),
        html.Section([html.H3("Scope & limitations"), html.Ul([html.Li(item) for item in view.get("limitations", [])])], className="panel quiet-panel"),
    ])


def render_evidence(view):
    return html.Div([
        html.H2("Evidence explorer"), html.P("Select a row to inspect exact source text, native location, related claims and verification status.", className="muted"),
        grid("evidence-grid", view.get("evidence", []), [column("statement", "Evidence / claim", 280, 2), column("stance", "Stance", 120),
             column("provenance", "Classification", 180), column("verification_level", "Verification", 160), column("review_status", "Review", 120),
             column("source_refs", "Source references", 200), column("lifecycle", "Lifecycle", 120)]),
        html.H3("Claim matrix"), grid("claim-grid", view.get("claims", []), [column("statement", "Claim", 280, 2),
             column("support_status", "Evidence support", 150), column("truth_status", "Truth status", 160), column("claim_kind", "Claim type", 170),
             column("review_status", "Review", 120), column("thesis_title", "Investment thesis", 220)], height=330),
    ])


def render_thesis(view):
    rows = []
    for row in view.get("theses", []):
        rows.append({**row, **{key: human(row.get(key)) for key in ("claims_summary", "financial_drivers", "evidence_status", "verification_requirements", "question_ids")}})
    return html.Div([html.H2("Investment thesis board"), html.P("A source-backed statement is not automatically independently verified. Select a thesis to examine its claims and questions.", className="muted"),
        grid("thesis-grid", rows, [column("title", "Investment hypothesis", 260, 2), column("counter_thesis", "Counter-thesis", 280),
             column("evidence_status", "Evidence status", 180), column("materiality", "Materiality", 120), column("financial_drivers", "Financial drivers", 180), column("claims_summary", "Supporting claims", 300),
             column("verification_requirements", "Outstanding verification", 300), column("review_status", "Review", 120)], height=460),
        html.Div("Financial driver mappings describe qualitative exposure. No valuation or DCF calculation is implied.", className="callout"),
    ])


def render_questions(view):
    return html.Div([html.Div([html.H2("Adaptive DD matrix"), badge("read_only")], className="section-bar"),
        html.P("Canonical priority = 9 × Evidence Gap + 8 × Materiality + 3 × Obtainability. Grid sorting changes the view; the Rank column remains the engine ranking.", className="callout"),
        html.Details([html.Summary("Optional matrix columns"), dcc.Checklist(id="question-columns", options=[
            {"label": " Question ID", "value": "id"}, {"label": " Requested artifact", "value": "request_text"}, {"label": " Investment thesis", "value": "thesis_title"},
            {"label": " Financial driver", "value": "financial_driver"}, {"label": " EIG (bits)", "value": "eig_bits"},
            {"label": " Linked evidence IDs", "value": "evidence_ids"}, {"label": " Review status", "value": "review_status"},
        ], value=[], className="column-chooser")], className="column-options"),
        grid("question-grid", view.get("questions", []), question_columns(), height=500),
        html.P("A blank EIG means the necessary probability assumptions are unavailable. EIG is an analytical comparison and is not added to the priority score.", className="muted"),
    ])


def question_columns(selected=()):
    columns = [column("rank", "Rank", 96, minWidth=96, filter=False), column("issue", "Due diligence question", 290, 2),
            column("score", "Priority", 120), column("gap", "Evidence gap", 140), column("materiality_score", "Materiality", 140), column("obtainability_score", "Obtainability", 150),
            column("workflow_status", "Status", 130), column("request_text", "Verification artifact", 300), column("thesis_title", "Investment thesis", 240),
            column("financial_driver", "Financial driver", 180), column("eig_bits", "EIG (bits)", 120), column("evidence_ids", "Linked evidence", 220), column("review_status", "Review", 120), column("id", "Question ID", 220)]
    optional = {"id", "request_text", "thesis_title", "financial_driver", "eig_bits", "evidence_ids", "review_status"}
    for col in columns:
        if col["field"] in optional:
            col["hide"] = col["field"] not in selected
    return columns


def change_grid(view):
    rows = [{**row, "reason_codes": human(row.get("reason", row.get("reason_codes", row.get("reasons", []))))} for row in view.get("changes", [])]
    if not rows:
        return empty("No committed update yet. The current ranking remains the initial state.")
    return grid("change-grid", rows, [column("issue", "Question", 280, 2), column("before_rank", "Before rank", 110), column("after_rank", "After rank", 110),
         column("before_score", "Before score", 110), column("after_score", "After score", 110), column("before_status", "Before status", 140),
         column("after_status", "After status", 140), column("reason_codes", "Change rationale", 240)], identity="question_id", height=340)


def render_review(view):
    return html.Div([html.H2("Analyst review & evidence updates"),
        html.P("Use the review panel to inspect the next source event before making a decision. A preview does not change the committed snapshot.", className="muted"),
        html.Div([html.Div([html.Span(f"T{e.get('stage', '')}", className="event-step"), html.Div([html.Strong(e.get("label", e["id"])),
            html.Div(e["id"], className="identifier"), badge(e.get("status", "pending"))])], className="event-card") for e in view.get("events", [])], className="event-timeline"),
        html.H3("Latest committed ranking comparison"), change_grid(view),
        html.H3("Immutable review history"), html.P(view.get("timestamp_basis", "Deterministic synthetic replay times; not real-world analyst sign-off times."), className="muted"),
        html.Div([html.Div([badge(a.get("event_type")), html.Strong(f"Revision {a.get('before_revision')} → {a.get('after_revision')}"),
                  html.P(a.get("reason", "")), html.Div(a.get("created_at", ""), className="muted"),
                  html.Details([html.Summary("Audit identity & hash"), html.Code(a.get("id", "")), html.P(a.get("event_hash", ""), className="hash-value")])], className="audit-card") for a in reversed(view.get("audit", []))]) or empty("No review decisions yet."),
    ])


def figure_layout(figure, *, height=300):
    figure.update_layout(template="plotly_white", height=height, margin={"l": 48, "r": 20, "t": 28, "b": 50},
                         font={"family": "Segoe UI, Arial, sans-serif", "size": 14, "color": "#172b3a"},
                         legend={"orientation": "h", "y": 1.15}, paper_bgcolor="white", plot_bgcolor="white")
    return figure


def render_analytics(view):
    analysis = view.get("analytics", {})
    beliefs = analysis.get("belief_snapshots", [])
    content = [html.H2("Adaptive analytics"), html.Div("Canonical DD priority, EIG and financial materiality are distinct. Bayesian outputs below use explicit synthetic scenario assumptions, not empirical investment success probabilities.", className="callout")]
    if beliefs:
        chart = go.Figure()
        labels = [f"T{x.get('stage', i + 1)} · {x.get('hypothesis_id', '')}" for i, x in enumerate(beliefs)]
        chart.add_bar(name="Prior", x=labels, y=[x.get("prior") for x in beliefs], marker_color="#91a7bb")
        chart.add_bar(name="Posterior", x=labels, y=[x.get("posterior") for x in beliefs], marker_color="#145e63")
        chart.update_yaxes(range=[0, 1], tickformat=".0%", title_text="Scenario probability")
        content += [html.H3("Prior → posterior"), dcc.Graph(id="bayes-chart", figure=figure_layout(chart), config={"displayModeBar": False}),
                    html.Div([html.Details([html.Summary(f"T{x.get('stage', i + 1)} · {x.get('evidence_id', '')} · assumptions"),
                       html.P(f"Prior: {x.get('prior', 0):.4f} · Posterior: {x.get('posterior', 0):.4f}"),
                       html.P(f"Likelihood under H: {x.get('likelihood_h')} · under not-H: {x.get('likelihood_not_h')}"),
                       html.P(x.get("assumption_source", "")), html.P(f"Assumption: {x.get('assumption_id', '')} · Author: {x.get('assumption_author_id', '')} · As of: {x.get('assumption_as_of', '')}"),
                       html.P(x.get("conditional_model_source") or "")], className="assumption-card") for i, x in enumerate(beliefs)])]
    else:
        content.append(empty("No approved Bayesian update yet." if analysis.get("status") != "not_parameterized" else "Bayesian analysis unavailable: this case has no approved probability parameters."))
    eig = analysis.get("initial_eig")
    content.append(html.H3("Expected information gain"))
    prospective = analysis.get("candidate_eig")
    if prospective:
        content.append(html.Section([badge("unapproved", "Prospective · "), html.H3("Next evidence model"),
            html.P(f"Event: {prospective['event_id']}"), html.Strong(f"{prospective['eig_bits']:.6f} bits", className="eig-value"),
            html.P("Related questions: " + "; ".join(prospective.get("question_ids", []))),
            html.P("This calculation considers expected answers before approval. It does not update the committed belief or canonical priority.", className="muted"),
            html.Details([html.Summary("Assumptions and expected answers"), html.P(prospective.get("assumption_source", "")),
                html.Ul([html.Li(f"{a['answer']}: probability {a['probability']:.2%}; posterior {a['posterior']:.2%}" if a.get("posterior") is not None else f"{a['answer']}: posterior unavailable") for a in prospective.get("answers", [])])])], className="panel"))
    if eig:
        content += [html.Div([html.Strong(f"{eig['eig_bits']:.6f} bits", className="eig-value"), html.P("Initial binary verification scenario · not a score weight")], className="panel"),
                    html.P(eig.get("assumption_source", ""), className="muted"),
                    html.Table([html.Thead(html.Tr([html.Th("Expected answer"), html.Th("Answer probability"), html.Th("Posterior")])),
                                html.Tbody([html.Tr([html.Td(x["answer"]), html.Td(f"{x['probability']:.2%}"), html.Td(f"{x['posterior']:.2%}" if x.get("posterior") is not None else "Unavailable")]) for x in eig.get("answers", [])])], className="data-table")]
    else:
        content.append(empty("EIG unavailable: required probability parameters have not been supplied."))
    candidates = analysis.get("eig_candidates", [])
    if len(candidates) > 1:
        chart = go.Figure(go.Bar(x=[x["label"] for x in candidates], y=[x["eig_bits"] for x in candidates], marker_color="#145e63"))
        chart.update_yaxes(title_text="Information gain (bits)", rangemode="tozero")
        content += [html.H3("Supplied evidence-model comparison"),
                    html.P("Each bar uses its stage-specific prior and explicit likelihoods. These are evidence scenario models, not invented EIG values for every DD question.", className="muted"),
                    dcc.Graph(id="eig-chart", figure=figure_layout(chart, height=340), config={"displayModeBar": False}),
                    html.Div([html.Details([html.Summary(x["label"]), html.P(f"EIG: {x['eig_bits']:.6f} bits · Prior: {x['prior']:.4f}"),
                        html.P(x.get("assumption_source", "")),
                        html.Ul([html.Li(f"{a['answer']}: probability {a['probability']:.2%}; posterior {a['posterior']:.2%}" if a.get("posterior") is not None else f"{a['answer']}: probability {a['probability']:.2%}; posterior unavailable") for a in x.get("answers", [])])], className="assumption-card") for x in candidates])]
    content += [html.H3("Adaptive ranking comparison"), change_grid(view), html.H3("Financial materiality"),
                html.P("Qualitative financial driver mappings are taken from the existing DD questions. No numerical valuation sensitivity is fabricated.", className="muted"),
                html.Div([badge(driver) for driver in sorted({q.get("financial_driver", "") for q in view.get("questions", [])})], className="badge-row")]
    return html.Div(content)


def render_export(view):
    summary = view.get("summary", {})
    return html.Div([html.H2("Screening memo & DD export"),
        html.P("Export source-grounded findings, unresolved risks and review history for preliminary investment screening.", className="muted"),
        html.Div([html.H3("Approval scope"), html.P(f"Snapshot: {view.get('snapshot_id')}"),
                  html.P(f"Revision {view.get('revision')} · {summary.get('open_questions', 0)} open DD questions · {summary.get('evidence', 0)} evidence records"),
                  html.P("Unapproved findings retain their draft status. These files are synthetic preliminary screening documents, not completed financial due diligence reports."),
                  html.P("Changing the snapshot or document format clears your export approval.", className="muted")], className="panel"),
    ])


def render_page(page, view):
    return {"overview": render_overview, "evidence": render_evidence, "thesis": render_thesis,
            "questions": render_questions, "review": render_review, "analytics": render_analytics,
            "export": render_export}.get(page, render_overview)(view)


def render_span(span):
    locator = span.get("locator", {})
    quote = span.get("quote", "")
    return html.Div([
        html.Div([html.Strong(span.get("filename", span.get("document_id", ""))), badge(span.get("source_origin", ""))], className="source-heading"),
        html.Div(f"Document v{span.get('document_version', 1)} · {span.get('id', '')}", className="identifier"),
        html.Div(human(locator), className="locator"),
        html.Blockquote([span.get("prefix", ""), html.Mark(quote), span.get("suffix", "")], className="source-excerpt"),
        html.Div([badge(span.get("locator_status"), "Locator: "), badge(span.get("extraction_method"), "Extraction: ")], className="badge-row"),
        html.Details([html.Summary("Source integrity"), html.Div(span.get("text_sha256", ""), className="hash-value")]),
    ], className="source-span")


def render_inspection(detail):
    if not detail:
        return empty("Select a record to inspect its original source.")
    metadata = detail.get("metadata", {})
    spans = detail.get("spans", [])
    source_content = [render_span(spans[0])] if spans else [empty("This record has no source span; it is not presented as a verified source quotation.")]
    if len(spans) > 1:
        source_content.append(html.Details([html.Summary(f"Additional source passages ({len(spans) - 1})"), *[render_span(span) for span in spans[1:]]], className="additional-sources"))
    question = next((q for q in detail.get("questions", []) if q.get("id") == detail.get("id")), None)
    score_detail = None
    if question is not None:
        score_detail = html.Div([html.Strong("Canonical priority rationale"),
            html.P(f"Priority {question.get('score', '—')} = 9 × {question.get('gap', '—')} gap + 8 × {question.get('materiality_score', '—')} materiality + 3 × {question.get('obtainability_score', '—')} obtainability"),
            html.P(human(question.get("reason_codes", []))), html.Strong("Requested verification artifact"), html.P(question.get("request_text", "")),
            html.Details([html.Summary("Input rationale and outstanding requirements"), html.P(question.get("materiality", {}).get("rationale", "")),
                html.P(question.get("obtainability", {}).get("rationale", "")), html.Ul([html.Li(item) for item in question.get("outstanding_requirements", [])])])], className="callout")
    return html.Div([
        html.Div(human(detail.get("kind", "source")), className="eyebrow"), html.H3(detail.get("title", detail.get("id", ""))),
        html.Div(detail.get("id", ""), className="identifier"),
        html.Div([badge(metadata[key], human(key) + ": ") for key in ("support_status", "truth_status", "review_status", "verification_level", "provenance") if key in metadata], className="badge-row"),
        score_detail,
        html.Details([html.Summary("Record details"), html.Dl([html.Div([html.Dt(human(key)), html.Dd(human(value))], className="metadata-row") for key, value in metadata.items()])]),
        html.Div(source_content),
        html.Div([html.H4("Related claims"), *[html.P(c.get("statement", c.get("id", ""))) for c in detail.get("claims", [])]]) if detail.get("claims") else None,
        html.Div([html.H4("Related DD questions"), *[html.P(q.get("issue", q.get("id", ""))) for q in detail.get("questions", [])]]) if detail.get("questions") else None,
    ])


def render_preview(preview):
    if not preview:
        return empty("No reviewable event. Reset to begin a new branch.")
    event = preview.get("event", {})
    note = preview.get("note") or event.get("analyst_note", "")
    spans = preview.get("spans", [])
    return html.Div([
        badge("preview_approval_required"), html.P(note),
        html.P(("Top 3 unchanged; lower-ranked requests may change." if not preview.get("top3_changed", preview.get("ranking_changed")) else "Top 3 priorities change on approval.") if preview.get("ranking_changed") else "The ranking is unchanged by this evidence; the underlying evidence state may still change.", className="preview-result"),
        html.Details([html.Summary(f"Original source · {len(spans)} passages"), *[render_span(span) for span in spans]]),
        html.Details([html.Summary("Before / after priority preview"),
                      html.Div("Before: " + "; ".join(preview.get("before_top3", []))),
                      html.Div("After: " + "; ".join(preview.get("after_top3", [])))]),
    ])

"""Presentation callbacks call trusted services; browser data is never evidence."""
from __future__ import annotations

import base64
from dash import Input, Output, State, ctx, html, no_update
from flask import session

from orion.services.workspace import ActorContext
from .layout import empty, metrics, question_columns, render_inspection, render_page, render_preview, render_top3
from .i18n import text
from .visuals import score_waterfall


def _session_id():
    return session["orion_session"]


def safe_error(error):
    code = getattr(error, "code", "REQUEST_REJECTED")
    messages = {
        "REVISION_CONFLICT": "스냅샷이 변경되었습니다. 현재 리비전을 검토한 뒤 다시 시도하세요.",
        "INVALID_TOKEN": "작업 영역 토큰이 유효하지 않거나 다른 브라우저 세션에 속합니다. 데모를 초기화하세요.",
        "TOKEN_INVALID": "작업 영역 토큰이 유효하지 않거나 다른 브라우저 세션에 속합니다. 데모를 초기화하세요.",
        "EVENT_NOT_AVAILABLE": "현재 검토 분기에서는 이 이벤트를 사용할 수 없습니다.",
        "DEMO_ACTION_NOT_ALLOWED": "합성 자료 데모에서는 이 작업을 허용하지 않습니다.",
        "IDEMPOTENCY_CONFLICT": "이 검토 요청은 이전 결정과 충돌합니다.",
        "EXPORT_APPROVAL_REQUIRED": "다운로드 전에 현재 스냅샷을 검토하고 승인하세요.",
    }
    return f"{code}: {messages.get(code, '요청이 거부되었습니다. 선택한 이벤트, 검토 의견, 스냅샷을 확인하거나 데모를 초기화하세요.')}"


def register_callbacks(app, workspace, exports):
    from .studio_callbacks import register_studio
    register_studio(app, workspace)
    from .fdd import register as register_fdd
    register_fdd(app, workspace)
    from .fdd_callbacks import register_finance
    register_finance(app, workspace)
    @app.callback(Output("score-waterfall-content", "children"),
                  Input("score-question-selector", "value", allow_optional=True),
                  Input("workspace-token", "data"))
    def selected_score(question_id, token):
        if not question_id or not token:
            return no_update
        try:
            view = workspace.view(token, _session_id())
            question = next((q for q in view["questions"] if q["id"] == question_id), None)
            return score_waterfall(question)
        except Exception as error:
            return empty(safe_error(error))

    @app.callback(Output("workbench", "className"), Output("inspector-toggle", "children"),
                  Output("inspector-toggle", "aria-expanded"), Input("inspector-toggle", "n_clicks"))
    def toggle_inspector(clicks):
        collapsed = (clicks or 0) % 2 == 1
        return ("workbench inspector-collapsed" if collapsed else "workbench",
                "원문 패널 열기" if collapsed else "원문 패널 접기", "false" if collapsed else "true")

    @app.callback(
        Output("workspace-token", "data"), Output("status-live-region", "children"),
        Input("deal-selector", "value"), Input("reset-demo", "n_clicks"),
        Input("review-approve", "n_clicks"), Input("review-reject", "n_clicks"),
        State("workspace-token", "data"), State("workspace-revision", "data"),
        State("event-selector", "value"), State("review-reason", "value"),
        running=[(Output("review-approve", "disabled"), True, False),
                 (Output("review-reject", "disabled"), True, False)],
    )
    def dispatch(case_id, _reset, _approve, _reject, token, revision, event_id, reason):
        trigger = ctx.triggered_id
        try:
            sid = _session_id()
            if trigger in (None, "deal-selector", "reset-demo") or not token:
                return workspace.new(case_id, sid), "초기 합성 스냅샷을 불러왔습니다. 업데이트 승인 전에 원문 증빙을 검토하세요."
            action = {"review-approve": "approve", "review-reject": "reject"}.get(trigger)
            if action is None:
                return no_update, no_update
            if not event_id:
                return no_update, "검토 가능한 이벤트가 없습니다. 데모를 초기화하여 새 검토 분기를 시작하세요."
            result = workspace.act(token, sid, action=action, event_id=event_id,
                                   expected_revision=revision,
                                   idempotency_key=f"web:{case_id}:{event_id}:{action}",
                                   reason=reason)
            return result["token"], text(result.get("message", "검토 작업이 완료되었습니다."))
        except Exception as error:
            return no_update, safe_error(error)

    @app.callback(
        Output("deal-heading", "children"), Output("deal-description", "children"),
        Output("snapshot-summary", "children"), Output("top3-list", "children"),
        Output("page-content", "children"), Output("document-selector", "options"),
        Output("document-selector", "value"), Output("document-summary", "children"),
        Output("event-selector", "options"), Output("event-selector", "value"),
        Output("export-controls", "style"), Output("workspace-revision", "data"), Output("workspace-snapshot", "data"),
        Output("rendered-workspace-token", "data"),
        Output("dashboard-metrics", "children"),
        Input("workspace-token", "data"), Input("workspace-tabs", "value"),
        State("document-selector", "value"), State("event-selector", "value"),
    )
    def render(token, page, selected_document, selected_event):
        if not token:
            return ("투자 대상을 불러오는 중…", "", "", empty("검증된 우선순위를 불러오는 중…"), empty("검증된 작업 영역을 불러오는 중…"),
                    [], None, "", [], None, {"display": "none"}, None, None, None, None)
        try:
            view = workspace.view(token, _session_id())
            docs = view.get("documents", [])
            document_options = [{"label": d.get("title", d.get("filename", d["id"])), "value": d["id"]} for d in docs]
            doc_ids = {d["id"] for d in docs}
            document = selected_document if selected_document in doc_ids else (docs[0]["id"] if docs else None)
            events = view.get("events", [])
            event_options = [{"label": f"{text(e.get('label', e['id']))} · {text(e.get('status', 'pending'))}",
                              "value": e["id"], "disabled": not e.get("available", False)} for e in events]
            available = [e["id"] for e in events if e.get("available")]
            event = selected_event if selected_event in available else (available[0] if available else None)
            summary = [html.Strong(f"리비전 {view['revision']}"), html.Span(f"단계 T{view.get('stage', 0)}"),
                       html.Span(view.get("snapshot_id", ""), className="identifier")]
            return (view["deal"]["name"], view["deal"].get("business_model", ""), summary, render_top3(view),
                    render_page(page, view), document_options, document,
                    f"{len(docs)}개 원문 문서 사용 가능 · 후속 문서는 검토 대기 상태 유지", event_options, event,
                    {"display": "block" if page == "export" else "none"}, view["revision"], view["snapshot_id"], token, metrics(view))
        except Exception as error:
            return ("작업 영역을 사용할 수 없습니다", "", "", empty("검증된 상태를 사용할 수 없습니다."), empty(safe_error(error)),
                    [], None, "", [], None, {"display": "none"}, None, None, None, None)

    @app.callback(
        Output("source-inspector", "children"),
        Input("document-selector", "value"), Input("workspace-token", "data"),
        Input("evidence-grid", "selectedRows", allow_optional=True),
        Input("claim-grid", "selectedRows", allow_optional=True),
        Input("question-grid", "selectedRows", allow_optional=True),
        Input("thesis-grid", "selectedRows", allow_optional=True),
        Input("evidence-grid", "cellClicked", allow_optional=True),
        Input("claim-grid", "cellClicked", allow_optional=True),
        Input("question-grid", "cellClicked", allow_optional=True),
        Input("thesis-grid", "cellClicked", allow_optional=True),
    )
    def inspect(document_id, token, evidence, claims, questions, theses, evidence_click, claim_click, question_click, thesis_click):
        if not token:
            return empty("자료를 선택해 원문 구간을 확인하세요.")
        trigger = ctx.triggered_id
        kind, item_id = "document", document_id
        sources = {
            "evidence-grid": ("evidence", evidence, evidence_click), "claim-grid": ("claim", claims, claim_click),
            "question-grid": ("question", questions, question_click), "thesis-grid": ("thesis", theses, thesis_click),
        }
        if trigger in sources:
            kind, rows, click = sources[trigger]
            prop = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
            if prop.endswith("cellClicked") and click:
                item_id = click.get("rowId") or click.get("data", {}).get("id")
            else:
                item_id = rows[0].get("id") if rows else None
            if not item_id:
                return no_update
        if not item_id:
            return empty("선택한 원문이 없습니다.")
        try:
            return render_inspection(workspace.inspect(token, _session_id(), kind, item_id))
        except Exception as error:
            return empty(safe_error(error))

    @app.callback(Output("event-preview", "children"), Input("event-selector", "value"), Input("workspace-token", "data"))
    def preview(event_id, token):
        if not event_id or not token:
            return empty("검토할 이벤트가 없습니다. 반려된 분기는 데모 초기화 후 다시 시도하세요.")
        try:
            return render_preview(workspace.preview(token, _session_id(), event_id))
        except Exception as error:
            return empty(safe_error(error))

    @app.callback(Output("export-confirm", "value"), Input("workspace-token", "data"), Input("export-format", "value"))
    def clear_export_approval(_token, _format):
        return []

    @app.callback(Output("export-approval", "data"), Output("export-approval-status", "children"),
                  Input("export-confirm", "value"), Input("workspace-token", "data"), Input("export-format", "value"),
                  State("workspace-revision", "data"), State("workspace-snapshot", "data"), State("rendered-workspace-token", "data"),
                  prevent_initial_call=True)
    def approve_export(confirmation, token, format_name, displayed_revision, displayed_snapshot, rendered_token):
        # A state/format change invalidates consent even before the checkbox's
        # separate clearing callback has reached the browser. Only a fresh
        # checkbox action can create a signed approval of a displayed snapshot.
        if ctx.triggered_id != "export-confirm" or confirmation != ["approved"]:
            return None, ""
        try:
            sid = _session_id()
            state, resolver = workspace.validated_state(token, sid)
            if token != rendered_token or state.state_revision != displayed_revision or state.head_snapshot_id != displayed_snapshot:
                return None, "스냅샷을 업데이트하는 중입니다. 표시된 스냅샷을 검토한 뒤 승인을 다시 체크하세요."
            approval = exports.approve(state, resolver, actor=ActorContext("actor_web_reviewer", "reviewer"),
                                       session_id=sid, format=format_name,
                                       reason="Analyst explicitly reviewed the displayed synthetic snapshot and approved this preliminary screening export.")
            return {"receipt": approval, "workspace_token": token, "format": format_name}, f"표시된 리비전 {displayed_revision}의 내보내기가 승인되었습니다. 다운로드할 수 있습니다."
        except Exception as error:
            return None, safe_error(error)

    @app.callback(Output("export-download", "data"), Output("export-status", "children"),
                  Input("export-button", "n_clicks"), State("export-confirm", "value"),
                  State("export-format", "value"), State("workspace-token", "data"),
                  State("export-approval", "data"),
                  prevent_initial_call=True)
    def export_file(_click, confirmation, format_name, token, approval):
        if confirmation != ["approved"] or not approval:
            return no_update, "먼저 현재 스냅샷을 검토하고 내보내기 승인란을 체크하세요."
        if not isinstance(approval, dict) or approval.get("workspace_token") != token or approval.get("format") != format_name:
            return no_update, "작업 영역이나 형식이 변경되었습니다. 현재 내보내기를 다시 검토하고 승인하세요."
        try:
            sid = _session_id()
            state, resolver = workspace.validated_state(token, sid)
            artifact = exports.generate(state, resolver, approval.get("receipt"), session_id=sid, format=format_name)
            content = artifact.content
            if isinstance(content, str):
                content = content.encode("utf-8")
            return {"content": base64.b64encode(content).decode("ascii"), "filename": artifact.filename,
                    "type": artifact.mime_type, "base64": True}, f"검토한 스냅샷의 리비전 {state.state_revision} 내보내기 완료: {artifact.filename}."
        except Exception as error:
            return no_update, safe_error(error)

    @app.callback(Output("source-download", "data"), Output("source-download-status", "children"),
                  Input("source-download-button", "n_clicks"), State("document-selector", "value"),
                  State("workspace-token", "data"), prevent_initial_call=True)
    def download_source(_click, document_id, token):
        if not document_id or not token:
            return no_update, "사용 가능한 원문 문서를 선택하세요."
        try:
            filename, content = workspace.document_bytes(token, _session_id(), document_id)
            return {"content": base64.b64encode(content).decode("ascii"), "filename": filename,
                    "type": "application/octet-stream", "base64": True}, "원문을 검증하고 다운로드했습니다."
        except Exception as error:
            return no_update, safe_error(error)

    @app.callback(Output("question-grid", "columnDefs"), Input("question-columns", "value", allow_optional=True), prevent_initial_call=True)
    def choose_columns(selected):
        return question_columns(selected if isinstance(selected, list) else [])

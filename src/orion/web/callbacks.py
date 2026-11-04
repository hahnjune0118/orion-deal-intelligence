"""Presentation callbacks call trusted services; browser data is never evidence."""
from __future__ import annotations

import base64
from dash import Input, Output, State, ctx, html, no_update
from flask import session

from orion.services.workspace import ActorContext
from .layout import empty, question_columns, render_inspection, render_page, render_preview, render_top3


def _session_id():
    return session["orion_session"]


def safe_error(error):
    code = getattr(error, "code", "REQUEST_REJECTED")
    messages = {
        "REVISION_CONFLICT": "The snapshot changed. Review the current revision and try again.",
        "INVALID_TOKEN": "The workspace token is invalid or belongs to another browser session. Reset the demo.",
        "TOKEN_INVALID": "The workspace token is invalid or belongs to another browser session. Reset the demo.",
        "EVENT_NOT_AVAILABLE": "This event is not available on the current review branch.",
        "DEMO_ACTION_NOT_ALLOWED": "This action is not allowed in the synthetic demo.",
        "IDEMPOTENCY_CONFLICT": "This review request conflicts with an earlier decision.",
        "EXPORT_APPROVAL_REQUIRED": "Review and approve the current snapshot before downloading.",
    }
    return f"{code}: {messages.get(code, 'The request was rejected. Check the selected event, review note and snapshot, or reset the demo.')}"


def register_callbacks(app, workspace, exports):
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
                return workspace.new(case_id, sid), "Initial synthetic snapshot loaded. Review source evidence before approving an update."
            action = {"review-approve": "approve", "review-reject": "reject"}.get(trigger)
            if action is None:
                return no_update, no_update
            if not event_id:
                return no_update, "No event is available. Reset the demo to start another review branch."
            result = workspace.act(token, sid, action=action, event_id=event_id,
                                   expected_revision=revision,
                                   idempotency_key=f"web:{case_id}:{event_id}:{action}",
                                   reason=reason)
            return result["token"], result.get("message", "Review action completed.")
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
        Input("workspace-token", "data"), Input("workspace-tabs", "value"),
        State("document-selector", "value"), State("event-selector", "value"),
    )
    def render(token, page, selected_document, selected_event):
        if not token:
            return ("Loading opportunity…", "", "", empty("Loading validated priorities…"), empty("Loading validated workspace…"),
                    [], None, "", [], None, {"display": "none"}, None, None, None)
        try:
            view = workspace.view(token, _session_id())
            docs = view.get("documents", [])
            document_options = [{"label": d.get("title", d.get("filename", d["id"])), "value": d["id"]} for d in docs]
            doc_ids = {d["id"] for d in docs}
            document = selected_document if selected_document in doc_ids else (docs[0]["id"] if docs else None)
            events = view.get("events", [])
            event_options = [{"label": f"{e.get('label', e['id'])} · {e.get('status', 'pending')}",
                              "value": e["id"], "disabled": not e.get("available", False)} for e in events]
            available = [e["id"] for e in events if e.get("available")]
            event = selected_event if selected_event in available else (available[0] if available else None)
            summary = [html.Strong(f"Revision {view['revision']}"), html.Span(f"Stage T{view.get('stage', 0)}"),
                       html.Span(view.get("snapshot_id", ""), className="identifier")]
            return (view["deal"]["name"], view["deal"].get("business_model", ""), summary, render_top3(view),
                    render_page(page, view), document_options, document,
                    f"{len(docs)} available source documents · future documents remain staged", event_options, event,
                    {"display": "block" if page == "export" else "none"}, view["revision"], view["snapshot_id"], token)
        except Exception as error:
            return ("Workspace unavailable", "", "", empty("Validated state unavailable."), empty(safe_error(error)),
                    [], None, "", [], None, {"display": "none"}, None, None, None)

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
            return empty("Select a source to inspect its original passage.")
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
            return empty("No source selected.")
        try:
            return render_inspection(workspace.inspect(token, _session_id(), kind, item_id))
        except Exception as error:
            return empty(safe_error(error))

    @app.callback(Output("event-preview", "children"), Input("event-selector", "value"), Input("workspace-token", "data"))
    def preview(event_id, token):
        if not event_id or not token:
            return empty("No reviewable event. A rejected branch requires Reset demo before retrying.")
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
                return None, "The snapshot is still updating. Review the displayed snapshot and check approval again."
            approval = exports.approve(state, resolver, actor=ActorContext("actor_web_reviewer", "reviewer"),
                                       session_id=sid, format=format_name,
                                       reason="Analyst explicitly reviewed the displayed synthetic snapshot and approved this preliminary screening export.")
            return {"receipt": approval, "workspace_token": token, "format": format_name}, f"Export approved for displayed revision {displayed_revision}. Ready to download."
        except Exception as error:
            return None, safe_error(error)

    @app.callback(Output("export-download", "data"), Output("export-status", "children"),
                  Input("export-button", "n_clicks"), State("export-confirm", "value"),
                  State("export-format", "value"), State("workspace-token", "data"),
                  State("export-approval", "data"),
                  prevent_initial_call=True)
    def export_file(_click, confirmation, format_name, token, approval):
        if confirmation != ["approved"] or not approval:
            return no_update, "Review the current snapshot and check the export approval box first."
        if not isinstance(approval, dict) or approval.get("workspace_token") != token or approval.get("format") != format_name:
            return no_update, "The workspace or format changed. Review and approve the current export again."
        try:
            sid = _session_id()
            state, resolver = workspace.validated_state(token, sid)
            artifact = exports.generate(state, resolver, approval.get("receipt"), session_id=sid, format=format_name)
            content = artifact.content
            if isinstance(content, str):
                content = content.encode("utf-8")
            return {"content": base64.b64encode(content).decode("ascii"), "filename": artifact.filename,
                    "type": artifact.mime_type, "base64": True}, f"Export generated for the reviewed snapshot at revision {state.state_revision}: {artifact.filename}."
        except Exception as error:
            return no_update, safe_error(error)

    @app.callback(Output("source-download", "data"), Output("source-download-status", "children"),
                  Input("source-download-button", "n_clicks"), State("document-selector", "value"),
                  State("workspace-token", "data"), prevent_initial_call=True)
    def download_source(_click, document_id, token):
        if not document_id or not token:
            return no_update, "Select an available source document."
        try:
            filename, content = workspace.document_bytes(token, _session_id(), document_id)
            return {"content": base64.b64encode(content).decode("ascii"), "filename": filename,
                    "type": "application/octet-stream", "base64": True}, "Original source verified and downloaded."
        except Exception as error:
            return no_update, safe_error(error)

    @app.callback(Output("question-grid", "columnDefs"), Input("question-columns", "value", allow_optional=True), prevent_initial_call=True)
    def choose_columns(selected):
        return question_columns(selected if isinstance(selected, list) else [])

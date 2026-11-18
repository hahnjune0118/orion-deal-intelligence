"""Review-only workspace actions against trusted server views."""
from dash import ALL, Input, Output, State, ctx, html, no_update
from flask import session

from orion.services.draft_review import DraftReview, DraftReviewError
from . import studio
from .i18n import text
from .layout import render_inspection


def register_studio(app, workspace):
    drafts = DraftReview(app.server.secret_key)

    @app.callback(Output('studio-source-search', 'value'), Output('studio-source-type', 'value'), Input('deal-selector', 'value'))
    def reset_library_filter(_case):
        return '', 'all'

    def current(token):
        sid = session["orion_session"]
        return sid, workspace.view(token, sid)

    @app.callback(Output("studio-side-tabs", "className"), Input("studio-side-tabs", "value"))
    def side_mode(mode):
        return "studio-side-tabs mode-" + (mode if mode in {"settings", "editor", "source"} else "settings")

    @app.callback(Output("studio-draft-token", "data"), Output("studio-message", "children"),
                  Input("workspace-token", "data"), Input("studio-save", "n_clicks"), Input("studio-approve", "n_clicks"),
                  Input("studio-reject", "n_clicks"), Input("studio-approve-selected", "n_clicks"), Input("studio-save-memo", "n_clicks"),
                  State("studio-draft-token", "data"), State("studio-active-question", "value"),
                  State("studio-edit-issue", "value"), State("studio-edit-request", "value"), State("studio-edit-note", "value"),
                  State("studio-question-selection", "value"), State("studio-memo", "value"))
    def update(token, _save, _approve, _reject, _batch, _memo, draft_token, active, issue, request, note, selected, memo):
        if not token:
            return no_update, no_update
        try:
            sid, view = current(token)
            if ctx.triggered_id in {None, "workspace-token"}:
                return drafts.sign(drafts.read(None, token, sid, view)), ""
            draft = drafts.read(draft_token, token, sid, view)
            action = {"studio-save": "edit", "studio-approve": "approve", "studio-reject": "reject",
                      "studio-approve-selected": "approve_selected", "studio-save-memo": "memo"}[ctx.triggered_id]
            if action in {"approve", "reject"} or (action == "approve_selected" and active in (selected or [])):
                q = next((q for q in view["questions"] if q["id"] == active), None)
                saved = draft["edits"].get(active, {})
                if q and (issue != saved.get("issue", q["issue"]) or request != saved.get("request_text", q["request_text"])):
                    raise DraftReviewError("입력한 수정 내용을 먼저 저장한 뒤 검토 상태를 변경하세요.")
            result = drafts.update(draft, view, action=action, question_id=active, issue=issue or "", request_text=request or "",
                                   note=note or "", selected=selected or [], memo=memo or "")
            messages = {"edit": "수정 초안을 저장했습니다. 이전 검토 완료 표시는 해제됩니다.", "approve": "이 질문 초안을 검토 완료로 표시했습니다.",
                        "reject": "이 질문 초안에 제외 표시를 남겼습니다.", "approve_selected": "선택한 질문 초안을 검토 완료로 표시했습니다.",
                        "memo": "현재 작업 영역의 참고 메모를 저장했습니다."}
            return drafts.sign(result), messages[action]
        except DraftReviewError as error:
            return no_update, str(error)
        except Exception:
            return no_update, "초안을 저장할 수 없습니다. 현재 투자 건과 선택한 질문을 확인하세요."

    @app.callback(Output("studio-source-list", "children"), Output("studio-theses", "children"),
                  Output("studio-question-selection", "options"), Output("studio-result-count", "children"),
                  Output("studio-question-selection", "className"), Output("studio-list-heading", "children"),
                  Output("studio-list-empty", "children"), Output("studio-analysis-summary", "children"),
                  Output("studio-attention", "children"), Output("studio-history", "children"),
                  Output("studio-active-question", "options"), Output("studio-active-question", "value"),
                  Output("studio-claims-heading", "children"), Output("studio-linked-claims", "children"),
                  Input("workspace-token", "data"), Input("studio-draft-token", "data"), Input("studio-source-search", "value"),
                  Input("studio-source-type", "value"), Input("document-selector", "value"), Input("studio-types", "value"), Input("studio-question-search", "value"),
                  Input("studio-kpi", "value"), Input("studio-view", "value"), State("studio-active-question", "value"))
    def render(token, draft_token, source_query, file_type, document, categories, query, kpi, mode, active):
        if not token:
            return (no_update,) * 14
        try:
            sid, view = current(token)
            try:
                draft = drafts.read(draft_token, token, sid, view)
            except DraftReviewError:
                draft = drafts.read(None, token, sid, view)
            rows = studio.filtered_questions(view, categories, query, "first" in (kpi or []))
            options = [{"label": f"Q{q['rank']:02} · {draft['edits'].get(q['id'], {}).get('issue', q['issue'])}" if q.get("rank") is not None else q["issue"], "value": q["id"]} for q in view["questions"]]
            active = active if active in {q["id"] for q in view["questions"]} else (view["questions"][0]["id"] if view["questions"] else None)
            actions = {"edit": "초안 수정", "approve": "검토 완료", "approve_selected": "선택 질문 검토 완료", "reject": "제외 표시", "memo": "메모 저장"}
            history = [html.Div([html.Span(f"{item['sequence']:02}", className="studio-history-sequence"), html.Strong(actions[item["action"]]),
                                 html.Small(f"질문 {len(item['question_ids'])}개" if item["question_ids"] else "참고 메모"),
                                 html.Details([html.Summary("수정 전후"), html.P("이전: " + item["before"]["issue"]), html.P("변경: " + item["after"]["issue"])]) if item.get("before") else None], className="studio-history-item") for item in reversed(draft["history"])]
            return (studio.source_list(view, source_query, document, file_type), studio.thesis_cards(view), studio.question_options(view, rows, draft),
                    f"{len(rows)} / {len(view['questions'])}", "studio-question-list mode-" + (mode if mode in {"list", "matrix", "checklist"} else "list"),
                    [html.Span("공식 순위 · 질문 / 요청 자료"), html.Span("재무 요인"), html.Span("점수"), html.Span("초안 검토") ] if mode == "matrix" else [],
                    "표시할 질문이 없습니다. 질문 유형이나 검색어를 변경하세요." if not rows else "", studio.analysis_summary(view, draft), studio.attention(view),
                    history or html.P("아직 저장된 검토 작업이 없습니다.", className="studio-help"), options, active,
                    f"연결된 핵심 주장 · {len(view['claims'])}개", [html.Div([html.Span(str(i + 1)), html.P(c["statement"])], className="studio-linked-claim") for i, c in enumerate(view["claims"])])
        except Exception:
            return (no_update,) * 14

    @app.callback(Output("studio-edit-issue", "value"), Output("studio-edit-request", "value"), Output("studio-edit-note", "value"),
                  Output("studio-editor-meta", "children"), Input("studio-active-question", "value"), Input("studio-draft-token", "data"), State("workspace-token", "data"))
    def edit_form(active, draft_token, token):
        if not token or not active:
            return "", "", "", "질문을 선택하세요."
        try:
            sid, view = current(token)
            draft = drafts.read(draft_token, token, sid, view)
            q = next(q for q in view["questions"] if q["id"] == active)
            edited = draft["edits"].get(active, {})
            decision = draft["decisions"].get(active, {})
            return edited.get("issue", q["issue"]), edited.get("request_text", q["request_text"]), decision.get("note", ""), [
                html.Span(f"공식 순위 {q['rank']} · 점수 {q['score']}", className="studio-tag"),
                html.Span(text(q["financial_driver"]), className="studio-tag"),
                html.Details([html.Summary("원본 질문 · 판정 기준"), html.P(q["issue"]),
                              html.Ul([html.Li(r.get("label", r.get("key", ""))) for r in q["requirements"]])])]
        except Exception:
            return "", "", "", "현재 작업 영역의 질문을 선택하세요."

    @app.callback(Output("studio-memo", "value"), Input("workspace-tabs", "value"), Input("workspace-token", "data"), State("studio-draft-token", "data"))
    def load_memo(page, token, draft_token):
        if ctx.triggered_id == "workspace-token":
            return ""
        if page != "studio" or not token:
            return no_update
        try:
            sid, view = current(token)
            return drafts.read(draft_token, token, sid, view)["memo"]
        except Exception:
            return ""

    @app.callback(Output("studio-question-selection", "value"), Input("studio-select-visible", "n_clicks"),
                  Input("studio-clear-selection", "n_clicks"), Input("workspace-token", "data"),
                  State("studio-types", "value"), State("studio-question-search", "value"), State("studio-kpi", "value"))
    def select(_all, _clear, token, categories, query, kpi):
        if ctx.triggered_id != "studio-select-visible" or not token:
            return []
        _, view = current(token)
        return [q["id"] for q in studio.filtered_questions(view, categories, query, "first" in (kpi or []))]

    @app.callback(Output("studio-selection-count", "children"), Input("studio-question-selection", "value"), State("workspace-token", "data"))
    def selection_count(selected, token):
        if not token:
            return "질문을 선택하세요"
        try:
            _, view = current(token)
            count = len(set(selected or []) & {q["id"] for q in view["questions"]})
            return f"{count}개 선택 · 필터로 숨겨진 선택도 포함"
        except Exception:
            return "질문을 선택하세요"

    @app.callback(Output("studio-active-question", "value", allow_duplicate=True),
                  Output("studio-side-tabs", "value", allow_duplicate=True), Input("studio-review-selection", "n_clicks"),
                  State("studio-question-selection", "value"), State("workspace-token", "data"), prevent_initial_call=True)
    def review_selected(_click, selected, token):
        if not _click or not selected or not token:
            return no_update, no_update
        _, view = current(token)
        ids = {q["id"] for q in view["questions"]}
        chosen = next((identifier for identifier in selected if identifier in ids), None)
        return (chosen, "editor") if chosen else (no_update, no_update)

    @app.callback(Output("document-selector", "value", allow_duplicate=True), Output("studio-side-tabs", "value", allow_duplicate=True),
                  Output("fw-inspection", "value", allow_duplicate=True),
                  Input({"type": "studio-document", "document": ALL}, "n_clicks"), State("workspace-token", "data"), prevent_initial_call=True)
    def choose_document(_clicks, token):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or not ctx.triggered[0].get("value") or not token:
            return no_update, no_update, no_update
        _, view = current(token)
        identifier = trigger["document"]
        return (identifier, "source", "native:" + identifier) if identifier in {d["id"] for d in view["documents"]} else (no_update, no_update, no_update)

    @app.callback(Output("source-inspector", "children", allow_duplicate=True), Output("studio-side-tabs", "value", allow_duplicate=True),
                  Input("studio-open-source", "n_clicks"), State("studio-active-question", "value"), State("workspace-token", "data"), prevent_initial_call=True)
    def question_source(click, active, token):
        if not click or not active or not token:
            return no_update, no_update
        sid, view = current(token)
        if active not in {q["id"] for q in view["questions"]}:
            return no_update, no_update
        return render_inspection(workspace.inspect(token, sid, "question", active)), "source"

    @app.callback(Output("studio-download", "data"), Output("studio-message", "children", allow_duplicate=True),
                  Input("studio-export-draft", "n_clicks"), Input("studio-export-reviewed", "n_clicks"),
                  State("studio-question-selection", "value"), State("studio-draft-token", "data"), State("workspace-token", "data"), prevent_initial_call=True)
    def export(_draft, _reviewed, selected, draft_token, token):
        if not token:
            return no_update, "작업 영역을 먼저 불러오세요."
        try:
            sid, view = current(token)
            draft = drafts.read(draft_token, token, sid, view)
            reviewed = ctx.triggered_id == "studio-export-reviewed"
            content = drafts.export(draft, view, selected or [], reviewed_only=reviewed)
            return {"content": content, "filename": "orion_reviewed_question_drafts.csv" if reviewed else "orion_question_drafts.csv", "type": "text/csv"}, "선택 질문의 검토용 CSV를 저장했습니다. 공식 보고서 승인은 별도입니다."
        except DraftReviewError as error:
            return no_update, str(error)
        except Exception:
            return no_update, "내보내기를 완료할 수 없습니다. 현재 투자 건과 질문을 확인하세요."

"""Document-centered review workspace. No model calls or canonical mutations."""
from collections import defaultdict
import re

from dash import dcc, html

from .i18n import text

TYPES = [("core", "핵심 검증"), ("finance", "재무"), ("business", "사업"), ("customer", "고객"), ("risk", "리스크")]


def question_tags(question, claims):
    driver = question.get("financial_driver", "")
    tags = {"core"}
    tags.add("customer" if driver in {"customer_concentration", "revenue_quality"} else "finance")
    if driver in {"unit_economics", "capex"}:
        tags.add("business")
    if claims.get(question.get("claim_id"), {}).get("support_status") in {"missing", "partial", "contradicted"}:
        tags.add("risk")
    return tags


def is_kpi(question):
    return bool(re.search(r"\b(arr|nrr|revenue|cash|cost|contribution|margin|retention|growth|collection)\b", question.get("issue", "") + " " + question.get("request_text", ""), re.I))


def filtered_questions(view, categories, query="", kpi_first=False):
    claims = {c["id"]: c for c in view["claims"]}
    categories = set(categories or []) & {key for key, _ in TYPES}
    query = str(query or "")[:200].casefold().strip()
    rows = [q for q in view["questions"] if question_tags(q, claims) & categories
            and (not query or query in (q["issue"] + " " + q["request_text"] + " " + text(q["financial_driver"])).casefold())]
    if kpi_first:
        rows = sorted(rows, key=lambda q: (not is_kpi(q), q["rank"] is None, q["rank"] or 0))
    return rows


def sidebar():
    return html.Div([
        html.Div([html.H3("프로젝트 자료"), html.Span("SOURCE LIBRARY", className="studio-overline")], className="studio-side-heading"),
        dcc.Input(id="studio-source-search", type="search", placeholder="파일명 검색…", maxLength=200, debounce=.2, className="studio-search"),
        html.Div(id="studio-source-list"),
        html.Div([html.Span("자료 추가", className="studio-mini-label"),
                  html.P("현재는 제공된 합성 자료를 검토합니다. 업로드·AI 분석은 다음 연결 단계입니다.")], className="studio-local-notice"),
    ], className="studio-sidebar")


def settings():
    return html.Div([
        html.H3("질문 설정"), html.P("현재 질문 목록에 적용할 검토 관점", className="studio-help"),
        html.Label("질문 유형 · 복수 선택", className="control-label"),
        dcc.Checklist(id="studio-types", options=[{"label": label, "value": key} for key, label in TYPES], value=[key for key, _ in TYPES], className="studio-type-chips"),
        html.Div([html.Label("추가 옵션", className="control-label"),
                  dcc.Checklist(id="studio-kpi", options=[{"label": " KPI 관련 질문 먼저 표시", "value": "first"}], value=[], className="studio-switch"),
                  html.P("표시 순서만 변경합니다. 엔진의 공식 점수·순위는 유지합니다.", className="studio-help"),
                  html.Div([html.Span("산업·경쟁사 관점 생성"), html.Span("AI 연결 예정", className="studio-status neutral")], className="studio-unavailable")], className="studio-settings-section"),
        html.Div([html.Span("실행 모드", className="studio-overline"), html.Strong("합성 자료 검토"),
                  html.P("질문을 새로 생성하지 않습니다. 기존 사례의 가설과 질문을 검토·편집하는 작업 공간입니다.")], className="studio-mode-note"),
        html.Button("AI 질문 생성 · 연결 예정", disabled=True, className="button studio-generate"),
        html.Div(id="studio-analysis-summary", className="studio-summary-card"),
        html.Div(id="studio-attention", className="studio-attention"),
    ], id="studio-settings", className="studio-settings")


def editor():
    return html.Div([
        html.H3("질문 검토 및 편집"), html.P("선택한 질문의 검토용 사본을 편집합니다.", className="studio-help"),
        html.Label("검토할 질문", className="control-label"),
        dcc.Dropdown(id="studio-active-question", options=[], placeholder="질문 선택", clearable=False),
        html.Div(id="studio-editor-meta", className="studio-editor-meta"),
        html.Label("질문", htmlFor="studio-edit-issue", className="control-label"),
        dcc.Textarea(id="studio-edit-issue", maxLength=1000, className="studio-edit-issue"),
        html.Label("검증 요청 자료", htmlFor="studio-edit-request", className="control-label"),
        dcc.Textarea(id="studio-edit-request", maxLength=6000, className="studio-edit-request"),
        html.Label("검토 의견", htmlFor="studio-edit-note", className="control-label"),
        dcc.Textarea(id="studio-edit-note", maxLength=2000, className="studio-edit-note", placeholder="검토 근거 또는 보완할 내용"),
        html.Button("수정 초안 저장", id="studio-save", n_clicks=0, className="button button-primary"),
        html.Div([html.Button("검토 완료", id="studio-approve", n_clicks=0, className="button button-secondary"),
                  html.Button("제외 표시", id="studio-reject", n_clicks=0, className="button button-secondary")], className="studio-review-actions"),
        html.Button("인용 원문 확인 ↗", id="studio-open-source", n_clicks=0, className="button button-quiet"),
        html.P("검토 완료는 이 초안에 대한 확인입니다. 공식 질문·점수·증빙 승인은 변경하지 않습니다.", className="studio-help"),
    ], id="studio-editor")


def workspace(view):
    steps = [("evidence", "자료 분석"), ("thesis", "가설 정리"), ("studio", "질문 검토"), ("questions", "중요도 평가"), ("review", "새 증거 반영")]
    return html.Div([
        html.Div([html.Div([html.Span("DEAL WORKSPACE", className="studio-overline"), html.H2("실사 질문 검토 워크스페이스")]),
                  html.Nav([html.Button([html.Span(str(i + 1).zfill(2)), html.Small(label)], id={"type": "studio-route", "page": page},
                                       n_clicks=0, className="studio-step active" if page == "studio" else "studio-step") for i, (page, label) in enumerate(steps)],
                           className="studio-stepper", **{"aria-label": "실사 작업 단계"})], className="studio-workflow-header"),
        html.Section([
            html.Div([html.H3("현재 투자 가설"), html.Span("원문 연결 · 합성 사례", className="studio-status blue")], className="section-bar"),
            html.Div(id="studio-theses"),
            html.Details([html.Summary("연결된 핵심 주장", id="studio-claims-heading"), html.Div(id="studio-linked-claims")], className="studio-linked-claims"),
        ], className="studio-thesis-panel"),
        html.Section([
            html.Div([html.Div([html.H3("실사 질문"), html.Span(id="studio-result-count", className="studio-count")], className="studio-title-count"),
                      dcc.RadioItems(id="studio-view", options=[{"label": "질문 목록", "value": "list"}],
                                     value="list", className="studio-view-tabs", inline=True)], className="studio-list-toolbar"),
            html.Div([dcc.Input(id="studio-question-search", type="search", placeholder="질문·요청 자료·재무 요인 검색…", maxLength=200, debounce=.2, className="studio-search"),
                      html.Button("표시된 질문 선택", id="studio-select-visible", n_clicks=0, className="button button-quiet"),
                      html.Button("선택 해제", id="studio-clear-selection", n_clicks=0, className="button button-quiet")], className="studio-filter-toolbar"),
            html.Div(id="studio-list-heading", className="studio-matrix-heading"),
            dcc.Checklist(id="studio-question-selection", options=[], value=[], className="studio-question-list"),
            html.Div(id="studio-list-empty", className="studio-list-empty"),
            html.Div([html.Span(id="studio-selection-count"), html.Button("선택 질문 검토", id="studio-review-selection", n_clicks=0, className="button button-primary"),
                      html.Button("선택 질문 검토 완료", id="studio-approve-selected", n_clicks=0, className="button button-secondary")], className="studio-batch-bar"),
            html.Div([html.Button("초안 CSV", id="studio-export-draft", n_clicks=0, className="button button-quiet"),
                      html.Button("검토 완료 CSV", id="studio-export-reviewed", n_clicks=0, className="button button-quiet"),
                      html.Span("수정 초안과 원문 참조를 함께 저장", className="studio-help")], className="studio-export-bar"),
        ], className="studio-question-panel"),
        html.Section([html.Div([html.H3("참고 메모"), html.Span("현재 탭 · 최대 4,000자", className="studio-help")], className="section-bar"),
                      dcc.Textarea(id="studio-memo", maxLength=4000, placeholder="검토 범위, 추가 확인 사항, 팀에 남길 메모…"),
                      html.Button("메모 저장", id="studio-save-memo", n_clicks=0, className="button button-quiet")], className="studio-memo-panel"),
        html.Details([html.Summary("검토 작업 이력"), html.Div(id="studio-history")], className="studio-history-panel"),
        html.P("합성 사례의 검토용 초안 · 실제 AI 생성 미연결 · 새로고침·사례 변경·증빙 반영·초기화 시 초안이 초기화됩니다. 필요한 내용은 CSV로 저장하세요.", className="studio-session-notice"),
    ], className="studio-workspace")


def source_list(view, query, selected):
    groups = defaultdict(list)
    for doc in view["documents"]:
        name = doc.get("filename", doc["id"])
        if query and str(query).casefold() not in name.casefold():
            continue
        group = "투자 소개 · CIM" if "cim" in name.lower() else "재무 자료" if any(word in name.lower() for word in ["financ", "ledger", "cost"]) else "사업 · 운영 자료"
        groups[group].append(doc)
    result = [html.Div([html.Span("등록 자료"), html.Strong(f"{len(view['documents'])}개")], className="studio-file-count")]
    for group, docs in groups.items():
        result.append(html.Details([html.Summary([html.Span(group), html.Small(str(len(docs)))]),
            *[html.Button([html.Span(d.get("filename", "").rsplit(".", 1)[-1].upper(), className="studio-file-type file-" + file_family(d.get("filename", ""))),
                           html.Span(d.get("filename", d["id"]), className="studio-file-name"),
                           html.Small(text(d.get("parse_status", "unknown")))],
                          id={"type": "studio-document", "document": d["id"]}, n_clicks=0,
                          className="studio-file selected" if selected == d["id"] else "studio-file") for d in docs]], open=True))
    if not groups:
        result.append(html.P("검색 결과가 없습니다.", className="studio-help"))
    return result


def file_family(filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return {"doc": "word", "docx": "word", "xls": "excel", "xlsx": "excel", "csv": "excel",
            "ppt": "powerpoint", "pptx": "powerpoint", "pdf": "pdf"}.get(extension, "other")


def thesis_cards(view):
    return [html.Div([html.Span(str(i + 1).zfill(2), className="studio-thesis-number"),
                      html.Div([html.Strong(thesis["title"]), html.P(thesis.get("counter_thesis", "")),
                                html.Div([html.Span(text(driver.strip()), className="studio-tag") for driver in thesis.get("financial_drivers", "").split(",") if driver.strip()])])],
                     className="studio-thesis-card") for i, thesis in enumerate(view["theses"])]


def question_options(view, rows, draft):
    claims = {c["id"]: c for c in view["claims"]}
    options = []
    for q in rows:
        edit = draft["edits"].get(q["id"], {})
        decision = draft["decisions"].get(q["id"], {}).get("status")
        status, color = ("검토 완료", "green") if decision == "approved" else ("제외 표시", "red") if decision == "rejected" else ("수정 초안", "amber") if edit else ("검토 대기", "neutral")
        options.append({"value": q["id"], "label": html.Div([
            html.Span(f"{q['rank']:02}" if q.get("rank") is not None else "—", className="studio-question-rank"),
            html.Div([html.Strong(edit.get("issue", text(q["issue"]))),
                      html.P(edit.get("request_text", q["request_text"]), className="studio-request-text"),
                      html.Small(claims.get(q["claim_id"], {}).get("source_refs", "원문 참조 없음"), className="studio-question-source")], className="studio-question-body"),
            html.Div([html.Span(text(q["financial_driver"]), className="studio-tag driver-" + q["financial_driver"]),
                      html.Span("KPI", className="studio-tag kpi") if is_kpi(q) else None], className="studio-question-tags"),
            html.Div([html.Strong(f"{float(q['score']):g}" if q.get("score") is not None else "—"),
                      html.Div(html.Span(style={"width": f"{min(100, max(0, float(q['score'] or 0)))}%"}), className="studio-score-track")],
                     className="studio-question-score", title="엔진의 공식 점수 · 0~100점 · 초안 편집과 독립"),
            html.Span(status, className=f"studio-status {color}"),
        ], className="studio-question-row")})
    return options


def analysis_summary(view, draft):
    approved = sum(d.get("status") == "approved" for d in draft["decisions"].values())
    rejected = sum(d.get("status") == "rejected" for d in draft["decisions"].values())
    total = len(view["questions"])
    return [html.Div([html.Span("✦", className="studio-spark"), html.H3("검토 요약"), html.Span("데모 데이터", className="studio-status blue")], className="studio-summary-title"),
            html.P(f"등록 문서 {len(view['documents'])}개에 연결된 투자 가설 {len(view['theses'])}개, 주장 {len(view['claims'])}개와 실사 질문 {len(view['questions'])}개를 검토합니다."),
            html.Div([html.Div([html.Strong(str(approved)), html.Small("검토 완료")]),
                      html.Div([html.Strong(str(len(draft['edits']))), html.Small("수정 초안")])], className="studio-review-stats"),
            html.Div([html.Span(style={"width": f"{100 * approved / total if total else 0}%"}, className="review-complete"),
                      html.Span(style={"width": f"{100 * rejected / total if total else 0}%"}, className="review-excluded")],
                     className="studio-review-progress", role="img", **{"aria-label": f"전체 {total}개 중 검토 완료 {approved}개, 제외 {rejected}개"}),
            html.P(f"검토 완료 {approved} · 제외 {rejected} · 미검토 {total - approved - rejected}", className="studio-progress-label"),
            html.Small("현재 사례를 집계한 요약입니다. AI가 새로 작성한 분석이 아닙니다.")]


def attention(view):
    claims = [c for c in view["claims"] if c.get("support_status") in {"missing", "partial", "contradicted"}]
    return [html.H3(f"우선 확인 포인트 · {len(claims)}"), *[html.Div([html.Span(str(i + 1)), html.Div([
        html.Strong(text(c["support_status"])), html.P(c["statement"])])], className="studio-attention-item") for i, c in enumerate(claims[:3])]]

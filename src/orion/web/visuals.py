"""Read-only visual summaries of the trusted workspace view."""
from collections import Counter

from dash import dcc, html
import plotly.graph_objects as go

from .i18n import text

COLORS = ["#7366e9", "#35b58b", "#f2b544", "#ec6b78", "#ad79d3", "#31b9cb"]
STATUS_COLORS = {"missing": "#94a3c3", "partial": "#f2b544", "supported": "#35b58b",
                 "contradicted": "#ec6b78", "approved": "#35b58b", "open": "#7366e9",
                 "resolved": "#35b58b", "rejected": "#ec6b78"}


def number(value):
    return float(value) if value is not None else 0.0


def graph(identifier, figure, height=285):
    figure.update_layout(template="plotly_white", height=height,
                         margin={"l": 48, "r": 28, "t": 28, "b": 58},
                         font={"family": "Segoe UI, Malgun Gothic, Arial, sans-serif", "size": 13, "color": "#384967"},
                         colorway=COLORS, paper_bgcolor="white", plot_bgcolor="white",
                         legend={"orientation": "h", "y": 1.2, "font": {"size": 12}},
                         hoverlabel={"font": {"size": 12}})
    figure.update_xaxes(gridcolor="#eff1f7", zerolinecolor="#e4e7ef", automargin=True)
    figure.update_yaxes(gridcolor="#eff1f7", zerolinecolor="#e4e7ef", automargin=True)
    return dcc.Graph(id=identifier, figure=figure, style={"height": f"{height}px"},
                     config={"displayModeBar": False, "responsive": True})


def panel(title, content, caption):
    return html.Section([html.Div([html.H3(title), html.Span("현재 스냅샷", className="visual-basis")], className="section-bar"),
                         content, html.P(caption, className="chart-caption")], className="panel visual-panel")


def unavailable(message):
    return html.Div([html.Span("—", className="visual-empty-mark"), html.P(message)], className="visual-empty")


def distribution(identifier, records, field):
    counts = Counter(record.get(field) or "unknown" for record in records)
    if not counts:
        return unavailable("집계할 기록이 없습니다.")
    figure = go.Figure(go.Pie(labels=[text(key) for key in counts], values=list(counts.values()),
                             hole=.72, sort=False, textinfo="none",
                             marker={"colors": [STATUS_COLORS.get(key, COLORS[i % len(COLORS)]) for i, key in enumerate(counts)]},
                             hovertemplate="%{label}<br>%{value}개 · %{percent}<extra></extra>"))
    figure.update_layout(annotations=[{"text": f"<b>{sum(counts.values())}</b><br>기록", "showarrow": False, "font": {"size": 17}}])
    result = graph(identifier, figure)
    result.figure.update_layout(legend={"y": -.08, "x": .5, "xanchor": "center"})
    return result


def stacked(identifier, records, group, category):
    if not records:
        return unavailable("집계할 기록이 없습니다.")
    groups = list(dict.fromkeys(record.get(group) or "unknown" for record in records))
    categories = list(dict.fromkeys(record.get(category) or "unknown" for record in records))
    figure = go.Figure()
    for i, value in enumerate(categories):
        figure.add_bar(name=text(value), y=[text(key) if len(text(key)) <= 25 else text(key)[:24] + "…" for key in groups], orientation="h",
                       x=[sum((r.get(group) or "unknown") == key and (r.get(category) or "unknown") == value for r in records) for key in groups],
                       marker_color=STATUS_COLORS.get(value, COLORS[i % len(COLORS)]),
                       customdata=[text(key) for key in groups],
                       hovertemplate="%{customdata}<br>%{x}개<extra>%{fullData.name}</extra>")
    figure.update_layout(barmode="stack")
    figure.update_xaxes(title_text="기록 수 (개)", dtick=1, rangemode="tozero")
    return graph(identifier, figure)


def question_tree(view):
    counts = Counter((q.get("thesis_title", "미분류"), q.get("financial_driver", "unknown")) for q in view.get("questions", []))
    if not counts:
        return unavailable("연결된 실사 질문이 없습니다.")
    groups = list(dict.fromkeys(group for group, _ in counts))
    ids, labels, parents, values = ["root"], ["전체 실사 질문"], [""], [sum(counts.values())]
    for i, group in enumerate(groups):
        group_id = f"thesis-{i}"
        ids.append(group_id); labels.append(group); parents.append("root")
        values.append(sum(count for (name, _), count in counts.items() if name == group))
        for j, ((name, driver), count) in enumerate(counts.items()):
            if name == group:
                ids.append(f"driver-{i}-{j}"); labels.append(text(driver)); parents.append(group_id); values.append(count)
    figure = go.Figure(go.Treemap(ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
                                 textinfo="label+value", marker={"colors": ["#f3f5fc"] + [COLORS[i % len(COLORS)] for i in range(len(ids) - 1)]},
                                 hovertemplate="%{label}<br>연결 질문 %{value}개<extra></extra>"))
    return graph("thesis-question-treemap", figure, 315)


def score_waterfall(question):
    if not question or question.get("score") is None:
        return unavailable("점수가 제공된 질문을 선택하세요.")
    values = [9 * number(question.get("gap")), 8 * number(question.get("materiality_score")),
              3 * number(question.get("obtainability_score")), number(question["score"])]
    figure = go.Figure(go.Waterfall(x=["증빙 공백 ×9", "중요도 ×8", "확보 가능성 ×3", "공식 점수"],
                                   measure=["relative", "relative", "relative", "total"], y=values,
                                   text=[f"{value:g}" for value in values], textposition="outside",
                                   increasing={"marker": {"color": "#8b97db"}}, totals={"marker": {"color": "#5965d8"}},
                                   connector={"line": {"color": "#d7ddec"}},
                                   hovertemplate="%{x}<br>%{y:g}점<extra></extra>"))
    figure.update_yaxes(title_text="우선순위 점수", range=[0, max(sum(values[:3]), values[3], 1) * 1.22])
    return graph("question-score-waterfall", figure, 315)


def score_stack(view):
    rows = [q for q in view.get("questions", []) if q.get("score") is not None][:6]
    if not rows:
        return unavailable("표시할 점수가 없습니다.")
    figure = go.Figure()
    for field, weight, label, color in [("gap", 9, "증빙 공백", COLORS[0]), ("materiality_score", 8, "중요도", COLORS[1]), ("obtainability_score", 3, "확보 가능성", COLORS[2])]:
        figure.add_bar(y=[f"Q{q['rank']:02}" for q in reversed(rows)], x=[weight * number(q.get(field)) for q in reversed(rows)],
                       orientation="h", name=label, marker_color=color,
                       customdata=[q["issue"] for q in reversed(rows)], hovertemplate="%{customdata}<br>%{x:g}점<extra>%{fullData.name}</extra>")
    figure.update_layout(barmode="stack")
    figure.update_xaxes(title_text="가중 점수 합계", rangemode="tozero")
    return graph("question-score-components", figure, 315)


def review_comparison(view):
    rows = [row for row in view.get("changes", []) if row.get("before_score") is not None and row.get("after_score") is not None][:8]
    if not rows:
        return unavailable("증빙 승인 후 변경 전후 점수가 표시됩니다. 반려 시 공식 점수는 유지됩니다.")
    figure = go.Figure()
    for field, label, color in [("before_score", "변경 전", "#bec6dd"), ("after_score", "변경 후", COLORS[0])]:
        figure.add_bar(x=[f"질문 {i + 1}" for i in range(len(rows))], y=[number(r[field]) for r in rows],
                       name=label, marker_color=color, customdata=[r.get("issue", r["question_id"]) for r in rows],
                       hovertemplate="%{customdata}<br>%{y:g}점<extra>%{fullData.name}</extra>")
    figure.update_layout(barmode="group")
    figure.update_yaxes(title_text="공식 우선순위 점수", rangemode="tozero")
    return graph("review-score-comparison", figure)


def review_progress(view):
    history = view.get("history", [])
    if not history:
        return unavailable("검토 결정 후 단계별 변화가 표시됩니다. 실제 검토 이력만 연결합니다.")
    stages = [f"T{row['stage']} · {'승인' if row['action'] == 'approve' else '반려'}" for row in history]
    changed = [sum(change.get("before_score") != change.get("after_score") or change.get("before_status") != change.get("after_status") for change in row.get("changes", [])) for row in history]
    top3 = [len(set(row.get("after_top3", [])) - set(row.get("before_top3", []))) for row in history]
    figure = go.Figure(go.Bar(x=stages, y=changed, name="점수·상태 변경 질문", marker_color="#b1a3e0"))
    figure.add_scatter(x=stages, y=top3, name="상위 3개 신규 진입", mode="lines+markers", line={"color": "#53a79a", "width": 2})
    figure.update_yaxes(title_text="질문 수 (개)", dtick=1, rangemode="tozero")
    return graph("review-stage-combo", figure)


def probability_waterfall(view):
    rows = view.get("analytics", {}).get("belief_snapshots", [])
    if not rows:
        return unavailable("승인된 확률 업데이트가 없습니다. 확률 가정이 없는 사례는 임의로 추정하지 않습니다.")
    row = rows[-1]
    prior, posterior = number(row.get("prior")), number(row.get("posterior"))
    figure = go.Figure(go.Waterfall(x=["사전확률", "증빙 반영 변화", "사후확률"],
                                   measure=["absolute", "relative", "total"], y=[prior, posterior - prior, posterior],
                                   text=[f"{prior:.1%}", f"{(posterior-prior)*100:+.1f}%p", f"{posterior:.1%}"], textposition="outside",
                                   increasing={"marker": {"color": COLORS[1]}}, decreasing={"marker": {"color": COLORS[3]}},
                                   totals={"marker": {"color": COLORS[0]}}))
    figure.update_yaxes(title_text="합성 시나리오 확률", tickformat=".0%", range=[0, 1.15])
    return html.Div([html.P(f"최근 승인 단계 T{row.get('stage', '')} · {row.get('hypothesis_id', '')}", className="chart-caption"),
                     graph("belief-waterfall", figure)])


def materiality_scatter(view):
    rows = [q for q in view.get("questions", []) if q.get("score") is not None]
    if not rows:
        return unavailable("분석할 실사 질문이 없습니다.")
    figure = go.Figure(go.Scatter(x=[number(q.get("gap")) for q in rows], y=[number(q.get("materiality_score")) for q in rows],
                                 mode="markers", marker={"size": [10 + 3 * number(q.get("obtainability_score")) for q in rows],
                                                         "color": [number(q["score"]) for q in rows], "colorscale": "Blues", "showscale": True,
                                                         "colorbar": {"title": "점수", "thickness": 10}},
                                 text=[q["issue"] for q in rows], hovertemplate="%{text}<br>증빙 공백 %{x}<br>중요도 %{y}<extra></extra>"))
    figure.update_xaxes(title_text="증빙 공백 · 원래 척도", rangemode="tozero")
    figure.update_yaxes(title_text="중요도 · 원래 척도", rangemode="tozero")
    return graph("materiality-gap-scatter", figure)


def page_visuals(page, view):
    evidence, claims, questions = view.get("evidence", []), view.get("claims", []), view.get("questions", [])
    if page == "evidence":
        cards = [panel("출처별 증빙 입장", stacked("evidence-origin-stack", evidence, "provenance", "stance"), "증빙 기록 수 기준 누적 막대입니다. 출처 구분과 지지·반박 입장을 함께 확인하세요."),
                 panel("검증 수준 분포", distribution("evidence-verification-donut", evidence, "verification_level"), "문서의 진술과 독립적인 사실 검증을 구분합니다. 범례를 누르면 항목을 숨길 수 있습니다.")]
    elif page == "thesis":
        cards = [panel("가설 × 재무 영향 요인", question_tree(view), "면적은 연결된 실사 질문 수입니다. 투자 비중·기업가치·위험 확률을 의미하지 않습니다. 영역을 눌러 확대하세요."),
                 panel("가설별 주장 충족 상태", stacked("thesis-support-stack", claims, "thesis_title", "support_status"), "각 가설에 연결된 주장 수를 상태별로 집계했습니다. 긴 가설 이름은 마우스를 올려 확인하세요.")]
    elif page == "questions":
        scored = [q for q in questions if q.get("score") is not None]
        selector = dcc.Dropdown(id="score-question-selector", options=[{"label": f"Q{q['rank']:02} · {q['issue']}", "value": q["id"]} for q in scored],
                                value=scored[0]["id"] if scored else None, clearable=False, placeholder="점수를 확인할 질문 선택")
        cards = [panel("질문 점수 구성 · 워터폴", html.Div([selector, html.Div(score_waterfall(scored[0] if scored else None), id="score-waterfall-content")]), "선택한 질문의 9G + 8M + 3O를 분해합니다. 마지막 막대는 엔진의 공식 점수입니다."),
                 panel("상위 질문의 점수 구성 비교", score_stack(view), "동일한 점수도 공백·중요도·확보 가능성의 구성이 다를 수 있습니다. 현재 순위 상위 6개를 표시합니다.")]
    elif page == "review":
        events = view.get("events", [])
        cards = [panel("최근 결정 · 변경 전후 점수", review_comparison(view), "최근 검토 이력의 동일 질문별 점수를 비교합니다. 막대에 마우스를 올리면 질문을 확인할 수 있습니다."),
                 panel("증빙 이벤트 진행 상태", distribution("review-events-donut", events, "status"), "이벤트 개수 기준입니다. 승인 전 미리보기는 확정 점수나 상태를 바꾸지 않습니다."),
                 panel("검토 단계별 변경 규모", review_progress(view), "막대는 점수 또는 상태가 바뀐 질문 수, 선은 상위 3개에 새로 진입한 질문 수입니다. 달력 기준 추세가 아닌 합성 검토 순서입니다.")]
    elif page == "analytics":
        cards = [panel("증빙 반영 확률 변화 · 워터폴", probability_waterfall(view), "최근 승인된 단일 가설 업데이트입니다. 변화량은 %p이며, 명시된 합성 확률 가정에만 적용됩니다."),
                 panel("증빙 공백 × 재무 중요도", materiality_scatter(view), "원 크기는 확보 가능성, 색은 공식 점수입니다. 겹치는 질문이 있을 수 있으며 상관관계나 가치평가를 추정하지 않습니다.")]
    elif page == "export":
        figure = go.Figure(go.Bar(x=["문서", "투자 가설", "주장", "증빙", "실사 질문"],
                                 y=[len(view.get(field, [])) for field in ("documents", "theses", "claims", "evidence", "questions")],
                                 marker_color=COLORS, hovertemplate="%{x}: %{y}개<extra></extra>"))
        figure.update_yaxes(title_text="항목 수 (개)", dtick=1, rangemode="tozero")
        cards = [panel("현재 스냅샷 · 검토 자료 구성", graph("export-inventory-bars", figure), "유형별 보유 기록 수입니다. 내보내기 형식별 실제 포함 필드는 다르며, 서로 다른 유형의 수를 합산하지 않습니다."),
                 panel("실사 질문 처리 현황", distribution("export-question-donut", questions, "workflow_status"), "미해결 질문은 보고서의 검토 공백으로 유지됩니다. 자료 내보내기는 아래 별도 승인 절차가 필요합니다.")]
    else:
        return None
    return html.Div([html.Div([html.Span("시각 분석", className="visual-kicker"), html.Span("범례로 항목 선택 · 마우스로 상세 확인", className="muted")], className="section-bar"),
                     html.Div(cards, className="visual-grid")], className="page-visuals")

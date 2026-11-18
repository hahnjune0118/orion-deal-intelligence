"""One eight-stage navigation; existing evidence and financial approvals stay independent."""
import json
from orion.services.fdd_workpapers import content_hash
from dash import Input, Output, State, html, dcc, ctx, no_update
from flask import session
from orion.services.fdd_workpapers import FDDWorkpapers, review_status
from orion.services.fdd_finance import FinanceError, calculations
from . import fdd_workspace as ui

VIEWS = {
    'deal': [('deal','범위·거래 배경'),('thesis','투자 가설'),('overview','증빙 개요')],
    'dataroom':[('dataroom','자료 요청'),('evidence','원문·증빙 탐색')],
    'reconciliation':[('reconciliation','재무 데이터·대사')],
    'financial':[('financial','재무 분석'),('analytics','고급 분석 · Bayesian/EIG')],
    'issues':[('issues','쟁점·경영진 Q&A'),('studio','실사 질문 검토'),('questions','질문 중요도')],
    'adjustments':[('adjustments','조정·거래 영향')],
    'quality':[('quality','조서 작성·검토'),('review','증빙 승인·반려')],
    'deliverables':[('deliverables','FDD 보고서·데이터북'),('export','질문표·예비 심사 메모'),('fdd','참고 수동 조서')],
}
PARENT={view:parent for parent,views in VIEWS.items() for view,_ in views}


def register_workflow(app,workspace):
    service=FDDWorkpapers(app.server.secret_key)
    @app.callback(Output('fdd-stage','value'),Output('stage-view','options'),Output('stage-view','value'),
                                                            Output('workspace-tabs','value',allow_duplicate=True),
                                                            Input('fdd-stage','value'),Input('stage-view','value'),Input('workspace-tabs','value'),prevent_initial_call=True)
    def navigate(stage,subview,route):
        trigger=ctx.triggered_id
        route=stage if trigger=='fdd-stage' else subview if trigger=='stage-view' else route
        parent=PARENT.get(route,'deal')
        return parent,[{'label':label,'value':key} for key,label in VIEWS[parent]],route,route

    @app.callback(Output('workflow-related','children'),Input('workspace-tabs','value'),Input('fw-inspection','value'),
                                                            Input('studio-active-question','value'),Input('finance-token','data'),Input('workspace-token','data'))
    def related(page,selection,question,finance_token,token):
        if not token:return []
        sid=session['orion_session'];view=workspace.view(token,sid)
        try:state=service.read(finance_token,view['case_id'],sid,view['deal']['name'])
        except FinanceError:return []
        issues=state['issues'];kind,_,identifier=(selection or '').partition(':')
        matches=[i for i in issues if (page=='studio' and i.get('question_ref')==question) or
                                            (page in ui.PAGES and ((kind=='issue' and i['id']==identifier) or
                                                (kind=='adjustment' and i['adjustment_id']==identifier) or (kind=='request' and i['request_id']==identifier) or
                                                (i.get('origin_ref')==selection)))]
        children=[html.Div('증빙 확인 · 조정 반영 · 조서 검토는 별도 상태입니다.',className='workflow-state')]
        for issue in matches:
            children += [html.Strong(issue['id']+' · '+issue['title']),html.P('질문 '+issue.get('question_ref','—')+' · 요청 '+(issue['request_id'] or '—')+' · 조정 '+(issue['adjustment_id'] or '—')),
                                                                html.P('쟁점: '+issue['status']+' / 조서: '+review_status(state)),
                                                                html.Small('연결 당시 증빙 스냅샷: '+issue.get('question_snapshot','—')),
                                                                ui.select_button('관련 쟁점 열기', 'issue:'+issue['id'])]
            if issue.get('origin_ref'):children.append(ui.select_button('발견 원천 확인',issue['origin_ref']))
            for prefix,key in [('request', 'request_id'),('adjustment','adjustment_id')]:
                if issue.get(key):children.append(ui.select_button('연결 '+('자료 요청' if prefix=='request' else '조정')+' 확인',prefix+':'+issue[key]))
            children.append(html.P('최근 이력: '+' / '.join(str(h.get('action','')) for h in state['history'][-3:])))
        link_key='question_ref' if page=='studio' else 'origin_ref'
        candidates=[i for i in issues if not i.get(link_key)]
        children.append(html.Label('연결할 쟁점 (선택)'))
        children.append(dcc.Dropdown(id='workflow-target-issue',options=[{'label':'새 쟁점 등록','value':''}]+[{'label':i['id']+' · '+i['title'],'value':i['id']} for i in candidates],value='',clearable=False,placeholder='새 쟁점 등록'))
        if page in ui.PAGES and selection and ui.valid_selection(state,calculations(state),selection):
            children.append(html.Button('선택 항목을 쟁점에 연결',id='workflow-origin-issue',n_clicks=0,className='button button-secondary'))
        unique=[];seen=set()
        for child in children:
            identifier=getattr(child,'id',None)
            if identifier is not None:
                identity=json.dumps(identifier,sort_keys=True)
                if identity in seen:continue
                seen.add(identity)
            unique.append(child)
        return html.Div(unique,className='workflow-related')

    @app.callback(Output('finance-registry','data',allow_duplicate=True),Output('finance-token','data',allow_duplicate=True),
                                                            Output('workspace-tabs','value',allow_duplicate=True),Output('fw-inspection','value',allow_duplicate=True),
                                                            Input('workflow-question-issue','n_clicks'),Input('workflow-origin-issue','n_clicks',allow_optional=True),
                                                            State('workspace-token','data'),State('finance-token','data'),State('finance-registry','data'),
                                                            State('studio-active-question','value'),State('fw-inspection','value'),State('studio-draft-token','data'),State('workflow-target-issue','value',allow_optional=True),prevent_initial_call=True)
    def connect(qclick,origin_click,token,finance_token,registry,question,selection,draft_token,target):
        if not token or not any(t.get('value') for t in ctx.triggered):return (no_update,)*4
        sid=session['orion_session'];view=workspace.view(token,sid)
        try:state=service.read(finance_token,view['case_id'],sid,view['deal']['name'])
        except FinanceError:return (no_update,)*4
        is_question=ctx.triggered_id=='workflow-question-issue'
        q=next((q for q in view['questions'] if q['id']==question),None) if is_question else None
        if is_question and not q:return (no_update,)*4
        if not is_question and not ui.valid_selection(state,calculations(state),selection):return (no_update,)*4
        key='question_ref' if is_question else 'origin_ref';reference=question if is_question else selection
        existing=next((i for i in state['issues'] if i.get(key)==reference),None)
        if existing:return no_update,no_update,'issues','issue:'+existing['id']
        title=q['issue'] if q else '추가 검증: '+selection
        if q:
            from orion.services.draft_review import DraftReview
            draft=DraftReview(app.server.secret_key).read(draft_token,token,sid,view)
            title=draft['edits'].get(question,{}).get('issue',title)
        target_issue=next((i for i in state['issues'] if i['id']==target),None)
        if target and (not target_issue or target_issue.get(key)):return (no_update,)*4
        values=dict(target_issue) if target_issue else dict(title=title,area='과거 실적',impact=None,priority='보통',status='추가 확인',request_id='',adjustment_id='',management='',conclusion='원본 질문: '+question if q else '발견 원천: '+selection)
        state=service.update(state,'issue',values)
        issue=next(i for i in state['issues'] if i['id']==target) if target else state['issues'][-1]
        issue[key]=reference
        state['review']['prepared_hash']=None;state['review']['approved_hash']=None
        if q:issue['question_snapshot']=view['snapshot_id']
        state['history'][-1]['after']=content_hash(state)
        changes=json.loads(state['history'][-1]['changes'] or '{}');changes[key]={'before':None,'after':reference}
        if q:changes['question_snapshot']={'before':None,'after':view['snapshot_id']}
        state['history'][-1]['changes']=json.dumps(changes,ensure_ascii=False)
        signed=service.sign(state);registry=dict(registry or {});registry[view['case_id']]=signed
        return registry,signed,'issues','issue:'+issue['id']

    @app.callback(Output('workflow-open-question','disabled'), Input('fw-inspection','value'), Input('finance-token','data'), State('workspace-token','data'))
    def question_available(selection,finance_token,token):
        if not token:return True
        view=workspace.view(token,session['orion_session'])
        try:state=service.read(finance_token,view['case_id'],session['orion_session'],view['deal']['name'])
        except FinanceError:return True
        return not any(i.get('question_ref') and ('issue:'+i['id']==selection or 'adjustment:'+i['adjustment_id']==selection or 'request:'+i['request_id']==selection) for i in state['issues'])

    @app.callback(Output('workspace-tabs','value',allow_duplicate=True),Output('studio-active-question','value',allow_duplicate=True),
                  Output('studio-side-tabs','value',allow_duplicate=True),Input('workflow-open-question','n_clicks'),
                  State('workspace-token','data'),State('finance-token','data'),State('fw-inspection','value'),prevent_initial_call=True)
    def open_question(clicks,token,finance_token,selection):
        if not clicks or not token:return (no_update,)*3
        view=workspace.view(token,session['orion_session'])
        state=service.read(finance_token,view['case_id'],session['orion_session'],view['deal']['name'])
        issue=next((i for i in state['issues'] if i.get('question_ref') and ('issue:'+i['id']==selection or 'adjustment:'+i['adjustment_id']==selection or 'request:'+i['request_id']==selection)),None)
        question=issue.get('question_ref') if issue else None
        return ('studio',question,'editor') if question in {q['id'] for q in view['questions']} else (no_update,)*3

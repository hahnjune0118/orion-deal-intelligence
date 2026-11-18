"""User-entered FDD workpapers, separate from canonical evidence and scores."""
from decimal import Decimal, InvalidOperation
import csv
import io
from dash import html, dcc, dash_table, Input, Output, State, ctx, no_update
from flask import session

PROGRAM = [
('S01','범위·거래 구조','대상 법인·사업 범위, 검토 기간, 회계기준·통화·단위 및 제한사항 합의'),
('D01','자료 기반·대사','감사보고서, 월별 관리손익, 시산표·총계정원장 확보 및 상호 대사'),
('T01','과거 실적','매출·매출총이익·고객 및 제품별 추세, 기간 귀속·일회성 항목 분석'),
('Q01','QoE','보고 EBITDA에서 비경상·비영업·회계정책·실행 가능한 run-rate 조정 검토'),
('W01','운전자본','월별 AR/AP·재고, 연령 분석·충당금·계절성 및 정상 운전자본 기준 검토'),
('N01','순차입금','차입·현금·제한성 현금·리스·debt-like 항목 및 NWC 중복 분류 검토'),
('C01','현금흐름·CAPEX','EBITDA와 영업현금흐름 대사, 유지보수·성장 CAPEX 및 자금 소요 검토'),
('F01','예산·전망','경영진 전망을 과거 실적·계약·생산능력·운전자본 가정과 대조'),
('P01','가격·계약상 시사점','EV–Equity bridge, NWC peg·closing mechanism 및 SPA 검토 요청사항 정리'),
('R01','보고·검토','핵심 발견사항·미해결 요청·범위 제한 및 작성자·검토자 의견 정리')]
STATUS=['미요청','요청','수령','작성','검토']

def initial():
    return [dict(id=i, workstream=w, procedure=p, owner='', due='', status='미요청', source_document='', finding='', reviewer_note='') for i,w,p in PROGRAM]

def table(identifier, rows, fields):
    return dash_table.DataTable(id=identifier, data=rows, columns=[{'name':label,'id':key,'editable':key not in {'id','workstream','procedure'}} for key,label in fields],
        editable=True, style_table={'overflowX':'auto'}, style_cell={'textAlign':'left','fontFamily':'Segoe UI, Malgun Gothic','fontSize':14,'padding':'10px','minWidth':'120px','maxWidth':'320px','whiteSpace':'normal','height':'auto'},
        style_header={'backgroundColor':'#e9efff','fontWeight':'600'}, style_data_conditional=[{'if':{'row_index':'odd'},'backgroundColor':'#f7f9ff'}])

def layout():
    return html.Div([
        html.H2('FDD 업무조서'), html.P('범위 설정 → 자료 요청·대사 → QoE / NWC / Net debt → 쟁점 검토 → 보고. 공개 업무 범위를 바탕으로 구성한 사용자 입력 조서입니다.'),
        html.Div([html.Label('범위·기간·회계기준·통화·단위'),dcc.Textarea(id='fdd-scope',placeholder='예: 매수자 실사 / 대상 법인 / FY2024–2026 YTD / K-IFRS / KRW 백만원 / 제외 범위',style={'width':'100%','minHeight':90})],className='panel'),
        html.Div([html.H3('1. 자료 요청·분석 작업 프로그램'),html.P('상태: 미요청 / 요청 / 수령 / 작성 / 검토. 검토 표시는 담당자·원문 문서 ID·발견사항·검토 의견 입력이 필요하며, 전문적인 독립 검증을 뜻하지 않습니다.'),
        html.Div(id='fdd-documents'), table('fdd-program',initial(),[(k,v) for k,v in [('id','조서 ID'),('workstream','업무 영역'),('procedure','절차·요청 자료'),('owner','담당자'),('due','요청 기한'),('status','상태'),('source_document','문서 ID'),('finding','발견사항·미해결 질문'),('reviewer_note','검토 의견')]])],className='panel'),
        html.Div([html.H3('2. 조정 후보 등록부'),html.P('분류: QoE / NWC / Net debt. 금액은 같은 통화·단위로 입력하세요. +/− 부호는 각 소계에 대한 증감입니다. QoE·NWC·순차입금은 서로 합산하지 않습니다. 기준 금액·EV가 없으면 조정 EBITDA·Equity Value는 산출하지 않습니다.'),
        table('fdd-adjustments',[dict(category=k,description='',amount=None,source_document='',reviewer_note='',status='초안') for k in ['QoE','NWC','Net debt']], [('category','분류'),('description','조정 근거·기간'),('amount','증감 금액'),('source_document','문서 ID'),('reviewer_note','검토 의견·중복 분류 확인'),('status','초안 / 검토')]),
        html.Button('조정 후보 행 추가',id='fdd-add',n_clicks=0,className='button button-quiet')],className='panel'),
        html.Div([html.Button('조서 검증·저장',id='fdd-save',n_clicks=0,className='button button-primary'), html.Button('저장된 조서 CSV',id='fdd-export',n_clicks=0,className='button button-secondary')]),
        html.Div(id='fdd-status',role='status',className='callout'),html.Div(id='fdd-summary',className='panel'),
        html.P('현재 브라우저 탭의 세션 저장입니다. 다른 기기·사용자와 공유되지 않습니다. 이 조서와 수동 검토 표시는 실제 FDD 완료·회계법인 서명·투자 승인 또는 기존 공식 증빙 승인을 의미하지 않습니다.')
    ],id='fdd-workpaper')

def validate(scope, rows, adjustments, docs):
    if not isinstance(scope,str) or not scope.strip() or len(scope)>4000: raise ValueError('범위·기간·회계기준·통화·단위를 먼저 입력하세요.')
    if not isinstance(rows,list) or len(rows)!=len(PROGRAM) or {r.get('id') for r in rows}!={p[0] for p in PROGRAM}: raise ValueError('작업 프로그램의 조서 ID를 유지하세요.')
    if not isinstance(adjustments,list) or len(adjustments)>100: raise ValueError('조정 후보는 100개까지 등록할 수 있습니다.')
    sums={k:Decimal(0) for k in ['QoE','NWC','Net debt']}
    for r in rows:
        if r.get('status') not in STATUS: raise ValueError('작업 상태는 미요청 / 요청 / 수령 / 작성 / 검토 중 하나를 입력하세요.')
        if r.get('source_document') and r['source_document'] not in docs: raise ValueError('현재 투자 건의 문서 ID만 연결할 수 있습니다.')
        if r['status']=='검토' and not all(str(r.get(k) or '').strip() for k in ['owner','source_document','finding','reviewer_note']): raise ValueError('검토 상태에는 담당자·문서 ID·발견사항·검토 의견이 필요합니다.')
    for r in adjustments:
        if r.get('category') not in sums or r.get('status') not in {'초안','검토'}: raise ValueError('조정 분류 또는 상태가 올바르지 않습니다.')
        if r.get('source_document') and r['source_document'] not in docs: raise ValueError('조정 근거 문서는 현재 투자 건에 속해야 합니다.')
        if r.get('amount') in (None,''):
            if r['status']=='검토': raise ValueError('검토 조정에는 금액이 필요합니다.')
            continue
        try:
            amount=Decimal(str(r['amount']).replace(',',''))
            if not amount.is_finite() or abs(amount)>Decimal('1e18'): raise InvalidOperation()
        except (InvalidOperation,ValueError): raise ValueError('조정 금액은 유한한 숫자로 입력하세요.')
        if r['status']=='검토':
            if not all(str(r.get(k) or '').strip() for k in ['description','source_document','reviewer_note']): raise ValueError('검토 조정에는 근거·문서 ID·검토 의견이 필요합니다.')
            sums[r['category']]+=amount
    return {k:format(v,'f') for k,v in sums.items()}

def register(app, workspace):
    @app.callback(Output('fdd-summary','children',allow_duplicate=True),Output('fdd-status','children',allow_duplicate=True),Input('workspace-token','data'),prevent_initial_call=True)
    def clear_summary(token):return '', ''

    @app.callback(Output('fdd-scope','value'),Output('fdd-program','data'),Output('fdd-adjustments','data'),Output('fdd-documents','children'),Input('workspace-token','data'),State('fdd-store','data'))
    def hydrate(token, store):
        if not token:return no_update,no_update,no_update,''
        v=workspace.view(token,session['orion_session']); saved=(store or {}).get(v['deal']['id'],{})
        if saved.get('snapshot')!=v['snapshot_id']:saved={}
        return saved.get('scope',''),saved.get('rows',initial()),saved.get('adjustments',[dict(category=k,description='',amount=None,source_document='',reviewer_note='',status='초안') for k in ['QoE','NWC','Net debt']]),html.P('利用 가능한 문서 ID: '.replace('利用','사용')+' / '.join(d['id']+' ('+d['filename']+')' for d in v['documents']))
    @app.callback(Output('fdd-adjustments','data',allow_duplicate=True),Input('fdd-add','n_clicks'),State('fdd-adjustments','data'),prevent_initial_call=True)
    def add(n,rows):return (rows or [])+[dict(category='QoE',description='',amount=None,source_document='',reviewer_note='',status='초안')] if len(rows or [])<100 else no_update
    @app.callback(Output('fdd-store','data'),Output('fdd-status','children'),Output('fdd-summary','children'),Output('fdd-download','data'),Input('fdd-save','n_clicks'),Input('fdd-export','n_clicks'),State('workspace-token','data'),State('fdd-scope','value'),State('fdd-program','data'),State('fdd-adjustments','data'),State('fdd-store','data'),prevent_initial_call=True)
    def save(_save,_export,token,scope,rows,adjustments,store):
        try:
            v=workspace.view(token,session['orion_session']); docs={d['id'] for d in v['documents']}; store=dict(store or {})
            if ctx.triggered_id=='fdd-export':
                record=store.get(v['deal']['id'])
                if not record or record.get('snapshot')!=v['snapshot_id']:raise ValueError('현재 스냅샷의 조서를 먼저 저장하세요.')
                validate(record['scope'],record['rows'],record['adjustments'],docs)
                stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['scope','section','record','snapshot','notice'])
                for section in ['rows','adjustments']:
                    for r in record[section]:
                        values=[record['scope'],section,str(r),record['snapshot'],'사용자 입력 FDD 작업 초안 / 독립 검증·실사 완료 아님']
                        writer.writerow(["'"+x if x.lstrip(' \t\r\n\ufeff').startswith(('=','+','-','@')) else x for x in values])
                return no_update,'저장된 조서를 내보냈습니다. 저장 후 수정한 내용은 포함되지 않습니다.',no_update,dict(content='\ufeff'+stream.getvalue(),filename='orion_fdd_workpapers.csv',type='text/csv')
            sums=validate(scope,rows,adjustments,docs);store[v['deal']['id']]=dict(scope=scope,rows=rows,adjustments=adjustments,snapshot=v['snapshot_id'])
            return store,'작업 조서를 저장했습니다. 분류별 합계는 검토로 표시한 조정 후보만 포함합니다.',html.Div([html.P(f"수동 검토 표시 {sum(r['status']=='검토' for r in rows)} / {len(rows)}개 · 실사 완료율이 아닙니다."),*[html.P(k+' 조정 후보 소계: '+value+' (입력 단위)') for k,value in sums.items()]]),no_update
        except ValueError as e:return no_update,str(e),no_update,no_update
        except Exception:return no_update,'현재 작업 영역을 확인하세요.',no_update,no_update

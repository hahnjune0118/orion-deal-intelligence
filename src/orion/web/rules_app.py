"""Persistent rules MVP with local and explicitly configured hosted entry points."""
import csv
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, g, jsonify, request, send_file, render_template_string
from werkzeug.local import LocalProxy

from orion.rules import engine, retrieval, analysis, reporting, deal_visuals
from orion.rules.store import Store, Conflict
from orion.rules.parsing import parse
from orion.rules.case_studies import CaseStudies, apply_scenario
from orion.rules.orion_case import CASE_ID, FORMATS, pdf_preview


ASSETS = Path(__file__).parent/'assets'


def create_rules_app(data_dir=None, port=8050, *, hosted=None):
    root=Path(data_dir) if data_dir else Path(__file__).resolve().parents[3]/'.local'/'orion-rules'
    store=LocalProxy(lambda: g.rules_store) if hosted else Store(root/'projects.sqlite3')
    cases=CaseStudies(root/'case-studies') if not hosted else hosted.cases
    app=Flask(__name__,static_folder=str(ASSETS),static_url_path='/assets')
    app.config['MAX_CONTENT_LENGTH']=16*1024*1024
    app.config['RULES_PORT']=port
    app.extensions['rules_store']=store
    if hosted:
        hosted.configure(app)

    @app.before_request
    def local_only():
        if hosted:
            return hosted.guard()
        if request.remote_addr not in {'127.0.0.1','::1',None}:
            abort(403)
        current_port=app.config['RULES_PORT']
        allowed={f'127.0.0.1:{current_port}',f'localhost:{current_port}'}
        # Test-client hosts use localhost; production still binds only loopback.
        if request.host not in allowed and not (app.testing and request.host=='localhost'):
            abort(403)
        if request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('Origin') != request.host_url.rstrip('/'):
            abort(403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(ValueError)
    def bad_input(error):
        return jsonify(error=str(error)),409 if isinstance(error,Conflict) else 400

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error='파일/요청 크기가 한도를 초과했습니다.'),413

    @app.get('/')
    def home():
        return render_template_string((ASSETS/'rules.html').read_text(encoding='utf-8'), hosted=bool(hosted))

    @app.get('/healthz')
    def health():
        return dict(status='ok',mode='pythonanywhere_demo' if hosted else 'rules_local',live_provider=False,persistent=True,policy=engine.POLICY)

    def result(row):
        value=engine.view(row['state'])
        value['visual_workspace']=deal_visuals.view(row['state'])
        if cases and cases.orion.available() and value.get('case_study', {}).get('id') == CASE_ID:
            value['review_sources'] = cases.orion.review_sources
        return dict(id=row['id'],version=row['version'],state=value,snapshots=row['snapshots'])

    @app.get('/api/projects')
    def projects():
        return jsonify(store.list())

    @app.get('/api/cases')
    def case_catalog():
        return jsonify(cases.catalog() if cases else [])

    def original_file(fid, *, download=False):
        source = cases.orion.source(fid) if cases else None
        if source is None:
            abort(404)
        path = cases.orion.original_path(source)
        if not path.is_file() or path.stat().st_size != source['bytes']:
            abort(404)
        file_format = source['format']
        if request.args.get('view') == 'details':
            return jsonify(total_units=source['total_units'])
        if file_format == '.pdf' and request.args.get('view') == 'page':
            page = request.args.get('page', type=int)
            if page is None or not 1 <= page <= source['total_units']:
                abort(404)
            data = pdf_preview(path, page, source['sha256'])
            if data is None:
                abort(503)
            return send_file(io.BytesIO(data), mimetype='image/png')
        if file_format == '.xlsx' and request.args.get('view') == 'worksheet':
            return jsonify(cases.orion.worksheet_preview(source))
        attachment = download or file_format != '.pdf' or request.args.get('download') == '1'
        return send_file(path, mimetype=FORMATS[file_format], as_attachment=attachment,
                         download_name=source['filename'], conditional=True, etag=source['sha256'])

    @app.get('/case-sources/orion-271560/<fid>')
    def orion_source(fid):
        return original_file(fid)

    @app.post('/case-sources/orion-271560/lease-demo')
    def lease_demo():
        if not cases or not cases.orion.available() or cases.orion.lease_source is None:
            abort(404)
        state, demo = cases.orion.run_lease_demo(python=hosted.python if hosted else None)
        return jsonify(demo=demo, report_html=reporting.report(state, 1))

    @app.post('/api/cases/<key>/open')
    def open_case(key):
        if cases is None:
            abort(404)
        data=request.get_json() or {}
        return result(cases.open(store,key,copy=data.get('copy') is True))

    @app.post('/api/projects')
    def create():
        d=request.get_json()
        return result(store.create(d.get('company'),d.get('period'),d.get('industry','general')))

    @app.get('/api/projects/<pid>')
    def get(pid):
        return result(store.get(pid))

    @app.post('/api/projects/<pid>/documents')
    def upload(pid):
        row=store.get(pid)
        file=request.files.get('file')
        if not file:
            raise ValueError('자료 파일을 선택하세요.')
        filename=engine.text(file.filename.replace('\\','/').rsplit('/',1)[-1],'파일명',200)
        source=file.read(10*1024*1024+1)
        parsed=parse(source,filename,python=hosted.python if hosted else None)
        for doc in row['state']['documents']:
            if doc['sha256']==parsed['sha256']:
                answer=result(row);answer['notice']='동일 파일은 이미 등록되어 있어 중복 저장하지 않았습니다.'
                return answer
        identifier='d_'+uuid4().hex[:20]
        group=engine.text(request.form.get('group') or filename,'자료 의존 그룹',120)
        origin=request.form.get('origin','company')
        if origin not in {'company','independent','counterparty','analyst'}:
            raise ValueError('자료 출처를 선택하세요.')
        doc=dict(id=identifier,filename=filename,group=group,origin=origin,version=1,**parsed)
        def add(state):
            if len(state['documents'])>=30 or sum(len(s['text']) for s in engine.spans(state))+sum(len(s['text']) for s in doc['spans'])>4_000_000:
                raise ValueError('프로젝트당 30개 자료·추출 텍스트 400만 자 한도입니다.')
            doc['version']=1+max([d['version'] for d in state['documents'] if d['filename']==filename] or [0])
            state['documents'].append(doc)
            engine.audit(state,'자료 등록',filename+' · '+doc['status'])
        try:
            version=int(request.form.get('version',''))
        except ValueError:
            raise ValueError('최신 프로젝트 버전을 확인하세요.') from None
        return result(store.update(pid,version,add,file=(identifier,filename,parsed['sha256'],source)))

    @app.get('/api/projects/<pid>/files/<fid>')
    def download(pid,fid):
        row=store.get(pid)
        if row['state'].get('case_study',{}).get('id') == CASE_ID:
            doc=next((d for d in row['state']['documents'] if d['id']==fid and d.get('original')),None)
            if doc:
                return original_file(fid, download=True)
        name,data=store.file(pid,fid)
        return send_file(io.BytesIO(data),as_attachment=True,download_name=name)

    @app.get('/api/projects/<pid>/search')
    def search(pid):
        state=store.get(pid)['state']
        query=engine.text(request.args.get('q',''),'검색어',200,required=False).casefold()
        return jsonify(retrieval.search(state['documents'],query,40))

    @app.post('/api/projects/<pid>/actions/<action>')
    def mutate(pid,action):
        d=request.get_json()
        operations={'analyze':lambda s:engine.analyze(s),'generate':lambda s:engine.generate(s),
                    'case_scenario':apply_scenario,
                    'hypothesis':lambda s:engine.hypothesis_update(s,d),
                    'question':lambda s:engine.question_update(s,d),
                    'custom':lambda s:engine.custom_question(s,d),
                    'decision':lambda s:engine.decision_update(s,d),
                    'fact':lambda s:engine.fact_update(s,d),
                    'fact_new':lambda s:engine.fact_add(s,d),
                    'visual':lambda s:save_visual(s,d),
                    'visual_import':lambda s:import_visual(s)}
        if action=='case_documents' and cases and cases.orion.available():
            operations[action]=lambda s:cases.orion.register_group(s,d.get('group'))
        elif action=='case_evidence' and cases and cases.orion.available():
            operations[action]=lambda s:cases.orion.apply_group(s,d.get('group'))
        elif action=='evidence':
            if d.get('reviewed') is not True:
                raise ValueError('원문과 판정 기준을 검토한 뒤 적용하세요.')
            operations[action]=lambda s:engine.evidence_apply(s,d,reject=d.get('reject') is True)
        elif action=='revoke':
            def revoke(s):
                e=engine.find(s['evidence'],d.get('id'),'증거')
                if e['status']!='approved':
                    raise ValueError('적용된 증거만 철회할 수 있습니다.')
                e['status']='revoked'
                engine.replay(s)
                engine.audit(s,'증거 철회',e['id'])
            operations[action]=revoke
        if action not in operations:
            abort(404)
        return result(store.update(pid,d.get('version'),operations[action]))

    def save_visual(state,data):
        deal_visuals.update(state,data)
        deal_visuals.calculate(state['deal_visuals'])
        deal_visuals.calculate(state['deal_visuals'],True)
        engine.audit(state,'거래 시각화 시나리오 저장','재무 조정 시나리오 · 질문/증거 승인과 별개')

    def import_visual(state):
        deal_visuals.import_budget(state)
        engine.audit(state,'사례 자금표 연결','기존 사례의 기재 예산 · 조달 확약 확인 전')

    @app.post('/api/projects/<pid>/preview')
    def preview(pid):
        d=request.get_json()
        row=store.get(pid)
        if type(d.get('version')) is not int or d['version']!=row['version']:
            raise Conflict('프로젝트가 변경됐습니다. 최신 상태에서 미리보기를 다시 확인하세요.')
        before=engine.snapshot(row['state'])
        state=deepcopy(row['state'])
        e=engine.evidence_apply(state,d,reject=d.get('reject') is True)
        return dict(before=before,after=engine.snapshot(state),trace=engine.evidence_trace(state),evidence={**e,'application':engine.replay(state)[1].get(e['id'],'미적용')})

    @app.get('/api/projects/<pid>/history')
    def history(pid):
        return jsonify(store.history(pid))

    @app.get('/api/projects/<pid>/export/<kind>')
    def export(pid,kind):
        row=store.get(pid);state=engine.view(row['state'])
        if kind=='json':
            data=json.dumps({**row,'state':state,'all_snapshots':store.history(pid)},ensure_ascii=False,indent=2).encode('utf-8')
            return send_file(io.BytesIO(data),as_attachment=True,download_name='Orion_rules_review.json',mimetype='application/json')
        if kind=='html':
            data=reporting.report(row['state'],row['version']).encode('utf-8')
            return send_file(io.BytesIO(data),as_attachment=True,download_name='Orion_review_report.html',mimetype='text/html')
        if kind!='csv':
            abort(404)
        buf=io.StringIO(newline='');writer=csv.writer(buf)
        writer.writerow(['질문 ID','질문','가설','요청 자료','판정 기준','상태','현재 추천 순위','중요도','EIG(bits)','추천 점수','가정 기반 확률','EVSI','효용 단위','원문 참조','정책','확보 비용','지연 비용','EVSI 비용 차감 후','EVPI','우도 가정 출처','효용 가정 출처'])
        def safe(v):
            if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):
                return "'"+v
            return v
        for q in state['questions']:
            writer.writerow([safe(v) for v in [q['id'],q['title'],q['topic'],q['request'],q['criterion'],q['status'],q.get('rank',''),q['importance'],q['eig'],q['score'],q['probability'],q['evsi']['gross'] if q['evsi'] else '',q['evsi']['unit'] if q['evsi'] else '', ';'.join(q['refs']),engine.POLICY,
                state['decisions'].get(q['id'],{}).get('cost'),state['decisions'].get(q['id'],{}).get('delay'),
                q['evsi']['net'] if q['evsi'] else '',q['evsi']['evpi'] if q['evsi'] else '',
                state['models'].get(q['id'],{}).get('source',''),state['decisions'].get(q['id'],{}).get('source','')]])
        return send_file(io.BytesIO(('\ufeff'+buf.getvalue()).encode()),as_attachment=True,download_name='Orion_rules_questions.csv',mimetype='text/csv')

    @app.get('/api/projects/<pid>/analysis')
    def decision_analysis(pid):
        row=store.get(pid)
        return jsonify(analysis.inspect(row['state'],request.args.get('question')))

    @app.get('/api/evaluation')
    def evaluation():
        from orion.rules.benchmark import evaluate
        return jsonify(evaluate())

    @app.get('/api/templates/financial.xlsx')
    def financial_template():
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='재무 관측치'
        ws.append(['항목','값','단위','기간','범위','구분'])
        ws.append(['매출',100,'억원','2025년','별도','실적'])
        ws.append(['매출',120,'억원','2026년','별도','계획'])
        ws.append(['현금',15,'억원','2025년말','별도','실적'])
        note=wb.create_sheet('읽어주세요');note.append(['합성 예시입니다. 실제 회사 자료가 아닙니다. 원본 수치와 기준을 확인한 뒤 교체하세요.'])
        stream=io.BytesIO();wb.save(stream);wb.close();stream.seek(0)
        return send_file(stream,as_attachment=True,download_name='Orion_financial_template.xlsx')

    @app.post('/api/example')
    def example():
        source=('합성 사례입니다. 실제 기업의 자료가 아닙니다.\n'
                '2025년 매출 100 중 반복매출 70이라고 회사가 설명했습니다. 반복매출의 산정 정의는 추가 확인이 필요합니다.\n'
                '고객 A와 B가 주요 고객입니다. 고객별 매출과 독립성, 계약 갱신 조건을 확인해야 합니다.\n'
                '매출 인식·채권 잔액·후속 수금의 연결표는 미제공입니다.\n'
                '성장 전망은 계약 확보와 공급능력 검토가 필요합니다.').encode()
        parsed=parse(source,'합성_사례.txt',python=hosted.python if hosted else None)
        row=store.create('Orion 합성 검증 사례','2025년','subscription')
        fid='d_'+uuid4().hex[:20]
        def setup(s):
            s['demo']=True
            s['deal_visuals']=deal_visuals.sample()
            s['documents']=[dict(id=fid,filename='합성_사례.txt',group='company-example',origin='company',version=1,**parsed)]
            engine.analyze(s)
            for h in s['hypotheses']:
                h.update(approved=True,prior=.3,prior_source='합성 계산 예시 · 실제 기업의 확률 아님',prior_version=1)
            engine.generate(s)
            s['decisions']['recurring.definition']=dict(utilities=[[100,-100],[0,0]],cost=5,delay=0,unit='효용점수',source='2행동×2상태 합성 시나리오')
        return result(store.update(row['id'],row['version'],setup,file=(fid,'합성_사례.txt',parsed['sha256'],source)))

    return app

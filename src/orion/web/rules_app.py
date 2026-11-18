"""Loopback-only persistent rules MVP; separate from the preserved demo app."""
import csv
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, jsonify, request, send_file

from orion.rules import engine
from orion.rules.store import Store, Conflict
from orion.rules.parsing import parse
from orion.rules.case_studies import CaseStudies, apply_scenario


ASSETS = Path(__file__).parent/'assets'


def create_rules_app(data_dir=None, port=8050):
    root=Path(data_dir) if data_dir else Path(__file__).resolve().parents[3]/'.local'/'orion-rules'
    store=Store(root/'projects.sqlite3')
    cases=CaseStudies(root/'case-studies')
    app=Flask(__name__,static_folder=str(ASSETS),static_url_path='/assets')
    app.config['MAX_CONTENT_LENGTH']=16*1024*1024
    app.config['RULES_PORT']=port
    app.extensions['rules_store']=store

    @app.before_request
    def local_only():
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
        return (ASSETS/'rules.html').read_text(encoding='utf-8')

    @app.get('/healthz')
    def health():
        return dict(status='ok',mode='rules_local',live_provider=False,persistent=True,policy=engine.POLICY)

    def result(row):
        return dict(id=row['id'],version=row['version'],state=engine.view(row['state']),snapshots=row['snapshots'])

    @app.get('/api/projects')
    def projects():
        return jsonify(store.list())

    @app.get('/api/cases')
    def case_catalog():
        return jsonify(cases.catalog())

    @app.post('/api/cases/<key>/open')
    def open_case(key):
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
        file=request.files.get('file')
        if not file:
            raise ValueError('자료 파일을 선택하세요.')
        filename=engine.text(file.filename.replace('\\','/').rsplit('/',1)[-1],'파일명',200)
        source=file.read(10*1024*1024+1)
        parsed=parse(source,filename)
        row=store.get(pid)
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
        name,data=store.file(pid,fid)
        return send_file(io.BytesIO(data),as_attachment=True,download_name=name)

    @app.get('/api/projects/<pid>/search')
    def search(pid):
        state=store.get(pid)['state']
        query=engine.text(request.args.get('q',''),'검색어',200,required=False).casefold()
        terms=query.split()
        candidates=[]
        for doc in state['documents']:
            for s in doc['spans']:
                score=sum(t in s['text'].casefold() for t in terms)
                if not terms or score:
                    candidates.append({**s,'document':doc['id'],'filename':doc['filename'],'matches':score})
        return jsonify(sorted(candidates,key=lambda r:(-r['matches'],r['id']))[:40])

    @app.post('/api/projects/<pid>/actions/<action>')
    def mutate(pid,action):
        d=request.get_json()
        operations={'analyze':lambda s:engine.analyze(s),'generate':lambda s:engine.generate(s),
                    'case_scenario':apply_scenario,
                    'hypothesis':lambda s:engine.hypothesis_update(s,d),
                    'question':lambda s:engine.question_update(s,d),
                    'custom':lambda s:engine.custom_question(s,d),
                    'decision':lambda s:engine.decision_update(s,d)}
        if action=='evidence':
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

    @app.post('/api/projects/<pid>/preview')
    def preview(pid):
        d=request.get_json()
        row=store.get(pid)
        if type(d.get('version')) is not int or d['version']!=row['version']:
            raise Conflict('프로젝트가 변경됐습니다. 최신 상태에서 미리보기를 다시 확인하세요.')
        before=engine.snapshot(row['state'])
        state=deepcopy(row['state'])
        e=engine.evidence_apply(state,d,reject=d.get('reject') is True)
        return dict(before=before,after=engine.snapshot(state),evidence={**e,'application':engine.replay(state)[1].get(e['id'],'미적용')})

    @app.get('/api/projects/<pid>/history')
    def history(pid):
        return jsonify(store.history(pid))

    @app.get('/api/projects/<pid>/export/<kind>')
    def export(pid,kind):
        row=store.get(pid);state=engine.view(row['state'])
        if kind=='json':
            data=json.dumps({**row,'state':state,'all_snapshots':store.history(pid)},ensure_ascii=False,indent=2).encode('utf-8')
            return send_file(io.BytesIO(data),as_attachment=True,download_name='Orion_rules_review.json',mimetype='application/json')
        if kind!='csv':
            abort(404)
        buf=io.StringIO(newline='');writer=csv.writer(buf)
        writer.writerow(['질문 ID','질문','가설','요청 자료','판정 기준','상태','현재 추천 순위','중요도','EIG(bits)','추천 점수','가정 기반 확률','EVSI','효용 단위','원문 참조','정책'])
        def safe(v):
            if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):
                return "'"+v
            return v
        for q in state['questions']:
            writer.writerow([safe(v) for v in [q['id'],q['title'],q['topic'],q['request'],q['criterion'],q['status'],q.get('rank',''),q['importance'],q['eig'],q['score'],q['probability'],q['evsi']['gross'] if q['evsi'] else '',q['evsi']['unit'] if q['evsi'] else '', ';'.join(q['refs']),engine.POLICY]])
        return send_file(io.BytesIO(('\ufeff'+buf.getvalue()).encode()),as_attachment=True,download_name='Orion_rules_questions.csv',mimetype='text/csv')

    @app.post('/api/example')
    def example():
        row=store.create('Orion 합성 검증 사례','2025년','subscription')
        source=('합성 사례입니다. 실제 기업의 자료가 아닙니다.\n'
                '2025년 매출 100 중 반복매출 70이라고 회사가 설명했습니다. 반복매출의 산정 정의는 추가 확인이 필요합니다.\n'
                '고객 A와 B가 주요 고객입니다. 고객별 매출과 독립성, 계약 갱신 조건을 확인해야 합니다.\n'
                '매출 인식·채권 잔액·후속 수금의 연결표는 미제공입니다.\n'
                '성장 전망은 계약 확보와 공급능력 검토가 필요합니다.').encode()
        parsed=parse(source,'합성_사례.txt');fid='d_'+uuid4().hex[:20]
        def setup(s):
            s['demo']=True
            s['documents']=[dict(id=fid,filename='합성_사례.txt',group='company-example',origin='company',version=1,**parsed)]
            engine.analyze(s)
            for h in s['hypotheses']:
                h.update(approved=True,prior=.3,prior_source='합성 계산 예시 · 실제 기업의 확률 아님',prior_version=1)
            engine.generate(s)
            s['decisions']['recurring.definition']=dict(utilities=[[100,-100],[0,0]],cost=5,delay=0,unit='효용점수',source='2행동×2상태 합성 시나리오')
        return result(store.update(row['id'],row['version'],setup,file=(fid,'합성_사례.txt',parsed['sha256'],source)))

    return app

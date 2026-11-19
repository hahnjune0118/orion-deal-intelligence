"""Deterministic question selection, explicit Bayesian replay and decision value."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import math
import re
from uuid import uuid4

from orion.quant.bayes import posterior
from orion.quant.information_gain import binary_eig
from .library import TOPICS, RULES, VERSION
from . import financial, retrieval

POLICY = 'adaptive-rules-1.0.0'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def text(value, name, limit=2000, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{name}: {limit}자 이내로 입력하세요.')
    return value.strip()


def number(value, name, lo=0, hi=1, optional=False):
    if optional and value in (None, ''):
        return None
    if isinstance(value, bool):
        raise ValueError(name+' 값을 확인하세요.')
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(name+' 값을 확인하세요.') from None
    if not math.isfinite(n) or not lo <= n <= hi:
        raise ValueError(f'{name}: {lo}~{hi} 범위여야 합니다.')
    return n


def initial(company, period, industry):
    if industry not in {'general', 'subscription', 'manufacturing', 'service'}:
        raise ValueError('업종을 선택하세요.')
    return dict(company=text(company,'기업명',120), period=text(period,'검토 기간',120), industry=industry,
                library=VERSION, policy=POLICY, demo=False, documents=[], hypotheses=[], questions=[],
                evidence=[], models={}, decisions={}, history=[])


def audit(state, action, detail):
    state['history'].append(dict(at=now(), action=action, detail=detail))


def spans(state):
    return [s for doc in state['documents'] for s in doc['spans']]


def analyze(state):
    units = spans(state)
    if not units:
        raise ValueError('자료를 먼저 등록하세요. 추출에 실패한 자료는 분석하지 않습니다.')
    state['financial_facts'] = financial.observations(state['documents'], state.get('financial_facts', []))
    state['reconciliations'] = financial.reconcile(state['financial_facts'])
    if state.get('case_study'):
        audit(state,'사례 근거 재확인','사례별 가설·질문과 원문 연결을 유지합니다. 새 자료의 의미·상충 여부는 담당자가 검토합니다.')
        return
    hits = {topic: [s['id'] for s in units if re.search(spec['pattern'], s['text']+' '+s.get('cell',{}).get('row_context',''), re.I)]
            for topic, spec in TOPICS.items()}
    chosen = ['revenue', 'customer', 'cash']
    extras = [t for t in TOPICS if t not in chosen and hits[t]]
    # Explicit recurring terminology is required even for a subscription company.
    extras.sort(key=lambda t: (t != 'recurring', -len(hits[t]), t))
    chosen += extras[:2]
    known = {h['id'] for h in state['hypotheses']}
    for topic in chosen:
        if topic in known:
            h = next(h for h in state['hypotheses'] if h['id'] == topic)
            h['refs'] = hits[topic][:12]
            h['origin_kind'] = '자료 기반 검증 과제' if h['refs'] else '기본 점검 과제 · 근거 미검출'
            continue
        spec = TOPICS[topic]
        state['hypotheses'].append(dict(id=topic, label=spec['label'],
            origin_kind='자료 기반 검증 과제' if hits[topic] else '기본 점검 과제 · 근거 미검출',
            title=spec['hypothesis'].format(company=state['company'],period=state['period']),
            counter=spec['counter'], refs=hits[topic][:12], approved=False, prior=None,
            prior_source='', prior_version=0, rubric='질문 라이브러리의 검증 과제 · 사실 판정 아님'))
    state['findings'] = []
    for topic in chosen:
        for identifier in hits[topic][:4]:
            unit = find(units,identifier,'원문')
            numbers = re.findall(r'(?<![\w])[-+]?\d[\d,]*(?:\.\d+)?\s*(?:%|억원|백만원|만원|원|달러|명|건|개월|년|USD|KRW)?',unit['text'])
            state['findings'].append(dict(topic=topic,span=identifier,numbers=numbers[:12],
                                           interpretation='원문 표현 추출 · 단위/기간/산정 정의 직접 확인 필요'))
    audit(state, '자료 분석', '키워드 규칙으로 가설 초안을 선택했습니다. 미검출은 부재의 증명이 아닙니다.')


def generate(state):
    approved = {h['id'] for h in state['hypotheses'] if h['approved']}
    if not approved:
        raise ValueError('가설을 먼저 검토·확정하세요.')
    existing = {q['id'] for q in state['questions']}
    for rule in state.get('case_rules',RULES):
        if rule['topic'] not in approved or rule['id'] in existing:
            continue
        q = deepcopy(rule)
        q.update(title=rule['title'].format(company=state['company'],period=state['period']),
                 excluded=False, reviewed_priority=False, version=1, model_version=0)
        if 'source_refs' not in q:
            relevant = [dict(d, spans=[u for u in d['spans'] if re.search(TOPICS[q['topic']]['pattern'],u['text']+' '+u.get('cell',{}).get('row_context',''),re.I)]) for d in state['documents']]
            q['source_refs'] = [r['id'] for r in retrieval.search(relevant, q['title']+' '+q['request'],3)]
            q['retrieval_method'] = retrieval.VERSION
        state['questions'].append(q)
        if state['demo']:
            state['models'][q['id']] = dict(a=.8, b=.2, source='합성 계산 예시 · 경험적 추정 아님', version=1)
    audit(state, '질문 구성', f"라이브러리 {state['library']} · 기존 질문 ID와 답변은 보존")


def hypothesis_update(state, data):
    h = find(state['hypotheses'], data.get('id'), '가설')
    h['title'] = text(data.get('title',h['title']), '가설', 1000)
    h['counter'] = text(data.get('counter',h['counter']), '반대 가설', 1000)
    h['approved'] = data.get('approved') is True
    prior = number(data.get('prior'), '사전확률', optional=True)
    source = text(data.get('prior_source',''), '사전확률 근거', 1000, required=prior is not None)
    if (prior,source) != (h['prior'],h['prior_source']):
        h['prior_version'] += 1
    h.update(prior=prior, prior_source=source)
    replay(state)  # An impossible observation cannot be silently accepted after an assumption change.
    audit(state, '가설 검토', h['id']+' · 사전확률 변경 시 승인 증거를 재생하고 이전 스냅샷을 보존')


def find(rows, identifier, name):
    row = next((r for r in rows if r['id'] == identifier), None)
    if row is None:
        raise ValueError('현재 프로젝트의 '+name+'을 선택하세요.')
    return row


def question_update(state, data):
    q = find(state['questions'], data.get('id'), '질문')
    for key, label, limit in [('title','질문',1500),('request','요청 자료',2000),('criterion','판정 기준',2000)]:
        q[key] = text(data.get(key,q[key]),label,limit)
    q['importance'] = number(data.get('importance',q['importance']),'중요도',1,5)
    q['obtainability'] = number(data.get('obtainability',q['obtainability']),'확보 가능성',1,5)
    q['mandatory'] = data.get('mandatory') is True
    q['excluded'] = data.get('excluded') is True
    if 'gap_codes' in data:
        allowed = {'missing', 'period', 'reconciliation', 'source', 'definition'}
        codes = data['gap_codes']
        if not isinstance(codes,list) or any(c not in allowed for c in codes):
            raise ValueError('증빙 공백 분류를 확인하세요.')
        q['gap_codes'] = sorted(set(codes))
    q['reviewed_priority'] = True
    q['version'] += 1
    a = number(data.get('a'), 'P(지지|H)', optional=True)
    b = number(data.get('b'), 'P(지지|반대 H)', optional=True)
    if (a is None) != (b is None):
        raise ValueError('두 우도를 함께 입력하거나 함께 비우세요.')
    if a is None:
        state['models'].pop(q['id'],None)
    else:
        source = text(data.get('model_source',''),'우도 가정 출처',1000)
        q['model_version'] += 1
        state['models'][q['id']] = dict(a=a,b=b,source=source,version=q['model_version'])
    audit(state,'질문·평가 설정',q['id']+' · 과거 증거에 사용한 우도는 변경하지 않음')


def custom_question(state, data):
    h = find(state['hypotheses'],data.get('topic'),'가설')
    if not h['approved']:
        raise ValueError('확정한 가설에 질문을 추가하세요.')
    state['questions'].append(dict(id='custom.'+uuid4().hex[:12],topic=h['id'],
        title=text(data.get('title'),'질문',1500),request=text(data.get('request'),'요청 자료'),
        criterion=text(data.get('criterion'),'판정 기준'),importance=3,obtainability=3,
        mandatory=False,parent=None,answer=None,excluded=False,reviewed_priority=False,version=1,model_version=0,
        source_refs=[],retrieval_method='담당자 직접 추가 · 근거 미연결'))
    audit(state,'질문 직접 추가','규칙이 다루지 못한 검증 과제를 담당자가 추가')


def replay(state):
    probabilities = {h['id']: h['prior'] for h in state['hypotheses']}
    used, groups = set(), set()
    applied = {}
    for e in state['evidence']:
        if e['status'] != 'approved':
            continue
        hid = e['hypothesis']
        key = (hid,e['fingerprint'])
        group = (hid,e['group'])
        if e['outcome'] in {'insufficient','reopen'}:
            applied[e['id']] = '불충분/재개 · 확률 유지'
            continue
        if key in used or group in groups:
            applied[e['id']] = '중복·동일 의존 그룹 · 확률 중복 반영 안 함'
            continue
        if any(g[0] == hid for g in groups) and not e['independent']:
            applied[e['id']] = '추가 증거 독립성 미확인 · 확률 반영 보류'
            continue
        model = e.get('model')
        if probabilities.get(hid) is None or not model:
            applied[e['id']] = '확률 가정 미설정 · 질문 상태만 반영'
            continue
        a,b = model['a'],model['b']
        if e['outcome'] == 'contradict':
            a,b = 1-a,1-b
        probabilities[hid] = posterior(probabilities[hid],a,b)
        used.add(key);groups.add(group)
        applied[e['id']] = '검토된 가정으로 반영'
    return probabilities, applied


def latest_answers(state):
    answers = {}
    for e in state['evidence']:
        if e['status'] == 'approved':
            answers[e['question']] = e['outcome']
    return answers


def evsi(p, model, decision):
    if p is None or not model or not decision:
        return None
    result = binary_eig(p,model['a'],model['b'],model['source'])
    u = decision['utilities']
    utility = lambda prob: max(prob*a+(1-prob)*b for a,b in u)
    before = utility(p)
    after = sum(a.probability*utility(a.posterior) for a in result.answers if a.posterior is not None)
    gross = max(0.,after-before)
    perfect = p*max(row[0] for row in u)+(1-p)*max(row[1] for row in u)-before
    return dict(gross=gross,net=gross-decision['cost']-decision['delay'],evpi=max(0.,perfect),
                unit=decision['unit'],source=decision['source'])


def decision_update(state, data):
    q = find(state['questions'],data.get('id'),'질문')
    utilities = [[number(data.get(key),label,-1e12,1e12) for key,label in pair]
                 for pair in [[('go_h','진행·H'),('go_not','진행·반대 H')],[('hold_h','보류·H'),('hold_not','보류·반대 H')]]]
    state['decisions'][q['id']] = dict(utilities=utilities,cost=number(data.get('cost'),'질문 비용',0,1e12),
        delay=number(data.get('delay',0),'지연 비용',0,1e12),unit=text(data.get('unit'),'효용 단위',40),
        source=text(data.get('source'),'효용 가정 출처',1000))
    audit(state,'EVSI 시나리오',q['id']+' · 실제 거래가치 추정 아님')


def ranked(state):
    probabilities,_ = replay(state)
    answers = latest_answers(state)
    hypotheses = {h['id']:h for h in state['hypotheses']}
    rows = []
    sources = {u['id']:u for u in spans(state)}
    current_recon = {r['id']+':'+r['difference']+':'+r['period']+':'+r['scope'] for r in financial.reconcile(state.get('financial_facts',[])) if financial.decimal(r['difference'])!=0}
    for q in state['questions']:
        h = hypotheses[q['topic']]
        active = h['approved'] and (not q['parent'] or answers.get(q['parent']) == q['answer'])
        if q.get('reconciliation_signature') and q['reconciliation_signature'] not in current_recon:
            active = False
        status = {'support':'해소','contradict':'해소·반박','insufficient':'보완 필요','reopen':'검토 대기'}.get(answers.get(q['id']),'검토 대기')
        model = state['models'].get(q['id'])
        info = binary_eig(probabilities[q['topic']],model['a'],model['b'],model['source']) if model else None
        gap = min(1., .4+.15*len(q['gap_codes'])) if 'gap_codes' in q else 1. if status == '보완 필요' else .8
        parts = dict(importance=.35*q['importance']/5,gap=.25*gap,obtainability=.15*q['obtainability']/5)
        if info:
            parts['eig'] = .25*info.eig_bits
        score = 100*sum(parts.values())/(1 if info else .75)
        row = {**q, 'active':active,'status':status,'probability':probabilities[q['topic']],
               'eig':info.eig_bits if info else None,'score':score,'parts':parts,
               'provisional':not q['reviewed_priority'] or info is None,
               'evsi':evsi(probabilities[q['topic']],model,state['decisions'].get(q['id'])),
               'eligible':active and not q['excluded'] and status in {'검토 대기','보완 필요'},
               'refs':q.get('source_refs',h['refs']), 'grounding':dict(method=q.get('retrieval_method','사례 작성·기존 주제 연결'), observation='; '.join(sources[r]['text'][:240] for r in q.get('source_refs',h['refs']) if r in sources)[:800], gap=q['criterion'], verified=False), 'reason':('필수 확인 우선 · ' if q['mandatory'] else '')+
                   ('정보량·중요도·공백·확보 가능성 평가' if info else 'EIG 미계산 · 정성 가중치 재정규화')}
        rows.append(row)
    candidates = sorted([q for q in rows if q['eligible']],key=lambda q:(not q['mandatory'],-q['score'],q['id']))
    for i,q in enumerate(candidates,1):
        q['rank'] = i
    return rows,candidates


def evidence_apply(state, data, *, reject=False):
    q = find(state['questions'],data.get('question'),'질문')
    if not find(state['hypotheses'],q['topic'],'가설')['approved']:
        raise ValueError('가설을 먼저 확정하세요.')
    outcome = data.get('outcome')
    if outcome not in {'support','contradict','insufficient','reopen'}:
        raise ValueError('판정 결과를 선택하세요.')
    note = text(data.get('note'),'판정 근거',2000)
    source_id = data.get('span')
    if source_id:
        unit = find(spans(state),source_id,'원문 구간')
        quote = unit['text']
        doc = next(d for d in state['documents'] if any(s['id'] == source_id for s in d['spans']))
        default_group = doc['group']
        origin = doc['filename']+' · '+unit['location']
    else:
        quote = text(data.get('response'),'답변 원문',6000)
        default_group = 'management-response'
        origin = '담당자 입력 답변 · 외부 검증 전'
    group = text(data.get('group') or default_group,'증거 의존 그룹',120)
    fingerprint = sha256(re.sub(r'\s+',' ',quote.strip()).encode()).hexdigest()
    if not reject and any(e['status']=='approved' and e['hypothesis']==q['topic'] and e['fingerprint']==fingerprint for e in state['evidence']):
        raise ValueError('동일 원문/답변은 이 가설에 이미 적용됐습니다. 기존 증거를 확인하세요.')
    e = dict(id='e_'+uuid4().hex[:16],question=q['id'],question_version=q['version'],hypothesis=q['topic'],
             outcome=outcome,note=note,span=source_id,quote=quote,origin=origin,group=group,fingerprint=fingerprint,
             independent=data.get('independent') is True,status='rejected' if reject else 'approved',
             practice=data.get('practice') is True,
             model=deepcopy(state['models'].get(q['id'])),at=now())
    state['evidence'].append(e)
    replay(state)
    audit(state,'증거 반려' if reject else '증거 적용',e['id']+' · '+q['id'])
    return e


def snapshot(state):
    rows,candidates = ranked(state)
    probabilities,_ = replay(state)
    return dict(at=now(),policy=POLICY,library=state['library'],probabilities=probabilities,
                ranks={q['id']:q['rank'] for q in candidates},
                questions={q['id']:dict(title=q['title'],status=q['status'],score=q['score'],eig=q['eig'],evsi=deepcopy(q['evsi']),active=q['active'],importance=q['importance'],obtainability=q['obtainability'],gap_codes=q.get('gap_codes'),refs=q['refs'],mandatory=q['mandatory']) for q in rows},
                decisions=deepcopy(state['decisions']), financial_facts=deepcopy(state.get('financial_facts',[])), evidence=deepcopy(state['evidence']),
                deal_visuals=deepcopy(state.get('deal_visuals')),
                assumptions=deepcopy(state['models']),priors={h['id']:dict(prior=h['prior'],source=h['prior_source'],version=h['prior_version']) for h in state['hypotheses']},
                documents=[dict(id=d['id'],sha256=d['sha256'],version=d['version']) for d in state['documents']])


def view(state):
    probabilities,applied = replay(state)
    rows,candidates = ranked(state)
    return {**state, 'financial_facts':state.get('financial_facts',[]), 'reconciliations':financial.reconcile(state.get('financial_facts',[])), 'hypotheses':[{**h,'probability':probabilities[h['id']]} for h in state['hypotheses']],
            'questions':rows,'recommendations':[q['id'] for q in candidates[:3]],
            'evidence':[{**e,'application':applied.get(e['id'],'미적용')} for e in state['evidence']]}


def fact_update(state, data):
    fact = find(state.get('financial_facts',[]),data.get('id'),'재무 관측치')
    for key in financial.FIELDS:
        fact[key] = str(financial.decimal(data.get(key))) if key=='value' else text(data.get(key),key,120)
    if fact['unit'] not in financial.UNITS:
        raise ValueError('지원 단위: '+', '.join(financial.UNITS))
    fact['reviewed'] = data.get('reviewed') is True
    fact['review_note'] = text(data.get('review_note',''),'검토 근거',1000,required=fact['reviewed'])
    state['reconciliations'] = financial.reconcile(state['financial_facts'])
    audit(state,'재무 관측치 검토',fact['id'])
    # Difference questions are generated only from reviewed matching-basis facts.
    for r in state['reconciliations']:
        signature=r['id']+':'+r['difference']+':'+r['period']+':'+r['scope']
        identifier=r['id']+'_'+sha256(signature.encode()).hexdigest()[:8]
        if financial.decimal(r['difference'])==0 or any(q['id']==identifier for q in state['questions']):
            continue
        topic = 'revenue' if r['metric'] in {'매출','매출액','revenue'} else 'cash' if '현금' in r['metric'] or '수금' in r['metric'] else 'margin'
        if not any(h['id']==topic for h in state['hypotheses']):
            continue
        state['questions'].append(dict(id=identifier,topic=topic,
            title=f"{r['period']} {r['scope']} {r['metric']}의 자료 간 차이 {r['difference']} {r['unit']}를 설명해 주십시오.",
            request='동일 기간·범위·정의의 대사표와 차이 원인 증빙',criterion='검토된 두 원천의 차이 원인과 수정 여부 확인',
            importance=5,obtainability=3,mandatory=True,parent=None,answer=None,excluded=False,
            reviewed_priority=False,version=1,model_version=0,source_refs=r['refs'],reconciliation_id=r['id'],reconciliation_signature=signature))


def evidence_trace(state):
    partial=deepcopy(state);partial['evidence']=[];trace=[]
    for e in state['evidence']:
        before,_=replay(partial);partial['evidence'].append(e);after,applied=replay(partial)
        m=e.get('model');likelihood=None
        if m and e['outcome'] in {'support','contradict'}:
            a,b=(m['a'],m['b']) if e['outcome']=='support' else (1-m['a'],1-m['b'])
            likelihood='무한대' if b==0 and a else None if b==0 else a/b
        trace.append(dict(id=e['id'],question=e['question'],outcome=e['outcome'],status=e['status'],
            before=before.get(e['hypothesis']),after=after.get(e['hypothesis']),likelihood_ratio=likelihood,
            application=applied.get(e['id'],'미적용'),model=deepcopy(m),source=e['origin']))
    return trace


def fact_add(state, data):
    span=find(spans(state),data.get('span'),'원문')
    # User-selected numeric cells/text; no automatic meaning assignment.
    cell=span.get('cell',{})
    value=financial.decimal(cell.get('cached') if cell else data.get('value'))
    doc=next(d for d in state['documents'] if span in d['spans'])
    identifier='manual_'+sha256(span['id'].encode()).hexdigest()[:20]
    facts=state.setdefault('financial_facts',[])
    if any(f['span']==span['id'] for f in facts):
        return  # Reuse an existing observation, including an automatically extracted one.
    if not any(f['id']==identifier for f in facts):
        facts.append(dict(id=identifier,span=span['id'],document=doc['id'],filename=doc['filename'],location=span['location'],
            metric='',value=str(value),unit='',period='',scope='',basis='',reviewed=False,manual=True))
    audit(state,'재무 관측치 직접 등록',identifier+' · 해석 검토 필요')

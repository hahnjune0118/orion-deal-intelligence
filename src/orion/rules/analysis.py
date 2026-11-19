"""Read-only decision branches, sensitivity and transparent policy comparisons."""
from copy import deepcopy
from . import engine
from orion.quant.information_gain import binary_eig


def tree(state, q):
    model=state['models'].get(q['id']);decision=state['decisions'].get(q['id'])
    if model is None or q['probability'] is None:
        return dict(available=False,reason='사전확률과 우도 가정이 필요합니다.')
    result=binary_eig(q['probability'],model['a'],model['b'],model['source'])
    def action(p):
        if not decision or p is None:
            return None
        values=[p*a+(1-p)*b for a,b in decision['utilities']]
        best=max(values)
        return dict(actions=[['진행','보류'][i] for i,v in enumerate(values) if abs(v-best)<1e-10],utility=best)
    return dict(available=True,prior=q['probability'],entropy=result.prior_entropy_bits,
        current_action=action(q['probability']),unit=decision['unit'] if decision else None,
        answers=[dict(answer=['지지','반박'][i],mass=a.probability,posterior=a.posterior,
                      entropy=a.entropy_bits,action=action(a.posterior)) for i,a in enumerate(result.answers)],
        eig=q['eig'],evsi=q['evsi'],source=model['source'])


def inspect(state, question):
    rows,candidates=engine.ranked(state)
    q=engine.find(rows,question,'질문')
    h=engine.find(state['hypotheses'],q['topic'],'가설')
    baseline=[r['id'] for r in candidates[:3]]
    scenarios=[]
    settings=[('사전확률',v) for v in (.1,.3,.5,.7,.9)]
    settings += [('우도 차이',v) for v in (-.1,.1)] if q['id'] in state['models'] else []
    settings += [('비용 배수',v) for v in (.5,2)] if q['id'] in state['decisions'] else []
    for kind,value in settings:
        trial=deepcopy(state)
        if kind=='사전확률':
            engine.find(trial['hypotheses'],h['id'],'가설')['prior']=value
        elif kind=='우도 차이':
            m=trial['models'][q['id']]
            m.update(a=max(0,min(1,m['a']+value)),b=max(0,min(1,m['b']-value)))
        else:
            d=trial['decisions'][q['id']];d['cost']*=value;d['delay']*=value
        try:
            rr,cc=engine.ranked(trial);target=engine.find(rr,q['id'],'질문')
            top=[r['id'] for r in cc[:3]]
            scenarios.append(dict(parameter=kind,value=value,probability=target['probability'],eig=target['eig'],
                evsi=target['evsi'],rank=target.get('rank'),top3=top,overlap=len(set(top)&set(baseline)),error=None))
        except (ValueError, ArithmeticError) as e:
            scenarios.append(dict(parameter=kind,value=value,error=str(e)))
    # Same candidates and mandatory-first constraints for qualitative and EIG arms.
    qualitative=sorted(candidates,key=lambda r:(not r['mandatory'],-sum(v for k,v in r['parts'].items() if k!='eig')/.75,r['id']))
    fixed=sorted(candidates,key=lambda r:next(i for i,v in enumerate(state['questions']) if v['id']==r['id']))
    groups={}
    for r in candidates:
        if r['evsi'] is not None:
            key=(r['evsi']['unit'],r['evsi']['source'])
            groups.setdefault(key,[]).append(r)
    return dict(question=q['id'],tree=tree(state,q),scenarios=scenarios,
        comparison=dict(fixed=[r['id'] for r in fixed[:3]],qualitative=[r['id'] for r in qualitative[:3]],eig=baseline,
            evsi=[dict(unit=key[0],source=key[1],top3=[r['id'] for r in sorted(group,key=lambda r:-r['evsi']['net'])[:3]]) for key,group in groups.items()]),
        trace=engine.evidence_trace(state),
        note='읽기 전용 가정 실험입니다. 실제 저장 확률·추천은 바꾸지 않습니다. 사전확률 변경은 기존 승인 증거를 재생하고, 우도 변경은 다음 질문의 정보량에만 적용합니다. 비교는 동일 후보를 사용하며 EVSI는 동일 효용 기준 내에서만 비교합니다.')

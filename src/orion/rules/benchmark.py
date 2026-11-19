"""Small authored synthetic policy experiment, not an external performance study."""
from copy import deepcopy
import hashlib
import math
from . import engine


def fixtures():
    for kind in ('판단 경계', '정보량과 판단가치의 차이', '비용이 큰 정보'):
        s=engine.initial('공유 가능한 합성 기업', '2025년', 'service')
        s['documents']=[dict(id='doc',filename='합성.txt',spans=[dict(id='source',text='합성 계약 매출 수금 자료',location='1행')])]
        s['hypotheses']=[dict(id='revenue',label='합성 매출 가설',title='합성 계약을 증빙할 수 있다.',counter='증빙할 수 없다.',refs=['source'],approved=True,prior=.5,prior_source='작성된 합성 확률',prior_version=1)]
        for i,(a,b,importance) in enumerate(((.6,.4,5),(.9,.1,3),(.8,.2,4),(.5,.5,5),(.7,.3,3))):
            key='eval.'+str(i)
            s['questions'].append(dict(id=key,topic='revenue',title=f'합성 확인 질문 {i}',request='계약·대사표',criterion='정의·범위·기간 일치',
                importance=importance,obtainability=3,mandatory=False,parent=None,answer=None,excluded=False,
                reviewed_priority=True,source_refs=['source'],version=1,model_version=1))
            s['models'][key]=dict(a=a,b=b,source='공통 합성 가정')
            s['decisions'][key]=dict(utilities=[[100,-100],[0,0]],cost=2 if i!=1 else 15,delay=0,unit='공통 효용점수',source='동일 합성 의사결정')
        if kind=='정보량과 판단가치의 차이':
            for d in s['decisions'].values():d['utilities']=[[100,100],[0,0]]
        if kind=='비용이 큰 정보':
            s['decisions']['eval.1']['cost']=70
        yield kind,s


def evaluate():
    rows=[];recipes=[]
    # Authored reference labels are evaluation-only; they never reach the engine.
    relevance={'eval.0':1,'eval.1':3,'eval.2':3,'eval.3':0,'eval.4':2}
    for name,s in fixtures():
        rr,cc=engine.ranked(s)
        arms={'고정 체크리스트':rr, '정성 중요도':sorted(cc,key=lambda q:(-sum(v for k,v in q['parts'].items() if k!='eig'),q['id'])),
              'Bayesian·EIG':cc, 'EVSI·비용':sorted(cc,key=lambda q:(-q['evsi']['net'],q['id']))}
        recipes.append(dict(name=name,models=s['models'],decisions=s['decisions'],prior=.5,reference_labels=relevance))
        for arm,qs in arms.items():
            top=qs[:3];ids=[q['id'] for q in top]
            dcg=sum((2**relevance[q]-1)/math.log2(i+2) for i,q in enumerate(ids))
            ideal=sum((2**v-1)/math.log2(i+2) for i,v in enumerate(sorted(relevance.values(),reverse=True)[:3]))
            # Independent approved synthetic observation; measure actual replay, not a forced rank.
            trial=deepcopy(s)
            e=engine.evidence_apply(trial,dict(question=ids[0],outcome='support',response='합성 답변',note='합성 검토',group='synthetic',independent=False))
            after=engine.view(trial)
            rows.append(dict(case=name,arm=arm,top3=ids,critical_recall=sum(q in ids for q in ('eval.1','eval.2'))/2,
                ndcg=dcg/ideal,minutes=15,budget='질문당 5분 × 3개 = 15분 (합성 가정)',
                first_evsi=top[0]['evsi']['net'],posterior=after['hypotheses'][0]['probability'],
                next_top3=after['recommendations'],evidence_id=e['id'].split('_')[0],
                source_link_coverage=sum(bool(q['refs']) for q in top)/3))
    canonical=repr(recipes).encode()
    return dict(version='rules-mvp-evaluation-1',scope='작성된 합성 사례 3개 · 외부/독립 검증 아님',
        input_sha256=hashlib.sha256(canonical).hexdigest(),rows=rows,
        limitations=['실제 기업 성능·투자 수익 개선의 증거가 아닙니다.',
          '참조 중요도는 작성자가 지정했으며 독립 검토와 미사용 자료 검증은 미실행입니다.',
          'EVSI는 동일 효용 기준의 개별 질문 가치입니다. 질문 간 값을 더해 포트폴리오 가치로 해석하지 않습니다.',
          '근거 연결률은 ID 존재 검사이며 의미적 적합성은 사람 검토가 필요합니다.',
          '정책마다 장단점이 드러나도록 모든 결과를 공개하며 우수한 결과만 선택하지 않습니다.'])

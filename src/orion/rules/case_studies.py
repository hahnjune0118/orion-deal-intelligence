"""Local, already anonymized case packs. Raw source paths are never served."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

from . import engine


class CaseStudies:
    def __init__(self,root):
        self.root=Path(root)

    def read(self,key):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,60}',key or ''):
            raise ValueError('사례를 선택하세요.')
        path=self.root/(key+'.json')
        if not path.is_file() or path.stat().st_size>15_000_000:
            raise ValueError('이 PC에 등록된 사례가 아닙니다.')
        pack=json.loads(path.read_text(encoding='utf-8'))
        if pack.get('schema')!='orion-anonymized-case-1' or pack.get('id')!=key:
            raise ValueError('사례 형식을 확인하세요.')
        return pack

    def catalog(self):
        rows=[]
        for path in sorted(self.root.glob('*.json')):
            pack=self.read(path.stem)
            rows.append({k:pack[k] for k in ('id','title','description','period')})
        return rows

    def open(self,store,key,*,copy=False):
        pack=self.read(key)
        if not copy:
            for row in store.list():
                current=store.get(row['id'])
                if current['state'].get('case_study',{}).get('id')==key:
                    return current
        state=engine.initial(pack['title'],pack['period'],pack['industry'])
        state['library']='local-case-'+key+'-v1'
        state['case_study']=deepcopy(pack['case_study'])
        state['case_study']['id']=key
        state['case_rules']=deepcopy(pack['questions'])
        state['hypotheses']=deepcopy(pack['hypotheses'])
        state['documents']=deepcopy(pack['documents'])
        files=[];identifiers=set()
        for doc in state['documents']:
            if not doc.get('masked') or not doc['spans']:
                raise ValueError('사례에는 마스킹한 텍스트와 위치 근거가 필요합니다.')
            content='\n\n'.join(s['location']+'\n'+s['text'] for s in doc['spans']).encode('utf-8')
            if sha256(content).hexdigest()!=doc['sha256']:
                raise ValueError('사례의 마스킹 텍스트 해시가 일치하지 않습니다.')
            identifiers.update(s['id'] for s in doc['spans'])
            files.append((doc['id'],Path(doc['filename']).stem+'_마스킹텍스트.txt',doc['sha256'],content))
        for h in state['hypotheses']:
            if h['prior'] is not None or any(r not in identifiers for r in h['refs']):
                raise ValueError('사례 근거·초기 확률을 확인하세요.')
        for q in state['case_rules']:
            if any(r not in identifiers for r in q.get('source_refs',[])):
                raise ValueError('질문의 원문 연결을 확인하세요.')
        engine.generate(state)
        engine.audit(state,'익명화 사례 열기','자료 기재·검토 쟁점·실습 계산 가정을 구분한 사례 초안입니다. 원본 바이너리는 포함하지 않습니다.')
        return store.import_case(state,files)


def apply_scenario(state):
    case=state.get('case_study')
    if not case:
        raise ValueError('등록된 사례에서만 사용할 수 있습니다.')
    if case.get('scenario_enabled'):
        raise ValueError('이미 적용했습니다. 개별 가설·질문 상세에서 가정을 수정하세요.')
    scenario=case['practice_assumptions']
    for h in state['hypotheses']:
        assumptions=scenario['priors'].get(h['id'])
        if assumptions is not None:
            engine.hypothesis_update(state,dict(id=h['id'],approved=h['approved'],prior=assumptions,
                                              prior_source=scenario['source']))
    for q in state['questions']:
        model=scenario['models'].get(q['id'])
        if not model:
            continue  # A manually added question has no authored practice likelihood.
        engine.question_update(state,{**q,**model,'model_source':scenario['source']})
        # Loading a practice rubric is not the user's review of financial materiality.
        q['reviewed_priority']=False
        decision=scenario['decisions'].get(q['id'])
        if decision:
            engine.decision_update(state,dict(id=q['id'],**decision,source=scenario['source']))
    case['scenario_enabled']=True
    engine.audit(state,'실습 계산 가정 적용','확률·우도·효용·비용은 실제 딜에서 추정한 수치가 아닌 편집 가능한 시나리오입니다.')

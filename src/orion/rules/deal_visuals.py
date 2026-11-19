"""Explicit deal diagrams and FDD adjustment scenarios, independent of evidence approval."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from .financial import decimal

VERSION = 'deal-visuals-1'
STREAMS = {'qoe': 'QoE · 정상화 EBITDA', 'nwc': 'NWC · 영업운전자본', 'net_debt': 'Net Debt · 순차입금'}
CATEGORIES = {'qoe': ['일회성 비용', '일회성 수익', 'Run-rate', '회계정책', '기타'],
              'nwc': ['매출채권', '재고', '매입채무', '미지급비용', '기타 영업항목'],
              'net_debt': ['차입금', '현금·현금성', '리스', '채무 유사항목', '기타']}
KINDS = ['보통주', '은행차입', 'CB', 'RCPS', '리스', '기타 부채', '기타 자본']


def empty():
    return dict(schema=VERSION, origin='manual', unit='억원', scope='', earnings_period='', balance_date='',
                entity='인수 주체 / SPC', notes='', assets=None, balance_complete=False,
                bases=dict(qoe=None, nwc=None, net_debt=None), base_refs=[],
                ev_mode='fixed', enterprise_value=None, multiple=None, peg=None,
                flows=[], instruments=[], adjustments=[])


def _text(value, label, maximum=500, required=True):
    if not isinstance(value, str) or len(value)>maximum or (required and not value.strip()):
        raise ValueError(label+' 내용을 확인하세요.')
    return value.strip()


def _amount(value, optional=False, positive=False):
    if value in (None, '') and optional:
        return None
    result=decimal(value)
    if positive and result<0:
        raise ValueError('음수가 될 수 없는 금액입니다.')
    return str(result)


def _refs(state, values):
    allowed={s['id'] for d in state['documents'] for s in d['spans']}
    if not isinstance(values,list) or len(values)>10 or any(v not in allowed for v in values):
        raise ValueError('현재 프로젝트의 원문 근거를 선택하세요.')
    return list(dict.fromkeys(values))


def update(state, data):
    if not state.get('deal_visuals'):
        state['deal_visuals']=_initial_model(state)
    model=state['deal_visuals']
    operation=data.get('operation')
    if operation=='settings':
        unit=data.get('unit')
        if unit not in {'원','백만원','억원','USD'}:
            raise ValueError('표시 단위를 확인하세요.')
        has_numbers=any(model[k] for k in ('flows','instruments','adjustments')) or any(v is not None for v in model['bases'].values()) or any(model[k] is not None for k in ('assets','enterprise_value','peg'))
        if unit!=model['unit'] and has_numbers:
            raise ValueError('금액이 입력된 시나리오의 단위를 바꿀 수 없습니다. 새 프로젝트에서 작성하세요.')
        for k in ('scope','earnings_period','balance_date','entity','notes'):
            model[k]=_text(data.get(k,''),k,1000,required=k=='entity')
        model['unit']=unit
        model['base_refs']=_refs(state,data.get('base_refs',[]))
        model['assets']=_amount(data.get('assets'),True,True)
        model['balance_complete']=data.get('balance_complete') is True
        model['bases']={k:_amount(data.get(k),True) for k in STREAMS}
        model['ev_mode']=data.get('ev_mode','fixed')
        if model['ev_mode'] not in {'fixed','multiple'}:
            raise ValueError('기업가치 계산 방식을 확인하세요.')
        for key in ('enterprise_value','multiple','peg'):
            model[key]=_amount(data.get(key),True,positive=key!='peg')
    elif operation in {'save','delete'}:
        section=data.get('section')
        if section not in {'flows','instruments','adjustments'}:
            raise ValueError('시각화 항목을 선택하세요.')
        items=model[section];identifier=data.get('item_id')
        old=next((i for i in items if i['id']==identifier),None)
        if identifier and old is None:
            raise ValueError('현재 시나리오의 항목이 아닙니다.')
        if operation=='delete':
            if old is None:
                raise ValueError('삭제할 항목을 선택하세요.')
            items.remove(old)
        else:
            if not old and len(items)>=40:
                raise ValueError('유형별 40개 항목 한도입니다.')
            row=dict(id=identifier or 'v_'+uuid4().hex[:16],label=_text(data.get('label'),'항목명',160),
                     note=_text(data.get('note',''),'입력 근거',1000),refs=_refs(state,data.get('refs',[])))
            if section=='flows':
                if data.get('side') not in {'source','use'}:
                    raise ValueError('Source / Use를 선택하세요.')
                row.update(side=data['side'],amount=_amount(data.get('amount'),positive=True))
            elif section=='instruments':
                if data.get('kind') not in KINDS or data.get('classification') not in {'liability','equity','split','unknown'}:
                    raise ValueError('상품과 회계 분류를 확인하세요.')
                row.update(kind=data['kind'],classification=data['classification'],
                    issuer=_text(data.get('issuer'),'발행 주체',160),terms=_text(data.get('terms',''),'계약 조건',1000,False),
                    proceeds=_amount(data.get('proceeds'),True,True),book=_amount(data.get('book'),positive=data['kind']!='기타 자본'))
                row['liability_part']=_amount(data.get('liability_part'),True,True)
                if row['classification']=='split' and (row['liability_part'] is None or not 0<=decimal(row['liability_part'])<=decimal(row['book'])):
                    raise ValueError('복합상품은 0~장부금액 범위의 부채 부분을 입력하세요.')
                if row['kind'] in {'CB','RCPS'} and row['classification']!='unknown' and not row['terms']:
                    raise ValueError('CB·RCPS 회계 분류에는 검토한 계약 조건을 기록하세요.')
                if decimal(row['book'])<0 and (row['kind']!='기타 자본' or row['classification']!='equity'):
                    raise ValueError('조달 상품 장부금액은 음수가 될 수 없습니다.')
            else:
                stream=data.get('stream');status=data.get('status')
                if stream not in STREAMS or data.get('category') not in CATEGORIES[stream] or status not in {'proposed','accepted','rejected'}:
                    raise ValueError('FDD 구분·하위 항목·검토 상태를 확인하세요.')
                question=data.get('question_id') or None
                if question and not any(q['id']==question for q in state['questions']):
                    raise ValueError('연결할 질문을 확인하세요.')
                row.update(stream=stream,category=data['category'],status=status,question_id=question,
                    amount=_amount(data.get('amount')),economic_key=_text(data.get('economic_key',''),'중복 검토 키',100,False).casefold())
            if old:
                items[items.index(old)]=row
            else:
                items.append(row)
    else:
        raise ValueError('시각화 저장 작업을 확인하세요.')


def _bridge(start, rows):
    if start is None:
        return dict(available=False,reason='기준 금액을 입력하세요.',rows=rows)
    running=decimal(start);steps=[]
    for row in rows:
        before=running;running+=decimal(row['amount'])
        steps.append({**row,'before':str(before),'after':str(running)})
    return dict(available=True,start=str(decimal(start)),end=str(running),delta=str(running-decimal(start)),rows=steps)


def calculate(model, include_proposed=False):
    sources=[r for r in model['flows'] if r['side']=='source'];uses=[r for r in model['flows'] if r['side']=='use']
    total=lambda rows:sum((decimal(r['amount']) for r in rows),Decimal(0))
    liability=equity=unknown=Decimal(0)
    for row in model['instruments']:
        if row['issuer']!=model['entity']:
            continue
        amount=decimal(row['book'])
        if row['classification']=='liability':liability+=amount
        elif row['classification']=='equity':equity+=amount
        elif row['classification']=='split':
            liability+=decimal(row['liability_part']);equity+=amount-decimal(row['liability_part'])
        else:unknown+=amount
    capital=dict(liability=str(liability),equity=str(equity),unknown=str(unknown),total=str(liability+equity+unknown),
        issuer=model['entity'], excluded_issuers=sum(r['issuer']!=model['entity'] for r in model['instruments']),
        balance_gap=str(decimal(model['assets'])-liability-equity) if model['assets'] is not None and model['balance_complete'] and not any(r['classification']=='unknown' and r['issuer']==model['entity'] for r in model['instruments']) else None)
    active=[r for r in model['adjustments'] if r['status']=='accepted' or include_proposed and r['status']=='proposed']
    bridges={k:_bridge(model['bases'][k],[r for r in active if r['stream']==k]) for k in STREAMS}
    duplicate_keys={r['economic_key'].casefold() for r in active if r['stream']=='nwc' and r['economic_key']} & {r['economic_key'].casefold() for r in active if r['stream']=='net_debt' and r['economic_key']}
    missing_keys=[r['label'] for r in active if r['stream'] in {'nwc','net_debt'} and not r['economic_key']]
    warnings=[]
    if duplicate_keys:warnings.append('NWC·Net Debt에 동일 항목이 중복 반영돼 지분가치 브리지를 보류합니다: '+', '.join(sorted(duplicate_keys)))
    if missing_keys:warnings.append('NWC·Net Debt 중복 검토 키를 입력해야 지분가치 브리지를 계산합니다: '+', '.join(missing_keys))
    ev=decimal(model['enterprise_value']) if model['enterprise_value'] is not None else None
    if model['ev_mode']=='multiple':
        ev=decimal(model['bases']['qoe'])*decimal(model['multiple']) if model['bases']['qoe'] is not None and model['multiple'] is not None else None
    ready=ev is not None and model['peg'] is not None and bridges['nwc']['available'] and bridges['net_debt']['available'] and not duplicate_keys and not missing_keys and bool(model['scope'] and model['balance_date']) and (model['ev_mode']=='fixed' or bool(model['earnings_period']))
    if ready:
        start=ev-decimal(model['bases']['net_debt'])+decimal(model['bases']['nwc'])-decimal(model['peg'])
        price_rows=[]
        for k in STREAMS:
            if not bridges[k]['available']:continue
            change=decimal(bridges[k]['delta'])* (decimal(model['multiple']) if model['ev_mode']=='multiple' else 0) if k=='qoe' else decimal(bridges[k]['delta'])*(-1 if k=='net_debt' else 1)
            price_rows.append(dict(id=k,label=STREAMS[k]+' 영향',amount=str(change)))
        price=_bridge(str(start),price_rows)
    else:price=dict(available=False,reason='대상 범위·기준일·손익 기간과 EV 또는 EBITDA·배수, NWC, Net Debt, NWC 목표값을 확인하세요. 중복 항목·누락된 검토 키가 있으면 먼저 정리하세요.')
    if total(sources)!=total(uses):warnings.append('Sources와 Uses의 차이가 있습니다. 미배분 자금·미확보 재원·누락 비용을 확인하세요.')
    return dict(flow=dict(sources=sources,uses=uses,total_sources=str(total(sources)),total_uses=str(total(uses)),gap=str(total(sources)-total(uses))),
                capital=capital,bridges=bridges,price=price,warnings=warnings,include_proposed=include_proposed)


def view(state):
    model=deepcopy(state.get('deal_visuals') or _initial_model(state))
    model['linked_preview']=not bool(state.get('deal_visuals')) and model['origin']=='case_budget'
    return dict(model=model,accepted=calculate(model),preview=calculate(model,True))


def _initial_model(state):
    if state.get('case_study',{}).get('waterfall'):
        temporary={'case_study':state['case_study']}
        try:
            import_budget(temporary)
            return temporary['deal_visuals']
        except ValueError:
            pass  # Unsupported budgets remain empty, never repaired by invented cash flows.
    return empty()


def import_budget(state):
    """Import only an already authored, reconciled case budget; never infer financing terms."""
    model=state.setdefault('deal_visuals',empty())
    if model['flows']:
        raise ValueError('기존 자금 항목이 있습니다. 중복 가져오기는 허용하지 않습니다.')
    if model['unit']!='억원' and (model['instruments'] or model['adjustments'] or any(v is not None for v in model['bases'].values()) or any(model[k] is not None for k in ('assets','enterprise_value','peg'))):
        raise ValueError('기존 시나리오 단위와 사례 예산의 억원 단위가 다릅니다.')
    budget=state.get('case_study',{}).get('waterfall')
    if not budget:
        raise ValueError('연결할 사례 자금표가 없습니다.')
    values=[decimal(v) for v in budget['values']]
    if len(values)<3 or values[0]<=0 or values[-1]<0 or any(v>0 for v in values[1:-1]) or sum(values[:-1])!=values[-1]:
        raise ValueError('단순 자금 사용표로 대사되지 않습니다. 원문을 확인하고 직접 입력하세요.')
    model.update(origin='case_budget',unit='억원',notes=budget['note'])
    refs=budget.get('refs',[])[:10]
    model['flows']=[dict(id='budget_source',side='source',label=budget['labels'][0]+' · 조달자 미분류',amount=str(values[0]),note='사례 기재 계획 총액. 투자자·계약 확약 확인 전.',refs=refs)]
    for i,v in enumerate(values[1:],1):
        if v:
            model['flows'].append(dict(id='budget_use_'+str(i),side='use',label=budget['labels'][i],amount=str(abs(v)),note=budget['note'],refs=refs))


def sample():
    m=empty();m.update(origin='synthetic',scope='합성 대상회사 (인수 SPC와 별도)',earnings_period='2025 FY',balance_date='2025-12-31',entity='합성 인수 SPC',
        notes='모든 수치는 합성 학습 예시입니다. BS는 인수 SPC의 조달 직후·자금 집행 전, Uses는 집행 계획, FDD 조정은 별도 대상회사 기준입니다. 실제 거래·회계 분류·실사 조정이 아닙니다.',assets='300',balance_complete=True,
        bases=dict(qoe='30',nwc='25',net_debt='50'),ev_mode='multiple',multiple='8',peg='22')
    for i,(side,label,amount) in enumerate([('source','PE 보통주 투자','120'),('source','은행 인수금융','100'),('source','CB 투자','60'),('source','RCPS 투자','20'),('use','매도인 구주대금','220'),('use','기존 차입 상환','50'),('use','거래 비용','10'),('use','운영 현금 유보','20')]):
        m['flows'].append(dict(id='sample_f'+str(i),side=side,label=label,amount=amount,note='합성 거래 예산',refs=[]))
    for i,(label,kind,classification,book,part) in enumerate([('보통주','보통주','equity','120',None),('은행 차입','은행차입','liability','100',None),('CB 복합 분류 예시','CB','split','60','50'),('RCPS 계약 검토 예시','RCPS','liability','20',None)]):
        m['instruments'].append(dict(id='sample_i'+str(i),label=label,kind=kind,classification=classification,book=book,liability_part=part,
            issuer='합성 인수 SPC',proceeds=book,terms='회계 분류를 설명하기 위한 합성 조건',note='합성 발행 직후·자금 집행 전의 장부금액 예시. 실제 발행비용·조건은 별도 검토합니다.',refs=[]))
    for i,(stream,label,category,amount,status,key) in enumerate([
        ('qoe','일회성 소송비용 가산','일회성 비용','4','accepted','litigation'),('qoe','일회성 처분이익 차감','일회성 수익','-2','accepted','asset_gain'),('qoe','Run-rate 인건비','Run-rate','-1','proposed','payroll'),
        ('nwc','장기 미수채권 제외','매출채권','-3','accepted','old_ar'),('nwc','재고 평가 검토','재고','-2','proposed','inventory'),
        ('net_debt','채무 유사 미지급대금','채무 유사항목','5','accepted','debt_like'),('net_debt','현금 유사 항목 검토','현금·현금성','-2','proposed','cash_like')]):
        m['adjustments'].append(dict(id='sample_a'+str(i),stream=stream,label=label,category=category,amount=amount,status=status,economic_key=key,
            question_id=None,note='합성 학습 시나리오 · 검토 반영은 실제 감사/증빙 승인이 아닙니다.',refs=[]))
    return m

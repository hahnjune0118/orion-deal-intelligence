"""Self-contained escaped review report, suitable for browser print-to-PDF."""
from html import escape
from . import engine, deal_visuals


def report(state, version):
    view=engine.view(state)
    def table(headers, rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(c if c is not None else '미계산'))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><title>Orion 검토 보고서</title><style>body{font:15px/1.7 system-ui,sans-serif;max-width:1200px;margin:36px auto;padding:20px;color:#20334e}h1,h2{color:#304c96}table{width:100%;border-collapse:collapse}td,th{border:1px solid #dde4ef;padding:9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#edf2fa}.scroll{overflow:auto}small{color:#536781}@media print{body{margin:0}tr{break-inside:avoid}}</style>']
    parts += ['<h1>Orion · 실사 질문 검토 보고서</h1>', '<p>'+escape(view['company'])+' · '+escape(view['period'])+' · v'+str(version)+'</p>',
        '<p>검색 기반 규칙형 의사결정 지원. 감사의견·투자권고가 아닙니다. 원문 기재·담당자 판단·계산 가정을 구분합니다. 확률·효용은 명시적 시나리오이며 실증 추정값이 아닙니다.</p>']
    parts += ['<h2>자료 범위와 품질</h2>',table(['자료','버전','상태','처리 범위','SHA-256','경고'],[[d['filename'],d['version'],d['status'],f"{d['parsed_units']}/{d['total_units']}",d['sha256'],'; '.join(d['warnings'])] for d in state['documents']])]
    parts += ['<h2>가설과 미확인 사항</h2>',table(['가설','분류','현재 확률','확률 근거','반대 가설'],[[h['title'],h.get('origin_kind','사례 작성'),h['probability'],h['prior_source'],h['counter']] for h in view['hypotheses']])]
    parts += ['<h2>재무 관측치 · 검토 여부</h2>',table(['항목','값','단위','기간','범위','실적/계획','검토','출처'],[[f.get(k,'') for k in ('metric','value','unit','period','scope','basis','reviewed','location')] for f in view['financial_facts']])]
    parts += ['<h2>동일 기준 대사 · 원인 미판정</h2>',table(['항목','기간','범위','구분','원천 1','원천 2','차이','단위','판정'],[[r[k] for k in ('metric','period','scope','basis','left','right','difference','unit','status')] for r in view['reconciliations']])]
    parts += ['<h2>질문과 정보가치</h2>',table(['질문','요청 자료·판정 기준','상태/순위','EIG bits','EVSI','비용 차감 후','단위','근거 ID'],[[q['title'],q['request']+' / '+q['criterion'],q['status']+' / '+str(q.get('rank','대상 외')),q['eig'],q['evsi']['gross'] if q['evsi'] else None,q['evsi']['net'] if q['evsi'] else None,q['evsi']['unit'] if q['evsi'] else '',', '.join(q['refs'])] for q in view['questions']])]
    parts += ['<h2>확률·효용·비용 가정</h2>',table(['질문','우도 가정','효용·비용 가정'],[[q['id'],state['models'].get(q['id'],'미설정'),state['decisions'].get(q['id'],'미설정')] for q in view['questions']])]
    parts += ['<h2>증거와 확률 변화</h2>',table(['질문','판정','이전 확률','이후 확률','우도비','반영 여부'],[[t[k] for k in ('question','outcome','before','after','likelihood_ratio','application')] for t in engine.evidence_trace(state)])]
    parts += ['<h2>원문 근거 명세</h2>',table(['원문 ID','문서','위치','기재 내용'],[[s['id'],d['filename'],s['location'],s['text']] for d in state['documents'] for s in d['spans'] if any(s['id'] in q['refs'] for q in view['questions'])])]
    if state.get('deal_visuals') or state.get('case_study',{}).get('waterfall'):
        workspace=deal_visuals.view(state);model=workspace['model'];accepted=workspace['accepted'];preview=workspace['preview']
        parts += ['<h2>거래 시각화 시나리오</h2>', '<p>'+escape(model['origin']+' · 단위 '+model['unit']+' · '+model['notes'])+'</p>',
            table(['Source/Use','항목','금액','근거'],[[r['side'],r['label'],r['amount'],r['note']] for r in model['flows']]),
            table(['상품','발행 주체','분류','장부금액','부채 부분','계약 조건'],[[r.get(k) for k in ('kind','issuer','classification','book','liability_part','terms')] for r in model['instruments']]),
            table(['FDD 구분','조정 전','검토 반영 후','제안 포함'],[[deal_visuals.STREAMS[k],accepted['bridges'][k].get('start'),accepted['bridges'][k].get('end'),preview['bridges'][k].get('end')] for k in deal_visuals.STREAMS]),
            table(['구분','하위 항목','조정','금액','상태','근거'],[[r[k] for k in ('stream','category','label','amount','status','note')] for r in model['adjustments']]),
            '<p>'+escape('; '.join(accepted['warnings']))+'</p>',
            '<p>조정은 시나리오 입력이며 증거 승인·확정 회계 조정과 별개입니다. 지분가치 = EV − Net Debt + (NWC − Peg). CB·RCPS의 분류는 계약 조건에 따라 검토합니다.</p>',
            table(['지분가치 기준','조정 전','검토 반영 후','제안 포함'],[['계약상 가정',accepted['price'].get('start'),accepted['price'].get('end'),preview['price'].get('end')]])]
    parts += ['<h2>정책·한계</h2><p>추천: 필수 확인 우선, 중요도 35%·증빙 공백 25%·EIG 25%·확보 가능성 15%. EIG 미계산 시 정성 가중치를 재정규화합니다. EVSI와 EIG는 합산하지 않습니다. 검색 근거는 진실성 검증이 아니며, 자료 미검출은 위험이나 부재의 증명이 아닙니다. 과거 가정이 저장되지 않은 구버전은 소급 복구하지 않습니다.</p></html>']
    return ''.join(parts)

"""Specification QA only. No app, persistence, provider calls, or product metrics.
Run from package root: python QA/validate_package.py
Requires jsonschema==4.25.1. Standard-library reference arithmetic is deliberately
small and independent of the future production engine.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import re
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=json.loads((ROOT/'SCHEMAS/models.schema.json').read_text(encoding='utf-8'))
VALIDATOR=Draft202012Validator(SCHEMA,format_checker=FormatChecker())
CHECKS=[]

def record(name, fn):
    try:
        detail=fn()
        CHECKS.append({'check':name,'status':'pass','detail':detail})
    except Exception as exc:
        CHECKS.append({'check':name,'status':'fail','detail':type(exc).__name__+': '+str(exc)})

def require(condition,message):
    if not condition:raise ValueError(message)

def must_reject(fn):
    try:fn()
    except (ValueError,AssertionError):return 'rejected as required'
    raise ValueError('invalid input was accepted')

def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(x):return hashlib.sha256(x.encode('utf-8')).hexdigest()
def norm(s):return unicodedata.normalize('NFC',s).replace('\r\n','\n').replace('\r','\n')
def structural(x):
    errors=sorted(VALIDATOR.iter_errors(x),key=lambda e:str(e.path))
    require(not errors,'; '.join(str(e.message)[:300] for e in errors[:3]))
    return x['kind']

def leaf_structural(name,value):
    validator=Draft202012Validator({'$schema':SCHEMA['$schema'],'$defs':SCHEMA['$defs'],'$ref':'#/$defs/'+name},format_checker=FormatChecker())
    errors=list(validator.iter_errors(value))
    require(not errors,'; '.join(e.message for e in errors[:2]))
    return name+' validated'

def focused_schema_checks():
    s=read('EXAMPLES/initial_state.json')
    bad=copy.deepcopy(s);bad['extra_field']='unexpected'
    record('schema rejects unknown root field',lambda:must_reject(lambda:structural(bad)))
    locator={'kind':'docx_paragraph','part_uri':'word/document.xml','block_index':0,'paragraph_index':0,'heading_path':['Overview'],'page':2}
    record('DOCX fabricated page field rejected',lambda:must_reject(lambda:leaf_structural('Locator',locator)))
    pptx={'kind':'pptx','slide':3,'shape_id':7,'paragraph_index':0,'table_cell':{'row':1,'column':2}}
    record('PPTX slide and table locator schema',lambda:leaf_structural('Locator',pptx))
    ev=copy.deepcopy(s['evidence'][0]);ev['verification_level']='independent_check';ev['independent_check_reference']=None
    record('independent check requires reference',lambda:must_reject(lambda:leaf_structural('Evidence',ev)))
    decision=copy.deepcopy(s['analyst_decisions'][0]);decision['target_type']='snapshot_export'
    record('export approval requires selection digest',lambda:must_reject(lambda:leaf_structural('AnalystDecision',decision)))
    valid=copy.deepcopy(decision);valid['selection_digest']='a'*64
    record('export approval digest accepted',lambda:leaf_structural('AnalystDecision',valid))
    run=copy.deepcopy(s['analysis_runs'][0]);run.update(mode='live',token_input=None,token_output=None)
    record('completed live run cannot omit usage',lambda:must_reject(lambda:leaf_structural('AnalysisRun',run)))
    claim=copy.deepcopy(s['claims'][0]);claim['support_status']='verified'
    record('support and truth enums stay separate',lambda:must_reject(lambda:leaf_structural('Claim',claim)))
    score=copy.deepcopy(s['dd_questions'][0]);score['materiality']['score']='5'
    record('score string rejected without coercion',lambda:must_reject(lambda:leaf_structural('DDQuestion',score)))

def check_refs(s):
    structural(s)
    deal=s['deal']['id'];allids=[deal]
    collections=['documents','source_spans','theses','claims','evidence','evidence_relations','dd_questions','ranking_snapshots','analyst_decisions','audit_events','analysis_runs']
    for group in collections:
        for entity in s[group]:
            allids.append(entity['id']);require(entity['deal_id']==deal,'cross-deal entity')
    require(len(allids)==len(set(allids)),'duplicate entity ID')
    docs={x['id']:x for x in s['documents']};spans={x['id']:x for x in s['source_spans']}
    claims={x['id']:x for x in s['claims']};theses={x['id']:x for x in s['theses']}
    evidence={x['id']:x for x in s['evidence']};questions={x['id']:x for x in s['dd_questions']}
    for span in spans.values():
        require(span['document_id'] in docs,'unknown document');doc=docs[span['document_id']]
        require(span['document_version']==doc['document_version'],'document version mismatch')
        expected={'pdf':['pdf'],'docx':['docx_paragraph','docx_table_cell'],'pptx':['pptx']}[doc['format']]
        require(span['locator']['kind'] in expected,'wrong format locator')
        txt=span['normalized_text'];require(norm(txt)==txt,'text-v1 normalization mismatch')
        require(sha(txt)==span['text_sha256'],'span hash mismatch')
        require(0<=span['start']<span['end']<=len(txt),'invalid offsets')
        require(txt[span['start']:span['end']]==span['quote'],'quote mismatch')
    require(set(s['deal']['thesis_ids'])==set(theses),'deal thesis references')
    for thesis in theses.values():
        for cid in thesis['claim_ids']:
            require(cid in claims and claims[cid]['thesis_id']==thesis['id'],'thesis claim relationship')
    policy={}
    for claim in claims.values():
        require(claim['thesis_id'] in theses and claim['id'] in theses[claim['thesis_id']]['claim_ids'],'claim thesis relationship')
        require(claim['period_start']<=claim['period_end'],'invalid claim period')
        require(set(claim['source_span_ids'])<=set(spans),'claim unknown source')
    for question in questions.values():
        require(question['claim_id'] in claims,'question unknown claim')
        keys=[r['key'] for r in question['requirements']]
        require(len(keys)==len(set(keys)),'duplicate requirement')
        require(set(keys)<=set(claims[question['claim_id']]['required_criterion_keys']),'unknown question criterion')
        for r in question['requirements']:
            key=(question['claim_id'],r['key']);val=(r['min_reliability'],r['require_independent'])
            require(key not in policy or policy[key]==val,'conflicting criterion policies');policy[key]=val
        if question['duplicate_of'] is not None:require(question['duplicate_of'] in questions and question['duplicate_of']!=question['id'],'bad duplicate question')
        require(set(question['materiality']['source_span_ids'])<=set(spans),'materiality unknown source')
        m=question['materiality'];o=question['obtainability']
        if m['basis']=='objective_ratio':
            require(m['exposure_minor'] is not None and m['denominator_minor'] is not None,'missing ratio inputs')
            require(m['score']==materiality(m['exposure_minor'],m['denominator_minor']),'materiality bin mismatch')
        if m['basis']=='unknown':require(m['score'] is None,'unknown materiality must be null')
        if o['basis']=='derived_cost_time':require(o['score']==obtainability(o['days'],o['external_cost_minor']),'obtainability bin mismatch')
        if o['basis']=='unknown':require(o['score'] is None,'unknown obtainability must be null')
    for claim in claims.values():
        require(all((claim['id'],key) in policy for key in claim['required_criterion_keys']),'claim criterion has no question policy')
    for ev in evidence.values():
        require(ev['claim_id'] in claims,'evidence unknown claim')
        require(set(ev['criterion_keys'])<=set(claims[ev['claim_id']]['required_criterion_keys']),'evidence unknown criterion')
        for sid in ev['source_span_ids']:
            require(sid in spans,'evidence unknown span')
            if ev['review_status']=='approved':require(spans[sid]['locator_status']=='validated' and docs[spans[sid]['document_id']]['parse_status']=='parsed','approved unvalidated evidence')
    graph={}
    for rel in s['evidence_relations']:
        a,b=rel['from_evidence_id'],rel['to_evidence_id']
        require(a in evidence and b in evidence and a!=b,'invalid evidence relation')
        require(evidence[a]['claim_id']==evidence[b]['claim_id'],'relation cross-claim')
        require(set(rel['scope_criterion_keys'])<=set(evidence[a]['criterion_keys'])&set(evidence[b]['criterion_keys']),'relation scope mismatch')
        if rel['relation_type']=='duplicates':require(evidence[a]['stance']==evidence[b]['stance'],'opposite stances cannot be duplicates')
        if rel['relation_type']=='supersedes' and rel['review_status']=='approved':graph.setdefault(a,[]).append(b)
    def visit(n,path):
        require(n not in path,'supersession cycle')
        for child in graph.get(n,[]):visit(child,path|{n})
    for node in graph:visit(node,set())
    snapshots={x['id']:x for x in s['ranking_snapshots']}
    require(s['head_snapshot_id'] in snapshots,'head snapshot missing')
    for snap in snapshots.values():
        rows=snap['rows'];ids=[x['question_id'] for x in rows]
        require(len(ids)==len(set(ids)) and set(ids)<=set(questions),'snapshot bad question refs')
        require([x['rank'] for x in rows]==list(range(1,len(rows)+1)),'rank not sequential')
        require(snap['top3']==ids[:3],'top3 differs from rows')
    previous=None
    for i,event in enumerate(s['audit_events'],1):
        require(event['sequence']==i and event['previous_hash']==previous,'audit chain sequence')
        raw={k:v for k,v in event.items() if k!='event_hash'}
        require(sha(canonical(raw))==event['event_hash'],'audit hash mismatch');previous=event['event_hash']
    return f'{len(allids)} unique entity IDs; sources/references/criterion policies/hash chain checked'

def materiality(exposure,denominator):
    require(exposure is not None and denominator is not None and exposure>=0 and denominator>0,'invalid ratio')
    r=Decimal(exposure)/Decimal(denominator)
    return next((i for i,threshold in enumerate(['.01','.03','.05','.10','.20']) if r<Decimal(threshold)),5)

def obtainability(days,cost):
    require(days is not None and cost is not None and days>=0 and cost>=0,'invalid obtainability')
    a=next((5-i for i,t in enumerate([1,3,7,14,30]) if days<=t),0)
    b=next((5-i for i,t in enumerate([0,10000,50000,150000,500000]) if cost<=t),0)
    return min(a,b)

def credits(s,q):
    covered=set();conflict=False
    for e in s['evidence']:
        if e['claim_id']!=q['claim_id'] or e['review_status']!='approved' or e['lifecycle']!='active':continue
        for r in q['requirements']:
            if r['key'] not in e['criterion_keys'] or e['source_reliability'] is None or e['source_reliability']<r['min_reliability']:continue
            if e['stance']=='refutes':conflict=True
            if e['stance']=='supports' and (not r['require_independent'] or e['verification_level']=='independent_check'):covered.add(r['key'])
    return covered,conflict

def rank(s):
    result=[]
    for q in s['dd_questions']:
        if q['review_status']!='approved' or q['workflow_status'] in ['rejected','duplicate','awaiting_review']:continue
        covered,conflict=credits(s,q);n=len(q['requirements'])
        if len(covered)==n and not conflict:continue
        gap=Decimal(5) if conflict else Decimal(5)*(1-Decimal(len(covered))/Decimal(n))
        m=q['materiality']['score'];o=q['obtainability']['score'];provisional=m is None or o is None
        m=3 if m is None else m;o=2 if o is None else o
        raw=9*gap+8*m+3*o
        result.append(((-raw,-m,-gap,-o,q['canonical_key'],q['id']),{'question_id':q['id'],'rank':0,'gap':float(gap),'materiality':m,'obtainability':o,'score':float(raw.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),'provisional':provisional,'reason_codes':['CONFLICT_UNRESOLVED' if conflict else 'EVIDENCE_GAP']+(['INPUT_DEFAULTED'] if provisional else [])}))
    result=[row for _,row in sorted(result,key=lambda x:x[0])]
    for i,row in enumerate(result,1):row['rank']=i
    return result

def input_digest(s):
    keys=['deal','documents','source_spans','theses','claims','evidence','evidence_relations','dd_questions']
    records={k:sorted(s[k],key=lambda x:(x['id'],x['entity_version'])) if isinstance(s[k],list) else s[k] for k in keys}
    return sha(canonical({'scoring_version':'1.0.0','contract_version':'1.0.0','records':records}))

def apply_reference(s,u,decision):
    # Arithmetic reference for these examples, deliberately no persistence engine.
    structural(u);require(decision['actor_role']=='reviewer' and decision['action']=='approve','reviewer approval required')
    require(u['base_revision']==s['state_revision']==decision['base_revision'],'stale revision')
    require(u['deal_id']==s['deal']['id']==decision['deal_id'],'update deal mismatch')
    require(u['validation_status']=='validated' and decision['target_id']==u['id'],'unvalidated/wrong approval target')
    after=copy.deepcopy(s)
    for k in ['documents','source_spans','evidence','evidence_relations']:
        records=copy.deepcopy(u[k])
        for record in records:
            if 'review_status' in record:record['review_status']='approved'
        after[k].extend(records)
    check_refs(after)
    for question in after['dd_questions']:
        if question['workflow_status'] in ['rejected','duplicate','awaiting_review']:continue
        covered,conflict=credits(after,question)
        question['workflow_status']='resolved' if len(covered)==len(question['requirements']) and not conflict else 'open'
    for claim in after['claims']:
        relevant=[q for q in after['dd_questions'] if q['claim_id']==claim['id']]
        keys=set();conflict=False
        for q in relevant:
            c,f=credits(after,q);keys|=c;conflict|=f
        count=len(keys&set(claim['required_criterion_keys']))
        claim['support_status']='contradicted' if conflict else 'supported' if count==len(claim['required_criterion_keys']) else 'partial' if count else 'missing'
        claim['truth_status']='disputed' if conflict else 'document_only'
    after['state_revision']+=1
    return after

def transition_check(s,u,e):
    before=rank(s);afterstate=apply_reference(s,u,e['approval']);after=rank(afterstate)
    require([x['question_id'] for x in before[:3]]==e['before_top3'],'before Top-3 mismatch')
    require([x['question_id'] for x in after[:3]]==e['after_top3'],'after Top-3 mismatch')
    bm={x['question_id']:x for x in before};am={x['question_id']:x for x in after}
    qs={q['id']:q for q in s['dd_questions']};qa={q['id']:q for q in afterstate['dd_questions']}
    for c in e['question_changes']:
        b=bm.get(c['question_id'],{});a=am.get(c['question_id'],{})
        for field in ['rank','score']:
            require(c['before_'+field]==b.get(field),'before value mismatch');require(c['after_'+field]==a.get(field),'after value mismatch')
        require(c['before_status']==qs[c['question_id']]['workflow_status'],'before status mismatch')
        require(c['after_status']==qa[c['question_id']]['workflow_status'],'after status mismatch')
    for expected in e['claim_after']:
        claim=next(c for c in afterstate['claims'] if c['id']==expected['claim_id'])
        require(claim['support_status']==expected['support_status'] and claim['truth_status']==expected['truth_status'],'claim status mismatch')
    require(afterstate['state_revision']==e['after_revision'],'after revision mismatch')
    return {'before':[(r['question_id'],r['score']) for r in before[:3]],'after':[(r['question_id'],r['score']) for r in after[:3]]}

def negatives(s,u,e,case):
    a=apply_reference(s,u,e['approval'])
    duplicate=copy.deepcopy(a);item=copy.deepcopy(duplicate['evidence'][-1]);item['id']+='_copy';duplicate['evidence'].append(item)
    record(case+' duplicate credit stability',lambda:require(rank(duplicate)==rank(a),'duplicate changed ranking'))
    unrelated=copy.deepcopy(s);item=copy.deepcopy(s['evidence'][0]);item.update(id=item['id']+'_unrelated',stance='context',criterion_keys=[]);unrelated['evidence'].append(item)
    record(case+' unrelated evidence stability',lambda:require(rank(unrelated)==rank(s),'unrelated changed ranking'))
    staged=copy.deepcopy(s)
    for k in ['documents','source_spans','evidence','evidence_relations']:staged[k]+=copy.deepcopy(u[k])
    record(case+' unapproved update stability',lambda:require(rank(staged)==rank(s),'draft changed ranking'))
    invalid=copy.deepcopy(u);invalid['source_spans'][0]['quote']+=' fabricated'
    record(case+' invalid quote rejected',lambda:must_reject(lambda:apply_reference(s,invalid,e['approval'])))
    record(case+' stale update rejected',lambda:must_reject(lambda:apply_reference(a,u,e['approval'])))
    baddecision=copy.deepcopy(e['approval']);baddecision['actor_role']='analyst'
    record(case+' analyst approval rejected',lambda:must_reject(lambda:apply_reference(s,u,baddecision)))
    invalid=copy.deepcopy(s);invalid['source_spans'][0]['document_id']='doc_missing'
    record(case+' orphan source rejected',lambda:must_reject(lambda:check_refs(invalid)))
    cross=copy.deepcopy(s);cross['evidence'][0]['deal_id']='deal_other'
    record(case+' cross deal rejected',lambda:must_reject(lambda:check_refs(cross)))
    reordered=copy.deepcopy(s)
    for k in ['documents','source_spans','theses','claims','evidence','evidence_relations','dd_questions']:reordered[k].reverse()
    record(case+' collection-order invariance',lambda:require(rank(s)==rank(reordered) and input_digest(s)==input_digest(reordered),'order instability'))

def score_boundaries():
    require([materiality(x,10000) for x in [0,99,100,299,300,499,500,999,1000,1999,2000]]==[0,0,1,1,2,2,3,3,4,4,5],'ratio boundaries')
    require(obtainability(2,60000)==2,'time-cost double count/bin')
    require([obtainability(d,0) for d in [0,1,3,7,14,30,31]]==[5,5,4,3,2,1,0],'days boundary')
    return '11 materiality boundaries, 7 day boundaries and combined cost/time checked'

def null_and_tie(s):
    a=copy.deepcopy(s);q=a['dd_questions'][0];q['materiality'].update(score=None,basis='unknown');q['obtainability'].update(score=None,basis='unknown')
    row=next(x for x in rank(a) if x['question_id']==q['id']);require(row['score']==75 and row['provisional'],'null defaults')
    q['materiality'].update(score=0,basis='analyst_rubric');q['obtainability'].update(score=0,basis='analyst_estimate')
    row=next(x for x in rank(a) if x['question_id']==q['id']);require(row['score']==45 and not row['provisional'],'zero incorrectly defaulted')
    b=copy.deepcopy(s)
    for question in b['dd_questions']:question['materiality']['score']=3;question['obtainability']['score']=3
    require([r['question_id'] for r in rank(b)]==[q['id'] for q in sorted(b['dd_questions'],key=lambda q:(q['canonical_key'],q['id']))],'canonical tie-break')
    return 'null=>75 provisional; zero=>45 nonprovisional; exact tie uses canonical key'

def financials():
    cases=read('DATASET_SPECS/financial_truth.json')['cases']
    for case in cases:
        require(case['revenue']-case['cogs']-case['opex_excluding_da']==case['ebitda'],'EBITDA mismatch')
        require(sum(case['customer_revenue'])==case['revenue'],'customer sum mismatch')
        require(case['ar']+case['inventory']-case['ap']==case['nwc_operating'],'NWC mismatch')
        if 'subscription' in case:require(case['subscription']+case['services']==case['revenue'],'revenue split')
        if 'hours_delivered' in case:require(case['hours_delivered']*case['hourly_price_minor']==case['revenue'],'hour revenue')
    return '3 cases: EBITDA/customer totals/NWC; NS revenue split; Lumen hours'

def bayes():
    def h(p):return 0 if p in [0,1] else -p*math.log2(p)-(1-p)*math.log2(1-p)
    p,a,b=.3,.8,.2;pe=p*a+(1-p)*b;pp=p*a/pe;pn=p*(1-a)/(1-pe);eig=h(p)-pe*h(pp)-(1-pe)*h(pn)
    require(abs(pp-12/19)<1e-12 and abs(pn-3/31)<1e-12,'Bayes posterior')
    require(abs(eig-.2361139273389372)<1e-10,'EIG expected value')
    return {'hypothetical_prior':p,'P_positive':pe,'posterior_positive':pp,'posterior_negative':pn,'EIG_bits':eig,'not_empirical':True}

def links():
    missing=[];count=0
    for file in ROOT.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
            if target.startswith(('http:','https:','mailto:','#')):continue
            target=target.split('#')[0]
            if not target:continue
            count+=1
            if not (file.parent/target).exists():missing.append(str(file.relative_to(ROOT))+': '+target)
    require(not missing,'missing links: '+str(missing));return {'local_links_checked':count}

def required_files():
    required=['00_READ_FIRST.md','01_MASTER_SPECIFICATION.md','02_PRD_AND_ACCEPTANCE_TESTS.md','03_SYSTEM_ARCHITECTURE.md','04_DATA_CONTRACTS.md','05_SCORING_AND_ADAPTIVE_ENGINE.md','06_DASH_UI_UX_DESIGN_SYSTEM.md','07_SYNTHETIC_DEAL_DATASET_SPEC.md','08_EVALUATION_PROTOCOL.md','09_SECURITY_COST_DEPLOYMENT.md','10_IMPLEMENTATION_PLAN.md','11_DECISION_LOG_AND_SOURCES.md','PROMPTS/00_ORCHESTRATOR.md','PROMPTS/01_FOUNDATION.md','PROMPTS/02_CORE_ENGINE.md','PROMPTS/03_SYNTHETIC_DATA_EVAL.md','PROMPTS/04_DASH_UI.md','PROMPTS/05_INTEGRATION_RELEASE.md','SCHEMAS/models.schema.json','EXAMPLES/initial_state.json','EXAMPLES/staged_evidence_update.json','EXAMPLES/expected_top3_transition.json','DELIVERY_MANIFEST.md']
    for path in required:require((ROOT/path).is_file() and (ROOT/path).stat().st_size>100,path+' missing or empty')
    return {'required_files_present':len(required)}

def main():
    record('JSON Schema meta-validation',lambda:Draft202012Validator.check_schema(SCHEMA))
    focused_schema_checks()
    for case,folder in [('ns','EXAMPLES'),('cd','DATASET_SPECS/cd'),('lm','DATASET_SPECS/lm')]:
        s,u,e=[read(folder+'/'+name+'.json') for name in ['initial_state','staged_evidence_update','expected_top3_transition']]
        for label,value in [('state',s),('update',u),('transition',e)]:record(case+' schema '+label,lambda value=value:structural(value))
        record(case+' reference and source integrity',lambda s=s:check_refs(s))
        record(case+' stored initial ranking',lambda s=s:require(rank(s)==s['ranking_snapshots'][0]['rows'],'stored rows mismatch'))
        record(case+' input digest',lambda s=s:require(input_digest(s)==s['ranking_snapshots'][0]['input_digest'],'input hash mismatch'))
        record(case+' worked transition',lambda s=s,u=u,e=e:transition_check(s,u,e))
        negatives(s,u,e,case)
    record('rubric numerical boundaries',score_boundaries)
    record('null zero and tie rules',lambda:null_and_tie(read('EXAMPLES/initial_state.json')))
    record('synthetic finance consistency',financials)
    record('hypothetical Bayes and EIG',bayes)
    record('required deliverables',required_files)
    record('internal Markdown links',links)
    record('publisher dependency metadata',lambda:require(all(p['verified'] for p in read('QA/dependency_metadata.json')['packages']),'unverified dependency'))
    # All these tests concern specification artifacts. They do not prove app behavior.
    failures=[r for r in CHECKS if r['status']=='fail']
    report={'executed_at_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version.split()[0],'scope':'Specification QA only; no application/product evaluation','passed':len(CHECKS)-len(failures),'failed':len(failures),'checks':CHECKS,'not_executed':['Windows dependency installation and security audit','Native PDF/DOCX/PPTX parser tests','Pydantic implementation parity','Production transactions, authorization and export tests','Dash browser accessibility and session isolation','Hosting deployment and restart','Live API budget enforcement and real model evaluation','Independent gold annotation and empirical citation/Top-3 metrics']}
    (ROOT/'QA/validation_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Specification validation report','',f"Executed UTC: {report['executed_at_utc']} · Python {report['python']}",'',f"**{report['passed']} passed / {report['failed']} failed.** Contract arithmetic and file checks only. 제품 구현·성능 평가가 아니다.",'','| Check | Result | Detail |','|---|---|---|']
    for r in CHECKS:lines.append('| '+r['check']+' | '+r['status']+' | '+json.dumps(r['detail'],ensure_ascii=False).replace('|','\\|')+' |')
    lines+=['','## Not executed','']+['- '+x for x in report['not_executed']]+['','95% citation accuracy, zero fabricated product citations and 80% Top-3 coverage remain unmeasured targets. Authored fixture correctness is not LLM accuracy.','']
    (ROOT/'QA/VALIDATION_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'failures':failures},ensure_ascii=False,indent=2))
    return 1 if failures else 0

if __name__=='__main__':sys.exit(main())

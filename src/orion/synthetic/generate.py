"""Deterministic original source generation, contract assembly and frozen gold.

Gold expectations are authored in cases.py, never copied from replay outputs.
The 1.0.0 domain and scoring contracts remain unchanged.
"""
from __future__ import annotations
import io
import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from docx import Document as WordDocument
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from orion.adapters.parsers.native import NativeSourceIndex
from orion.domain.models import DealState, StagedEvidenceUpdate, RankingSnapshot
from orion.domain.scoring import build_snapshot
from orion.domain.transitions import derive_statuses
from .cases import northstar
from .models import DatasetDocument, Hypothesis, EvidenceLabel, QuestionLabel

from .constants import VERSION, STAMP, CASE_FOLDERS


def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def _canonical_docx(word):
    raw=io.BytesIO();word.save(raw);result=io.BytesIO()
    with ZipFile(raw) as source, ZipFile(result,'w',compression=ZIP_DEFLATED,compresslevel=9) as target:
        for name in sorted(source.namelist()):
            info=ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=0o600<<16
            target.writestr(info,source.read(name))
    return result.getvalue()


def render_source(source, case, folder):
    """Write readable original DOCX + machine JSON + Markdown; parse real bytes."""
    word=WordDocument();sec=word.sections[0]
    sec.top_margin=sec.bottom_margin=Inches(.65);sec.left_margin=sec.right_margin=Inches(.7)
    for sty in ('Normal','Title'):
        word.styles[sty].font.name='Calibri';word.styles[sty].font.color.rgb=RGBColor(0,0,0)
    word.styles['Normal'].font.size=Pt(11)
    word.styles['Normal'].paragraph_format.space_after=Pt(6)
    word.styles['Title'].font.size=Pt(19)
    for style in word.styles:
        if style.element.pPr is not None:
            for border in list(style.element.pPr.findall(qn('w:pBdr'))):style.element.pPr.remove(border)
    word.core_properties.title=source['title'];word.core_properties.author='Orion synthetic dataset authors'
    word.core_properties.created=word.core_properties.modified=datetime(2026,11,3)
    word.core_properties.last_modified_by='Orion deterministic generator'
    word.add_paragraph(source['title'],style='Title')
    document_id=f"{case}_doc_{source['key']}"
    word.add_paragraph(f"SYNTHETIC | {document_id} | {source['date']} | Version {source['version']}")
    word.add_paragraph(f"Reporting period: {source['period']}")
    if case=='nb':word.add_paragraph('Independent expanded research scenario NB version 3.0.0. This is not a continuation of legacy Northstar NS; contract, cash and customer assumptions differ.')
    for p in source['paragraphs']:
        word.add_paragraph(p['text'])
    for item in source['tables']:
        if case=='mf' and source['key']=='financial' and item['key']=='balance':word.add_page_break()
        t=word.add_table(rows=1,cols=len(item['columns']));t.style='Table Grid'
        t.autofit=False
        for cell,text in zip(t.rows[0].cells,item['columns']):
            cell.text=str(text)
            for run in cell.paragraphs[0].runs:run.bold=True
        header=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(header)
        for row in item['rows']:
            for cell,value in zip(t.add_row().cells,row):cell.text=str(value)
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(3)
                    for run in p.runs:run.font.size=Pt(10)
    content=_canonical_docx(word)
    filename=f"{document_id}.docx";folder.mkdir(parents=True,exist_ok=True)
    (folder/filename).write_bytes(content)
    metadata=dict(id=document_id,entity_version=1,deal_id=f'deal_{case}',filename=filename,format='docx',document_version=source['version'],asset_status='fixture_text_only',file_sha256=None,parse_status='pending',parser_version='pending',source_origin=source['origin'],origin_key=document_id,created_at=source['date']+'T00:00:00Z')
    index=NativeSourceIndex();parsed=index.add(content,metadata)
    if parsed.document.parse_status!='parsed':raise ValueError(f"Native parser rejected {document_id}: {parsed.warnings}")
    keys={}
    for p in source['paragraphs']:
        matches=[s for s in parsed.source_spans if s.normalized_text==p['text']]
        if len(matches)!=1:raise ValueError(f"Expected unique paragraph {document_id}:{p['key']}")
        keys[p['key']]=matches[0].id
    wrapped=DatasetDocument(record=parsed.document,title=source['title'],date=source['date'],reporting_period=source['period'],document_type=source['key'],available_stage=source['stage'],elements=list(parsed.source_spans))
    machine=wrapped.model_dump(mode='json');machine['source_element_keys']=keys
    dump(folder/f'{document_id}.json',machine)
    md=f"# {source['title']}\n\nSYNTHETIC DATA — {document_id} — {source['date']} — version {source['version']}\n\nReporting period: {source['period']}\n\n"
    md+='\n\n'.join(p['text'] for p in source['paragraphs'])+'\n'
    for t in source['tables']:
        md+='\n| '+' | '.join(map(str,t['columns']))+' |\n| '+' | '.join('---' for _ in t['columns'])+' |\n'
        md+=''.join('| '+' | '.join(map(str,row))+' |\n' for row in t['rows'])
    (folder/f'{document_id}.md').write_text(md,encoding='utf-8')
    return parsed,index,keys


def _question_record(case, q):
    key,hyp,issue,criteria,materiality,obtainability,artifact,criterion=q
    periods_nb={'contract_a':'2026-11-01 through 2027-11-30','contract_b':'2026-11-01 through 2027-11-30','execution_a':'2026-11-01 through 2027-10-31','execution_b':'2026-11-01 through 2027-10-31','margin_a':'Aster contract year 2026-12-01 through 2027-11-30','margin_b':'Birch first contract year beginning 2026-11-22','independence':'2026-11-01 through 2027-10-31','count':'customer classification as of 2026-11-03','arr':'signed recurring obligations as of 2026-11-03','capacity':'calendar FY2027','revenue':'calendar FY2025','costs':'first contract years beginning in November or December 2026','balance':'INV-01 dated 2026-11-12 and subsequent receipts through 2027-10-31'}
    periods_mf={'inventory_count':'inventory at 2025-12-31','inventory_valuation':'inventory at 2025-12-31 and subsequent sales through 2026-11-05','ebitda':'calendar FY2025','working_capital':'FY2025 actual and FY2027 forecast','maintenance_capex':'calendar FY2025 and sustainable annual maintenance thereafter','cash_conversion':'calendar FY2025','concentration':'FY2025 actual and FY2027 contractual demand','capacity':'calendar FY2027','sales_mix':'calendar FY2025'}
    period=(periods_nb if case=='nb' else periods_mf)[key]
    return dict(id=f'{case}_q_{key}',entity_version=1,deal_id=f'deal_{case}',claim_id=f'{case}_claim_{hyp}',canonical_key=f'{case}.{key}',issue=issue,
        request_text=f"For {period}, provide {artifact}. {criterion}",
        financial_driver=('unit_economics' if hyp=='h2' and case=='nb' else 'revenue_quality') if case=='nb' else {'inventory_count':'nwc','inventory_valuation':'nwc','ebitda':'ebitda','concentration':'customer_concentration','maintenance_capex':'capex','working_capital':'nwc','cash_conversion':'nwc','capacity':'capex','sales':'revenue_quality'}.get(key,'revenue_quality'),
        requirements=[dict(key=k,label=k.replace('_',' '),min_reliability=3,require_independent=False) for k in criteria],
        materiality=dict(score=materiality,basis='analyst_rubric',exposure_minor=None,denominator_minor=None,rationale='Explicit synthetic analyst materiality on 0-5 scale; no monetary valuation or calibrated utility.',source_span_ids=[]),
        obtainability=dict(score=obtainability,basis='analyst_estimate',days=None,external_cost_minor=None,rationale='Synthetic analyst estimate on 0-5 scale; time and cost not empirically measured.'),
        review_status='approved',workflow_status='open',duplicate_of=None,owner_label='Simulated analyst')


def assemble_case(case_data, root):
    case=case_data['case'];folder=root/'data'/CASE_FOLDERS[case];docfolder=folder/'documents'
    index=NativeSourceIndex();parsed_by_key={};keys_by_doc={};docs=[];spans=[]
    for source in case_data['documents']:
        parsed,_,keys=render_source(source,case,docfolder)
        # Populate a single resolver from immutable files, not authored text.
        parsed=index.add((docfolder/parsed.document.filename).read_bytes(),parsed.document.model_dump(mode='json'))
        parsed_by_key[source['key']]=(source,parsed);keys_by_doc[source['key']]=keys
        docs.append(parsed.document);spans.extend(parsed.source_spans)
    criteria={h:[] for h in case_data['hypotheses']}
    questions=[_question_record(case,q) for q in case_data['questions']]
    for q in questions:
        hyp=q['claim_id'].removeprefix(f'{case}_claim_')
        for r in q['requirements']:
            if r['key'] not in criteria[hyp]:criteria[hyp].append(r['key'])
    claims=[]
    initial_spans=[s.id for source,parsed in parsed_by_key.values() if source['stage']==0 for s in parsed.source_spans]
    for h,(statement,threshold,driver) in case_data['hypotheses'].items():
        claims.append(dict(id=f'{case}_claim_{h}',entity_version=1,deal_id=f'deal_{case}',thesis_id=f'{case}_thesis',statement=statement,subject_key=f'{case}_{h}',period_start='2026-11-01' if case=='nb' and h in {'h1','h2'} else '2025-01-01',period_end=('2027-10-31' if h=='h1' else '2027-11-30' if h=='h2' else '2027-12-31') if case=='nb' else '2027-12-31',claim_kind='binary_hypothesis',source_span_ids=[],required_criterion_keys=criteria[h],support_status='missing',truth_status='document_only',review_status='approved'))
    evidences=[];labels=[]
    span_map={s.id:s for s in spans}
    for key,doc_key,pkey,hyp,stance,scope,reliability,group,provenance,contradiction in case_data['evidence']:
        source,parsed=parsed_by_key[doc_key];span=span_map[keys_by_doc[doc_key][pkey]]
        ev=dict(id=f'{case}_ev_{key}',entity_version=1,deal_id=f'deal_{case}',claim_id=f'{case}_claim_{hyp}',source_span_ids=[span.id],stance=stance,criterion_keys=scope,provenance=provenance,source_reliability=reliability,reliability_rationale='Scenario author assessed documentary specificity; simulated counterparties are not actual independent authentication.',verification_level='document_only',independent_check_reference=None,origin_key=f'{case}_{group}',review_status='approved' if source['stage']==0 else 'draft',lifecycle='active',created_at=source['date']+'T00:00:00Z')
        evidences.append((source['stage'],ev))
        labels.append(EvidenceLabel(record=ev,evidence_type=source['key'],evidence_group_id=f'{case}_{group}',contradiction_group=contradiction,exact_source_excerpt=span.quote,available_stage=source['stage'],world_truth_status='synthetic observation only; future outcome unobserved',document_visible_status='document_only',rationale='The exact source supports what this fictional document reports; neither source presence nor analyst approval asserts real-world verification.').model_dump(mode='json'))
    placeholder=RankingSnapshot(id=f'{case}_snapshot_t0',entity_version=1,deal_id=f'deal_{case}',state_revision=1,scoring_version='1.0.0',input_digest='0'*64,created_at=STAMP,trigger_event_id=None,rows=[],top3=[])
    state=DealState.model_validate(dict(kind='deal_state',contract_version='1.0.0',state_revision=1,mode='demo',deal=dict(id=f'deal_{case}',entity_version=1,name=case_data['name'],business_model=case_data['business'],currency='USD',synthetic=True,as_of='2026-11-03',thesis_ids=[f'{case}_thesis']),documents=[p.document.model_dump(mode='json') for src,p in parsed_by_key.values() if src['stage']==0],source_spans=[s.model_dump(mode='json') for src,p in parsed_by_key.values() if src['stage']==0 for s in p.source_spans],theses=[dict(id=f'{case}_thesis',entity_version=1,deal_id=f'deal_{case}',title='Evidence-grounded preliminary screening',counter_thesis='Commercial or financial performance may not support management assumptions.',claim_ids=[c['id'] for c in claims],review_status='approved')],claims=claims,evidence=[e for stage,e in evidences if stage==0],evidence_relations=[],dd_questions=questions,ranking_snapshots=[placeholder.model_dump(mode='json')],analyst_decisions=[],audit_events=[],analysis_runs=[],head_snapshot_id=placeholder.id))
    state=derive_statuses(state)
    state.ranking_snapshots=[build_snapshot(state,placeholder.id,STAMP,source_resolver=index)]
    dump(folder/'structured'/'initial_state.json',state.model_dump(mode='json'))
    stages=sorted(set(src['stage'] for src in case_data['documents'])-{0})
    events=[]
    for stage in stages:
        rel=[]
        if case=='nb' and stage==4:
            rel=[dict(id='nb_rel_taxonomy_correction',entity_version=1,deal_id='deal_nb',from_evidence_id='nb_ev_count_corrected',to_evidence_id='nb_ev_taxonomy',relation_type='supersedes',scope_criterion_keys=['count'],review_status='draft',rationale='Dated correction explicitly replaces the initial taxonomy dispute, while ARR and ownership remain unresolved.')]
        event=StagedEvidenceUpdate.model_validate(dict(kind='staged_evidence_update',contract_version='1.0.0',id=f'{case}_update_t{stage}',deal_id=f'deal_{case}',base_revision=stage,idempotency_key=f'{case}:t{stage}',validation_status='validated',created_at=next(src['date'] for src in case_data['documents'] if src['stage']==stage)+'T00:00:00Z',documents=[p.document.model_dump(mode='json') for src,p in parsed_by_key.values() if src['stage']==stage],source_spans=[s.model_dump(mode='json') for src,p in parsed_by_key.values() if src['stage']==stage for s in p.source_spans],evidence=[e for available,e in evidences if available==stage],evidence_relations=rel,analyst_note=case_data['event_reasons'][stage]))
        dump(folder/'updates'/f't{stage}.json',event.model_dump(mode='json'));events.append(event)
    # These rankings/labels are scenario-author judgments written before running the engine.
    gold_questions=[]
    expected0=case_data['expected_top3'][0]
    # Independent rubric arithmetic for initial labels, without rank_state/evaluate_requirements.
    initial_labels=sorted(case_data['questions'],key=lambda q:(-(45+8*q[4]+3*q[5]),-q[4],-q[5],f'{case}.{q[0]}'))
    initial_priority={q[0]:i for i,q in enumerate(initial_labels,1)}
    for q,record in zip(case_data['questions'],questions):
        key,hyp,issue,scope,materiality,obtainability,artifact,criterion=q
        gold_questions.append(QuestionLabel(record=record,hypothesis_id=f'{case}_hyp_{hyp}',question_text=record['request_text'],unresolved_assumption=issue,requested_artifact=artifact,verification_criterion=criterion,business_impact=f"Impacts {record['financial_driver']} under the stated synthetic case assumptions.",linked_evidence_ids=[e['id'] for _,e in evidences if e['claim_id']==record['claim_id'] and (set(e['criterion_keys'])&set(scope) or not e['criterion_keys'])],expected_priority=initial_priority[key],information_gain=(0.2361139273389372 if case=='nb' and key=='contract_a' else None),expected_update_behavior='Remove only after all request criteria have approved support; reopen or retain if qualified refutation exists.',acceptable_question_family=f'{case}.{key}',acceptable_alternatives=[artifact,issue]).model_dump(mode='json'))
    hypotheses=[Hypothesis(hypothesis_id=f'{case}_hyp_{h}',claim=next(c for c in state.claims if c.id==f'{case}_claim_{h}'),threshold=v[1],financial_driver=v[2]).model_dump(mode='json') for h,v in case_data['hypotheses'].items()]
    golden_claims=[]
    for c in state.claims:
        golden_claims.append(dict(record=c.model_dump(mode='json'),hypothesis_id=f'{case}_hyp_'+c.id.rsplit('_',1)[-1],claim_type=c.claim_kind,source_locators=[s.model_dump(mode='json') for s in state.source_spans if s.id in c.source_span_ids],evidence_relationships=[dict(evidence_id=e['id'],relation=e['stance']) for _,e in evidences if e['claim_id']==c.id],ground_truth_status='future_outcome_unobserved' if c.id.endswith('h1') else 'scenario_provisional',financial_driver=case_data['hypotheses'][c.id.rsplit('_',1)[-1]][2],materiality='analyst_defined_per_question',rationale='Scenario-designed hypothesis; document-visible support status is separate from terminal world truth.'))
    stages_gold={str(stage):dict(expected_top3=[f'{case}_q_{key}' for key in keys],critical_families=[f'{case}.{key}' for key in keys],expected_scores={f'{case}_q_{key}':45+8*next(q[4] for q in case_data['questions'] if q[0]==key)+3*next(q[5] for q in case_data['questions'] if q[0]==key) for key in keys},label_basis='self-authored scenario policy; not universally optimal investment priorities') for stage,keys in case_data['expected_top3'].items()}
    # Hand-authored evidence-visible expectations; do not copy replay states into gold.
    status_plan=({'0':['missing','missing','contradicted'],'1':['partial','missing','contradicted'],'2':['partial','missing','contradicted'],'3':['partial','contradicted','contradicted'],'4':['contradicted','contradicted','contradicted']} if case=='nb' else {'0':['contradicted']*3,'1':['contradicted']*3})
    resolved_plan=({'0':[],'1':['contract_a'],'2':['contract_a','execution_a'],'3':['contract_a','execution_a','costs'],'4':['contract_a','execution_a','costs','contract_b','execution_b','count']} if case=='nb' else {'0':[],'1':['inventory_count']})
    for stage,labels_status in status_plan.items():
        stages_gold[stage]['expected_hypothesis_statuses']={f'{case}_claim_h{i}':status for i,status in enumerate(labels_status,1)}
        stages_gold[stage]['expected_truth_statuses']={f'{case}_claim_h{i}':('disputed' if status=='contradicted' else 'document_only') for i,status in enumerate(labels_status,1)}
        stages_gold[stage]['supporting_evidence_ids']=[ev['id'] for available,ev in evidences if available<=int(stage)]
        stages_gold[stage]['expected_resolved_questions']=[f'{case}_q_{q}' for q in resolved_plan[stage]]
        stages_gold[stage]['rationale']=case_data['event_reasons'].get(int(stage),'Initial documentary gaps and contradictions are deliberately specified before replay.')
    # Company-reported extraction gold uses exact originating paragraphs and is
    # separate from the analyst-defined binary hypotheses used for ranking.
    documentary_claims=[]
    for key,doc_key,pkey,ctype,statement,hyp,status in case_data.get('source_claims',[]):
        src,parsed=parsed_by_key[doc_key];span=span_map[keys_by_doc[doc_key][pkey]]
        record=dict(id=f'{case}_assertion_{key}',entity_version=1,deal_id=f'deal_{case}',thesis_id=f'{case}_thesis',statement=statement,subject_key=f'{case}_{key}',period_start='2025-01-01',period_end='2027-12-31',claim_kind=ctype,source_span_ids=[span.id],required_criterion_keys=criteria[hyp],support_status=status if status in {'missing','partial','supported','contradicted'} else 'partial',truth_status='disputed' if status=='contradicted' else 'document_only',review_status='draft')
        claim_scopes=({'traction':{'count','arr'},'margin':{'margin_a'},'capacity':{'capacity'}} if case=='nb' else {'inventory':{'inventory_valuation'},'cash':{'cash_conversion'},'capex':{'maintenance_capex'},'growth':{'capacity'}})
        record['required_criterion_keys']=sorted(claim_scopes[key])
        lifecycle_links=[dict(evidence_id=e['id'],relation=e['stance'],available_stage=available) for available,e in evidences if span.id in e['source_span_ids'] or (e['claim_id']==f'{case}_claim_{hyp}' and set(e['criterion_keys']) & claim_scopes[key])]
        label_links=[edge for edge in lifecycle_links if edge['available_stage']<=src['stage']]
        documentary_claims.append(dict(record=record,hypothesis_id=f'{case}_hyp_{hyp}',claim_type=ctype,source_locators=[span.model_dump(mode='json')],exact_source_excerpt=span.quote,available_stage=src['stage'],evidence_relationships=label_links,lifecycle_evidence_relationships=lifecycle_links,label_stage=src['stage'],ground_truth_status=status,financial_driver=case_data['hypotheses'][hyp][2],materiality='analyst_defined_per_question',rationale='Actual company assertion extraction label; original source establishes reported wording, while conflicting documents determine support. Analyst-defined hypotheses are a separate annotation class.'))
    gold=dict(dataset_version=VERSION,case=case,review_status='self-authored provisional; no external analyst review',hypotheses=hypotheses,claims=golden_claims+documentary_claims,documentary_claims=documentary_claims,evidence=labels,questions=gold_questions,stages=stages_gold,documentary_assertions=case_data.get('source_claims',[]),answer_key_rules={'world_truth_is_not_agent_visible':True,'future_evidence_must_not_support_earlier_stage_labels':True,'source_quote_does_not_imply_independent_truth':True})
    dump(root/'gold'/f'{case}_gold.json',gold);dump(root/'gold'/f'{case}_world_model.json',case_data['world'])
    dump(folder/'structured'/'source_inventory.json',[dict(document_id=p.document.id,filename=p.document.filename,sha256=p.document.file_sha256,machine_sha256=sha256((docfolder/f"{p.document.id}.json").read_bytes()).hexdigest(),date=src['date'],reporting_period=src['period'],version=src['version'],available_stage=src['stage'],synthetic=True) for src,p in parsed_by_key.values()])
    return dict(case=case,documents=len(docs),evidence=len(evidences),questions=len(questions),hypotheses=len(hypotheses),events=len(events))


def generate_dataset(output):
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    from .manufacturing import manufacturing
    cases=[assemble_case(c,root) for c in (northstar(),manufacturing())]
    dump(root/'data'/'public_orion'/'source_manifest.json',dict(case='public_orion',status='pending_verified_sources',synthetic=False,public_facts=[],documents=[],requirements=['Actual issuer identity and reporting period must be confirmed before ingestion.','Only verifiable primary disclosures and issuer IR documents; retain URL, access date, checksum, locator and license/public-use basis.','No actual Orion fact or synthetic replacement is populated.','Keep any future synthetic supplemental scenario separately labelled and outside public-source facts.'],evaluation_specification={'status':'not_run','requires':['verified source inventory','period-specific claim and citation gold','independent review'],'metrics':['claim_recall','locator_accuracy','unsupported_claim_rate']}))
    dump(root/'config'/'dataset_config.json',dict(dataset_version=VERSION,seed=20261103,generation='deterministic original authored worlds; no stochastic calls',development=['nb'],frozen_rule_regression=['mf'],statistical_holdout=False,legacy_cases=['ns','cd','lm'],case_summaries=cases))
    (root/'config'/'dataset_config.yaml').write_text('dataset_version: "3.0.0"\nseed: 20261103\ndevelopment: [nb]\nfrozen_rule_regression: [mf]\nstatistical_holdout: false\npublic_orion_status: pending_verified_sources\n',encoding='utf-8')
    dump(root/'config'/'evaluation_config.json',dict(mode='authored_fixture',actual_llm_benchmark=False,arms=['B0','B1','B2','B3','B1-R'],bayesian_ablation='panel off; core ranking unchanged',acceptance_targets={'locator_precision':.95,'top3_critical_coverage':.80,'hallucinated_citations':0,'final_without_hitl':0}))
    (root/'config'/'evaluation_config.yaml').write_text('mode: authored_fixture\nactual_llm_benchmark: false\narms: [B0, B1, B2, B3, B1-R]\nlocator_precision_target: 0.95\ntop3_critical_coverage_target: 0.80\nhallucinated_citations_target: 0\n',encoding='utf-8')
    summary=dict(dataset_version=VERSION,cases=cases,public_orion='pending_verified_sources')
    dump(root/'data'/'generation_manifest.json',summary)
    return summary

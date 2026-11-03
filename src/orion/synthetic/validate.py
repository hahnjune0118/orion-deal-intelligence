"""Dataset integrity, independent arithmetic and stage-local answer-key audits."""
from __future__ import annotations
from pathlib import Path
import json
from copy import deepcopy
from orion.domain.grounding import validate_grounding
from orion.domain.models import Claim
from .load import load_scenario,load_sources,agent_visible_bundle
from .models import Hypothesis,EvidenceLabel,QuestionLabel
from .scenario import replay_scenario


def financial_checks(world):
    """Independent integer arithmetic; explicit exceptions are not erased."""
    results=[]
    def check(name,actual,expected):
        results.append(dict(check=name,actual=actual,expected=expected,passed=actual==expected))
    for year in (2024,2025):
        income=world[f'income_{year}'];balance=world[f'balance_{year}']
        other=income.get('other_operating_income',0)
        check(f'{year}_ebitda',income['revenue']-income['cogs']-income['opex']+other,income['ebitda'])
        check(f'{year}_net_income',income['ebitda']-income['depreciation']-income['interest']-income['tax'],income['net_income'])
        check(f'{year}_assets',sum(balance.get(k,0) for k in ('cash','ar','inventory','prepaid','ppe')),balance['assets'])
        check(f'{year}_balance',sum(balance.get(k,0) for k in ('debt','ap','accrued','deferred','equity')),balance['assets'])
    old,new=world['balance_2024'],world['balance_2025'];income=world['income_2025'];cf=world['cashflow_2025']
    cfo=income['net_income']+income['depreciation']
    cfo-=sum(new.get(k,0)-old.get(k,0) for k in ('ar','inventory','prepaid'))
    cfo+=sum(new.get(k,0)-old.get(k,0) for k in ('ap','accrued','deferred'))
    check('2025_cfo',cfo,cf['cfo'])
    change=cf['cfo']-cf['capex']+cf.get('debt_raised',0)+cf.get('equity_raised',0)-cf.get('dividends',0)-cf.get('debt_repaid',0)
    check('2025_cash_change',change,cf['cash_change']);check('2025_cash_bridge',old['cash']+change,new['cash'])
    check('2025_ppe_rollforward',old['ppe']+cf['capex']-income['depreciation'],new['ppe'])
    check('2025_equity_rollforward',old['equity']+income['net_income']+cf.get('equity_raised',0)-cf.get('dividends',0),new['equity'])
    if 'customers_revenue_2025' in world:check('customer_revenue',sum(world['customers_revenue_2025'].values()),income['revenue'])
    if 'sales_by_product_2025' in world:check('product_revenue',sum(world['sales_by_product_2025'].values()),income['revenue'])
    if 'sales_by_geography_2025' in world:check('geography_revenue',sum(world['sales_by_geography_2025'].values()),income['revenue'])
    if 'aster' in world:
        a=world['aster'];f=world['forecast']
        check('aster_recurring',a['subscription']-a['cloud']-a['inference']-a['support'],a['recurring_contribution'])
        check('aster_first_year',a['recurring_contribution']+a['implementation_revenue']-a['implementation_cost'],a['first_year_contribution'])
        check('aster_invoice_cash',a['cash_received']+a['receivable'],a['billed'])
        check('aster_invoice_recognition',a['recognized_on_acceptance']+a['deferred'],a['billed'])
        check('management_forecast_arithmetic',f['existing']+f['deployments']*f['per_deployment'],f['revenue'])
        check('capacity_constrained_forecast',f['existing']+f['squads']*f['capacity_per_squad']*f['per_deployment'],f['supported_revenue'])
        if f['revenue']!=f['supported_revenue']:
            check('capacity_exception_documented',any('capacity' in e['id'] for e in world['intentional_exceptions']),True)
    if 'normalization' in world:
        n=world['normalization'];check('normalized_ebitda',income['ebitda']-n['insurance_recovery']+n['relocation_addback'],n['provisional_normalized_ebitda'])
    if 'capex' in world:
        c=world['capex'];check('capex_split',c['maintenance']+c['expansion'],cf['capex'])
        check('cash_after_maintenance',cf['cfo']-c['maintenance'],c['cfo_less_maintenance'])
    if 'inventory_2025' in world:
        inv=world['inventory_2025'];check('inventory_total',inv['raw_materials']+inv['wip']+inv['finished_goods'],inv['total'])
        check('inventory_nrv',inv['aged_finished_cost']-inv['aged_finished_estimated_nrv'],inv['potential_write_down'])
        f=world['forecast'];check('manufacturing_forecast_revenue',f['planned_equivalents']*f['per_equivalent'],f['revenue'])
        check('manufacturing_supported_revenue',f['capacity_equivalents']*f['per_equivalent'],f['supported_revenue'])
        check('manufacturing_forecast_ebitda',f['revenue']-f['cogs']-f['opex'],f['ebitda'])
        check('manufacturing_forecast_nwc',f['ar']+f['inventory']+f['prepaid']-f['ap']-f['accrued'],f['nwc'])
        nwc=new['ar']+new['inventory']+new['prepaid']-new['ap']-new['accrued']
        check('manufacturing_nwc_release',nwc-f['nwc'],f['nwc_release_vs_2025'])
        p=world['product_revenue_2025'];check('storage_revenue',p['storage_units']*p['storage_price'],p['storage_revenue'])
        check('cookware_revenue',p['cookware_units']*p['cookware_price'],p['cookware_revenue'])
        check('products_total',p['storage_revenue']+p['cookware_revenue'],income['revenue'])
        check('geography_total',sum(world['geography_revenue_2025'].values()),income['revenue'])
    return results


def answer_key_audit(gold,documents):
    """Reject future/unresolved locators and unsupported assertions of verification.

    Exact excerpt validation is mechanical; relevance/entailment and materiality
    remain explicitly self-authored, human-reviewable judgments.
    """
    errors=[];spans={s['id']:(doc,s) for doc in documents for s in doc['elements']}
    hypotheses={h['hypothesis_id'] for h in gold['hypotheses']}
    evidence_ids=set()
    for h in gold['hypotheses']:Hypothesis.model_validate(h)
    for item in gold['evidence']:
        label=EvidenceLabel.model_validate(item);ev=label.record;evidence_ids.add(ev.id)
        if ev.verification_level!='document_only':errors.append(f'{ev.id}: synthetic source incorrectly independently verified')
        for sid in ev.source_span_ids:
            if sid not in spans:errors.append(f'{ev.id}: unresolved source');continue
            doc,span=spans[sid]
            if label.available_stage!=doc['available_stage']:errors.append(f'{ev.id}: future evidence label mismatch')
            if span['quote']!=label.exact_source_excerpt:errors.append(f'{ev.id}: excerpt mismatch')
    for item in gold['claims']:
        claim=Claim.model_validate(item['record'])
        if item['hypothesis_id'] not in hypotheses:errors.append(f'{claim.id}: missing parent hypothesis')
        if any(sid not in spans for sid in claim.source_span_ids):errors.append(f'{claim.id}: unresolved claim source')
        for claimed_span in item.get('source_locators',[]):
            real=spans.get(claimed_span['id'])
            if not real or claimed_span!=real[1]:errors.append(f'{claim.id}: source locator or quote mismatch')
        if claim.claim_kind=='company_reported':
            if not claim.source_span_ids:errors.append(f'{claim.id}: company assertion lacks source')
            if len(item.get('source_locators',[]))!=len(claim.source_span_ids):errors.append(f'{claim.id}: incomplete claim locator annotation')
            for sid in claim.source_span_ids:
                if sid in spans and (spans[sid][1]['quote']!=item.get('exact_source_excerpt') or spans[sid][0]['available_stage']>item['label_stage']):errors.append(f'{claim.id}: unsupported claim excerpt/stage')
        for link in item.get('evidence_relationships',[]):
            match=next((e for e in gold['evidence'] if e['record']['id']==link['evidence_id']),None)
            if not match:errors.append(f'{claim.id}: invalid claim evidence link')
            elif claim.claim_kind=='company_reported' and match['available_stage']>item['label_stage']:errors.append(f'{claim.id}: future evidence used for current verdict')
    for q in gold['questions']:
        label=QuestionLabel.model_validate(q)
        if label.hypothesis_id not in hypotheses:errors.append(f'{label.record.id}: missing hypothesis')
        if not set(label.linked_evidence_ids)<=evidence_ids:errors.append(f'{label.record.id}: unknown evidence')
        claim=label.record.claim_id
        for eid in label.linked_evidence_ids:
            if next(e['record']['claim_id'] for e in gold['evidence'] if e['record']['id']==eid)!=claim:errors.append(f'{label.record.id}: irrelevant cross-claim evidence')
    qids={q['record']['id'] for q in gold['questions']}
    for stage,item in gold['stages'].items():
        if 'supporting_evidence_ids' not in item or 'expected_hypothesis_statuses' not in item:errors.append(f'stage{stage}: missing independently authored visible labels')
        if len(item['expected_top3'])>3 or not set(item['expected_top3'])<=qids:errors.append(f'stage{stage}: invalid ranking labels')
        for eid in item.get('supporting_evidence_ids',[]):
            match=next((e for e in gold['evidence'] if e['record']['id']==eid),None)
            if not match or match['available_stage']>int(stage):errors.append(f'stage{stage}: unsupported future gold evidence')
    return dict(passed=not errors,errors=errors,mechanical_checks='ID,stage,exact excerpt,document-only status',semantic_review='self-authored provisional; this audit does not prove entailment or expert validity')


def _source_financial_checks(world,documents):
    """Check values in actual parsed table cells against the separate world."""
    results=[]
    lookup={'Revenue':'revenue','Cost of revenue':'cogs','Operating expense ex depreciation':'opex','EBITDA':'ebitda','Depreciation':'depreciation','Interest':'interest','Tax':'tax','Net income':'net_income','Cash':'cash','Accounts receivable':'ar','Inventory':'inventory','Prepaids':'prepaid','Net PPE':'ppe','Total assets':'assets','Total liabilities and equity':'assets','Debt':'debt','Trade payables':'ap','Accrued costs':'accrued','Deferred revenue':'deferred','Equity':'equity'}
    for doc in documents:
        tables={}
        for span in doc['elements']:
            loc=span['locator']
            if loc['kind']=='docx_table_cell':tables.setdefault(loc['table_index'],{}).setdefault(loc['row'],{})[loc['column']]=span['normalized_text']
        for table in tables.values():
            if table.get(0,{}).get(1)!='FY2024' or table.get(0,{}).get(2)!='FY2025':continue
            for row,cells in table.items():
                label=cells.get(0);key=lookup.get(label)
                if not key:continue
                for col,year in ((1,2024),(2,2025)):
                    world_source=world[f'income_{year}'] if key in world[f'income_{year}'] else world[f'balance_{year}']
                    if key not in world_source:continue
                    try:actual=int(cells[col].replace(',',''))
                    except (ValueError,KeyError):actual=None
                    results.append(dict(check=f"native_{doc['record']['id']}_{year}_{label}",actual=actual,expected=world_source[key],passed=actual==world_source[key]))
    # All other numeric source tables have explicit world-to-cell bridges.
    for doc in documents:
        did=doc['record']['id'];tables={}
        for span in doc['elements']:
            loc=span['locator']
            if loc['kind']=='docx_table_cell':tables.setdefault(loc['table_index'],{}).setdefault(loc['row'],{})[loc['column']]=span['normalized_text']
        mappings={}
        if did=='nb_doc_plan':
            f=world['forecast'];mappings={0:{'Existing revenue USD':f['existing'],'Planned new deployments':f['deployments'],'Revenue per deployment USD':f['per_deployment'],'Forecast revenue USD':f['revenue'],'Squads':f['squads'],'Deployments per squad':f['capacity_per_squad'],'Current capacity deployments':f['squads']*f['capacity_per_squad'],'Capacity constrained revenue USD':f['supported_revenue']}}
        elif did=='nb_doc_cost':
            a=world['aster'];mappings={0:{'Subscription revenue':a['subscription'],'Cloud':a['cloud'],'Inference':a['inference'],'Recurring support':a['support'],'Recurring contribution':a['recurring_contribution'],'Implementation revenue':a['implementation_revenue'],'Implementation labor':a['implementation_cost'],'First year contribution':a['first_year_contribution']}}
        elif did=='mf_doc_sales':mappings={0:world['customers_revenue_2025']}
        elif did=='mf_doc_inventory':
            inv=world['inventory_2025'];mappings={0:{'Raw materials':inv['raw_materials'],'Work in progress':inv['wip'],'Finished goods':inv['finished_goods'],'Total inventory':inv['total']}}
        elif did=='mf_doc_plant':
            c=world['capex'];mappings={0:{'Maintenance and safety':c['maintenance'],'Expansion':c['expansion'],'Total':c['total']}}
        elif did=='mf_doc_forecast':
            f=world['forecast'];mappings={0:{'Planned production equivalents':f['planned_equivalents'],'Current capacity equivalents':f['capacity_equivalents'],'Revenue per equivalent USD':f['per_equivalent'],'Revenue USD':f['revenue'],'Cost of sales USD':f['cogs'],'Operating expense USD':f['opex'],'EBITDA USD':f['ebitda'],'Inventory USD':f['inventory'],'Operating NWC USD':f['nwc']}}
        for ti,mapping in mappings.items():
            rows={r.get(0):r for i,r in tables.get(ti,{}).items() if i}
            for label,expected in mapping.items():
                try:actual=int(rows[label][1].replace(',',''))
                except (ValueError,KeyError):actual=None
                results.append(dict(check=f'native_{did}_{label}',actual=actual,expected=expected,passed=actual==expected))
        if did=='mf_doc_count':
            total=0
            for i,row in tables.get(0,{}).items():
                if not i:continue
                try:book,count,cost,value=[int(row[j].replace(',','')) for j in range(1,5)]
                except (ValueError,KeyError):
                    results.append(dict(check='native_count_numeric',actual=None,expected='integers',passed=False));continue
                results.append(dict(check=f'native_count_{i}_quantity',actual=count,expected=book,passed=count==book))
                results.append(dict(check=f'native_count_{i}_cost',actual=count*cost,expected=value,passed=count*cost==value));total+=value
            results.append(dict(check='native_count_total',actual=total,expected=world['inventory_2025']['total'],passed=total==world['inventory_2025']['total']))
    return results


def validate_dataset(root):
    root=Path(root);report={'dataset_version':'3.0.0','cases':{},'public_orion':None}
    for case in ('nb','mf'):
        index,documents=load_sources(root,case);state,events,_=load_scenario(root,case)
        validate_grounding(state,source_resolver=index).raise_for_errors()
        gold=json.loads((root/'gold'/f'{case}_gold.json').read_text());world=json.loads((root/'gold'/f'{case}_world_model.json').read_text())
        audit=answer_key_audit(gold,documents);checks=financial_checks(world)+_source_financial_checks(world,documents)
        replay=replay_scenario(root,case)
        for view in replay['states']:
            stage=str(view['stage']);expected=gold['stages'][stage]
            checks.append(dict(check=f"stage_{stage}_top3",actual=view['top3'],expected=expected['expected_top3'],passed=view['top3']==expected['expected_top3']))
            statuses={k:v['support'] for k,v in view['hypothesis_status'].items()}
            checks.append(dict(check=f"stage_{stage}_hypothesis_status",actual=statuses,expected=expected['expected_hypothesis_statuses'],passed=statuses==expected['expected_hypothesis_statuses']))
            checks.append(dict(check=f"stage_{stage}_resolved_questions",actual=sorted(view['questions_resolved']),expected=sorted(expected['expected_resolved_questions']),passed=set(view['questions_resolved'])==set(expected['expected_resolved_questions'])))
            scores={r['question_id']:r['score'] for r in view['ranking']}
            checks.append(dict(check=f"stage_{stage}_scores",actual={q:scores[q] for q in view['top3']},expected=expected['expected_scores'],passed=all(scores[q]==v for q,v in expected['expected_scores'].items())))
            bundle=agent_visible_bundle(root,case,view['stage']);text=json.dumps(bundle)
            blocked=('world_truth_status','ground_truth_status','expected_top3','critical_families','expected_priority','acceptable_alternatives','world_model','questions_resolved')
            checks.append(dict(check=f"stage_{stage}_no_gold",actual=[x for x in blocked if x in text],expected=[],passed=not any(x in text for x in blocked)))
        report['cases'][case]=dict(passed=audit['passed'] and all(c['passed'] for c in checks),documents=len(documents),native_source_spans=sum(len(d['elements']) for d in documents),evidence=len(gold['evidence']),questions=len(gold['questions']),events=len(events),answer_key_audit=audit,checks=checks)
    public=json.loads((root/'data'/'public_orion'/'source_manifest.json').read_text())
    report['public_orion']={'passed':public['status']=='pending_verified_sources' and not public['public_facts'] and not public['documents'],'status':public['status']}
    report['passed']=all(c['passed'] for c in report['cases'].values()) and report['public_orion']['passed']
    return report

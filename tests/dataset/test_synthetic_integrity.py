from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from orion.synthetic import generate_dataset, validate_dataset, agent_visible_bundle, replay_scenario
from orion.synthetic.load import load_scenario, load_sources, case_folder
from orion.synthetic.validate import answer_key_audit, financial_checks
from orion.domain.transitions import apply_approved_update
from orion.domain.models import AnalystDecision


@pytest.fixture(scope='module')
def dataset(tmp_path_factory):
    root=tmp_path_factory.mktemp('synthetic');generate_dataset(root);return root


def decision(state,event):
    return AnalystDecision(id=f'{event.id}_decision',entity_version=1,deal_id=state.deal.id,actor_id='test_reviewer',actor_role='reviewer',target_type='evidence_update',target_id=event.id,target_version=1,selection_digest=None,action='approve',reason='Fixture simulated analyst review',base_revision=state.state_revision,decided_at=event.created_at)


def test_all_integrity_arithmetic_and_scenarios(dataset):
    result=validate_dataset(dataset)
    assert result['passed'],result
    assert result['cases']['nb']['evidence']>=15
    assert result['cases']['nb']['questions']>=10
    assert result['cases']['nb']['events']==4
    assert result['cases']['nb']['documents']==8
    assert result['cases']['mf']['documents']==6


@pytest.mark.parametrize('case,stage,n',[('nb',0,4),('nb',1,5),('nb',2,6),('nb',3,7),('nb',4,8),('mf',0,5),('mf',1,6)])
def test_visible_stage_is_exact_allowlist(dataset,case,stage,n):
    bundle=agent_visible_bundle(dataset,case,stage)
    assert len(bundle['documents'])==n
    serialized=json.dumps(bundle)
    for forbidden in ('expected_top3','world_truth_status','ground_truth_status','critical_families','questions_resolved'):
        assert forbidden not in serialized
    if case=='nb' and stage<4:assert 'wholly owned by Aster' not in serialized


@pytest.mark.parametrize('case,stage',[('../gold',0),('nb',-1),('nb',5),('mf',2),('nb',True),('nb','0')])
def test_visible_bundle_rejects_unknown_scope(dataset,case,stage):
    with pytest.raises((ValueError,TypeError)):
        agent_visible_bundle(dataset,case,stage)


def test_future_doc_stage_tampering_rejected(dataset,tmp_path):
    import shutil
    target=tmp_path/'tampered';shutil.copytree(dataset,target)
    p=target/'data/synthetic_northstar/documents/nb_doc_followup.json'
    raw=json.loads(p.read_text());raw['available_stage']=0;p.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='checksum|stage'):agent_visible_bundle(target,'nb',0)


def test_coordinated_stage_metadata_tampering_rejected(dataset,tmp_path):
    import shutil
    target=tmp_path/'tampered';shutil.copytree(dataset,target)
    p=target/'data/synthetic_northstar/documents/nb_doc_followup.json'
    raw=json.loads(p.read_text());raw['available_stage']=0;p.write_text(json.dumps(raw))
    inventory=target/'data/synthetic_northstar/structured/source_inventory.json'
    items=json.loads(inventory.read_text());item=next(i for i in items if i['document_id']=='nb_doc_followup')
    item['available_stage']=0;item['machine_sha256']=sha256(p.read_bytes()).hexdigest();inventory.write_text(json.dumps(items))
    with pytest.raises(ValueError,match='stage'):agent_visible_bundle(target,'nb',0)


def test_native_bytes_and_index_are_both_checked(dataset,tmp_path):
    import shutil
    target=tmp_path/'tampered';shutil.copytree(dataset,target)
    p=target/'data/synthetic_northstar/documents/nb_doc_cim.docx';p.write_bytes(p.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='checksum'):load_sources(target,'nb')


def test_gold_future_labels_are_flagged(dataset):
    _,docs=load_sources(dataset,'nb');gold=json.loads((dataset/'gold/nb_gold.json').read_text())
    gold['stages']['0']['supporting_evidence_ids']=['nb_ev_ownership']
    assert not answer_key_audit(gold,docs)['passed']


def test_gold_bad_exact_excerpt_is_flagged(dataset):
    _,docs=load_sources(dataset,'nb');gold=json.loads((dataset/'gold/nb_gold.json').read_text())
    gold['evidence'][0]['exact_source_excerpt']='invented quote'
    assert not answer_key_audit(gold,docs)['passed']


def test_financial_bad_totals_fail_and_intentional_exception_retained(dataset):
    world=json.loads((dataset/'gold/nb_world_model.json').read_text())
    world['income_2025']['revenue']+=1
    assert not all(c['passed'] for c in financial_checks(world))
    world=json.loads((dataset/'gold/nb_world_model.json').read_text())
    world['intentional_exceptions']=[]
    assert not all(c['passed'] for c in financial_checks(world))


def test_hypothetical_bayes_independent_fraction_benchmarks(dataset):
    from fractions import Fraction
    out=replay_scenario(dataset,'nb');belief=out['bayesian']['belief_snapshots']
    assert belief[0]['posterior']==pytest.approx(float(Fraction(12,19)))
    assert belief[1]['posterior']==pytest.approx(float(Fraction(30,37)))
    assert belief[2]['posterior']==pytest.approx(float(Fraction(13,41)))
    assert belief[3]['posterior']==pytest.approx(float(Fraction(30,79)))
    assert out['bayesian']['initial_eig']['eig_bits']==pytest.approx(.2361139273389372)


def test_bayesian_ablation_does_not_change_core_ranking(dataset):
    one=replay_scenario(dataset,'nb');two=replay_scenario(dataset,'nb',bayesian=False)
    assert [s['ranking'] for s in one['states']]==[s['ranking'] for s in two['states']]


def test_signed_is_not_accepted_collected_or_independent(dataset):
    out=replay_scenario(dataset,'nb');t1=out['states'][1]
    assert 'nb_q_contract_a' in t1['questions_resolved']
    assert {'nb_q_execution_a','nb_q_contract_b','nb_q_independence'}<=set(t1['questions_open'])
    assert t1['hypothesis_status']['nb_claim_h1']=={'support':'partial','truth':'document_only'}


def test_partial_cash_and_complete_costs_are_not_full_diligence(dataset):
    out=replay_scenario(dataset,'nb')
    assert 'nb_q_execution_a' in out['states'][2]['questions_resolved']
    assert 'nb_q_balance' in out['states'][2]['questions_open']
    assert out['states'][2]['top3']==out['states'][3]['top3']
    assert out['states'][3]['hypothesis_status']['nb_claim_h2']['support']=='contradicted'
    assert 'nb_q_costs' in out['states'][3]['questions_resolved']
    assert 'nb_q_margin_a' in out['states'][3]['questions_open']
    assert 'nb_q_independence' in out['states'][4]['questions_open']


def test_complete_event_trace_no_fabricated_generation(dataset):
    out=replay_scenario(dataset,'nb')
    for event in out['events']:
        assert event['newly_generated_questions']==[]
        assert not event['final_investment_approval']
        assert event['new_evidence'] and event['new_documents']
        assert event['incomplete_evidence_behavior'] and event['contradictory_evidence_behavior']


def test_incomplete_execution_event_retains_open_question(dataset):
    state,events,index=load_scenario(dataset,'nb')
    state=apply_approved_update(state,events[0],decision=decision(state,events[0]),snapshot_id='test_snapshot_t1',now=events[0].created_at,source_resolver=index)
    event=events[1].model_copy(deep=True);event.evidence=[e for e in event.evidence if e.id!='nb_ev_cash_a']
    after=apply_approved_update(state,event,decision=decision(state,event),snapshot_id='test_snapshot_t2',now=event.created_at,source_resolver=index)
    assert next(q for q in after.dd_questions if q.id=='nb_q_execution_a').workflow_status=='open'


def test_unapproved_event_cannot_activate_itself(dataset):
    state,events,index=load_scenario(dataset,'nb');event=events[0].model_copy(deep=True)
    event.evidence[0].review_status='approved'
    with pytest.raises(ValueError):apply_approved_update(state,event,decision=decision(state,event),snapshot_id='test_snapshot_reject',now=event.created_at,source_resolver=index)


def test_fabricated_quote_cannot_be_approved(dataset):
    state,events,index=load_scenario(dataset,'nb');event=events[0].model_copy(deep=True)
    event.source_spans[0].quote='fabricated'
    with pytest.raises(ValueError):apply_approved_update(state,event,decision=decision(state,event),snapshot_id='test_snapshot_reject',now=event.created_at,source_resolver=index)


def test_sources_reproduce_byte_for_byte(dataset,tmp_path):
    other=tmp_path/'reproduced';generate_dataset(other)
    for p in dataset.rglob('*.docx'):
        assert p.read_bytes()==(other/p.relative_to(dataset)).read_bytes()
    for p in dataset.rglob('*.json'):
        assert p.read_bytes()==(other/p.relative_to(dataset)).read_bytes()


def test_public_orion_has_no_invented_facts(dataset):
    manifest=json.loads((dataset/'data/public_orion/source_manifest.json').read_text())
    assert manifest['status']=='pending_verified_sources'
    assert manifest['public_facts']==manifest['documents']==[]


def test_documentary_claim_wrong_locator_and_link_fail(dataset):
    _,docs=load_sources(dataset,'nb');gold=json.loads((dataset/'gold/nb_gold.json').read_text())
    claim=next(c for c in gold['claims'] if c['record']['claim_kind']=='company_reported')
    claim['source_locators'][0]['locator']['block_index']+=1
    claim['evidence_relationships'].append({'evidence_id':'missing_evidence','relation':'supports'})
    audit=answer_key_audit(gold,docs)
    assert not audit['passed']
    assert any('locator' in e for e in audit['errors'])
    assert any('evidence link' in e for e in audit['errors'])


def test_source_input_import_does_not_import_world_builder():
    import subprocess,sys
    result=subprocess.run([sys.executable,'-c',"import sys;from orion.synthetic.load import agent_visible_bundle;assert 'orion.synthetic.cases' not in sys.modules;assert 'orion.synthetic.generate' not in sys.modules"],capture_output=True,text=True)
    assert result.returncode==0,result.stderr

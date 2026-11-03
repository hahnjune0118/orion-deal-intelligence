"""Real Chunk 2 approved transitions plus separate hypothetical Bayesian panel."""
from __future__ import annotations
from dataclasses import asdict
from orion.domain.models import AnalystDecision
from orion.domain.transitions import apply_approved_update, assert_current_state, question_changes
from orion.quant.bayes import BayesianLedger, ProbabilityAssumptions, ConditionalLikelihoodModel
from orion.quant.information_gain import binary_eig
from orion.domain.grounding import text_sha256
from .load import load_scenario


def _view(state,stage):
    head=next(s for s in state.ranking_snapshots if s.id==state.head_snapshot_id)
    return dict(stage=stage,state=state.model_dump(mode='json'),top3=head.top3,ranking=[r.model_dump(mode='json') for r in head.rows],questions_open=[q.id for q in state.dd_questions if q.workflow_status=='open'],questions_resolved=[q.id for q in state.dd_questions if q.workflow_status=='resolved'],hypothesis_status={c.id:dict(support=c.support_status,truth=c.truth_status) for c in state.claims})


def _bayesian(case,events):
    if case!='nb':return dict(status='not_parameterized',belief_snapshots=[],note='No probability invented for the manufacturing case.')
    ledger=BayesianLedger();snapshots=[];current={'nb_hyp_h1':.30,'nb_hyp_h2':.65}
    specs={1:('nb_hyp_h1','nb_ev_contract_a','nb_aster_contract',.80,.20),2:('nb_hyp_h1','nb_ev_accept_a','nb_aster_execution',.75,.30),3:('nb_hyp_h2','nb_ev_cost_a','nb_aster_cost_v2',.20,.80),4:('nb_hyp_h1','nb_ev_ownership','nb_ownership_registry',.10,.70)}
    for stage,event in enumerate(events,1):
        hypothesis,eid,group,lh,lnh=specs[stage];evidence=next(e for e in event.evidence if e.id==eid)
        span=next(s for s in event.source_spans if s.id==evidence.source_span_ids[0]);aid=f'nb_assumption_t{stage}'
        source='Explicit hypothetical scenario likelihood supplied by synthetic analyst; not estimated from empirical investment outcomes.'
        conditional=None;dependencies=()
        if stage==2:
            source+=' P(acceptance and first cash | H1, signed Aster contract)=0.75; P(the same | not H1, signed Aster contract)=0.30. This explicitly conditional chain-rule scenario is not independent evidence multiplication.'
            dependencies=('nb_aster_contract',)
            conditional=ConditionalLikelihoodModel(model_id='nb_conditional_t2',hypothesis_id=hypothesis,evidence_id=eid,assumption_id=aid,likelihood_h=lh,likelihood_not_h=lnh,conditioning_evidence_ids=['nb_ev_contract_a'],conditioning_group_ids=['nb_aster_contract'],assumption_source=source,reviewer_id='synthetic_analyst',reviewed_at='2026-11-03',review_status='approved')
        if stage==4:
            source+=' Ownership likelihood is conditional on the previously observed contract and acceptance under this synthetic chain model.'
            dependencies=('nb_aster_contract','nb_aster_execution')
            conditional=ConditionalLikelihoodModel(model_id='nb_conditional_t4',hypothesis_id=hypothesis,evidence_id=eid,assumption_id=aid,likelihood_h=lh,likelihood_not_h=lnh,conditioning_evidence_ids=['nb_ev_contract_a','nb_ev_accept_a'],conditioning_group_ids=['nb_aster_contract','nb_aster_execution'],assumption_source=source,reviewer_id='synthetic_analyst',reviewed_at='2026-11-03',review_status='approved')
        assumptions=ProbabilityAssumptions(assumption_id=aid,assumption_source=source,author_id='synthetic_analyst',as_of='2026-11-03',prior=current[hypothesis],likelihood_h=lh,likelihood_not_h=lnh)
        result=ledger.update(hypothesis_id=hypothesis,evidence_id=eid,evidence_group_id=group,source_fingerprint=text_sha256(span.quote),assumptions=assumptions,approved=True,dependent_group_ids=dependencies,conditional_model=conditional)
        current[hypothesis]=result.posterior
        snapshots.append(dict(stage=stage,**asdict(result)))
    eig=binary_eig(.30,.80,.20,'Explicit synthetic analyst binary answer model, not empirical data')
    return dict(status='hypothetical_calculated',belief_snapshots=snapshots,initial_eig=asdict(eig),core_ranking_affected=False,interpretation='Scenario assumptions only; changes in belief do not establish investment success probabilities or completed diligence.')


def replay_scenario(root,case='nb',*,bayesian=True):
    """Execute approved source-backed updates; a fixture simulates the reviewer.

    This is authored functional replay, not an LLM run or real analyst sign-off.
    All questions are pre-authored; no new generative question production occurs.
    """
    state,events,index=load_scenario(root,case)
    assert_current_state(state,source_resolver=index)
    states=[_view(state,0)];transitions=[]
    for stage,event in enumerate(events,1):
        before=state
        decision=AnalystDecision(id=f'{case}_decision_t{stage}',entity_version=1,deal_id=state.deal.id,actor_id='synthetic_reviewer',actor_role='reviewer',target_type='evidence_update',target_id=event.id,target_version=1,selection_digest=None,action='approve',reason='Explicit analyst approval simulated by authored evaluation fixture; no investment approval.',base_revision=state.state_revision,decided_at=event.created_at)
        state=apply_approved_update(state,event,decision=decision,snapshot_id=f'{case}_snapshot_t{stage}',now=event.created_at,source_resolver=index)
        assert_current_state(state,source_resolver=index)
        after=_view(state,stage);old=states[-1]
        transitions.append(dict(stage=stage,event_id=event.id,new_documents=[d.id for d in event.documents],new_evidence=[e.id for e in event.evidence],before_hypothesis_status=old['hypothesis_status'],after_hypothesis_status=after['hypothesis_status'],previously_unanswered_questions=old['questions_open'],questions_now_resolved=sorted(set(after['questions_resolved'])-set(old['questions_resolved'])),questions_still_open=after['questions_open'],newly_generated_questions=[],duplicate_questions_removed=[],obsolete_questions_removed=[],new_question_policy='Chunk 3 uses fixed human-authored candidates; no LLM question generation is claimed.',before_top3=old['top3'],after_top3=after['top3'],ranking_changes=[r.model_dump(mode='json') for r in question_changes(before,state)],explanation=event.analyst_note,incomplete_evidence_behavior='Only individually supported criteria receive credit; partial evidence cannot resolve the whole request.',contradictory_evidence_behavior='Qualified refutation keeps or reopens the question; contrary evidence remains until explicitly superseded.',review_status='simulated_analyst_approved',final_investment_approval=False))
        states.append(after)
    return dict(case=case,mode='authored_fixture_functional_replay',states=states,events=transitions,bayesian=_bayesian(case,events) if bayesian else {'status':'disabled_ablation','core_ranking_affected':False},actual_llm_calls=0)

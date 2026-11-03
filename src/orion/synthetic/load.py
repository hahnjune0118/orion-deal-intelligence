"""Source-only stage allowlist and immutable native resolver construction."""
from pathlib import Path
import json
from hashlib import sha256
from orion.adapters.parsers.native import NativeSourceIndex
from orion.domain.models import DealState, StagedEvidenceUpdate
from .constants import CASE_FOLDERS
from .models import DatasetDocument

# Source-only disclosure schedule. It contains no gold, ranks, world facts or future text.
STAGE_ALLOWLIST = {
 'nb': {'nb_doc_cim':0,'nb_doc_financial':0,'nb_doc_plan':0,'nb_doc_crm':0,'nb_doc_contract':1,'nb_doc_execution':2,'nb_doc_cost':3,'nb_doc_followup':4},
 'mf': {'mf_doc_financial':0,'mf_doc_sales':0,'mf_doc_inventory':0,'mf_doc_plant':0,'mf_doc_forecast':0,'mf_doc_count':1},
}


def case_folder(root, case):
    if case not in CASE_FOLDERS:raise ValueError('Unknown synthetic case')
    return Path(root)/'data'/CASE_FOLDERS[case]


def load_sources(root, case):
    folder=case_folder(root,case);inventory=json.loads((folder/'structured'/'source_inventory.json').read_text())
    if len(inventory)!=len(STAGE_ALLOWLIST[case]) or {i['document_id'] for i in inventory}!=set(STAGE_ALLOWLIST[case]):raise ValueError('Source inventory differs from allowlist')
    index=NativeSourceIndex();documents=[]
    for item in inventory:
        filename=item['filename']
        if Path(filename).name!=filename:raise ValueError('Source filename must be a basename')
        source=folder/'documents'/filename
        if source.is_symlink() or not source.resolve().is_relative_to(folder.resolve()):raise ValueError('Source must remain inside dataset folder')
        content=source.read_bytes()
        if sha256(content).hexdigest()!=item['sha256']:raise ValueError('Immutable source checksum mismatch')
        machine_path=source.with_suffix('.json')
        if machine_path.is_symlink():raise ValueError('Machine source may not be a symlink')
        machine_bytes=machine_path.read_bytes()
        if sha256(machine_bytes).hexdigest()!=item.get('machine_sha256'):raise ValueError('Machine source checksum mismatch')
        machine=json.loads(machine_bytes)
        validated=DatasetDocument.model_validate({k:v for k,v in machine.items() if k!='source_element_keys'})
        if machine['available_stage']!=STAGE_ALLOWLIST[case][item['document_id']] or machine['available_stage']!=item['available_stage']:raise ValueError('Source disclosure stage mismatch')
        for key in ('date','reporting_period'):
            if machine[key]!=item[key]:raise ValueError('Source metadata mismatch')
        if machine['record']['id']!=item['document_id'] or machine['record']['document_version']!=item['version'] or machine['record']['filename']!=filename:raise ValueError('Source identity mismatch')
        parsed=index.add(content,machine['record'])
        if parsed.document.model_dump(mode='json')!=machine['record']:raise ValueError('Document metadata differs from native parser')
        if parsed.document.parse_status!='parsed':raise ValueError('Native source did not parse')
        if [s.model_dump(mode='json') for s in parsed.source_spans]!=machine['elements']:raise ValueError('Source index differs from native bytes')
        documents.append(machine)
    return index,documents


def load_scenario(root,case):
    folder=case_folder(root,case);index,_=load_sources(root,case)
    state=DealState.model_validate_json((folder/'structured'/'initial_state.json').read_bytes())
    events=[StagedEvidenceUpdate.model_validate_json(p.read_bytes()) for p in sorted((folder/'updates').glob('t*.json'))]
    return state,events,index


def agent_visible_bundle(root,case='nb',stage=0):
    """Only native source units currently available; never read gold/world/state.

    A pipeline caller must pass this returned object, not the entire project
    directory, to an adapter. Filesystem co-location is not a security sandbox.
    """
    if type(stage) is not int or stage<0:raise ValueError('Stage must be a nonnegative integer')
    _,documents=load_sources(root,case)
    max_stage=max(d['available_stage'] for d in documents)
    if stage>max_stage:raise ValueError('Unknown stage')
    visible=[]
    for doc in documents:
        if doc['available_stage']>stage:continue
        visible.append(dict(document_id=doc['record']['id'],document_version=doc['record']['document_version'],title=doc['title'],date=doc['date'],reporting_period=doc['reporting_period'],synthetic=True,sha256=doc['record']['file_sha256'],elements=[dict(source_span_id=s['id'],locator=s['locator'],text=s['normalized_text']) for s in doc['elements']]))
    return dict(dataset_version='3.0.0',case=case,stage=stage,scenario_universe='Independent research variant nb; not a continuation of legacy ns' if case=='nb' else 'Independent manufacturing research case',documents=visible,probability_assumptions=[dict(assumption_id='nb_initial_question',prior=.30,positive_likelihood_h=.80,positive_likelihood_not_h=.20,assumption_source='Explicit synthetic analyst thought experiment; not calibrated investment probabilities')] if case=='nb' else [])

"""Original-file source room for the Orion (271560) public-disclosure case."""
from copy import deepcopy
from functools import cached_property
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from . import engine, financial


CASE_ID = 'orion-271560'
TITLE = '(주)오리온 (271560)'
GROUPS = {
    'public': '사업보고서·공개 기초자료',
    'related-party': 'Related Party · 특수관계자',
    'foreign-subsidiaries': 'Foreign Subsidiaries · 러시아 법인',
}
FORMATS = {'.pdf': 'application/pdf',
           '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}


class OrionCase:
    def __init__(self, root):
        self.root = Path(root) / CASE_ID

    def available(self):
        return (self.root / 'manifest.json').is_file()

    @cached_property
    def manifest(self):
        pack = json.loads((self.root / 'manifest.json').read_text(encoding='utf-8'))
        if pack.get('id') != CASE_ID or pack.get('schema') != 1:
            raise ValueError('오리온 자료 묶음의 형식이 맞지 않습니다.')
        return pack

    def catalog_entry(self):
        return dict(id=CASE_ID, title=TITLE, period=self.manifest['period'],
                    description='오리온 공개자료와 특수관계자·러시아 법인 후속 증빙')

    def open(self, store, *, copy=False):
        pack = self.manifest
        project_id = None if copy else uuid5(NAMESPACE_URL, 'orion-dd/' + pack['archive_sha256']).hex
        state = engine.initial(TITLE, pack['period'], 'manufacturing')
        state['library'] = CASE_ID
        catalog = [
            {k: d[k] for k in ('id', 'filename', 'folder', 'group', 'format', 'bytes', 'sha256')}
            for d in pack['documents']
        ]
        state['case_study'] = dict(
            id=CASE_ID, scenario_enabled=True, archive_sha256=pack['archive_sha256'],
            source_catalog=catalog, active_groups=['public'], evidence_samples=pack['reviews'],
            groups=GROUPS,
        )
        state['documents'] = deepcopy([d for d in pack['documents'] if d['group'] == 'public'])
        state['hypotheses'] = deepcopy(pack['hypotheses'])
        state['case_rules'] = deepcopy(pack['questions'])
        engine.generate(state)
        state['models'] = deepcopy(pack['models'])
        state['decisions'] = deepcopy(pack['decisions'])
        for q in state['questions']:
            q['model_version'] = state['models'][q['id']]['version']
        engine.audit(state, '오리온 사례 개설', '공개 기초자료와 편집 가능한 EIG·EVSI 실습 가정을 적용했습니다.')
        return store.import_case(state, [], identifier=project_id)

    def register_group(self, state, group):
        case = state.get('case_study', {})
        if case.get('id') != CASE_ID or case.get('archive_sha256') != self.manifest['archive_sha256']:
            raise ValueError('오리온 사례의 현재 문서 묶음에서 자료를 선택하세요.')
        if group not in GROUPS or group == 'public':
            raise ValueError('추가 증빙 폴더를 선택하세요.')
        if group in case['active_groups']:
            raise ValueError('이미 이 폴더의 자료를 등록했습니다.')
        documents = [d for d in self.manifest['documents'] if d['group'] == group]
        state['documents'].extend(deepcopy(documents))
        case['active_groups'].append(group)
        for review in case['evidence_samples']:
            if review['packet'] == group:
                for q in state['questions']:
                    if review['question'] in (q['id'], q['parent']):
                        q['source_refs'].append(review['span'])
        state['financial_facts'] = financial.observations(
            state['documents'], state.get('financial_facts', []))
        state['reconciliations'] = financial.reconcile(state['financial_facts'])
        engine.audit(state, '후속 원본 등록', f'{GROUPS[group]} · {len(documents)}개 · 증거 판정 전')

    def source(self, fid):
        if not self.available():
            return None
        return next((d for d in self.manifest['documents'] if d['id'] == fid), None)

    def original_path(self, source):
        return self.root / 'originals' / (source['id'] + source['format'])

    def worksheet_preview(self, source):
        path = self.root / 'worksheets' / (source['id'] + '.json')
        return json.loads(path.read_text(encoding='utf-8'))

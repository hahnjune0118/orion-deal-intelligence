"""Original-file source room for the Orion (271560) public-disclosure case."""
from copy import deepcopy
from functools import cached_property, lru_cache
import json
from pathlib import Path
from shutil import which
from subprocess import run, TimeoutExpired
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


@lru_cache(maxsize=10)
def pdf_preview(path, page, _revision):
    """Render one page of a bundled original for browsers without an inline PDF viewer."""
    renderer = which('pdftocairo')
    options = ['-singlefile', str(path), '-'] if renderer else [str(path)]
    renderer = renderer or which('pdftoppm')
    if not renderer:
        return None
    args = [renderer, '-f', str(page), '-l', str(page), '-scale-to', '1600', '-png', *options]
    try:
        result = run(args, capture_output=True, timeout=8)
    except (OSError, TimeoutExpired):
        return None
    if result.returncode == 0 and result.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
        return result.stdout
    return None


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
        project_id = None if copy else uuid5(NAMESPACE_URL, 'orion-dd/' + self.manifest['archive_sha256']).hex
        return store.import_case(self.initial_state(), [], identifier=project_id)

    def initial_state(self):
        pack = self.manifest
        state = engine.initial(TITLE, pack['period'], 'manufacturing')
        state['library'] = CASE_ID
        catalog = [
            {k: d[k] for k in ('id', 'filename', 'folder', 'group', 'format', 'bytes', 'sha256', 'total_units')}
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
        return state

    def evidence_demo(self, group):
        sample = next((row for row in self.manifest['reviews'] if row['packet'] == group), None)
        if sample is None:
            return None
        state = self.initial_state()
        before = engine.snapshot(state)
        self.register_group(state, group)
        evidence = engine.evidence_apply(state, sample)
        after = engine.snapshot(state)
        hypothesis = engine.find(state['hypotheses'], evidence['hypothesis'], '가설')
        source = next(d for d in state['documents'] if any(s['id'] == evidence['span'] for s in d['spans']))
        span = engine.find(source['spans'], evidence['span'], '원문 구간')
        source_info = {key: source[key] for key in ('id', 'filename', 'folder', 'format', 'total_units')}
        application = engine.replay(state)[1].get(evidence['id'], '미적용')
        fields = ('hypothesis', 'question', 'outcome', 'note', 'origin')
        summary_keys = ('probabilities', 'ranks', 'questions')
        return dict(
            before={key: before[key] for key in summary_keys},
            after={key: after[key] for key in summary_keys},
            evidence=dict({k: evidence[k] for k in fields}, application=application),
            hypothesis=hypothesis['title'], source=source_info, page=span.get('page'),
        )

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

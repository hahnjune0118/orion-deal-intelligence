"""Original-file source room for the Orion (271560) public-disclosure case."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property, lru_cache
import json
from pathlib import Path
import re
from shutil import which
from subprocess import run, TimeoutExpired
from uuid import NAMESPACE_URL, uuid5

from . import engine, financial, parsing


CASE_ID = 'orion-271560'
TITLE = '(주)오리온 (271560)'
GROUPS = {
    'public': '사업보고서·공개 기초자료',
    'related-party': 'Related Party · 특수관계자',
    'foreign-subsidiaries': 'Foreign Subsidiaries · 러시아 법인',
}
FORMATS = {'.pdf': 'application/pdf',
           '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
LEASE_PACKET = 'related-party'
KOREAN_DATE = r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일'


def lease_terms(span):
    """Apply the sample's documented field rules to freshly extracted text."""
    text = span['text']
    if not all(re.search(pattern, text) for pattern in (
        r'회사명\s*\(주\)\s*오리온홀딩스',
        r'거래상대방\s*\(주\)\s*오리온\s+회사와의 관계\s*계열회사',
        r'임대목적물\s*토지 및 건축물',
        r'소재지\s*서울시 강남구 남부순환로 2745',
        r'\(단위\s*:\s*백만\s*원\)',
    )):
        return None
    period = re.search(r'임대기간\s*' + KOREAN_DATE + r'\s*~\s*' + KOREAN_DATE, text)
    rent = re.search(r'연간임대료[ \t]+([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)[ \t]*$', text, re.M)
    if not period or not rent:
        return None
    start, end = (date(*map(int, period.groups()[i:i+3])) for i in (0, 3))
    amount = int(rent[1].replace(',', ''))
    if end <= start or amount <= 0:
        return None
    return dict(start=start.isoformat(), end=end.isoformat(), rent_krw_million=amount,
                rent_display=f'{amount:,}백만원({Decimal(amount) / 100:,.2f}억원)')


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
                    description='오리온 공개자료와 특수관계자·러시아 법인 후속 증빙',
                    lease_demo=self.lease_source is not None)

    @cached_property
    def lease_source(self):
        review_source = self.review_sources.get(LEASE_PACKET)
        if review_source:
            source = self.source(review_source['id'])
            if source['format'] == '.pdf' and self.original_path(source).is_file():
                return source
        return None

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

    @cached_property
    def review_sources(self):
        spans = {span['id']: (doc, span) for doc in self.manifest['documents'] for span in doc['spans']}
        sources = {}
        for review in self.manifest['reviews']:
            doc, span = spans[review['span']]
            sources[review['packet']] = {
                **{key: doc[key] for key in ('id', 'filename', 'folder', 'format', 'total_units')},
                'page': span.get('page'),
            }
        return sources

    def apply_group(self, state, group):
        case = state.get('case_study', {})
        if case.get('id') != CASE_ID or case.get('archive_sha256') != self.manifest['archive_sha256']:
            raise ValueError('오리온 사례의 현재 문서 묶음에서 자료를 선택하세요.')
        review = next((row for row in self.manifest['reviews'] if row['packet'] == group), None)
        if review is None:
            raise ValueError('반영할 증빙을 선택하세요.')
        if group not in case['active_groups']:
            self.register_group(state, group)
        engine.evidence_apply(state, review)

    def run_lease_demo(self, *, python=None):
        """Replay a clean case from real PDF bytes without editing the visitor's project."""
        source = self.lease_source
        if source is None:
            raise ValueError('기말 데모용 임대 공시 PDF가 등록되지 않았습니다.')
        with self.original_path(source).open('rb') as handle:
            parsed = parsing.parse(handle.read(parsing.MAX_BYTES + 1), source['filename'], python=python)
        if parsed['sha256'] != source['sha256']:
            raise ValueError('공시 원본 SHA-256이 등록된 값과 일치하지 않습니다.')

        state = self.initial_state()
        before = engine.snapshot(state)
        review = next(row for row in self.manifest['reviews'] if row['packet'] == LEASE_PACKET)
        question = engine.find(state['questions'], review['question'], '질문')
        followup = next(q for q in state['questions'] if q['parent'] == question['id'] and q['answer'] == 'contradict')
        hyp = engine.find(state['hypotheses'], question['topic'], '가설')
        doc = {**source, **parsed}
        state['documents'].append(doc)
        engine.audit(state, '공시 PDF 등록 및 추출', f"{doc['filename']} · {doc['parsed_units']}/{doc['total_units']}페이지")
        engine.analyze(state)

        candidates = []
        for span in parsed['spans']:
            try:
                terms = lease_terms(span)
            except ValueError:  # Invalid calendar date in the extracted text.
                continue
            if terms:
                candidates.append((span, terms))
        unit, terms = candidates[0] if len(candidates) == 1 else (None, None)
        applied = False
        if terms:
            start, end = map(date.fromisoformat, (terms['start'], terms['end']))
            applied = (start.year, start.month) == (2026, 6) and end - start >= timedelta(days=365)
        if applied:
            for row in (question, followup):
                row['source_refs'].append(unit['id'])
            engine.evidence_apply(state, dict(question=question['id'], outcome='contradict', span=unit['id'],
                group=LEASE_PACKET, note=f"공시에서 {terms['start']}~{terms['end']} 도곡 임차와 연간 임대료 "
                    f"{terms['rent_display']}을 확인했습니다. 리스부채와 정상화 손익은 추가 증빙이 필요합니다."))

        after = engine.snapshot(state)
        def question_state(snapshot, row):
            status = snapshot['questions'][row['id']]
            if not status['active']:
                return '조건 충족 대기'
            rank = snapshot['ranks'].get(row['id'])
            return f"{status['status']} · {rank}순위" if rank else status['status']

        result = dict(
            applied=applied, status='가설 반박 증빙 반영' if applied else '검토 필요 · 가설 확률 유지',
            source={k: doc[k] for k in ('id', 'filename', 'sha256', 'parser', 'parsed_units', 'total_units', 'warnings')},
            terms=terms, location=unit['location'] if unit else None,
            quote=unit['text'] if unit else None,
            hypothesis=hyp['title'], assumption=hyp['prior_source'],
            rule='도곡 특수관계자 임차가 2026년 6월에 시작하고 계약기간이 1년 이상이면 가설 반박으로 판정합니다.',
            before=before['probabilities'][hyp['id']], after=after['probabilities'][hyp['id']],
            questions=[dict(title=row['title'], before=question_state(before, row),
                            after=question_state(after, row)) for row in (question, followup)],
            open_evidence=followup['request'] if applied else question['request'],
        )
        state['disclosure_demo'] = result
        return state, result

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

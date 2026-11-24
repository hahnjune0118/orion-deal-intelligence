from hashlib import sha256
from pathlib import Path
import shutil

import pytest

from orion.rules import parsing
from orion.rules.orion_case import OrionCase, lease_terms
from orion.web.rules_app import create_rules_app


CASE_DIRECTORY = Path(__file__).resolve().parents[2] / '.local/orion-rules/case-studies'
DEMO_PATH = '/case-sources/orion-271560/lease-demo'


def test_lease_terms_require_unit_and_normalize_the_extracted_values():
    source = dict(text='''회사명 (주)오리온홀딩스
(단위 : 백만 원)
거래상대방 (주)오리온 회사와의 관계 계열회사
임대목적물 토지 및 건축물
소재지 서울시 강남구 남부순환로 2745
임대기간 2026년 6월 12일 ~ 2032년 4월 30일
- 연간임대료 12,345
''')
    assert lease_terms(source) == dict(start='2026-06-12', end='2032-04-30',
                                       rent_krw_million=12345, rent_display='12,345백만원(123.45억원)')
    assert lease_terms(dict(text=source['text'].replace('백만 원', '천 원'))) is None
    assert lease_terms(dict(text=source['text'].replace('연간임대료', '보증금'))) is None


def published_case():
    case = OrionCase(CASE_DIRECTORY)
    if not case.available() or not case.lease_source:
        pytest.skip('Prepare the public Orion source room to run the real-PDF checks.')
    return case


def test_one_click_parses_original_and_generates_matching_report(tmp_path):
    case = published_case()
    case_dir = tmp_path / 'case-studies' / 'orion-271560'
    (case_dir / 'originals').mkdir(parents=True)
    shutil.copyfile(case.root / 'manifest.json', case_dir / 'manifest.json')
    source_path = case.original_path(case.lease_source)
    shutil.copyfile(source_path, case_dir / 'originals' / source_path.name)
    app = create_rules_app(tmp_path)
    app.testing = True
    client = app.test_client()
    assert client.post(DEMO_PATH, headers={'Origin': 'https://other.example'}).status_code == 403
    response = client.post(DEMO_PATH, headers={'Origin': 'http://localhost'})
    assert response.status_code == 200
    demo, report = response.json['demo'], response.json['report_html']
    original = case.original_path(case.lease_source).read_bytes()
    upload_parse = parsing.parse(original, case.lease_source['filename'])
    assert demo['source']['sha256'] == sha256(original).hexdigest()
    assert demo['source']['parser'] == upload_parse['parser']
    assert demo['source']['parsed_units'] == demo['source']['total_units'] == 2
    assert demo['quote'] == upload_parse['spans'][1]['text']
    assert demo['terms']['end'] == '2031-12-31' and demo['terms']['rent_krw_million'] == 13767
    assert demo['before'] == .55 and round(demo['after'], 3) == .234
    assert demo['questions'][0]['after'] == '해소·반박'
    assert demo['questions'][1]['before'] == '조건 충족 대기'
    assert demo['questions'][1]['after'] == '검토 대기 · 2순위'
    assert report.index('기말 공시 데모 · 전후 요약') < report.index('자료 범위와 품질')
    for value in ('55.0%', '23.4%', demo['terms']['rent_display'], demo['open_evidence']):
        assert value in report
    assert client.get('/api/projects').json == []


def test_incomplete_extraction_keeps_the_hypothesis_at_its_prior(monkeypatch):
    case = published_case()
    parse = parsing.parse

    def incomplete(source, filename, *, python=None):
        result = parse(source, filename, python=python)
        for span in result['spans']:
            span['text'] = span['text'].replace('연간임대료', '누락 항목')
        return result

    monkeypatch.setattr(parsing, 'parse', incomplete)
    state, demo = case.run_lease_demo()
    assert not demo['applied'] and demo['terms'] is None
    assert demo['before'] == demo['after'] == .55
    assert demo['questions'][1]['after'] == '조건 충족 대기'
    assert not state['evidence']

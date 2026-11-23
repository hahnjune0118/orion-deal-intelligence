"""Prepare original PDFs and spreadsheets from the Orion FDD Sources archive."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile

from openpyxl import load_workbook
from pypdf import PdfReader


CASE_ID = 'orion-271560'
SOURCE_HASH = '7729888de7023c48bf6b3c59e8f01a2ee3862654bb69c61632f4e99c4bbe81ec'
ANNUAL = '[오리온]사업보고서(2026.03.18).pdf'
LEASE = '2026_Related_Party_Real_Estate_Lease.pdf'
GROUP_DISCLOSURE = '2026_Large_Business_Group_Disclosure.pdf'
LOCAL_FINANCIALS = '01_BFO_2025_Financials.xlsx.xlsx'
PAGES = {
    ANNUAL: (5, 25, 225, 226, 251),
    LEASE: (2,),
    GROUP_DISCLOSURE: (2, 12, 13),
    '02_2025_Financial_Statement_Notes.pdf.pdf': (1,),
    '2024_USA_NDR_Presentation.pdf': (1, 4, 5),
    'Supplier_Payment_Terms_20260814.pdf': (2, 3),
}
FOLDER_GROUPS = {'02_Related_Party': 'related-party', '06_Foreign_Subsidiaries': 'foreign-subsidiaries'}
FOLDER_LABELS = {
    '01_Financials': '분기별 IR',
    '02_Related_Party': '특수관계자 공시',
    '03_NWC': '사업보고서·운전자본',
    '05_CAPEX': '기업가치 제고 계획',
    '06_Foreign_Subsidiaries': '러시아 법인 현지 공시',
}
ASSUMPTION = ('수업 시연용 가정입니다. 사전확률·우도·효용·비용을 공개문서의 수치나 '
              '오리온의 실증적 위험확률로 추정하지 않았습니다.')


def digest(blob):
    return sha256(blob).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def span(doc_id, location, text, page=None):
    return dict(id='s_' + digest(f'{doc_id}|{location}|{text}'.encode())[:24],
                location=location, text=text, sha256=digest(text.encode()), page=page)


def pdf_spans(doc_id, source, filename):
    reader = PdfReader(io.BytesIO(source))
    pages = PAGES.get(filename, (1, 2))
    spans = []
    seen = set()
    for page in pages:
        text = (reader.pages[page - 1].extract_text() or '').strip()
        if len(re.findall(r'\w', text)) < 12:
            continue
        seen.add(page)
        for offset in range(0, len(text), 1200):
            quote = text[offset:offset + 1200]
            spans.append(span(doc_id, f'PDF {page}쪽 · 문자 {offset}~{offset + len(quote)}', quote, page))
    return spans, len(seen), len(reader.pages)


def cell_text(cell):
    return '' if cell.value is None else str(cell.value)


def spreadsheet(doc_id, source, filename):
    book = load_workbook(io.BytesIO(source), data_only=False)
    try:
        sheets = [
            dict(title=sheet.title, rows=[[cell_text(c) for c in row] for row in sheet.iter_rows()])
            for sheet in book
        ]
        if filename != LOCAL_FINANCIALS:
            return sheets, []
        sheet = book['Отчет о финансовых результатах']
        selected = ('G5', 'P5', 'S5', 'Z5', 'G7', 'P7', 'S7', 'Z7', 'G12', 'P12', 'S12', 'Z12')
        rows = ['   '.join(f'{coord}  {cell_text(sheet[coord])}' for coord in selected[start:start+4])
                for start in (0, 4, 8)]
        unit = cell_text(book['Сведения об организации']['L16'])
        text = '\n'.join([unit, *rows])
        return sheets, [span(doc_id, f'{sheet.title}!G5:Z12 · 2110 / 2200', text)]
    finally:
        book.close()


def hypothesis(key, label, title, counter, prior, refs):
    return dict(id=key, label=label, title=title, counter=counter, refs=refs, approved=True, prior=prior,
                origin_kind='공개자료에서 출발한 실사 가설', prior_source=ASSUMPTION, prior_version=1,
                rubric='원문으로 확인 가능한 조건을 검증합니다.')


def question(key, topic, title, request, criterion, refs, *, parent=None, answer=None,
             importance=4, obtainability=4):
    return dict(id=key, topic=topic, title=title, request=request, criterion=criterion,
                source_refs=refs, retrieval_method='원문 위치를 지정한 사례 질문', importance=importance,
                obtainability=obtainability, mandatory=False, parent=parent, answer=answer)


def scenario(documents):
    by_name = {d['filename']: d for d in documents}
    current = by_name[ANNUAL]['spans']
    related_ref = next(s['id'] for s in current if s['page'] == 225 and '오리온홀딩스' in s['text'])
    foreign_ref = next(s['id'] for s in current if s['page'] == 251 and '47.3%' in s['text'])
    lease_span = by_name[LEASE]['spans'][0]
    local_span = by_name[LOCAL_FINANCIALS]['spans'][0]
    if '13,767' not in lease_span['text'] or '2031년 12월 31일' not in lease_span['text']:
        raise ValueError('임대 공시의 금액·만기 인용을 확인하세요.')
    margins = [2_526_841 / 15_643_329, 2_759_320 / 19_868_761]
    values = ('19 868 761', '15 643 329', '2 759 320', '2 526 841')
    if any(v not in local_span['text'] for v in values):
        raise ValueError('러시아 재무제표 인용 셀을 확인하세요.')
    growth = 19_868_761 / 15_643_329 - 1

    hypotheses = [
        hypothesis('related', '특수관계자 임차',
                   '2026년 6월 이후 도곡 소재 오리온홀딩스 부동산의 장기 임차가 이어지지 않는다.',
                   '기존 임차 종료 직후 같은 지역에서 장기 계열사 임대차가 시작된다.', .55, [related_ref]),
        hypothesis('foreign', '러시아 법인 수익성',
                   '러시아 법인의 2025년 현지 기준 매출이익률은 2024년보다 하락했다.',
                   '러시아 법인의 현지 기준 매출이익률은 2024년보다 하락하지 않았다.', .40, [foreign_ref]),
    ]
    questions = [
        question('related.lease', 'related', '도곡 부동산의 계열사 장기 임차가 2026년 6월 이후 이어지는가?',
                 '대규모기업집단 현황 및 오리온홀딩스 특수관계인 부동산 임대 공시',
                 '오리온을 임차인으로 하는 도곡 소재 부동산 장기계약의 기간과 연간 임대료를 확인합니다.',
                 [related_ref], importance=5, obtainability=5),
        question('foreign.margin', 'foreign', '현지 재무제표에서도 러시아 법인의 매출이익률이 하락했는가?',
                 '러시아 법인 2025년 현지 재무제표 BFO와 재무제표 주석',
                 '같은 법인과 단위의 2024·2025년 매출이익(2200)을 매출(2110)로 나눠 비교합니다.',
                 [foreign_ref], importance=5, obtainability=4),
        question('related.normalization', 'related', '신규 임차 조건을 정상화 손익과 리스부채에 어떻게 연결할 것인가?',
                 '신·구 계약서, 지급 일정, 임차 목적물 범위, 증분차입이자율 및 리스부채 명세',
                 '기존 토지 임차와 신규 토지·건축물의 범위를 대사하고 감가상각·이자·현금 지급액을 구분합니다.',
                 [related_ref], parent='related.lease', answer='contradict', importance=5, obtainability=2),
        question('foreign.bridge', 'foreign', '현지통화 성장과 원화 보고 성장의 차이는 어떻게 대사되는가?',
                 '월별 환율, 러시아 현지 회계와 연결 보고 패키지, 기업회계기준 조정 및 연결 제거 명세',
                 '같은 법인·같은 기간의 RUB 실적에서 KRW 보고 실적까지 환율·기준·조정 효과를 대사합니다.',
                 [foreign_ref], parent='foreign.margin', answer='support', importance=5, obtainability=2),
    ]
    models = {}
    decisions = {}
    for q in questions:
        original = q['parent'] is None
        models[q['id']] = dict(a=.8 if original else .72, b=.2 if original else .28,
                               source=ASSUMPTION, version=1)
        q['model_version'] = 1
        go = [100, -100] if q['topic'] == 'related' else [-100, 100]
        decisions[q['id']] = dict(utilities=[go, [0, 0]], cost=5 if original else 8,
                                  delay=0 if original else 2, unit='효용점수', source=ASSUMPTION)
    reviews = [
        dict(label='임대 공시로 계약 연장 검토', packet='related-party', question='related.lease',
             span=lease_span['id'], outcome='contradict', group='related-party',
             note=('공시상 오리온홀딩스는 오리온에 도곡 소재 토지·건축물을 2026.06.05~2031.12.31 임대하며 '
                   '연간 임대료는 13,767백만원(137.67억원)입니다. 기존 토지 임차와 목적물 범위가 다릅니다. '
                   '따라서 공시만으로 기존 대비 비용 증가액이나 회계 조정액을 확정할 수 없습니다.')),
        dict(label='현지 손익으로 매출이익률 검토', packet='foreign-subsidiaries', question='foreign.margin',
             span=local_span['id'], outcome='support', group='foreign-subsidiaries',
             note=(f'러시아 현지 재무제표의 2110행·2200행을 사용했습니다. RUB 기준 매출은 {growth:.2%} 증가했지만 '
                   f'매출이익률은 {margins[0]:.2%}에서 {margins[1]:.2%}로 하락했습니다. '
                   '한국 사업보고서의 원화 보고 성장률과 비교하려면 환율과 회계기준·연결조정 대사가 필요합니다.')),
    ]
    return dict(hypotheses=hypotheses, questions=questions, models=models, decisions=decisions, reviews=reviews)


def build(archive, destination):
    archive_hash = digest(archive.read_bytes())
    if archive_hash != SOURCE_HASH:
        raise ValueError('검토한 FDD Sources.zip과 원본 해시가 다릅니다.')
    root = destination / CASE_ID
    originals = root / 'originals'
    originals.mkdir(parents=True, exist_ok=True)
    documents = []
    with ZipFile(archive, metadata_encoding='cp949') as bundle:
        files = sorted((f for f in bundle.infolist() if not f.is_dir()), key=lambda f: f.filename)
        for member in files:
            _, *folders, filename = member.filename.split('/')
            folder = folders[0] if folders else ''
            data = bundle.read(member)
            checksum = digest(data)
            doc_id = 'd_orion_' + checksum[:16]
            suffix = Path(filename).suffix.lower()
            if suffix == '.pdf':
                spans, count, total = pdf_spans(doc_id, data, filename)
            elif suffix == '.xlsx':
                sheets, spans = spreadsheet(doc_id, data, filename)
                write_json(root / 'worksheets' / (doc_id + '.json'), sheets)
                count = total = len(sheets)
            else:
                raise ValueError(f'원본 형식 확인 필요: {filename}')
            (originals / (doc_id + suffix)).write_bytes(data)
            documents.append(dict(
                id=doc_id, filename=filename, archive_path=member.filename, bytes=len(data), format=suffix,
                folder=FOLDER_LABELS.get(folder, '공개 기초자료'), group=FOLDER_GROUPS.get(folder, 'public'),
                origin='company' if folder != '06_Foreign_Subsidiaries' else 'independent',
                version=1, sha256=checksum, original=True, masked=False, spans=spans,
                parsed_units=count, total_units=total, status='원본 등록 · 발췌' if spans else '원본 등록',
                warnings=['PDF 원본 전체를 열람할 수 있습니다. 검색·근거 연결은 추출한 일부 페이지를 사용합니다.']
                if suffix == '.pdf' else [],
            ))
    if len(documents) != 23 or len({d['id'] for d in documents}) != len(documents):
        raise ValueError('원본 23개와 파일별 식별자를 확인하세요.')
    write_json(root / 'manifest.json', dict(
        schema=1, id=CASE_ID, archive_sha256=archive_hash,
        period='2025 사업연도 · 2026년 후속 공시', documents=documents, **scenario(documents),
    ))
    return root


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('archive', type=Path)
    cli.add_argument('destination', type=Path)
    args = cli.parse_args()
    print(build(args.archive, args.destination))

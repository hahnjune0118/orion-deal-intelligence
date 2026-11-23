"""Build the public Flask demo from a positive list of source files and locked packages."""
from pathlib import Path
from hashlib import sha256
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    '': '__init__',
    'rules': '__init__ analysis benchmark case_studies deal_visuals engine financial library orion_case parsing reporting retrieval store xlsx',
    'domain': '__init__ grounding models',
    'quant': '__init__ bayes information_gain',
    'adapters': '__init__',
    'adapters/parsers': '__init__ base native',
    'web': '__init__ hosted rules_app',
}
PACKAGES = set('flask werkzeug jinja2 itsdangerous click blinker markupsafe '
               'pydantic pydantic-core typing-extensions typing-inspection annotated-types '
               'openpyxl et-xmlfile python-docx python-pptx pypdf pillow lxml xlsxwriter'.split())
ASSETS = ('rules.html rules.css rules.js deal_visuals.css deal_visuals.js file-word.svg file-excel.svg '
          'file-powerpoint.svg file-pdf.svg file-other.svg file-csv.svg file-icons-sources.json').split()


def requirements():
    lock = (ROOT / 'requirements-linux.lock').read_text(encoding='utf-8')
    entries = re.findall(r'^([\w-]+)(==[^\n]+\n(?:    --hash=[^\n]+\n)+)', lock, re.M)
    selected = {name: name + body for name, body in entries if name in PACKAGES}
    if selected.keys() != PACKAGES:
        raise ValueError(f'Missing locked packages: {PACKAGES - selected.keys()}')
    return ''.join(selected.values())


def public_case(filename):
    pack = json.loads((ROOT / '.local/orion-rules/case-studies' / filename).read_text(encoding='utf-8'))
    if pack['schema'] != 'orion-anonymized-case-1' or pack['id'] != Path(filename).stem:
        raise ValueError('Invalid case identity')
    # Some slide templates keep an earlier transaction code on a line by itself.
    heading = re.compile(r'(?im)^Project[ \t]+(?!Alpha\b|Beta\b)[A-Z]+(?=\r?$)')
    def digest(text):
        return sha256(text.encode('utf-8')).hexdigest()
    def document_text(doc):
        return '\n\n'.join(span['location']+'\n'+span['text'] for span in doc['spans'])
    for doc in pack['documents']:
        if not doc['masked'] or digest(document_text(doc)) != doc['sha256']:
            raise ValueError('Expected verified masked case text')
        for span in doc['spans']:
            if digest(span['text']) != span['sha256']:
                raise ValueError('Invalid source span hash')
            span['text'] = heading.sub('프로젝트 [명칭 비공개]', span['text'])
            span['sha256'] = digest(span['text'])
        doc['sha256'] = digest(document_text(doc))
    return json.dumps(pack, ensure_ascii=False, separators=(',', ':'))


def build(*, with_cases=False, orion_case=None):
    filename = 'orion-271560-release.zip' if orion_case else 'orion-cases-ab.zip' if with_cases else 'orion-public.zip'
    output = ROOT / 'build/pythonanywhere' / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as bundle:
        for directory, names in MODULES.items():
            for name in names.split():
                path = Path('src/orion') / directory / (name + '.py')
                bundle.write(ROOT / path, path)
        for name in ASSETS:
            path = Path('src/orion/web/assets') / name
            bundle.write(ROOT / path, path)
        if with_cases:
            for filename in ('logistics-alpha.json', 'spirits-beta.json'):
                bundle.writestr('published-cases/' + filename, public_case(filename))
        if orion_case:
            case_root = Path(orion_case)
            if case_root.name != 'orion-271560' or not (case_root / 'manifest.json').is_file():
                raise ValueError('Pass the prepared orion-271560 directory.')
            paths = [case_root / 'manifest.json', *sorted((case_root / 'originals').iterdir()),
                     *sorted((case_root / 'worksheets').glob('*.json'))]
            for path in paths:
                bundle.write(path, Path('published-cases/orion-271560') / path.relative_to(case_root))
        for name in ('setup.py', 'wsgi.py'):
            bundle.write(ROOT / 'deploy/pythonanywhere' / name, name)
        bundle.writestr('requirements.txt', requirements())
    return output


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-cases', action='store_true', help='Bundle the two approved anonymized case studies.')
    parser.add_argument('--orion-case', type=Path, help='Bundle the verified Orion source room.')
    args = parser.parse_args()
    print(build(with_cases=args.with_cases, orion_case=args.orion_case))

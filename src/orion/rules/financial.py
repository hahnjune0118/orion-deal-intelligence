"""Conservative financial observations and explicit-basis reconciliation."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re

UNITS = {'원': 1, '천원': 1000, '백만원': 1000000, '억원': 100000000,
         'USD': 1, '천USD': 1000, '%': 1}
FIELDS = ('metric', 'value', 'unit', 'period', 'scope', 'basis')


def decimal(value):
    try:
        result = Decimal(str(value).replace(',', '').strip())
    except InvalidOperation:
        raise ValueError('재무 값은 유한한 숫자여야 합니다.') from None
    if not result.is_finite() or abs(result)>Decimal('1e18'):
        raise ValueError('재무 값의 범위를 확인하세요.')
    return result


def observations(documents, previous=()):
    retained = {f['id']: f for f in previous if f.get('reviewed')}
    result = [f for f in previous if f.get('manual')]
    for doc in documents:
        for span in doc['spans']:
            candidates = []
            cell = span.get('cell', {})
            if cell.get('fact'):
                candidates.append(cell['fact'])
            # Strict, auditable record format; free text numbers stay in findings.
            match = re.search(r'항목=([^;\n]+);\s*값=([-+\d,.]+);\s*단위=([^;\n]+);\s*기간=([^;\n]+);\s*범위=([^;\n]+);\s*구분=([^;\n]+)', span['text'])
            if match:
                candidates.append(dict(zip(FIELDS, match.groups())))
            for i, candidate in enumerate(candidates):
                identifier = 'f_'+sha256((span['id']+str(i)).encode()).hexdigest()[:20]
                row = dict(id=identifier, span=span['id'], document=doc['id'], filename=doc['filename'],
                           location=span['location'], reviewed=False, **candidate)
                try:
                    row['value'] = str(decimal(row['value']))
                except ValueError:
                    continue
                result.append(retained.get(identifier, row))
    return result


def reconcile(facts):
    """Only independently reviewed, exactly matching bases can be compared."""
    groups = {}
    for f in facts:
        if not f.get('reviewed') or not all(f.get(k) for k in FIELDS) or f['unit'] not in UNITS:
            continue
        currency = 'USD' if 'USD' in f['unit'] else '%' if f['unit']=='%' else 'KRW'
        key = (f['metric'], f['period'], f['scope'], f['basis'], currency)
        groups.setdefault(key, []).append(f)
    result = []
    # Bound pair generation before materializing it; never silently truncate a reconciliation.
    for rows in groups.values():
        counts = {}
        for f in rows:
            counts[f['document']] = counts.get(f['document'], 0)+1
        pairs = (len(rows)**2-sum(n*n for n in counts.values()))//2
        if pairs>200:
            raise ValueError('동일 기준의 대사 후보가 200쌍을 초과합니다. 항목·기간·범위를 세분화하세요.')
    for key, rows in groups.items():
        for i, a in enumerate(rows):
            for b in rows[i+1:]:
                if a['document']==b['document']:
                    continue
                av, bv = (decimal(f['value'])*UNITS[f['unit']] for f in (a,b))
                result.append(dict(id='recon_'+a['id']+'_'+b['id'], facts=[a['id'],b['id']],
                    refs=[a['span'],b['span']], metric=key[0], period=key[1], scope=key[2], basis=key[3],
                    unit=key[4], left=str(av), right=str(bv), difference=str(av-bv),
                    status='일치' if av==bv else '대사 차이 · 원인 미판정'))
    return result

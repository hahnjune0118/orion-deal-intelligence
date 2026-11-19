"""Local BM25 retrieval with Korean substrings; retrieval is not fact validation."""
from collections import Counter
import math
import re

VERSION = 'local-bm25-1'
SYNONYMS = {'매출': ['revenue', 'sales'], '수금': ['collection', 'receivable', '채권'],
            '계약': ['contract', '갱신'], '원가': ['cost', '비용'], '반복매출': ['recurring', 'arr', '구독']}


def tokens(text):
    words = re.findall(r'[a-z0-9]+|[가-힣]+', text.casefold())
    return words + [w[i:i+2] for w in words if re.fullmatch('[가-힣]+', w) and len(w)>2 for i in range(len(w)-1)]


def search(documents, query, limit=12):
    terms = set(tokens(query))
    for word, others in SYNONYMS.items():
        if word in query.casefold():
            terms.update(t for other in others for t in tokens(other))
    corpus = [(d, s, Counter(tokens(s['text']+' '+s.get('cell',{}).get('row_context','')))) for d in documents for s in d['spans']]
    if not terms or not corpus:
        return []
    avg = sum(sum(c.values()) for _, _, c in corpus)/len(corpus) or 1
    df = {t: sum(t in c for _, _, c in corpus) for t in terms}
    rows = []
    for doc, span, counts in corpus:
        length = sum(counts.values())
        score = sum(math.log(1+(len(corpus)-df[t]+.5)/(df[t]+.5))*counts[t]*2.2/
                    (counts[t]+1.2*(.25+.75*length/avg)) for t in terms if counts[t])
        if score:
            rows.append({**span, 'document': doc['id'], 'filename': doc['filename'],
                         'matches': round(score, 6), 'retrieval': VERSION})
    return sorted(rows, key=lambda r: (-r['matches'], r['id']))[:limit]

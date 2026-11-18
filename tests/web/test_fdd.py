import pytest
from orion.web.fdd import validate,initial

def test_fdd_missing_scope_and_unsupported_review_blocked():
    with pytest.raises(ValueError): validate('',initial(),[],set())
    rows=initial();rows[0]['status']='검토'
    with pytest.raises(ValueError): validate('KRW 백만원 / FY2025',rows,[],set())

def test_fdd_adjustments_separate_and_finite():
    row=dict(category='QoE',description='비경상 비용',amount='10.1',source_document='doc1',reviewer_note='기간·중복 확인',status='검토')
    sums=validate('FY2025 / KRW 백만원',initial(),[row,dict(row,category='NWC',amount='-2')],{'doc1'})
    assert sums=={'QoE':'10.1','NWC':'-2','Net debt':'0'}
    with pytest.raises(ValueError):validate('범위',initial(),[dict(row,amount='NaN')],{'doc1'})
    with pytest.raises(ValueError):validate('범위',initial(),[dict(row,source_document='other-deal')],{'doc1'})

import io
import hashlib
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from orion.rules.parsing import parse


def pdf_bytes(count=1,text='Revenue 100 and customer contracts'):
    writer=PdfWriter()
    for _ in range(count):
        page=writer.add_blank_page(width=595,height=842)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 40 780 Td ('+text+') Tj ET').encode())
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=io.BytesIO();writer.write(output);return output.getvalue()


def test_long_pdf_keeps_original_page_numbers_and_full_file_hash():
    raw=pdf_bytes(61)
    result=parse(raw,'report.pdf')
    assert result['parsed_units']==result['total_units']==61
    assert result['sha256']==hashlib.sha256(raw).hexdigest()
    assert result['spans'][-1]['location'].startswith('61페이지')
    assert result['spans'][-1]['text'].strip()=='Revenue 100 and customer contracts'


def test_docx_and_pptx_preserve_exact_locations():
    from docx import Document
    from pptx import Presentation
    doc=Document();doc.add_paragraph('매출 100 계약');table=doc.add_table(rows=1,cols=1);table.cell(0,0).text='고객 수금'
    buf=io.BytesIO();doc.save(buf)
    result=parse(buf.getvalue(),'data.docx')
    assert any('행 1 · 열 1' in s['location'] for s in result['spans'])
    assert any(s['text']=='매출 100 계약' for s in result['spans'])
    deck=Presentation();slide=deck.slides.add_slide(deck.slide_layouts[1]);slide.shapes.title.text='매출 성장';slide.placeholders[1].text='계약 증빙'
    buf=io.BytesIO();deck.save(buf)
    result=parse(buf.getvalue(),'deck.pptx')
    assert any('슬라이드 1 · 도형' in s['location'] for s in result['spans'])
    assert any(s['text']=='계약 증빙' for s in result['spans'])


def test_scan_has_no_invented_text_or_success_status():
    writer=PdfWriter();writer.add_blank_page(width=595,height=842);buf=io.BytesIO();writer.write(buf)
    result=parse(buf.getvalue(),'scan.pdf')
    assert result['status']=='검토 필요'
    assert result['parsed_units']==0 and result['total_units']==1
    assert result['spans']==[]


@pytest.mark.parametrize('name,raw',[('fake.pdf',b'not-pdf'),('model.xlsx',b'not-supported'),('a.txt',b'\xff\xff')])
def test_unsupported_or_invalid_files_fail_without_fake_success(name,raw):
    with pytest.raises(ValueError):parse(raw,name)

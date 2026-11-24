"""Bounded local parsing in a subprocess. No OCR, macros or URL fetching."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 1_500_000


def _units(source, filename):
    ext = Path(filename).suffix.lower()
    result, warnings = [], []
    if ext == '.pdf':
        if not source.startswith(b'%PDF-'):
            raise ValueError('PDF 파일 형식이 올바르지 않습니다.')
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(source))
        if reader.is_encrypted:
            raise ValueError('암호화 PDF는 암호를 해제한 사본으로 등록하세요.')
        if len(reader.pages) > 600:
            raise ValueError('600페이지 이하의 문서/분할 사본을 등록하세요. 일부만 읽고 완료 처리하지 않습니다.')
        total = len(reader.pages)
        for i, page in enumerate(reader.pages,1):
            content = page.get_contents()
            if content and len(content.get_data()) > 64*1024*1024:
                raise ValueError('PDF 페이지의 확장 크기 한도를 초과했습니다.')
            value = page.extract_text() or ''
            if value.strip():
                result.append((f'{i}페이지',value))
            else:
                warnings.append(f'{i}페이지: 추출 텍스트 없음 · OCR/직접 확인 필요')
    elif ext == '.xlsx':
        from .xlsx import units
        result,warnings,total = units(source)
    elif ext in {'.docx','.pptx'}:
        from orion.adapters.parsers.native import _parse_bytes
        metadata = dict(id='doc_rules',entity_version=1,deal_id='deal_rules',filename=filename,
                        format=ext[1:],document_version=1,asset_status='file_verified',file_sha256=None,
                        parse_status='pending',parser_version='rules-native-wrapper-1',source_origin='company',
                        origin_key='rules-upload',created_at='2026-11-18T00:00:00Z')
        parsed = _parse_bytes(source,metadata)
        warnings += list(parsed.warnings)
        for span in parsed.source_spans:
            loc = span.locator.model_dump()
            label = (f"슬라이드 {loc['slide']} · 도형 {loc['shape_id']} · 문단 {loc['paragraph_index']+1}" +
                     (f" · 표 행 {loc['table_cell']['row']+1} · 열 {loc['table_cell']['column']+1}" if loc.get('table_cell') else '') if 'slide' in loc else
                     f"표 {loc.get('table_index',0)+1} · 행 {loc.get('row',0)+1} · 열 {loc.get('column',0)+1}"
                     + f" · 문단 {loc.get('paragraph_index',0)+1}"
                     if loc['kind']=='docx_table_cell' else f"본문 블록 {loc.get('block_index',0)+1} · 문단 {loc.get('paragraph_index',0)+1}")
            result.append((label,span.normalized_text))
        total = len(result)
    elif ext in {'.txt','.md','.csv'}:
        try:
            value = source.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('텍스트/CSV는 UTF-8로 저장한 사본을 사용하세요.') from None
        lines = value.splitlines()
        total = len(lines)
        result = [(f'{i}행',line) for i,line in enumerate(lines,1) if line.strip()]
    else:
        raise ValueError('PDF, DOCX, PPTX, XLSX, TXT, MD, CSV 형식을 지원합니다.')
    if sum(len(row[1]) for row in result) > MAX_CHARS:
        raise ValueError('추출 텍스트가 150만 자 한도를 초과했습니다. 문서를 분할하세요.')
    return result,warnings,total


def _parse(source, filename):
    if not source or len(source)>MAX_BYTES:
        raise ValueError('파일은 10MB 이하여야 합니다.')
    units,warnings,total = _units(source,filename)
    digest = hashlib.sha256(source).hexdigest()
    spans = []
    for unit in units:
        location,value = unit[:2]
        # Exact slices of extracted text, never summaries or invented citations.
        for start in range(0,len(value),1200):
            quote = value[start:start+1200]
            if not quote.strip():
                continue
            identifier = 's_'+hashlib.sha256((digest+'|'+location+'|'+str(start)+'|'+quote).encode()).hexdigest()[:24]
            spans.append(dict(id=identifier,location=location+f' · 문자 {start}~{start+len(quote)}',
                              text=quote,sha256=hashlib.sha256(quote.encode()).hexdigest()))
            if len(unit)>2:
                spans[-1]['cell'] = unit[2]
    return dict(sha256=digest,spans=spans,warnings=warnings,total_units=total,
                parsed_units=len(units),status='검토 필요' if warnings or not spans else '추출 완료',
                parser='rules-local-1.0.0')


def parse(source, filename, *, python=None):
    if not source or len(source)>MAX_BYTES:
        raise ValueError('파일은 10MB 이하여야 합니다.')
    payload=json.dumps(dict(data=base64.b64encode(source).decode(),filename=filename))
    try:
        completed=subprocess.run([python or sys.executable,'-m','orion.rules.parsing','--worker'],input=payload,
                                 text=True,encoding='utf-8',capture_output=True,timeout=40)
    except subprocess.TimeoutExpired:
        raise ValueError('자료 처리 시간이 40초를 초과했습니다. 문서를 분할해 등록하세요.') from None
    if completed.returncode:
        raise ValueError('자료를 추출하지 못했습니다. 원본 파일 형식을 확인하세요.')
    output=json.loads(completed.stdout)
    if 'error' in output:
        raise ValueError(output['error'])
    return output


if __name__ == '__main__':
    try:
        request=json.loads(sys.stdin.read())
        answer=_parse(base64.b64decode(request['data']),request['filename'])
    except Exception as error:
        answer={'error':str(error) if isinstance(error,ValueError) else '문서 파싱 실패 · 파일의 구조와 지원 형식을 확인하세요.'}
    sys.stdout.write(json.dumps(answer,ensure_ascii=True))

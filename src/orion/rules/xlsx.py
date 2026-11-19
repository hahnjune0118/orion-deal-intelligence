"""Read bounded XLSX cells without executing formulas or external links."""
import io
from zipfile import ZipFile, BadZipFile


def units(source):
    from openpyxl import load_workbook
    try:
        with ZipFile(io.BytesIO(source)) as z:
            if len(z.infolist())>3000 or sum(i.file_size for i in z.infolist())>64*1024*1024:
                raise ValueError('Excel 확장 크기 또는 항목 수 한도를 초과했습니다.')
    except BadZipFile:
        raise ValueError('XLSX 파일 형식을 확인하세요.') from None
    wb = load_workbook(io.BytesIO(source), read_only=True, data_only=False, keep_links=False)
    cached = load_workbook(io.BytesIO(source), read_only=True, data_only=True, keep_links=False)
    result, warnings = [], []
    count = 0
    aliases = {'항목':'metric','값':'value','단위':'unit','기간':'period','범위':'scope','구분':'basis'}
    try:
        if len(wb.worksheets)>30:
            raise ValueError('Excel은 최대 30개 시트를 지원합니다.')
        for sheet in wb:
            if sheet.max_row*sheet.max_column>50000:
                raise ValueError('Excel 시트당 5만 셀 한도입니다. 필요한 시트를 분리하세요.')
            header = {}
            for row, values in zip(sheet.iter_rows(), cached[sheet.title].iter_rows()):
                if not header:
                    candidate = {aliases[str(c.value).strip()]: i for i,c in enumerate(row) if str(c.value).strip() in aliases}
                    if len(candidate)==6:
                        header = candidate
                record = {k: row[i].value for k,i in header.items()} if header else {}
                for cell, cache in zip(row, values):
                    if cell.value is None:
                        continue
                    count += 1
                    if count>50000:
                        raise ValueError('Excel 전체 5만 비어 있지 않은 셀 한도입니다.')
                    formula = str(cell.value) if cell.data_type=='f' else None
                    value = cache.value if formula else cell.value
                    if cell.data_type=='e' or cache.data_type=='e':
                        warnings.append(f'{sheet.title}!{cell.coordinate}: Excel 오류 {value}')
                    if formula and value is None:
                        warnings.append(f'{sheet.title}!{cell.coordinate}: 수식 계산값 없음 · 자동 재계산 안 함')
                    meta = dict(sheet=sheet.title, address=cell.coordinate, raw=str(cell.value),
                                formula=formula, cached=value if isinstance(value,(str,int,float,bool)) else str(value) if value is not None else None,
                                number_format=cell.number_format, sheet_state=sheet.sheet_state)
                    if record:
                        meta['row_context']='; '.join(str(k)+'='+str(v) for k,v in record.items() if v is not None)
                    if header.get('value') is not None and cell.column==header['value']+1 and record.get('metric') not in (None,'항목') and value is not None and cell.data_type!='e' and cache.data_type!='e':
                        meta['fact'] = {k: str(value if k=='value' else record.get(k) or '') for k in aliases.values()}
                    result.append((f'시트 {sheet.title} · 셀 {cell.coordinate}', str(cell.value), meta))
            if sheet.sheet_state!='visible':
                warnings.append(f'{sheet.title}: 숨김 시트 포함 · 범위 확인 필요')
        warnings.insert(0,'Excel 수식은 실행하지 않습니다. 저장된 계산값은 최신 여부를 직접 확인하세요. 재무 관측치는 항목·값·단위·기간·범위·구분 열에서 추출하며 검토 후 대사합니다.')
    finally:
        wb.close(); cached.close()
    return result, warnings[:200], count

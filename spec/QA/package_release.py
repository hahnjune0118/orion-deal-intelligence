"""Build and verify the specification handoff ZIP, not the application.
Run: python QA/package_release.py
Requires the same jsonschema dependency as validate_package.py.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'ORION_GPT_PRO_HANDOFF.zip'
STANDALONE=ROOT.parent/'01_MASTER_SPECIFICATION.md'

def digest(data):return hashlib.sha256(data).hexdigest()

def purpose(name):
    if name=='DELIVERY_MANIFEST.md':return '제출 범위와 전체 파일 목록'
    if name=='CHECKSUMS.sha256':return '각 파일의 SHA-256 무결성 목록'
    if name.startswith('PROMPTS/'):return '후속 구현용 단계별 작업 지시와 실행 Gate'
    if name.startswith('SCHEMAS/'):return '기계 판독 모델 계약과 필드 사전'
    if name.startswith('EXAMPLES/'):return 'Northstar 초기 상태·단일 이벤트·기대 전이'
    if name.startswith('DATASET_SPECS/'):return '추가 합성 사례와 재무 일치 기준'
    if name.startswith('EVAL_GOLD/'):return '모델 입력에서 제외할 잠정 평가 기준'
    if name.startswith('DESIGN/'):return '독립적인 UI 배치와 승인 전후 wireframe'
    if name.startswith('CONFIG/'):return '의존성 후보와 fail-closed Live 가격 설정'
    if name.startswith('QA/'):return '실행한 명세 검증, 근거 기록, 재검증 도구'
    return 'Master Specification의 구성 문서'

def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('.'))

def main():
    (ROOT/'CHECKSUMS.sha256').touch()
    names=[p.relative_to(ROOT).as_posix() for p in files()]
    required_prefixes=('PROMPTS/','EXAMPLES/')
    def required(n):return (n in ['DELIVERY_MANIFEST.md','SCHEMAS/models.schema.json'] or n.startswith(required_prefixes) or (n.endswith('.md') and '/' not in n and n[:2].isdigit()))
    required_count=sum(required(n) for n in names)
    assert required_count==23,required_count
    lines=['# Delivery Manifest','','Orion Deal Intelligence 2.0 · Contract 1.0.0 · 2026-11-03','',
           f'필수 산출물 **23개 전부**와 보완 자료를 포함한 총 **{len(names)}개 파일**이다. ZIP의 최상위에서 00_READ_FIRST.md부터 읽는다. 전체 애플리케이션은 이번 산출물에 포함하지 않는다.','',
           '## 전달 파일','',
           '- `ORION_GPT_PRO_HANDOFF.zip`: 아래 파일 전체를 담은 압축파일.',
           '- `01_MASTER_SPECIFICATION.md`: ZIP 내부와 byte-identical인 별도 Markdown 사본. 단독 사본의 상대 링크는 ZIP을 풀었을 때 해당 동반 문서로 연결된다.','',
           '## 현재 검증 범위','',
           '[명세 검증 결과](QA/VALIDATION_REPORT.md)는 JSON Schema, 참조·원문 텍스트 무결성, 루브릭·Bayes/EIG 산술, 세 예시 전이, 음성 입력, 필수 파일과 내부 링크를 검사한 기록이다. 제품 실행·실제 문서 파서·브라우저·Live API·hosting·학술 성능 결과가 아니다.',
           '직접 dependency 17개 release metadata와 Linux CPython3.12 resolver dry-run(총63개)을 확인했다. 설치·취약점·Windows 통합 시험은 후속 Chunk1 Gate다. 두 SVG wireframe을 PNG로 렌더하여 내용·배치·승인 전후 상태 표기를 시각 확인했다. 이는 실제 앱의 접근성 통과 보고가 아니다.','',
           '## 파일 목록','','| File | Required | Purpose |','|---|---|---|']
    for name in names:lines.append(f'| [{name}]({name}) | {"필수" if required(name) else "보완"} | {purpose(name)} |')
    lines+=['','## 무결성 재확인','',
            '`CHECKSUMS.sha256`은 자신을 제외한 모든 파일의 SHA-256을 포함한다. `QA/package_release.py`는 실제 검증 스크립트 실행 후 manifest/checksum을 생성하고 ZIP CRC, 모든 member bytes/hash, JSON 구문, 내부 링크, 별도 Master 사본 일치를 확인한다.',
            '검증 보고서를 재실행하면 실행시각이 바뀌므로 기존 checksum과 다를 수 있다. 수정 후에는 package_release.py로 새 패키지를 만들고 기존 배포 파일과 구분한다.','',
            '## 의도적으로 포함하지 않은 것','',
            '원본 DOCX/업로드 자료의 재배포본, 실제 기업 비공개 데이터, API key, venv, 임시 파일, 앱 구현 코드, native 합성 source 파일은 포함하지 않는다. 현재 source 예시는 fixture_text_only이며 native PDF/DOCX/PPTX 생성과 parsing 검증은 Chunk3의 명시된 산출물이다.','']
    (ROOT/'DELIVERY_MANIFEST.md').write_text('\n'.join(lines),encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'QA/validate_package.py')],check=True)
    members=files()
    checksum=''.join(digest(p.read_bytes())+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in members if p.name!='CHECKSUMS.sha256')
    (ROOT/'CHECKSUMS.sha256').write_text(checksum,encoding='utf-8')
    local_links=0
    for path in members:
        if path.suffix=='.json':json.loads(path.read_text(encoding='utf-8'))
        if path.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
                if target.startswith(('http:','https:','mailto:','#')):continue
                target=target.split('#')[0]
                if target:
                    assert (path.parent/target).is_file(),(path,target)
                    local_links+=1
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in members:
            name=path.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,path.read_bytes())
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None,'ZIP CRC failure'
        assert sorted(archive.namelist())==sorted(p.relative_to(ROOT).as_posix() for p in members)
        for path in members:assert archive.read(path.relative_to(ROOT).as_posix())==path.read_bytes()
        for line in checksum.splitlines():
            expected,name=line.split('  ',1);assert digest(archive.read(name))==expected,name
        assert not any(n.startswith('/') or '..' in Path(n).parts for n in archive.namelist())
    shutil.copyfile(ROOT/'01_MASTER_SPECIFICATION.md',STANDALONE)
    assert STANDALONE.read_bytes()==(ROOT/'01_MASTER_SPECIFICATION.md').read_bytes()
    qa=json.loads((ROOT/'QA/validation_results.json').read_text())
    report={'status':'pass','files':len(members),'required_files':required_count,'qa_passed':qa['passed'],'qa_failed':qa['failed'],'internal_links':local_links,'zip_crc':'pass','member_bytes_and_sha256':'pass','standalone_master_identical':True,'zip_bytes':OUTPUT.stat().st_size,'zip_sha256':digest(OUTPUT.read_bytes()),'master_sha256':digest(STANDALONE.read_bytes())}
    (ROOT.parent/'orion_package_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

"""Baseline exceptions approve exact metadata bytes, not arbitrary changes."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import validate_chunk04 as validation

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def baseline(tmp_path,monkeypatch):
    evidence=tmp_path/'implementation_evidence';evidence.mkdir()
    original={'.gitignore':b'build/\n','src/core.py':b'protected core\n'}
    for name,data in original.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (evidence/'chunk04-baseline-manifest.json').write_text(json.dumps(dict(zip_sha256='fixture',files={n:sha256(b).hexdigest() for n,b in original.items()})),encoding='utf-8')
    monkeypatch.setattr(validation,'ROOT',tmp_path);monkeypatch.setattr(validation,'EVIDENCE',evidence)
    return tmp_path


def test_only_reviewed_private_data_ignore_change_is_allowed(baseline):
    (baseline/'.gitignore').write_bytes((ROOT/'.gitignore').read_bytes())
    assert validation.verify_baseline()['status']=='pass'
    with (baseline/'.gitignore').open('ab') as stream:stream.write(b'unreviewed-directory/\n')
    result=validation.verify_baseline()
    assert result['status']=='failed'
    assert result['unexpected_changes']==['.gitignore']


def test_protected_core_changes_and_missing_files_still_fail(baseline):
    (baseline/'.gitignore').write_bytes((ROOT/'.gitignore').read_bytes())
    (baseline/'src/core.py').write_bytes(b'changed core\n')
    assert validation.verify_baseline()['unexpected_changes']==['src/core.py']
    (baseline/'src/core.py').unlink()
    assert validation.verify_baseline()['missing_original_files']==['src/core.py']

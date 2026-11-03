"""Capture installed dependency metadata and retain upstream license notices."""
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]

def main():
    names = re.findall(r'^([A-Za-z0-9_.-]+)==', (ROOT/'requirements-linux.lock').read_text(), re.M)
    target = ROOT/'third_party_licenses'
    target.mkdir(exist_ok=True)
    entries = []
    for name in names:
        dist = metadata.distribution(name)
        meta = dist.metadata
        licenses = []
        for file in dist.files or []:
            basename = Path(str(file)).name.lower()
            if ('licenses' in str(file).lower().split('/') or basename.startswith(('license', 'copying', 'notice'))) and dist.locate_file(file).is_file():
                source = Path(dist.locate_file(file))
                dest = target / name.lower() / str(file).replace('..', '_').replace('/', '__')
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                licenses.append(str(dest.relative_to(ROOT)))
        expression = meta.get('License-Expression') or meta.get('License')
        if expression and len(expression)>100:
            expression = 'Full license text in metadata/notices'
        entries.append({'name':meta['Name'], 'version':dist.version, 'requires_python':meta.get('Requires-Python'),
                        'requires_dist':meta.get_all('Requires-Dist', []), 'license':expression,
                        'license_classifiers':[c for c in meta.get_all('Classifier', []) if c.startswith('License ::')],
                        'license_files':licenses})
    info={'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
          'environment':'CPython3.12 Linux x86_64 (installed)', 'packages':entries,
          'lock_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('requirements-*.lock')},
          'windows_only_packages':[{'name':'colorama','version':'0.4.6','license':'BSD-3-Clause',
                                    'verification':'Windows hash-verified wheel; native execution not_run',
                                    'license_files':['third_party_licenses/colorama/LICENSE.txt']}]}
    (ROOT/'implementation_evidence/dependency_inventory.json').write_text(json.dumps(info,indent=2)+'\n')
    text=['# Third-party notices', '', 'Generated from installed Linux distribution metadata; upstream license texts are retained in `third_party_licenses/`.',
          'Windows-only Colorama notice is copied separately from its verified wheel. This is an inventory, not a legal opinion.', '',
          '| Package | Version | License metadata | Retained license files |', '|---|---|---|---|']
    for e in entries:
        license_text=e['license'] or '; '.join(e['license_classifiers']) or 'Not declared; inspect upstream'
        text.append(f"| {e['name']} | {e['version']} | {license_text.replace('|','/')} | {len(e['license_files'])} |")
    text.extend(['', 'Some dependencies use license choices (for example text-unidecode: Artistic/GPL); review the retained upstream terms before redistribution.',
                 'Dash AG Grid is configured with `enableEnterpriseModules=False`; no Enterprise feature or license entitlement is added.',
                 'Windows-only dependency: Colorama 0.4.6, BSD-3-Clause; retained `third_party_licenses/colorama/LICENSE.txt`.'])
    (ROOT/'THIRD_PARTY_NOTICES.md').write_text('\n'.join(text)+'\n')

if __name__ == '__main__':
    main()

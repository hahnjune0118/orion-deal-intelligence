# Dependency security review — Foundation

Reviewed 2026-11-03 (UTC). This is a bounded review of official project documentation and publisher/GitHub-reviewed advisories, separate from the machine-readable `pip-audit` result. A package not listed as affected in these sources is **not** a claim that it has no vulnerabilities. No product HTTP server, parser worker or browser was deployed for this review.

## Findings and decisions to carry forward

| Candidate | Evidence checked | Assessment / required follow-up |
|---|---|---|
| `playwright==1.55.0` | GHSA-7mvr-c777-76hp / CVE-2025-59288 lists npm Playwright `<1.55.1` as affected and `1.55.1` as patched; issue is browser installer `curl -k` on macOS. | Python wheels bundle a JavaScript driver; Python-only vulnerability scanning may miss its advisories. The dependency engineer confirmed `playwright/driver/package/bin/reinstall_chrome_stable_mac.sh` in the installed Python 1.55.0 wheel contains `curl ... -k` at line 7. The first attempted Python patch version, `1.55.1`, is unavailable: pip returned `No matching distribution` (failure log retained). Implementation pins therefore use Python `playwright==1.56.0`, the next available Python release beyond the patched Node version `1.55.1`; approved `spec/` pins remain unchanged. Official PyPI release existence was verified by the dependency engineer. The dependency engineer then verified the installed Python 1.56.0 wheel bundles driver 1.56.1 and the same installer script no longer contains `-k`. See installation/lock logs for the exact commands. No browser installation using affected scripts is authorized by this review. Windows/Ubuntu exposure differs from the described macOS path; do not exaggerate it into a demonstrated runtime Orion exploit. |
| `pypdf==6.21.4` | Publisher GHSA-5849-834g-hvw5, GHSA-cggf-277g-3q54 and GHSA-mfr5-77xh-9j7h identify fixes at 6.21.4; GHSA-42gh-23hr-vphw and GHSA-4vqv-7265-gm2w identify fixes at 6.21.3. | Candidate contains those published fixes. Retain pin unless the full lock audit finds a different applicable issue. Chunk 3 still needs worker timeout, input/expanded-size limits, and malformed-file tests. |
| `python-docx==1.2.0` | GHSA-34wj-p5jm-2p96 reports XXE in versions through 0.8.5, patched 0.8.6. | Candidate is outside that affected interval. This does not validate all XML/ZIP processing. Native extraction is not implemented in Chunk 1. |
| `openpyxl==3.1.5` | GHSA-chqf-hx79-gxc6 reports XXE through 2.4.1, patched 2.4.2. Project documentation separately warns about XML amplification attacks and recommends `defusedxml`. | Candidate is outside the cited XXE interval. Orion intends XLSX **writing** for exports, not arbitrary workbook ingestion. Do not add an untrusted XLSX reader without explicit hardening and tests. |
| `waitress==3.0.2` | Project changelog documents untrusted proxy-header handling fix in 3.0.2; busy-loop/request-smuggling fixes in 3.0.1. Its current page also lists further HTTP-validation changes under **4.0.0 unreleased**. | Preserve Local loopback and exact Host/Origin checks. The page does not establish that a released successor fixes all listed unreleased changes. Do not present 3.0.2 as a universal secure-server endorsement. |
| `gunicorn==23.0.0` | Publisher security-advisory index was retrieved and showed no published repository advisories. | An empty repository advisory index is insufficient to establish absence of known advisories elsewhere. Use the resolved-lock audit; UNIX only, not the Windows launcher. |
| `dash==3.2.0` | Official package release and publisher security-program pages were found; direct advisory-page retrieval was unavailable. | No exhaustive current clean-security determination from these pages. Keep candidate only with install/import tests plus lock audit; no public deployment is performed in Foundation. |
| `dash-ag-grid==32.3.2` | Publisher changelog identifies 32.3.2 as a React update-depth fix. Official docs state `dangerously_allow_code` defaults false and enabling raw JavaScript/HTML can permit XSS. Publisher repository distinguishes included Community/Enterprise features. | Never enable `dangerously_allow_code` for untrusted values; use Community features only. A bundled-JavaScript audit remains a release follow-up beyond Python package audit. No unsupported pin upgrade is made from search snippets. |
| `openai==1.109.1` | Publisher security policy/index retrieved; index showed no published repository advisories. | A clean index is not a credential boundary. Demo must not construct this adapter even when an environment key exists; live runtime, retention and budget integration remain later chunks. |
| `python-pptx==1.0.2` | Official documentation retrieved; publisher security-page fetch unavailable. | Security status cannot be inferred from feature documentation. Check full lock including `lxml` and Pillow; OOXML size/resource controls remain mandatory in Chunk 3. |

## Automated audit findings received during implementation

The initial Linux audit artifact (retained as `dependency-audit-linux-before-patches.json`) was read directly. It contains two affected Python packages:

| Installed candidate | Scanner finding | Patch decision |
|---|---|---|
| `pytest==8.4.2` | `PYSEC-2026-1845`, `GHSA-6w46-j5rx-g56g`, `CVE-2025-71176`: predictable UNIX temporary-directory handling can permit local interference or privilege impact; advisory affected interval is `<9.0.3`. | Pin `pytest==9.0.3`; resolve compatibility with the Playwright pytest plugin and rerun the full tests. |
| `python-dotenv==1.1.1` | `PYSEC-2026-2270`, `GHSA-mf9w-mj56-hr94`, `CVE-2026-28684`: `set_key`/`unset_key` cross-device rename fallback can follow a crafted symlink and overwrite a local file. | Pin `python-dotenv==1.2.2`, the publisher's documented patched release. Orion should not write `.env` files through untrusted paths in any case. |

The pytest publisher's 9.0.3 release and the dotenv publisher advisory were independently retrieved. The dotenv advisory's affected-version field and descriptive interval differ at 1.2.1, but both identify 1.2.2 as the patched version; 1.1.1 is affected under either interval. Updating pytest also requires a compatible `pytest-playwright` version; use the dependency engineer's resolver result as the final version record. Initial findings are retained; only a subsequent actual audit can establish whether the final resolved locks have no scanner findings.

## Source links

- [pytest temporary-directory advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g)
- [pytest 9.0.3 publisher release](https://docs.pytest.org/en/stable/announce/release-9.0.3.html)
- [python-dotenv publisher advisory](https://github.com/theskumar/python-dotenv/security/advisories/GHSA-mf9w-mj56-hr94)
- [Playwright installer advisory](https://github.com/advisories/GHSA-7mvr-c777-76hp)
- [Python Playwright 1.56.0 release](https://pypi.org/project/playwright/1.56.0/)
- [pypdf publisher advisories](https://github.com/py-pdf/pypdf/security/advisories)
- [pypdf xref trailer fix](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5)
- [pypdf page-tree fix](https://github.com/py-pdf/pypdf/security/advisories/GHSA-cggf-277g-3q54)
- [pypdf dictionary clone fix](https://github.com/py-pdf/pypdf/security/advisories/GHSA-mfr5-77xh-9j7h)
- [python-docx XXE advisory](https://github.com/advisories/GHSA-34wj-p5jm-2p96)
- [openpyxl XXE advisory](https://github.com/advisories/GHSA-chqf-hx79-gxc6)
- [openpyxl security documentation](https://openpyxl.readthedocs.io/en/stable/)
- [Waitress changelog](https://docs.pylonsproject.org/projects/waitress/en/latest/)
- [Gunicorn publisher advisory index](https://github.com/benoitc/gunicorn/security/advisories)
- [Dash 3.2.0 publisher release](https://pypi.org/project/dash/3.2.0/)
- [Plotly security program](https://plotly.com/chart-studio-help/security/)
- [Dash AG Grid reference](https://dash.plotly.com/dash-ag-grid/reference)
- [Dash AG Grid changelog](https://github.com/plotly/dash-ag-grid/blob/v35/CHANGELOG.md)
- [Dash AG Grid project](https://github.com/plotly/dash-ag-grid)
- [OpenAI Python publisher security policy](https://github.com/openai/openai-python/security)
- [python-pptx documentation](https://python-pptx.readthedocs.io/en/latest/)

## Review limitations

The dependency engineer's logs and audit JSON determine installed versions, advisory scanner success/failure, and any pin changes. The initial automated audit completed and its two findings are recorded above; this document does not claim a clean final audit result, Windows execution, browser rendering, or application security. Native wheels, vendored browser/JavaScript libraries and operating-system packages need their own review before public release. No package version or approved contract file was changed by this review.

Final dependency-engineer verification: both 63-package target locks were re-audited successfully with zero reported known vulnerabilities; see `DEPENDENCIES.md` and the final audit JSON files. This does not expand the security-review coverage stated above.

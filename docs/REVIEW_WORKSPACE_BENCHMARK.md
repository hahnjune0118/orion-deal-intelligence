# Orion document-centered review workspace

Reviewed: 2026-11-17. Public product documentation was consulted; no authenticated competitor account or private implementation was accessed.

## Public references

- Hebbia Product: https://www.hebbia.com/product — document/company matrix and traceability to findings.
- Hebbia April Disclosure: https://www.hebbia.com/blog/whats-new-april-disclosure-2026 — project context, organized work, and connected workflow views.
- Rogo Projects: https://rogo.com/platform/projects — project file tree, shared context, and financial-process stages.
- Rogo Agent Library: https://rogo.com/blog/agent-library — task-specific financial workflows and finished deliverables.

The implementation applies general workflow principles to Orion's own data and components. It does not reproduce competitor assets, templates, proprietary prompts, or backend capabilities.

## Implemented behavior

- The default route is **실사 작업 공간**. All prior analytical routes remain available.
- The left library groups existing fixture documents, searches filenames, and opens the selected document in the existing source inspector.
- The center shows the actual thesis and linked claims. Claims are not counted as separate investment theses.
- Question filters operate on existing canonical questions. KPI-first is a disclosed display-order rule; canonical ranks and scores remain unchanged.
- List, Matrix-style, and checklist presentations share the same selection and source records. The Matrix view is a compact question review view, not an AI execution grid.
- Draft issue text and requested artifacts can be edited. The original question and verification requirements remain inspectable.
- Individual and batch draft reviews, exclusion marks, notes, and sequenced edit history are supported. Saving an edit clears the previous draft review approval. Unsaved edits must be saved before approving the affected selection.
- Draft CSV exports preserve both original and edited question text, canonical scores, draft review status, source references, and snapshot ID. Reviewed CSV requires every selected question to be marked approved in the draft review layer.
- Reference memos and signed draft state persist while navigating this tab. Refresh, deal switch, reset, or evidence updates begin a new draft context. Export before leaving if needed.

## Boundaries

The review layer is independent of canonical question/evidence approval and official report approval. Browser-provided IDs are checked against the trusted current workspace. Draft tokens are signed, session-bound, and bound to the original workspace token and snapshot. This does not provide user authentication or permanent project storage.

No upload endpoint, model provider, key setup, live AI call, automatic generation, paid service, or public deployment was added. The disabled AI generation control explicitly describes this pending connection. Summaries count existing demo data and do not claim model-generated analysis.

## Validation

Run the existing web and smoke tests plus the new draft and studio browser checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/web tests/smoke -q --strict-markers -p no:cacheprovider
```

The studio browser check covers source search and selection, editing, review gating, original-value preservation, CSV download, view switching, empty search, memos, deal isolation, and 390/720/1024/1440-pixel layouts. Unit checks cover signature tampering, cross-session/workspace rejection, atomic batch validation, edit invalidation, CSV formula escaping, and memo limits. Fixture functional checks do not measure actual LLM quality or enterprise security certification.

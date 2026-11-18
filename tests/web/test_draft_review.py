from copy import deepcopy
import csv
import io

import pytest

from orion.services.draft_review import DraftReview, DraftReviewError


@pytest.fixture
def view():
    return {"snapshot_id": "snapshot-1", "claims": [{"id": "c1", "source_refs": "file.docx · paragraph 1"}],
            "questions": [{"id": "q1", "claim_id": "c1", "rank": 1, "score": 100, "issue": "Original question", "request_text": "Signed contract"}]}


def test_signed_drafts_are_session_workspace_bound_and_tamper_evident(view):
    service = DraftReview("test-secret-long-enough")
    state = service.read(None, "workspace-1", "session-1", view)
    token = service.sign(state)
    assert service.read(token, "workspace-1", "session-1", view) == state
    for bad, workspace, sid in [(token[:-1] + "x", "workspace-1", "session-1"), (token, "workspace-2", "session-1"), (token, "workspace-1", "session-2")]:
        with pytest.raises(DraftReviewError):
            service.read(bad, workspace, sid, view)


def test_edit_invalidates_review_preserves_canonical_and_exports_source(view):
    original = deepcopy(view)
    service = DraftReview("test-secret-long-enough")
    draft = service.read(None, "workspace-1", "session-1", view)
    draft = service.update(draft, view, action="approve", question_id="q1")
    draft = service.update(draft, view, action="edit", question_id="q1", issue="=unsafe formula", request_text="Edited artifact")
    assert "q1" not in draft["decisions"]
    with pytest.raises(DraftReviewError):
        service.export(draft, view, ["q1"], reviewed_only=True)
    draft = service.update(draft, view, action="approve_selected", selected=["q1"], note="Reviewed")
    draft = service.update(draft, view, action="memo", memo="Reference memo preserved")
    content = service.export(draft, view, ["q1"], reviewed_only=True)
    row = list(csv.reader(io.StringIO(content.lstrip("\ufeff"))))[1]
    assert row[3] == "Original question"
    assert row[4] == "'=unsafe formula"
    assert row[8] == "file.docx · paragraph 1"
    assert row[-1] == "Reference memo preserved"
    assert view == original
    with pytest.raises(DraftReviewError):
        service.update(draft, view, action="approve_selected", selected=["other-deal-question"])
    with pytest.raises(DraftReviewError):
        service.export(draft, view, ["other-deal-question"])


def test_batch_review_is_atomic_and_memo_bounded(view):
    service = DraftReview("test-secret-long-enough")
    draft = service.read(None, "workspace-1", "session-1", view)
    before = deepcopy(draft)
    with pytest.raises(DraftReviewError):
        service.update(draft, view, action="approve_selected", selected=["q1", "missing"])
    assert draft == before
    with pytest.raises(DraftReviewError):
        service.update(draft, view, action="memo", memo="x" * 4001)

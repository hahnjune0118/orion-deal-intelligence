"""Signed presentation drafts; never mutate canonical DD questions or scores."""
from __future__ import annotations

import base64
from copy import deepcopy
import csv
import hashlib
import hmac
import io
import json


class DraftReviewError(ValueError):
    pass


class DraftReview:
    def __init__(self, secret):
        self.key = secret.encode() if isinstance(secret, str) else secret

    def _binding(self, workspace_token, session_id):
        return hmac.new(self.key, (workspace_token + "|" + session_id).encode(), hashlib.sha256).hexdigest()

    def read(self, token, workspace_token, session_id, view):
        binding = self._binding(workspace_token, session_id)
        if not token:
            return {"binding": binding, "snapshot": view["snapshot_id"], "edits": {}, "decisions": {}, "history": [], "memo": ""}
        try:
            if not isinstance(token, str) or len(token) > 300_000:
                raise ValueError()
            body, signature = token.rsplit(".", 1)
            expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            state = json.loads(base64.urlsafe_b64decode(body))
            if state["binding"] != binding or state["snapshot"] != view["snapshot_id"]:
                raise ValueError()
            return state
        except Exception:
            raise DraftReviewError("검토 초안이 현재 작업 영역과 일치하지 않습니다. 다시 선택해 주세요.") from None

    def sign(self, state):
        body = base64.urlsafe_b64encode(json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode()).decode()
        if len(body) > 299_935:
            raise DraftReviewError("초안 크기 한도에 도달했습니다. CSV를 저장한 뒤 데모를 초기화하세요.")
        return body + "." + hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()

    def update(self, state, view, *, action, question_id=None, issue="", request_text="", note="", memo="", selected=()):
        state = deepcopy(state)
        questions = {q["id"]: q for q in view["questions"]}
        if action not in {"edit", "approve", "reject", "memo", "approve_selected"}:
            raise DraftReviewError("지원하지 않는 검토 작업입니다.")
        if len(state["history"]) >= 100:
            raise DraftReviewError("이 데모의 검토 이력 한도에 도달했습니다. CSV를 저장한 뒤 데모를 초기화하세요.")
        ids = list(dict.fromkeys(selected)) if action == "approve_selected" else ([question_id] if action != "memo" else [])
        if action != "memo" and (not ids or any(identifier not in questions for identifier in ids)):
            raise DraftReviewError("현재 투자 건의 질문을 선택하세요.")
        if action == "edit":
            if not isinstance(issue, str) or not isinstance(request_text, str) or not issue.strip() or not request_text.strip() or len(issue) > 1000 or len(request_text) > 6000:
                raise DraftReviewError("질문은 1~1,000자, 요청 자료는 1~6,000자로 입력하세요.")
            before_edit = deepcopy(state["edits"].get(question_id, {"issue": questions[question_id]["issue"], "request_text": questions[question_id]["request_text"]}))
            state["edits"][question_id] = {"issue": issue.strip(), "request_text": request_text.strip()}
            state["decisions"].pop(question_id, None)
        elif action == "memo":
            if not isinstance(memo, str) or len(memo) > 4000:
                raise DraftReviewError("참고 메모는 4,000자까지 입력할 수 있습니다.")
            state["memo"] = memo
        else:
            if not isinstance(note, str) or len(note) > 2000:
                raise DraftReviewError("검토 의견은 2,000자까지 입력할 수 있습니다.")
            for identifier in ids:
                state["decisions"][identifier] = {"status": "approved" if action in {"approve", "approve_selected"} else "rejected", "note": note.strip()}
        state["history"].append({"sequence": len(state["history"]) + 1, "action": action, "question_ids": ids,
                                 "note": note[:2000] if isinstance(note, str) else ""})
        if action == "edit":
            state["history"][-1].update(before=before_edit, after=deepcopy(state["edits"][question_id]))
        return state

    def export(self, state, view, selected, *, reviewed_only=False):
        ids = set(selected)
        rows = [q for q in view["questions"] if q["id"] in ids]
        if not rows or len(rows) != len(ids):
            raise DraftReviewError("현재 투자 건에서 내보낼 질문을 선택하세요.")
        if reviewed_only and any(state["decisions"].get(q["id"], {}).get("status") != "approved" for q in rows):
            raise DraftReviewError("선택한 모든 질문을 검토 완료로 표시한 뒤 내보내세요.")
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["question_id", "canonical_rank", "canonical_score", "original_question", "draft_question", "draft_requested_artifact", "draft_review_status", "review_note", "source_references", "snapshot_id", "notice", "reference_memo"])
        def safe(value):
            value = str(value if value is not None else "")
            return "'" + value if value.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
        claims = {c["id"]: c for c in view["claims"]}
        for q in rows:
            edit = state["edits"].get(q["id"], {})
            decision = state["decisions"].get(q["id"], {})
            writer.writerow([safe(value) for value in [q["id"], q["rank"], q["score"], q["issue"], edit.get("issue", q["issue"]),
                edit.get("request_text", q["request_text"]), decision.get("status", "draft"), decision.get("note", ""),
                claims.get(q["claim_id"], {}).get("source_refs", ""), view["snapshot_id"],
                "합성 자료의 사용자 검토 초안. AI 생성·공식 질문 수정·투자 승인·원문 독립 검증이 아닙니다.", state["memo"]]])
        return "\ufeff" + stream.getvalue()

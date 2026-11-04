"""HTTP regressions for consent racing with a new token or document format."""
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def endpoint():
    from orion.app import create_app
    app = create_app(project_root=ROOT, secret_key="consent-test-only-key-with-32-bytes")
    client = app.server.test_client()
    client.get("/")
    with client.session_transaction() as session:
        sid = session["orion_session"]
    workspace = app.server.extensions["orion_workspace"]
    workspace.new("nb", sid)  # Validate and cache the actual native source pack once.
    return app, client, workspace, sid


def post_callback(endpoint, output_name, values, changed):
    app, client, _, _ = endpoint
    key = next(key for key in app.callback_map if output_name in key)
    callback = app.callback_map[key]
    outputs = callback["output"]
    payload = {
        "output": key,
        "outputs": [{"id": item.component_id, "property": item.component_property} for item in outputs],
        "inputs": [{**item, "value": values[f"{item['id']}.{item['property']}"]} for item in callback["inputs"]],
        "state": [{**item, "value": values[f"{item['id']}.{item['property']}"]} for item in callback["state"]],
        "changedPropIds": [changed],
    }
    result = client.post("/_dash-update-component", json=payload, headers={"Origin": "http://localhost"})
    assert result.status_code == 200, result.data.decode()
    return result.get_json()["response"]


def consent(endpoint, token, *, rendered_token=None, displayed_state=None,
            format_name="dd_csv", changed="export-confirm.value"):
    _, _, workspace, sid = endpoint
    state = displayed_state or workspace.validated_state(token, sid)[0]
    return post_callback(endpoint, "export-approval.data", {
        "export-confirm.value": ["approved"], "workspace-token.data": token,
        "export-format.value": format_name, "workspace-revision.data": state.state_revision,
        "workspace-snapshot.data": state.head_snapshot_id,
        "rendered-workspace-token.data": rendered_token or token,
    }, changed)


def download(endpoint, token, approval, format_name="dd_csv"):
    return post_callback(endpoint, "export-download.data", {
        "export-button.n_clicks": 1, "export-confirm.value": ["approved"],
        "export-format.value": format_name, "workspace-token.data": token,
        "export-approval.data": approval,
    }, "export-button.n_clicks")


def test_displayed_snapshot_consent_produces_real_download(endpoint):
    _, _, workspace, sid = endpoint
    token = workspace.new("nb", sid)
    approval = consent(endpoint, token)["export-approval"]["data"]
    assert approval["workspace_token"] == token
    result = download(endpoint, token, approval)
    assert result["export-download"]["data"]["filename"] == "deal_nb_dd_csv_r1.csv"
    assert result["export-download"]["data"]["content"]


@pytest.mark.parametrize("action", ["approve", "reject", "reset"])
def test_old_screen_and_checked_box_cannot_approve_new_branch(endpoint, action):
    _, _, workspace, sid = endpoint
    token = workspace.new("nb", sid)
    before = workspace.validated_state(token, sid)[0]
    approval = consent(endpoint, token)["export-approval"]["data"]
    if action == "reset":
        current = workspace.new("nb", sid)
    else:
        current = workspace.act(token, sid, action, "nb_update_t1", 1,
                                f"consent-{action}", "Checked synthetic source.")["token"]
    result = consent(endpoint, current, rendered_token=token, displayed_state=before)
    assert result["export-approval"]["data"] is None
    assert "still updating" in result["export-approval-status"]["children"]
    assert "export-download" not in download(endpoint, current, approval)


def test_format_change_invalidates_checked_consent_and_old_receipt(endpoint):
    _, _, workspace, sid = endpoint
    token = workspace.new("nb", sid)
    approval = consent(endpoint, token)["export-approval"]["data"]
    result = consent(endpoint, token, format_name="memo_md", changed="export-format.value")
    assert result["export-approval"]["data"] is None
    assert "export-download" not in download(endpoint, token, approval, "memo_md")


def test_client_cannot_relabel_old_signed_receipt_for_changed_state(endpoint):
    _, _, workspace, sid = endpoint
    token = workspace.new("nb", sid)
    approval = consent(endpoint, token)["export-approval"]["data"]
    current = workspace.act(token, sid, "reject", "nb_update_t1", 1,
                            "consent-receipt-reject", "Source rejected in this branch.")["token"]
    # Rejection keeps the revision and snapshot, but changes the signed state/audit.
    relabeled = {**approval, "workspace_token": current}
    result = download(endpoint, current, relabeled)
    assert "export-download" not in result
    assert "EXPORT_APPROVAL_STALE" in result["export-status"]["children"]

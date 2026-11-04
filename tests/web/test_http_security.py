"""HTTP boundaries are exercised through the real Flask/Dash client."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.security
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def app():
    from orion.app import create_app
    return create_app(project_root=ROOT, secret_key="http-test-only-secret-32-characters")


def test_actual_app_serves_layout_dependencies_and_local_assets(app):
    client = app.server.test_client()
    for path in ("/", "/_dash-layout", "/_dash-dependencies"):
        response = client.get(path)
        assert response.status_code == 200
    layout = client.get("/_dash-layout").data
    assert b"workspace-token" in layout
    assert b"dash_ag_grid" in layout or b"page-content" in layout
    assert b"Upload" not in layout
    assert b"api_key" not in layout.lower()
    css = client.get("/assets/orion.css")
    assert css.status_code == 200 and b"text/css" in css.content_type.encode()


@pytest.mark.parametrize("origin", [None, "https://evil.invalid", "http://localhost.evil.invalid"])
def test_state_changing_request_rejects_missing_or_foreign_origin(app, origin):
    client = app.server.test_client()
    client.get("/")
    headers = {} if origin is None else {"Origin": origin}
    result = client.post("/_dash-update-component", json={}, headers=headers)
    assert result.status_code == 403


def test_demo_rejects_unknown_download_and_filesystem_routes(app):
    client = app.server.test_client()
    # Dash fallback may return its generic HTML shell; it must never return file bytes.
    for path in ("/download?path=../../pyproject.toml", "/assets/../../pyproject.toml", "/src/orion/config.py", "/.env"):
        response = client.get(path)
        assert b"[build-system]" not in response.data
        assert b"class Settings" not in response.data
        assert b"OPENAI_API_KEY=" not in response.data
    response = client.post("/upload", data={"file": "confidential"}, headers={"Origin": "http://localhost"})
    assert response.status_code in {400, 404, 405}


def test_live_mode_is_not_silently_enabled():
    from orion.app import create_app
    from orion.config import Settings
    with pytest.raises((ValueError, RuntimeError)):
        create_app(project_root=ROOT, settings=Settings(mode="local_live"), secret_key="test-only-secret")

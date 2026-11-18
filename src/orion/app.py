"""Start the rules MVP; ``--legacy`` opens the preserved synthetic workbench."""
from __future__ import annotations

from pathlib import Path
import secrets

from dash import Dash
from flask import abort, request, session

from orion.config import BoundaryError, Settings
from orion.services.export import ExportService
from orion.services.web_workspace import WebWorkspace
from orion.web.callbacks import register_callbacks
from orion.web.layout import layout


def create_app(project_root=None, settings=None, secret_key=None):
    """Create an isolated Dash/Flask app; no provider or visitor database exists.

    The server session cookie supplies an opaque nonce. Authoritative data is
    reconstructed only from a service-signed per-tab log bound to that nonce.
    Canonical evidence, scores and filesystem paths are never accepted from the
    browser. The separate FDD draft boundary accepts validated financial entries
    as unverified user inputs; they never become canonical evidence implicitly.
    """
    settings = settings or Settings.from_env()
    if settings.mode != "demo":
        raise BoundaryError("FEATURE_NOT_IMPLEMENTED", "The web workbench currently supports synthetic Demo only; Local Live remains disabled.")
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    key = secret_key or secrets.token_hex(32)
    workspace = WebWorkspace(root, key)
    exports = ExportService(key)
    application = Dash(__name__, assets_folder=str(Path(__file__).parent / "web" / "assets"),
                       title="Orion · FDD 작업 공간", update_title="검토 중…",
                       suppress_callback_exceptions=True, external_scripts=[], external_stylesheets=[])
    application.index_string = application.index_string.replace("<html>", '<html lang="ko">')
    server = application.server
    server.secret_key = key
    server.config.update(MAX_CONTENT_LENGTH=1024 * 1024, SESSION_COOKIE_HTTPONLY=True,
                         SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=False)
    server.extensions["orion_workspace"] = workspace
    server.extensions["orion_exports"] = exports

    @server.before_request
    def enforce_boundary():
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin != request.host_url.rstrip("/"):
                abort(403)
        if "orion_session" not in session:
            session["orion_session"] = secrets.token_urlsafe(32)

    @server.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if not request.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @server.get("/healthz")
    def health():
        return {"status": "ok", "mode": "demo", "live_provider": False}

    application.layout = layout
    register_callbacks(application, workspace, exports)
    return application


# WSGI imports remain lazy so importing the factory does not create a second app.
def __getattr__(name):
    if name in {"app", "server"}:
        global _default_app
        if "_default_app" not in globals():
            _default_app = create_app()
        return _default_app if name == "app" else _default_app.server
    raise AttributeError(name)


def main():
    import argparse
    import os
    parser = argparse.ArgumentParser(description='Orion local rule-based adaptive DD MVP')
    parser.add_argument('--legacy', action='store_true', help='Open the preserved eight-stage synthetic FDD workbench')
    parser.add_argument('--port', type=int, default=None)
    args = parser.parse_args()
    settings = Settings.from_env()
    port = settings.port if args.port is None else args.port
    if not 1 <= port <= 65535:
        parser.error('port must be 1..65535')
    if args.legacy:
        application = create_app(settings=settings)
        application.run(host=settings.bind_host, port=port, debug=False)
    else:
        from orion.web.rules_app import create_rules_app
        application = create_rules_app(data_dir=os.environ.get('ORION_RULES_DATA_DIR'), port=port)
        application.run(host='127.0.0.1', port=port, debug=False)


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api import routes
from app.api.request_authority import GUEST_COOKIE_NAME
from app.db import make_engine
from app import models


def test_google_start_route_exists():
    assert callable(routes.google_login_start)


def _app(monkeypatch, settings):
    engine = make_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.session_factory = lambda: Session(engine)
    app.state.authority_session_factory = lambda: Session(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.dependency_overrides[routes.get_request_authority] = lambda: SimpleNamespace(
        mode="guest", user_id=None, workspace_id=1
    )
    app.include_router(routes.private_router)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    return app, engine


def test_google_start_returns_nonce_and_secure_state_cookie(monkeypatch):
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    settings = SimpleNamespace(google=SimpleNamespace(web_client_id="web-client"))
    app, engine = _app(monkeypatch, settings)
    monkeypatch.setattr(
        routes.login_transactions,
        "issue",
        lambda session, *, clock: SimpleNamespace(
            state=SecretStr("s" * 43),
            nonce=SecretStr("n" * 43),
            expires_at=now,
        ),
    )
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            client.cookies.set("__Host-fadir-csrf", csrf)
            result = client.post(
                "/api/auth/google/start",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={GUEST_COOKIE_NAME: "g" * 43},
            )
        assert result.status_code == 200
        assert result.json() == {
            "client_id": "web-client",
            "nonce": "n" * 43,
            "expires_at": now.isoformat().replace("+00:00", "Z"),
        }
        set_cookie = result.headers.get("set-cookie", "")
        assert "__Host-fadir-google-state=" in set_cookie
        assert "HttpOnly" in set_cookie and "Secure" in set_cookie
        assert "Max-Age=600" in set_cookie and "Path=/" in set_cookie
        assert "SameSite=lax" in set_cookie and "Domain=" not in set_cookie
        assert "s" * 43 not in result.text
    finally:
        engine.dispose()


def test_missing_client_config_fails_without_state_cookie(monkeypatch):
    settings = SimpleNamespace(google=SimpleNamespace(web_client_id=None))
    app, engine = _app(monkeypatch, settings)
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            result = client.post(
                "/api/auth/google/start",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={"__Host-fadir-csrf": csrf},
            )
        assert result.status_code == 503
        assert "set-cookie" not in result.headers
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.invalid", "X-CSRF-Token": "c" * 43},
        {"Origin": "https://ratatosk.dev", "X-CSRF-Token": "wrong"},
    ],
)
def test_invalid_origin_or_csrf_fails_without_state_cookie(monkeypatch, headers):
    settings = SimpleNamespace(google=SimpleNamespace(web_client_id="web-client"))
    app, engine = _app(monkeypatch, settings)
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            result = client.post(
                "/api/auth/google/start",
                headers=headers,
                cookies={"__Host-fadir-csrf": "c" * 43},
            )
        assert result.status_code == 403
        assert "set-cookie" not in result.headers
    finally:
        engine.dispose()


def test_commit_failure_rolls_back_without_state_cookie(monkeypatch, tmp_path):
    settings = SimpleNamespace(google=SimpleNamespace(web_client_id="web-client"))
    engine = make_engine(tmp_path / "commit-failure.db")
    models.Base.metadata.create_all(engine)
    roots = []

    class FailingRoot:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.rolled_back = False

        @property
        def is_active(self):
            return self.wrapped.is_active

        def commit(self):
            raise RuntimeError("synthetic commit failure")

        def rollback(self):
            self.rolled_back = True
            self.wrapped.rollback()

    class CommitFailSession(Session):
        def begin(self, *args, **kwargs):
            root = FailingRoot(super().begin(*args, **kwargs))
            roots.append(root)
            return root

    monkeypatch.setattr(
        routes.login_transactions,
        "issue",
        lambda session, *, clock: SimpleNamespace(
            state=SecretStr("s" * 43),
            nonce=SecretStr("n" * 43),
            expires_at=datetime.now(timezone.utc),
        ),
    )
    app = FastAPI()
    app.state.session_factory = lambda: CommitFailSession(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.dependency_overrides[routes.get_request_authority] = lambda: SimpleNamespace(
        mode="guest", user_id=None, workspace_id=1
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    app.include_router(routes.private_router)
    with TestClient(app, base_url="https://ratatosk.dev") as client:
        csrf = "c" * 43
        result = client.post(
            "/api/auth/google/start",
            headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
            cookies={"__Host-fadir-csrf": csrf},
        )
    assert result.status_code == 500
    assert "set-cookie" not in result.headers
    assert roots and roots[0].rolled_back is True
    engine.dispose()

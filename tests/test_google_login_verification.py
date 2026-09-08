from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models
from app.api import routes
from app.db import make_engine
from app.services.google_identity import VerifiedGoogleIdentity


def test_google_verify_route_and_pending_identity_surface_exist():
    from app.api import routes
    from app import models
    from app.services import login_transactions

    assert callable(routes.google_login_verify)
    assert hasattr(models.LoginTransaction, "verified_issuer")
    assert hasattr(models.LoginTransaction, "verified_subject")
    assert hasattr(models.LoginTransaction, "verified_at")
    assert callable(login_transactions.verify_pending)
    assert callable(login_transactions.consume_verified)


def _app(monkeypatch, settings):
    engine = make_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.session_factory = lambda: Session(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.dependency_overrides[routes.get_request_authority] = lambda: SimpleNamespace(
        mode="guest", user_id=None, workspace_id=1
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    app.include_router(routes.private_router)
    return app, engine


def test_registered_verify_stages_identity_without_leaking_claims(monkeypatch):
    settings = SimpleNamespace(google=SimpleNamespace(web_client_id="web-client"))
    app, engine = _app(monkeypatch, settings)
    calls = []
    expires = datetime(2026, 9, 8, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        routes,
        "verify_google_identity_from_settings",
        lambda credential, **kwargs: (calls.append("verify") or VerifiedGoogleIdentity(
            issuer="https://accounts.google.com", subject="opaque-subject"
        )),
    )
    monkeypatch.setattr(
        routes.login_transactions,
        "verify_pending",
        lambda *args, **kwargs: (
            calls.append("persist")
            or SimpleNamespace(expires_at=expires)
        ),
    )
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            result = client.post(
                "/api/auth/google/verify",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={
                    "__Host-fadir-csrf": csrf,
                    routes.GOOGLE_STATE_COOKIE_NAME: "s" * 43,
                },
                json={"credential": "raw-token", "nonce": "n" * 43},
            )
        assert result.status_code == 200
        assert result.json() == {
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "choice_needed": True,
        }
        assert calls == ["verify", "persist"]
        assert "opaque-subject" not in result.text
        assert "raw-token" not in result.text
        assert routes.GOOGLE_STATE_COOKIE_NAME not in result.headers
    finally:
        engine.dispose()


def test_verify_missing_state_or_identity_fails_generically(monkeypatch):
    settings = SimpleNamespace(google=SimpleNamespace(web_client_id="web-client"))
    app, engine = _app(monkeypatch, settings)
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            result = client.post(
                "/api/auth/google/verify",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={"__Host-fadir-csrf": csrf},
                json={"credential": "raw-token", "nonce": "n" * 43},
            )
        assert result.status_code == 401
        assert result.json() == {"detail": "request rejected"}
        assert "raw-token" not in result.text
    finally:
        engine.dispose()


def test_verify_identity_failure_is_generic(monkeypatch):
    from app.services.google_identity import GoogleIdentityError

    settings = SimpleNamespace(google=SimpleNamespace(web_client_id="web-client"))
    app, engine = _app(monkeypatch, settings)
    def fail_verification(*args, **kwargs):
        raise GoogleIdentityError()

    monkeypatch.setattr(routes, "verify_google_identity_from_settings", fail_verification)
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            result = client.post(
                "/api/auth/google/verify",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={
                    "__Host-fadir-csrf": csrf,
                    routes.GOOGLE_STATE_COOKIE_NAME: "s" * 43,
                },
                json={"credential": "raw-token", "nonce": "n" * 43},
            )
        assert result.status_code == 401
        assert result.json() == {"detail": "request rejected"}
        assert "Google identity verification failed" not in result.text
        assert "raw-token" not in result.text
    finally:
        engine.dispose()

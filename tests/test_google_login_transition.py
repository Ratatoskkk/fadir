from __future__ import annotations

from types import SimpleNamespace
import secrets

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest
from sqlalchemy.orm import Session

from app import models
from app.api import routes
from app.db import make_engine
from app.services.google_login_transition import GoogleLoginTransitionResult


def test_google_transition_surface_exists():
    from app.services import google_login_transition

    assert callable(routes.google_login_transition)
    assert callable(google_login_transition.transition)


def test_transition_route_sets_only_secure_session_cookies(monkeypatch):
    engine = make_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.session_factory = lambda: Session(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.dependency_overrides[routes.get_request_authority] = lambda: SimpleNamespace(
        mode="guest", workspace_id=1
    )
    public_id = secrets.token_urlsafe(16)
    session_secret = secrets.token_urlsafe(32)
    monkeypatch.setattr(
        routes.google_login_transition_service,
        "transition",
        lambda *args, **kwargs: GoogleLoginTransitionResult(
            action="claim", public_id=public_id, secret=SecretStr(session_secret)
        ),
    )
    app.include_router(routes.private_router)
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            result = client.post(
                "/api/auth/google/transition",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={
                    "__Host-fadir-csrf": csrf,
                    routes.GOOGLE_STATE_COOKIE_NAME: "t" * 43,
                    routes.GUEST_COOKIE_NAME: "g" * 43,
                },
                json={"action": "claim"},
            )
        assert result.status_code == 200
        assert result.json() == {"action": "claim"}
        cookie = result.headers.get("set-cookie", "")
        assert "__Host-fadir-user=" in cookie
        assert '__Host-fadir-guest=""' in cookie
        assert "HttpOnly" in cookie and "Secure" in cookie and "Path=/" in cookie
        assert "Domain=" not in cookie
        assert session_secret not in result.text
    finally:
        engine.dispose()


def test_transition_payload_rejects_raw_identity_claims():
    from app.schemas import GoogleLoginTransitionIn

    with pytest.raises(ValueError):
        GoogleLoginTransitionIn(action="claim", subject="raw-subject")

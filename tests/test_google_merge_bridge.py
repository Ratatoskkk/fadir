from app.schemas import GoogleLoginTransitionIn, GoogleLoginTransitionOut
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session
import secrets

from app import models
from app.api import routes
from app.api.request_authority import RequestAuthority, get_request_authority
from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.services.google_login_transition import GoogleLoginTransitionResult


def test_google_transition_accepts_merge_action():
    assert GoogleLoginTransitionIn(action="merge").action == "merge"
    assert GoogleLoginTransitionOut(action="merge").action == "merge"


def test_merge_route_retains_guest_cookie(monkeypatch):
    from app.db import make_engine

    engine = make_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.session_factory = lambda: Session(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(
        mode="guest", user_id=None, workspace_id=1
    )
    public_id = secrets.token_urlsafe(16)
    secret = secrets.token_urlsafe(32)
    monkeypatch.setattr(
        routes.google_login_transition_service,
        "transition",
        lambda *args, **kwargs: GoogleLoginTransitionResult(
            action="merge", public_id=public_id, secret=SecretStr(secret)
        ),
    )
    app.include_router(routes.private_router)
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = "c" * 43
            result = client.post(
                "/api/auth/google/transition",
                headers={"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: csrf},
                cookies={
                    CSRF_COOKIE_NAME: csrf,
                    routes.GOOGLE_STATE_COOKIE_NAME: "t" * 43,
                    routes.GUEST_COOKIE_NAME: "g" * 43,
                },
                json={"action": "merge"},
            )
        assert result.status_code == 200
        assert result.json() == {"action": "merge"}
        cookie = result.headers.get("set-cookie", "")
        assert "__Host-fadir-user=" in cookie
        assert '__Host-fadir-guest="' not in cookie
    finally:
        engine.dispose()

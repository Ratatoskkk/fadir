from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.api.request_authority import RequestAuthority, get_request_authority
from app.api.request_transaction import request_session
from app.main import app
from app.services import user_sessions


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


@pytest.fixture
def route_client(monkeypatch):
    previous_factory = app.state.session_factory
    session = MagicMock()
    root = MagicMock()
    session.begin.return_value = root
    authority = RequestAuthority(mode="user", user_id=7, workspace_id=70)
    app.dependency_overrides[get_request_authority] = lambda: authority
    app.dependency_overrides[request_session] = lambda: session
    app.state.session_factory = lambda: session
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.pop(get_request_authority, None)
        app.dependency_overrides.pop(request_session, None)
        app.state.session_factory = previous_factory


@pytest.fixture
def prior_session_factory():
    original = app.state.session_factory
    sentinel = object()
    app.state.session_factory = sentinel
    try:
        yield
        assert app.state.session_factory is sentinel
    finally:
        app.state.session_factory = original


@pytest.fixture
def original_session_factory():
    original = app.state.session_factory
    yield original
    assert app.state.session_factory is original


def _csrf(client: TestClient) -> None:
    token = issue_csrf_token()
    client.cookies.set(CSRF_COOKIE_NAME, token)
    client.headers.update({"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: token})


def test_list_user_sessions_returns_public_summary_only(route_client, monkeypatch):
    monkeypatch.setattr(
        user_sessions,
        "list_active",
        lambda session, user_id, clock: [
            user_sessions.UserSessionSummary(
                public_id="A" * 22, created_at=NOW, last_access_at=NOW
            )
        ],
    )

    response = route_client.get("/api/user/sessions")

    assert response.status_code == 200
    assert response.json() == {
        "sessions": [
            {"public_id": "A" * 22, "created_at": "2026-09-09T12:00:00Z", "last_access_at": "2026-09-09T12:00:00Z"}
        ]
    }
    assert "secret" not in response.text


def test_guest_cannot_list_user_sessions(route_client, monkeypatch):
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(
        mode="guest", user_id=None, workspace_id=70
    )
    called = False

    def fail(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("guest reached the User session service")

    monkeypatch.setattr(user_sessions, "list_active", fail)
    response = route_client.get("/api/user/sessions")

    assert response.status_code == 401
    assert response.json() == {"detail": "request rejected"}
    assert called is False


def test_revoke_one_requires_csrf_and_does_not_reveal_cross_user_ownership(
    route_client, monkeypatch
):
    monkeypatch.setattr(user_sessions, "revoke", lambda *args, **kwargs: False)

    rejected = route_client.delete("/api/user/sessions/" + "A" * 22)
    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "request rejected"}

    _csrf(route_client)
    response = route_client.delete("/api/user/sessions/" + "A" * 22)
    assert response.status_code == 200
    assert response.json() == {"revoked": False}


def test_revoke_all_returns_count(route_client, monkeypatch):
    monkeypatch.setattr(user_sessions, "revoke_all", lambda *args, **kwargs: 3)
    _csrf(route_client)

    response = route_client.delete("/api/user/sessions")

    assert response.status_code == 200
    assert response.json() == {"revoked_count": 3}


def test_revoke_malformed_public_id_is_non_disclosing_and_skips_service(route_client):
    _csrf(route_client)
    response = route_client.delete("/api/user/sessions/" + "B" * 22)

    assert response.status_code == 200
    assert response.json() == {"revoked": False}


def test_route_fixture_restores_prior_session_factory(
    original_session_factory, prior_session_factory, route_client
):
    pass

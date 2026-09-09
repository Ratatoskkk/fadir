"""Guarded PostgreSQL HTTP proof for User session-management routes."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.api.request_authority import RequestAuthority, get_request_authority
from app.models import User, Workspace
from app.services import user_sessions
from test_postgresql_user_sessions import database


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


@pytest.fixture
def prior_session_factory():
    from app.main import app

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
    from app.main import app

    original = app.state.session_factory
    yield original
    assert app.state.session_factory is original


@pytest.mark.live
def test_postgresql_user_session_routes(database, monkeypatch) -> None:
    if os.environ.get("FADIR_RUN_POSTGRESQL_USER_SESSION_ROUTES") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_USER_SESSION_ROUTES=1 for approved live proof")
    with Session(database) as session, session.begin():
        user = User(workspace=Workspace())
        session.add(user)
        session.flush()
        first = user_sessions.issue(session, user.id, clock=lambda: NOW)
        second = user_sessions.issue(session, user.id, clock=lambda: NOW)
        user_id = user.id
        workspace_id = user.workspace.id

    from app.main import app

    authority = RequestAuthority(
        mode="user",
        user_id=user_id,
        workspace_id=workspace_id,
        session_public_id=first.public_id,
    )
    previous_factory = app.state.session_factory
    app.dependency_overrides[get_request_authority] = lambda: authority
    app.state.session_factory = lambda: Session(database)
    client = TestClient(app)
    try:
        listed = client.get("/api/user/sessions")
        assert listed.status_code == 200
        assert {row["public_id"] for row in listed.json()["sessions"]} == {
            first.public_id,
            second.public_id,
        }
        assert all(set(row) == {"public_id", "created_at", "last_access_at"} for row in listed.json()["sessions"])

        token = issue_csrf_token()
        client.cookies.set(CSRF_COOKIE_NAME, token)
        client.headers.update({"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: token})
        revoked = client.delete(f"/api/user/sessions/{first.public_id}")
        assert revoked.status_code == 200
        assert revoked.json() == {"revoked": True}

        all_revoked = client.delete("/api/user/sessions")
        assert all_revoked.status_code == 200
        assert all_revoked.json() == {"revoked_count": 1}
    finally:
        client.close()
        app.dependency_overrides.pop(get_request_authority, None)
        app.state.session_factory = previous_factory


def test_postgresql_route_fixture_restores_prior_session_factory(
    original_session_factory, prior_session_factory
) -> None:
    pass

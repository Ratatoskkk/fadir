from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import secrets

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app import models
from app.api import routes
from app.api.request_authority import GUEST_COOKIE_NAME


def test_bootstrap_route_exists():
    assert callable(routes.bootstrap_guest)


def _request(*, cookies: dict[str, str] | None = None, origin: str = "https://ratatosk.dev") -> Request:
    headers = [(b"origin", origin.encode())]
    if cookies:
        headers.append(
            (b"cookie", "; ".join(f"{key}={value}" for key, value in cookies.items()).encode())
        )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/guest/bootstrap",
        "headers": headers,
        "query_string": b"",
        "app": SimpleNamespace(state=SimpleNamespace(configured_origin="https://ratatosk.dev")),
    }
    request = Request(scope)
    return request


def test_bootstrap_issues_sanitized_guest_and_csrf_cookies(monkeypatch, tmp_path):
    token = secrets.token_urlsafe(32)
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'bootstrap.db'}")
    models.Base.metadata.create_all(engine)
    calls = []

    def issue(session, *, clock):
        now = clock()
        workspace = models.Workspace(created_at=now, updated_at=now)
        workspace.guest_access = models.GuestAccess(
            secret_digest=b"x" * 32, created_at=now, last_access_at=now
        )
        session.add(workspace)
        session.flush()
        calls.append(workspace.id)
        return SimpleNamespace(workspace_id=workspace.id, secret=SecretStr(token))

    monkeypatch.setattr(routes.guest_access, "issue", issue)
    try:
        with Session(engine) as session, session.begin():
            response = Response()
            result = routes.bootstrap_guest(_request(), response, session)
            assert result.mode == "guest"
            assert result.created is True
            assert result.user is None
            assert result.portfolios == []
            assert result.migration_required is False
            assert response.status_code == 201
            set_cookie = "\n".join(
                value.decode() for key, value in response.raw_headers if key == b"set-cookie"
            )
            assert GUEST_COOKIE_NAME in set_cookie
            assert "__Host-fadir-csrf=" in set_cookie
            assert token not in result.model_dump_json()
            assert str(calls) not in result.model_dump_json()
        with engine.connect() as connection:
            assert connection.execute(select(models.Workspace.id)).all() == [(1,)]
    finally:
        engine.dispose()


def test_invalid_guest_cookie_is_rejected_and_cleared(monkeypatch):
    from app.services.guest_access import GuestAccessDenied

    monkeypatch.setattr(routes.guest_access, "require", lambda *_args, **_kwargs: (_ for _ in ()).throw(GuestAccessDenied()))
    with Session(create_engine("sqlite:///:memory:")) as session:
        response = Response()
        result = routes.bootstrap_guest(
            _request(cookies={GUEST_COOKIE_NAME: "bad"}), response, session
        )
        assert response.status_code == 401
        assert result.body == b'{"detail":"request rejected"}'
        assert GUEST_COOKIE_NAME in response.headers["set-cookie"]
        assert "Max-Age=0" in response.headers["set-cookie"]


def test_registered_wrapper_preserves_invalid_cookie_deletion(monkeypatch):
    from app.services.guest_access import GuestAccessDenied

    monkeypatch.setattr(
        routes.guest_access,
        "require",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(GuestAccessDenied()),
    )
    app = FastAPI()
    app.state.session_factory = lambda: Session(create_engine("sqlite:///:memory:"))
    app.state.configured_origin = "https://ratatosk.dev"
    app.include_router(routes.private_router)
    with TestClient(app) as client:
        result = client.post(
            "/api/guest/bootstrap",
            headers={"Origin": "https://ratatosk.dev"},
            cookies={GUEST_COOKIE_NAME: "bad"},
        )
    assert result.status_code == 401
    assert "Max-Age=0" in result.headers.get("set-cookie", "")


def test_saved_guest_portfolio_sets_retention_notice(monkeypatch, tmp_path):
    from app.services.guest_access import GuestAuthority

    token = secrets.token_urlsafe(32)
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'notice.db'}")
    models.Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        workspace = models.Workspace(created_at=now, updated_at=now)
        workspace.guest_access = models.GuestAccess(
            secret_digest=b"y" * 32, created_at=now, last_access_at=now
        )
        workspace.portfolios.append(models.Portfolio(name="Ana Portföy"))
        session.add(workspace)
        session.commit()
        monkeypatch.setattr(
            routes.guest_access,
            "require",
            lambda *_args, **_kwargs: GuestAuthority(workspace_id=workspace.id),
        )
        response = Response()
        with session.begin():
            result = routes.bootstrap_guest(
                _request(cookies={GUEST_COOKIE_NAME: token}), response, session
            )
        assert result.guest.notice_due is True
    engine.dispose()


def test_registered_wrapper_commit_failure_sends_no_authority_cookies(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'commit-failure.db'}")
    models.Base.metadata.create_all(engine)
    roots = []
    token = secrets.token_urlsafe(32)

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

    def issue(session, *, clock):
        now = clock()
        workspace = models.Workspace(created_at=now, updated_at=now)
        workspace.guest_access = models.GuestAccess(
            secret_digest=b"z" * 32, created_at=now, last_access_at=now
        )
        session.add(workspace)
        session.flush()
        return SimpleNamespace(workspace_id=workspace.id, secret=SecretStr(token))

    monkeypatch.setattr(routes.guest_access, "issue", issue)
    app = FastAPI()
    app.state.session_factory = lambda: CommitFailSession(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.include_router(routes.private_router)
    with TestClient(app, base_url="https://ratatosk.dev") as client:
        result = client.post(
            "/api/guest/bootstrap", headers={"Origin": "https://ratatosk.dev"}
        )
    assert result.status_code == 500
    assert "set-cookie" not in result.headers
    assert roots and roots[0].rolled_back is True
    with engine.connect() as connection:
        assert connection.execute(select(models.Workspace.id)).all() == []
    engine.dispose()

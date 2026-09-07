from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
from starlette.responses import Response

from app.api.request_authority import (
    GUEST_COOKIE_NAME,
    USER_COOKIE_NAME,
    RequestAuthorityError,
    get_request_authority,
    resolve_request_authority,
    set_guest_cookie,
    set_user_cookie,
)
from app.api.request_transaction import RequestTransactionRoute
from app.services.guest_access import GuestAuthority
from app.services.user_sessions import UserSessionAuthority


NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)
USER_ID = "YWFhYWFhYWFhYWFhYWFhYQ"
SECRET = "YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI"


class DummySession:
    pass


class Root:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.is_active = True
        self.fail_commit = fail_commit
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.is_active = False

    def rollback(self) -> None:
        self.rollbacks += 1
        self.is_active = False


class Session:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.root = Root(fail_commit=fail_commit)
        self.closed = 0

    def begin(self) -> Root:
        return self.root

    def close(self) -> None:
        self.closed += 1


def _api(session, endpoint, *, response_model=None) -> TestClient:
    app = FastAPI()
    app.state.session_factory = lambda: session
    app.state.authority_session_factory = lambda: Session()
    router = APIRouter(route_class=RequestTransactionRoute)
    router.add_api_route("/private", endpoint, methods=["GET"], response_model=response_model)
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_user_precedes_guest_and_stale_guest_is_ignored(monkeypatch) -> None:
    calls: list[str] = []

    def authenticate(session, public_id, secret, *, clock):
        calls.append("user")
        assert session.__class__ is DummySession
        assert (public_id, secret) == (USER_ID, SECRET)
        return UserSessionAuthority(user_id=7, workspace_id=11, public_id=USER_ID)

    def require(*args, **kwargs):
        calls.append("guest")
        raise AssertionError("Guest must not be consulted after valid User auth")

    monkeypatch.setattr("app.api.request_authority.user_sessions.authenticate", authenticate)
    monkeypatch.setattr("app.api.request_authority.guest_access.require", require)
    result = resolve_request_authority(
        DummySession(),
        {
            USER_COOKIE_NAME: f"{USER_ID}.{SECRET}",
            GUEST_COOKIE_NAME: "malformed",
        },
        clock=lambda: NOW,
    )
    assert result.mode == "user"
    assert result.user_id == 7 and result.workspace_id == 11
    assert result.session_public_id == USER_ID
    assert calls == ["user"]
    with pytest.raises(ValidationError):
        result.mode = "guest"


def test_invalid_user_never_falls_back_to_guest(monkeypatch) -> None:
    def authenticate(*args, **kwargs):
        raise RuntimeError("secret must not escape")

    monkeypatch.setattr("app.api.request_authority.user_sessions.authenticate", authenticate)
    monkeypatch.setattr(
        "app.api.request_authority.guest_access.require",
        lambda *args, **kwargs: pytest.fail("unexpected Guest fallback"),
    )
    with pytest.raises(RequestAuthorityError) as caught:
        resolve_request_authority(
            DummySession(),
            {
                USER_COOKIE_NAME: f"{USER_ID}.{SECRET}",
                GUEST_COOKIE_NAME: "C" * 43,
            },
            clock=lambda: NOW,
        )
    assert str(caught.value) == "request authentication failed"
    assert "secret" not in repr(caught.value)


def test_malformed_credentials_fail_before_service_access(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.request_authority.user_sessions.authenticate",
        lambda *args, **kwargs: pytest.fail("malformed User reached service"),
    )
    with pytest.raises(RequestAuthorityError):
        resolve_request_authority(DummySession(), {USER_COOKIE_NAME: "broken"})
    with pytest.raises(RequestAuthorityError):
        resolve_request_authority(DummySession(), {GUEST_COOKIE_NAME: "broken"})
    with pytest.raises(RequestAuthorityError):
        resolve_request_authority(DummySession(), {})


def test_guest_authority_is_structured_without_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.request_authority.guest_access.require",
        lambda session, token, *, clock: GuestAuthority(workspace_id=23),
    )
    result = resolve_request_authority(
        DummySession(), {GUEST_COOKIE_NAME: SECRET}, clock=lambda: NOW
    )
    assert result.mode == "guest"
    assert result.workspace_id == 23 and result.user_id is None
    assert SECRET not in repr(result)


def test_service_failure_has_no_exception_chain_or_secret(monkeypatch) -> None:
    secret = "service-secret-must-not-escape"

    def authenticate(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr("app.api.request_authority.user_sessions.authenticate", authenticate)
    with pytest.raises(RequestAuthorityError) as caught:
        resolve_request_authority(
            DummySession(), {USER_COOKIE_NAME: f"{USER_ID}.{SECRET}"}
        )
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert secret not in repr(caught.value)


def test_actual_fastapi_rejected_credential_is_generic_401_and_no_store(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.request_authority.user_sessions.authenticate",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError()),
    )

    def endpoint(authority=Depends(get_request_authority)):
        return {"ok": True}

    client = _api(Session(), endpoint)
    response = client.get("/private", cookies={USER_COOKIE_NAME: f"{USER_ID}.{SECRET}"})
    assert response.status_code == 401
    assert response.headers.get("cache-control") == "no-store"
    assert "secret" not in response.text


def test_actual_fastapi_endpoint_and_validation_failures_are_no_store() -> None:
    def endpoint():
        raise RuntimeError("endpoint failed")

    def invalid():
        return "not-an-integer"

    for response_model, handler in ((None, endpoint), (int, invalid)):
        client = _api(Session(), handler, response_model=response_model)
        response = client.get("/private")
        assert response.status_code == 500
        assert response.headers.get("cache-control") == "no-store"


def test_actual_fastapi_commit_failure_is_error_and_rolls_back() -> None:
    session = Session(fail_commit=True)
    client = _api(session, lambda: {"ok": True})
    response = client.get("/private")
    assert response.status_code == 500
    assert response.headers.get("cache-control") == "no-store"
    assert session.root.commits == 1 and session.root.rollbacks == 1


def test_auth_cookies_are_host_only_secure_and_http_only() -> None:
    response = Response()
    set_user_cookie(response, USER_ID, SECRET)
    set_guest_cookie(response, SECRET)
    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 2
    assert all("Secure" in header and "HttpOnly" in header for header in headers)
    assert all("Path=/" in header and "Domain=" not in header for header in headers)

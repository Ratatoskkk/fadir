from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from starlette.requests import Request
from starlette.responses import Response

from app.api import routes
from app.services import guest_access


def _request(host: str | None, headers: dict[str, str] | None = None) -> Request:
    raw = [(b"origin", b"https://ratatosk.dev")]
    raw += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/guest/bootstrap",
        "headers": raw,
        "query_string": b"",
        "client": (host, 1234) if host else None,
        "app": SimpleNamespace(state=SimpleNamespace(configured_origin="https://ratatosk.dev")),
    }
    return Request(scope)


@pytest.fixture
def issued(monkeypatch):
    calls: list[int] = []

    def issue(session, *, clock):
        calls.append(1)
        raise RuntimeError("stop after counting")

    monkeypatch.setattr(routes.guest_access, "issue", issue)
    return calls


def _bootstrap(request: Request) -> None:
    with Session(create_engine("sqlite:///:memory:")) as session:
        try:
            routes.bootstrap_guest(request, Response(), session)
        except RuntimeError:
            pass


def test_twenty_new_guests_per_client_per_hour(issued):
    for _ in range(guest_access.ISSUE_LIMIT):
        _bootstrap(_request("203.0.113.5"))
    assert len(issued) == guest_access.ISSUE_LIMIT
    with pytest.raises(HTTPException) as raised:
        _bootstrap(_request("203.0.113.5"))
    assert raised.value.status_code == 429
    assert len(issued) == guest_access.ISSUE_LIMIT
    _bootstrap(_request("203.0.113.6"))
    assert len(issued) == guest_access.ISSUE_LIMIT + 1


def test_loopback_client_is_keyed_by_cf_connecting_ip(issued):
    for _ in range(guest_access.ISSUE_LIMIT):
        _bootstrap(_request("127.0.0.1", {"CF-Connecting-IP": "198.51.100.1"}))
    with pytest.raises(HTTPException):
        _bootstrap(_request("::1", {"CF-Connecting-IP": "198.51.100.1"}))
    _bootstrap(_request("127.0.0.1", {"CF-Connecting-IP": "198.51.100.2"}))


def test_cf_connecting_ip_is_ignored_off_loopback(issued):
    for n in range(guest_access.ISSUE_LIMIT):
        _bootstrap(_request("203.0.113.9", {"CF-Connecting-IP": f"198.51.100.{n}"}))
    with pytest.raises(HTTPException):
        _bootstrap(_request("203.0.113.9", {"CF-Connecting-IP": "198.51.100.200"}))


def test_missing_client_does_not_crash(issued):
    _bootstrap(_request(None))
    assert len(issued) == 1

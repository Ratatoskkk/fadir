"""Cookie and CSRF primitives for same-origin authenticated requests."""

from __future__ import annotations

from dataclasses import dataclass
import re
import secrets
from typing import Mapping
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import Response


CSRF_COOKIE_NAME = "__Host-fadir-csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CsrfError(RuntimeError):
    """Raised when a state-changing request lacks valid same-origin proof."""

    message = "request rejected"

    def __init__(self) -> None:
        super().__init__(self.message)


class CsrfConfigurationError(CsrfError):
    message = "request protection is not configured"


@dataclass(frozen=True)
class CookiePolicy:
    """Explicit cookie attributes shared by authentication and CSRF cookies."""

    max_age: int
    secure: bool = True
    httponly: bool = True
    samesite: str = "lax"
    path: str = "/"
    domain: str | None = None

    def apply(self, response: Response, name: str, value: str) -> None:
        response.set_cookie(
            name,
            value,
            max_age=self.max_age,
            path=self.path,
            domain=self.domain,
            secure=self.secure,
            httponly=self.httponly,
            samesite=self.samesite,
        )

    def delete(self, response: Response, name: str) -> None:
        response.delete_cookie(
            name,
            path=self.path,
            domain=self.domain,
            secure=self.secure,
            httponly=self.httponly,
            samesite=self.samesite,
        )


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str, *, policy: CookiePolicy) -> None:
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError("invalid CSRF token")
    policy_without_http_only = CookiePolicy(
        max_age=policy.max_age,
        secure=policy.secure,
        httponly=False,
        samesite=policy.samesite,
        path=policy.path,
        domain=policy.domain,
    )
    policy_without_http_only.apply(response, CSRF_COOKIE_NAME, token)


def _configured_origin(value: str) -> str:
    if type(value) is not str or not value:
        raise CsrfConfigurationError()
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise CsrfConfigurationError()
    return value.rstrip("/")


def _origin_from_url(value: str | None) -> str | None:
    if not value or value == "null":
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def validate_csrf(request: Request, *, configured_origin: str) -> None:
    if request.method.upper() in _SAFE_METHODS:
        return

    expected_origin = _configured_origin(configured_origin)
    origin = request.headers.get("origin")
    if origin is None:
        origin = _origin_from_url(request.headers.get("referer"))
    if origin != expected_origin:
        raise CsrfError()

    cookie = request.cookies.get(CSRF_COOKIE_NAME)
    header = request.headers.get(CSRF_HEADER_NAME)
    if (
        cookie is None
        or header is None
        or not _TOKEN_RE.fullmatch(cookie)
        or not _TOKEN_RE.fullmatch(header)
        or not secrets.compare_digest(cookie, header)
    ):
        raise CsrfError()


def validate_request_csrf(request: Request) -> None:
    """FastAPI dependency adapter; the application supplies the allowed origin."""
    configured_origin = getattr(request.app.state, "configured_origin", None)
    if not isinstance(configured_origin, str):
        raise CsrfConfigurationError()
    validate_csrf(request, configured_origin=configured_origin)


def validate_csrf_headers(
    headers: Mapping[str, str], cookies: Mapping[str, str], *, method: str, configured_origin: str
) -> None:
    """Header-only equivalent used by policy tests and non-ASGI adapters."""
    if method.upper() in _SAFE_METHODS:
        return
    expected_origin = _configured_origin(configured_origin)
    origin = headers.get("origin")
    if origin is None:
        origin = _origin_from_url(headers.get("referer"))
    if origin != expected_origin:
        raise CsrfError()
    cookie = cookies.get(CSRF_COOKIE_NAME)
    header = headers.get(CSRF_HEADER_NAME)
    if (
        cookie is None
        or header is None
        or not _TOKEN_RE.fullmatch(cookie)
        or not _TOKEN_RE.fullmatch(header)
        or not secrets.compare_digest(cookie, header)
    ):
        raise CsrfError()


def no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response

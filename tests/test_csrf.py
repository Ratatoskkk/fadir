from __future__ import annotations

import pytest
from starlette.responses import Response

from app.api.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CookiePolicy,
    CsrfConfigurationError,
    CsrfError,
    issue_csrf_token,
    set_csrf_cookie,
    validate_csrf_headers,
)


ORIGIN = "https://ratatosk.dev"


def _headers(token: str, *, origin: str | None = ORIGIN) -> dict[str, str]:
    result = {CSRF_HEADER_NAME: token}
    if origin is not None:
        result["origin"] = origin
    return result


def test_csrf_requires_matching_token_and_exact_origin() -> None:
    token = issue_csrf_token()
    validate_csrf_headers(
        _headers(token), {CSRF_COOKIE_NAME: token}, method="POST", configured_origin=ORIGIN
    )
    for headers, cookies in (
        (_headers(token, origin="https://evil.example"), {CSRF_COOKIE_NAME: token}),
        (_headers(token), {CSRF_COOKIE_NAME: "A" * 43}),
        ({"origin": ORIGIN}, {CSRF_COOKIE_NAME: token}),
        (_headers(token, origin="null"), {CSRF_COOKIE_NAME: token}),
    ):
        with pytest.raises(CsrfError):
            validate_csrf_headers(headers, cookies, method="POST", configured_origin=ORIGIN)


def test_csrf_uses_referer_only_when_origin_is_absent() -> None:
    token = issue_csrf_token()
    validate_csrf_headers(
        {CSRF_HEADER_NAME: token, "referer": ORIGIN + "/form"},
        {CSRF_COOKIE_NAME: token},
        method="PATCH",
        configured_origin=ORIGIN,
    )
    with pytest.raises(CsrfError):
        validate_csrf_headers(
            {CSRF_HEADER_NAME: token},
            {CSRF_COOKIE_NAME: token},
            method="PATCH",
            configured_origin=ORIGIN,
        )


def test_safe_methods_skip_csrf_proof() -> None:
    validate_csrf_headers({}, {}, method="GET", configured_origin=ORIGIN)


def test_csrf_cookie_is_readable_but_secure() -> None:
    response = Response()
    set_csrf_cookie(response, issue_csrf_token(), policy=CookiePolicy(max_age=600))
    header = response.headers["set-cookie"]
    assert "__Host-fadir-csrf=" in header
    assert "Secure" in header and "HttpOnly" not in header
    assert "Path=/" in header and "SameSite=lax" in header


def test_invalid_origin_configuration_fails_closed() -> None:
    with pytest.raises(CsrfConfigurationError):
        validate_csrf_headers({}, {}, method="POST", configured_origin="not-an-origin")

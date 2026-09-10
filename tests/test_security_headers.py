from __future__ import annotations

from fastapi.testclient import TestClient
from httpx import Response


EXPECTED_SECURITY_HEADERS = {
    "strict-transport-security": "max-age=31536000",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://accounts.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src https://accounts.google.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    "referrer-policy": "strict-origin-when-cross-origin",
}

REQUIRED_CSP_DIRECTIVES = (
    "script-src 'self' 'unsafe-inline' https://accounts.google.com",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "frame-src https://accounts.google.com",
)


def assert_security_headers(response: Response) -> None:
    for name, value in EXPECTED_SECURITY_HEADERS.items():
        assert response.headers.get(name) == value


def test_security_headers_cover_shell_and_api_response(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        shell = client.get("/")
        api = client.get("/api/health")

    assert shell.status_code == 200
    assert shell.headers["content-type"].startswith("text/html")
    assert shell.headers["cache-control"] == "no-cache"
    assert_security_headers(shell)
    csp = shell.headers["content-security-policy"]
    for directive in REQUIRED_CSP_DIRECTIVES:
        assert directive in csp

    assert api.status_code == 200
    assert_security_headers(api)


def test_security_headers_preserve_no_store_on_private_api_denial(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/portfolios")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response)

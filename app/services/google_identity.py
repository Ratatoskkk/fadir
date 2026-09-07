"""Fail-closed verification of Google beta identity assertions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
import secrets
from typing import Any


CANONICAL_GOOGLE_ISSUER = "https://accounts.google.com"
Verifier = Callable[[str, str, float], Mapping[str, Any]]


class GoogleIdentityError(RuntimeError):
    message = "Google identity verification failed"

    def __init__(self) -> None:
        super().__init__(self.message)


class GoogleIdentityUnavailable(GoogleIdentityError):
    message = "Google identity verification unavailable"


@dataclass(frozen=True)
class VerifiedGoogleIdentity:
    issuer: str
    subject: str


def _load_google_verifier() -> Verifier | None:
    try:
        from google.auth.transport import requests
        from google.oauth2 import id_token
    except Exception:
        return None

    def verify(token: str, client_id: str, timeout_seconds: float) -> Mapping[str, Any]:
        request = requests.Request()

        def bounded_request(url, **kwargs):
            kwargs["timeout"] = timeout_seconds
            return request(url, **kwargs)

        return id_token.verify_oauth2_token(token, bounded_request, client_id)

    return verify


def _run_verifier(
    verifier: Verifier, token: str, client_id: str, timeout_seconds: float
) -> Mapping[str, Any] | None:
    failed = False
    result: Mapping[str, Any] | None = None
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(verifier, token, client_id, timeout_seconds)
        result = future.result(timeout=timeout_seconds)
    except Exception:
        failed = True
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    if failed:
        return None
    return result


def verify_google_identity(
    token: str,
    *,
    client_id: str,
    expected_nonce: str,
    timeout_seconds: float = 5.0,
    verifier: Verifier | None = None,
) -> VerifiedGoogleIdentity:
    """Verify one Google ID token and return only its durable issuer and subject."""
    if (
        type(token) is not str
        or not token
        or type(client_id) is not str
        or not client_id
        or type(expected_nonce) is not str
        or not expected_nonce
        or type(timeout_seconds) not in (int, float)
        or not 0.1 <= float(timeout_seconds) <= 30.0
    ):
        raise GoogleIdentityError()

    selected = verifier or _load_google_verifier()
    if selected is None:
        raise GoogleIdentityUnavailable()

    claims = _run_verifier(selected, token, client_id, float(timeout_seconds))
    if not isinstance(claims, Mapping):
        raise GoogleIdentityError()

    issuer = claims.get("iss")
    audience = claims.get("aud")
    subject = claims.get("sub")
    nonce = claims.get("nonce")
    valid = (
        issuer == CANONICAL_GOOGLE_ISSUER
        and type(audience) is str
        and secrets.compare_digest(audience, client_id)
        and type(subject) is str
        and bool(subject)
        and subject.strip() == subject
        and type(nonce) is str
        and secrets.compare_digest(nonce, expected_nonce)
    )
    if not valid:
        raise GoogleIdentityError()
    return VerifiedGoogleIdentity(issuer=CANONICAL_GOOGLE_ISSUER, subject=subject)


def verify_google_identity_from_settings(
    token: str,
    *,
    expected_nonce: str,
    settings: Any,
    verifier: Verifier | None = None,
) -> VerifiedGoogleIdentity:
    """Use the explicit Google settings without retaining settings or token data."""
    google = getattr(settings, "google", None)
    client_id = getattr(google, "web_client_id", None)
    timeout_seconds = getattr(google, "verification_timeout_seconds", None)
    if not client_id or timeout_seconds is None:
        raise GoogleIdentityUnavailable()
    return verify_google_identity(
        token,
        client_id=client_id,
        expected_nonce=expected_nonce,
        timeout_seconds=timeout_seconds,
        verifier=verifier,
    )

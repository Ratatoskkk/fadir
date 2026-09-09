"""Resolve one request's User or Guest authority inside its caller transaction."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.csrf import CookiePolicy
from app.services import guest_access, user_sessions


USER_COOKIE_NAME = "__Host-fadir-user"
GUEST_COOKIE_NAME = "__Host-fadir-guest"
USER_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
GUEST_COOKIE_MAX_AGE = 90 * 24 * 60 * 60
USER_COOKIE_POLICY = CookiePolicy(max_age=USER_COOKIE_MAX_AGE)
GUEST_COOKIE_POLICY = CookiePolicy(max_age=GUEST_COOKIE_MAX_AGE)
_PUBLIC_ID_RE = re.compile(r"[A-Za-z0-9_-]{22}\Z")
_SECRET_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class RequestAuthorityError(RuntimeError):
    """Sanitized authentication failure with no credential details."""

    message = "request authentication failed"

    def __init__(self) -> None:
        super().__init__(self.message)


class RequestAuthorityConfigurationError(RequestAuthorityError):
    message = "request authentication is not configured"


class RequestAuthority(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Literal["user", "guest"]
    user_id: int | None
    workspace_id: int
    session_public_id: str | None = None

    @property
    def is_user(self) -> bool:
        return self.mode == "user"

    @property
    def is_guest(self) -> bool:
        return self.mode == "guest"


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def _user_cookie(value: str) -> tuple[str, str]:
    if type(value) is not str or value.count(".") != 1:
        raise RequestAuthorityError()
    public_id, secret = value.split(".", 1)
    if not _canonical(public_id, 22, 16) or not _canonical(secret, 43, 32):
        raise RequestAuthorityError()
    return public_id, secret


def _guest_cookie(value: str) -> str:
    if not _canonical(value, 43, 32):
        raise RequestAuthorityError()
    return value


def _canonical(value: str, length: int, raw_length: int) -> bool:
    pattern = _PUBLIC_ID_RE if length == 22 else _SECRET_RE
    if type(value) is not str or not pattern.fullmatch(value):
        return False
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        raw = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        return False
    return len(raw) == raw_length and base64.urlsafe_b64encode(raw).decode().rstrip("=") == value


def set_user_cookie(response: Response, public_id: str, secret: str) -> None:
    public_id, secret = _user_cookie(f"{public_id}.{secret}")
    USER_COOKIE_POLICY.apply(response, USER_COOKIE_NAME, f"{public_id}.{secret}")


def set_guest_cookie(response: Response, secret: str) -> None:
    GUEST_COOKIE_POLICY.apply(response, GUEST_COOKIE_NAME, _guest_cookie(secret))


def delete_user_cookie(response: Response) -> None:
    USER_COOKIE_POLICY.delete(response, USER_COOKIE_NAME)


def delete_guest_cookie(response: Response) -> None:
    GUEST_COOKIE_POLICY.delete(response, GUEST_COOKIE_NAME)


def resolve_request_authority(
    session: Session,
    cookies: Mapping[str, str],
    *,
    clock=_clock,
) -> RequestAuthority:
    """Authenticate the request using User precedence, then Guest authority.

    The caller owns the active root transaction. This function never commits, rolls
    back, closes the session, logs credentials, or falls back from an invalid User
    cookie to Guest access.
    """
    user_value = cookies.get(USER_COOKIE_NAME)
    if user_value is not None:
        public_id, secret = _user_cookie(user_value)
        authority = None
        try:
            authority = user_sessions.authenticate(
                session, public_id, secret, clock=clock
            )
        except Exception:
            pass
        if authority is None:
            raise RequestAuthorityError()
        return RequestAuthority(
            mode="user",
            user_id=authority.user_id,
            workspace_id=authority.workspace_id,
            session_public_id=authority.public_id,
        )

    guest_value = cookies.get(GUEST_COOKIE_NAME)
    if guest_value is None:
        raise RequestAuthorityError()
    token = _guest_cookie(guest_value)
    authority = None
    try:
        authority = guest_access.require(session, token, clock=clock)
    except Exception:
        pass
    if authority is None:
        raise RequestAuthorityError()
    return RequestAuthority(mode="guest", user_id=None, workspace_id=authority.workspace_id)


def request_authority_from_session(session: Session, cookies: Mapping[str, str]) -> RequestAuthority:
    """Convenience adapter for a caller that supplies no custom clock."""
    return resolve_request_authority(session, cookies, clock=_clock)


def recover_invalid_user_cookie(
    session: Session,
    cookies: Mapping[str, str],
    *,
    clock=_clock,
) -> bool:
    """Clear permission for an unusable User cookie only after Guest proof."""
    user_value = cookies.get(USER_COOKIE_NAME)
    if user_value is None:
        return False

    user_authority = None
    try:
        public_id, secret = _user_cookie(user_value)
    except RequestAuthorityError:
        public_id = secret = None
    if public_id is not None and secret is not None:
        try:
            user_authority = user_sessions.authenticate(
                session, public_id, secret, clock=clock
            )
        except user_sessions.UserSessionDenied:
            user_authority = None
    if user_authority is not None:
        return False

    guest_value = cookies.get(GUEST_COOKIE_NAME)
    if guest_value is None:
        raise RequestAuthorityError()
    try:
        token = _guest_cookie(guest_value)
        guest_access.require(session, token, clock=clock)
    except (RequestAuthorityError, guest_access.GuestAccessDenied):
        raise RequestAuthorityError() from None
    return True


def get_request_authority(request: Request) -> RequestAuthority:
    """Resolve authority in a short, separate transaction before route data work."""
    factory = getattr(request.app.state, "authority_session_factory", None)
    if not callable(factory):
        raise RequestAuthorityConfigurationError()
    session = None
    root = None
    try:
        session = factory()
        root = session.begin()
        authority = request_authority_from_session(session, request.cookies)
        root.commit()
        return authority
    except RequestAuthorityError:
        if root is not None and root.is_active:
            root.rollback()
        raise
    except Exception:
        if root is not None and root.is_active:
            root.rollback()
        raise RequestAuthorityError() from None
    finally:
        if session is not None:
            session.close()

"""Portfolio Codes: a short, unique number that opens one Portfolio on another device.

A code is digits only. New codes take 4 digits while that space has room, then 5, then 6.
Entering a code issues a Portfolio Pass: an opaque browser secret, stored only as a hash,
that grants access to that one Portfolio. Changing the code revokes every pass.

Short codes are guessable by design (owner decision, ADR 0011), so failed attempts are
rate limited per client and across the service.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.models import GuestAccess, Portfolio, PortfolioPass

#: (digits, size of that space), in allocation order.
CODE_SPACES = ((4, 10**4), (5, 10**5), (6, 10**6))
PASS_TTL = timedelta(days=90)
_CODE_RE = re.compile(r"[0-9]{4,6}\Z")
_SECRET_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")

#: Failed code attempts one client may make per window, and the whole service.
CLIENT_FAILURE_LIMIT = 8
SERVICE_FAILURE_LIMIT = 120
FAILURE_WINDOW_SECONDS = 15 * 60


class PortfolioCodeError(RuntimeError):
    """Sanitized failure; never names the code or the Portfolio."""


class PortfolioCodesExhausted(PortfolioCodeError):
    pass


class PortfolioCodeThrottled(PortfolioCodeError):
    pass


class PortfolioCodeRejected(PortfolioCodeError):
    pass


@dataclass(frozen=True)
class IssuedPass:
    portfolio_id: int
    workspace_id: int
    secret: str


@dataclass(frozen=True)
class PassAuthority:
    portfolio_id: int
    workspace_id: int


# -- allocation --------------------------------------------------------------------


def _pick(connection: Connection, pending: set[str]) -> str:
    counts = dict(
        connection.execute(
            select(func.length(Portfolio.code), func.count()).group_by(func.length(Portfolio.code))
        ).all()
    )
    for digits, size in CODE_SPACES:
        pending_here = {code for code in pending if len(code) == digits}
        if counts.get(digits, 0) + len(pending_here) >= size:
            continue
        used = set(
            connection.execute(
                select(Portfolio.code).where(func.length(Portfolio.code) == digits)
            ).scalars()
        ) | pending_here
        if len(used) >= size:
            continue
        if len(used) * 2 < size:
            while True:
                code = f"{secrets.randbelow(size):0{digits}d}"
                if code not in used:
                    return code
        free = [f"{n:0{digits}d}" for n in range(size) if f"{n:0{digits}d}" not in used]
        return secrets.choice(free)
    raise PortfolioCodesExhausted("no Portfolio Code is free")


def assign_codes(session: Session) -> None:
    """Give every new Portfolio in this flush a free code (called from `before_flush`)."""
    new = [obj for obj in session.new if isinstance(obj, Portfolio) and not obj.code]
    if not new:
        return
    connection = session.connection()
    pending: set[str] = set()
    for portfolio in new:
        code = _pick(connection, pending)
        pending.add(code)
        portfolio.code = code


def normalize(raw: object) -> str | None:
    if type(raw) is not str:
        return None
    digits = re.sub(r"\s+", "", raw)
    return digits if _CODE_RE.fullmatch(digits) else None


def lengths_in_use(session: Session) -> list[int]:
    """Code lengths a visitor may need to type, shortest first; 4 is always offered."""
    found = {
        int(n)
        for n in session.execute(select(func.length(Portfolio.code)).distinct()).scalars()
        if n is not None
    }
    return sorted(found | {4})


# -- throttling --------------------------------------------------------------------

_failures: dict[str, deque[float]] = {}
_service_failures: deque[float] = deque()
_lock = threading.Lock()


def reset_limits() -> None:
    with _lock:
        _failures.clear()
        _service_failures.clear()


def _trim(stamps: deque[float], now: float) -> None:
    while stamps and stamps[0] <= now - FAILURE_WINDOW_SECONDS:
        stamps.popleft()


def _throttled(client_key: str) -> bool:
    now = time.monotonic()
    with _lock:
        _trim(_service_failures, now)
        stamps = _failures.get(client_key)
        if stamps is not None:
            _trim(stamps, now)
        return (
            len(_service_failures) >= SERVICE_FAILURE_LIMIT
            or (stamps is not None and len(stamps) >= CLIENT_FAILURE_LIMIT)
        )


def _record_failure(client_key: str) -> None:
    now = time.monotonic()
    with _lock:
        if len(_failures) > 10000:
            for key in [k for k, v in _failures.items() if not v or v[-1] <= now - FAILURE_WINDOW_SECONDS]:
                del _failures[key]
        _failures.setdefault(client_key, deque()).append(now)
        _service_failures.append(now)


# -- passes ------------------------------------------------------------------------


def _digest(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("ascii")).digest()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def redeem(session: Session, raw_code: object, client_key: str, *, now: datetime) -> IssuedPass:
    """Exchange a correct code for a new Portfolio Pass in the caller transaction."""
    if _throttled(client_key):
        raise PortfolioCodeThrottled("too many attempts")
    code = normalize(raw_code)
    portfolio = (
        session.scalar(select(Portfolio).where(Portfolio.code == code)) if code else None
    )
    if portfolio is None:
        _record_failure(client_key)
        raise PortfolioCodeRejected("code rejected")
    secret = secrets.token_urlsafe(32)
    session.add(
        PortfolioPass(
            portfolio_id=portfolio.id,
            secret_digest=_digest(secret),
            created_at=now,
            last_access_at=now,
        )
    )
    session.flush()
    return IssuedPass(portfolio_id=portfolio.id, workspace_id=portfolio.workspace_id, secret=secret)


def authenticate(session: Session, secret: str, *, now: datetime) -> PassAuthority:
    if type(secret) is not str or not _SECRET_RE.fullmatch(secret):
        raise PortfolioCodeRejected("pass rejected")
    row = session.execute(
        select(PortfolioPass, Portfolio.workspace_id)
        .join(Portfolio, Portfolio.id == PortfolioPass.portfolio_id)
        .where(PortfolioPass.secret_digest == _digest(secret))
    ).first()
    if row is None:
        raise PortfolioCodeRejected("pass rejected")
    pass_row, workspace_id = row
    if pass_row.revoked_at is not None or now >= _utc(pass_row.last_access_at) + PASS_TTL:
        raise PortfolioCodeRejected("pass rejected")
    pass_row.last_access_at = now
    # A Guest Portfolio used only through its code must not expire with its first browser.
    session.execute(
        update(GuestAccess)
        .where(
            GuestAccess.workspace_id == workspace_id,
            GuestAccess.revoked_at.is_(None),
            GuestAccess.last_access_at > now - timedelta(days=90),
        )
        .values(last_access_at=now)
    )
    return PassAuthority(portfolio_id=pass_row.portfolio_id, workspace_id=workspace_id)


def revoke(session: Session, secret: str, *, now: datetime) -> None:
    if type(secret) is not str or not _SECRET_RE.fullmatch(secret):
        return
    session.execute(
        update(PortfolioPass)
        .where(PortfolioPass.secret_digest == _digest(secret), PortfolioPass.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def regenerate(session: Session, portfolio: Portfolio, *, now: datetime) -> str:
    """Give the Portfolio a new code and close it on every device that used the old one."""
    portfolio.code = _pick(session.connection(), {portfolio.code})
    session.execute(
        update(PortfolioPass)
        .where(PortfolioPass.portfolio_id == portfolio.id, PortfolioPass.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    session.flush()
    return portfolio.code

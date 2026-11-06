"""Guest authority inside one caller-owned PostgreSQL root transaction.

The caller supplies a trusted, nondecreasing clock and suppresses database parameters.
Returned identifiers carry no authority after the caller ends the transaction.
"""

from __future__ import annotations

import base64
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
import secrets
import threading
import time

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import delete, inspect, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Base,
    GuestAccess,
    LoginTransaction,
    Portfolio,
    Snapshot,
    Transaction,
    Workspace,
)


Clock = Callable[[], datetime]
_GUEST = GuestAccess.__table__
_WORKSPACE = Workspace.__table__


#: New guests one client may create per rolling hour.
ISSUE_LIMIT = 20
ISSUE_WINDOW_SECONDS = 3600
_issued: dict[str, deque[float]] = {}
_issued_lock = threading.Lock()


def reset_issue_limits() -> None:
    with _issued_lock:
        _issued.clear()


def allow_issue(client_key: str) -> bool:
    """Count one new-guest attempt for `client_key`; False once it is over the limit."""
    now = time.monotonic()
    with _issued_lock:
        if len(_issued) > 10000:
            for key in [k for k, v in _issued.items() if not v or v[-1] <= now - ISSUE_WINDOW_SECONDS]:
                del _issued[key]
        stamps = _issued.setdefault(client_key, deque())
        while stamps and stamps[0] <= now - ISSUE_WINDOW_SECONDS:
            stamps.popleft()
        if len(stamps) >= ISSUE_LIMIT:
            return False
        stamps.append(now)
        return True


class GuestAccessError(RuntimeError):
    message = "Guest access failed"

    def __init__(self):
        super().__init__(self.message)


class GuestAccessDenied(GuestAccessError):
    message = "Guest access denied"


class GuestAccessBusy(GuestAccessError):
    message = "Guest access is busy"


class GuestAccessUnsupported(GuestAccessError):
    message = "Guest access requires a supported PostgreSQL caller transaction"


class GuestAccessPendingChanges(GuestAccessError):
    message = "Guest access has pending security changes"


class GuestAccessClockError(GuestAccessError):
    message = "Guest access requires a trusted nondecreasing UTC clock"


class GuestAccessCollision(GuestAccessError):
    message = "Guest issuance conflict"


class GuestAccessUnconfirmed(GuestAccessError):
    message = "Guest operation is unconfirmed; verify caller state before further work"


class GuestAuthority(BaseModel):
    model_config = ConfigDict(frozen=True)
    workspace_id: int


class IssuedGuest(GuestAuthority):
    secret: SecretStr = Field(exclude=True, repr=False)


def _digest(token: str) -> bytes:
    if type(token) is not str or len(token) != 43 or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        raise GuestAccessDenied()
    raw = base64.b64decode(token + "=", altchars=b"-_", validate=True)
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != token:
        raise GuestAccessDenied()
    return hashlib.sha256(token.encode("ascii")).digest()


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GuestAccessClockError()
    return value.astimezone(timezone.utc)


def _time(clock: Clock, row=None) -> datetime:
    now = _utc(clock())
    if row is not None and any(now < _utc(row[name]) for name in ("created_at", "last_access_at")):
        raise GuestAccessClockError()
    return now


def _connection(session: Session):
    root = session.get_transaction()
    if root is None or not root.is_active or root.parent is not None or session.in_nested_transaction():
        raise GuestAccessUnsupported()
    bind = session.get_bind()
    if (bind.dialect.name, bind.dialect.driver) != ("postgresql", "psycopg"):
        raise GuestAccessUnsupported()
    for mapper in Base.registry.mappers:
        if session.get_bind(mapper=mapper) is not bind:
            raise GuestAccessUnsupported()
    for obj in (*session.new, *session.dirty, *session.deleted):
        if session.get_bind(mapper=inspect(obj).mapper) is not bind:
            raise GuestAccessUnsupported()
    connection = session.connection()
    if connection.closed or connection.invalidated or connection.in_nested_transaction():
        raise GuestAccessUnsupported()
    driver = connection.connection.driver_connection
    if driver.autocommit or driver.info.transaction_status.name not in ("IDLE", "INTRANS"):
        raise GuestAccessUnsupported()
    if (not connection.engine.hide_parameters or connection.engine.echo
            or logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.DEBUG)
            or connection.engine.logger.isEnabledFor(logging.DEBUG)):
        raise GuestAccessUnsupported()
    if connection.get_isolation_level() != "READ COMMITTED":
        raise GuestAccessUnsupported()
    return connection


def _pending_security(session: Session, workspace_id: int):
    for obj in (*session.new, *session.dirty, *session.deleted):
        state = inspect(obj)
        if isinstance(obj, (Workspace, GuestAccess)):
            keys = [state.identity[0] if state.identity else None,
                    state.dict.get("id" if isinstance(obj, Workspace) else "workspace_id")]
            related = state.dict.get("workspace")
            if related is not None:
                related_state = inspect(related)
                keys.append(related_state.identity[0] if related_state.identity else related_state.dict.get("id"))
            if workspace_id in keys:
                raise GuestAccessPendingChanges()


def _locked(session, connection, digest):
    identifier = connection.scalar(select(_GUEST.c.workspace_id).where(_GUEST.c.secret_digest == digest))
    if identifier is None:
        raise GuestAccessDenied()
    _pending_security(session, identifier)
    workspace = connection.execute(select(_WORKSPACE.c.id, _WORKSPACE.c.user_id)
        .where(_WORKSPACE.c.id == identifier).with_for_update(nowait=True)).mappings().one_or_none()
    guest = connection.execute(select(_GUEST).where(_GUEST.c.workspace_id == identifier)
        .with_for_update(nowait=True)).mappings().one_or_none()
    if (workspace is None or guest is None or guest["secret_digest"] != digest
            or workspace["user_id"] is not None):
        raise GuestAccessDenied()
    return guest


def _run(session, operation):
    error_type = GuestAccessError
    savepoint = None
    try:
        connection = _connection(session)
        try:
            savepoint = connection.begin_nested()
        except Exception:
            raise GuestAccessUnconfirmed() from None
        result = operation(connection)
        savepoint.commit()
        return result
    except GuestAccessError as error:
        error_type = type(error)
    except IntegrityError as error:
        if (getattr(error.orig, "sqlstate", None) == "23505"
                and getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                == "uq_guest_access_secret_digest"):
            error_type = GuestAccessCollision
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            error_type = GuestAccessBusy
    except Exception:
        pass
    if savepoint is not None:
        try:
            if not savepoint.is_active or connection.invalidated or connection.closed:
                raise GuestAccessUnconfirmed()
            savepoint.rollback()
            if not session.is_active or not connection.in_transaction():
                raise GuestAccessUnconfirmed()
        except Exception:
            error_type = GuestAccessUnconfirmed
    raise error_type() from None


def issue(session: Session, *, clock: Clock) -> IssuedGuest:
    """Issue once; the caller must commit before it sends the secret."""
    def operation(connection):
        now = _time(clock)
        token = secrets.token_urlsafe(32)
        digest = _digest(token)
        identifier = connection.scalar(_WORKSPACE.insert().values(
            user_id=None, created_at=now, updated_at=now).returning(_WORKSPACE.c.id))
        connection.execute(_GUEST.insert().values(workspace_id=identifier,
            secret_digest=digest, created_at=now, last_access_at=now, revoked_at=None))
        return IssuedGuest(workspace_id=identifier, secret=SecretStr(token))
    return _run(session, operation)


def require(session: Session, token: str, *, clock: Clock) -> GuestAuthority:
    """Lock fresh Guest state and touch only accepted access."""
    def operation(connection):
        guest = _locked(session, connection, _digest(token))
        if guest["revoked_at"] is not None:
            raise GuestAccessDenied()
        now = _time(clock, guest)
        if now >= _utc(guest["last_access_at"]) + timedelta(days=90):
            raise GuestAccessDenied()
        connection.execute(update(_GUEST).where(_GUEST.c.workspace_id == guest["workspace_id"])
                           .values(last_access_at=now))
        return GuestAuthority(workspace_id=guest["workspace_id"])
    return _run(session, operation)


def revoke(session: Session, token: str, *, clock: Clock) -> bool:
    """Revoke by secret, including expired access; never touch access time."""
    def operation(connection):
        guest = _locked(session, connection, _digest(token))
        if guest["revoked_at"] is not None:
            return False
        now = _time(clock, guest)
        connection.execute(update(_GUEST).where(_GUEST.c.workspace_id == guest["workspace_id"])
                           .values(revoked_at=now))
        return True
    return _run(session, operation)


def purge_expired_guests(session: Session, now: datetime) -> int:
    """Delete Guest Workspaces unused for 90 days (or revoked) with all their data.

    Signed-in workspaces (user_id set) are never touched. Also drops login transactions
    that expired more than a day ago. Returns the number of workspaces deleted.
    """
    def aware(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    now = aware(now)
    cutoff = now - timedelta(days=90)
    guests: dict[int, bool] = {}
    for workspace_id, last_access_at, revoked_at in session.execute(
        select(_GUEST.c.workspace_id, _GUEST.c.last_access_at, _GUEST.c.revoked_at)
        .join(_WORKSPACE, _WORKSPACE.c.id == _GUEST.c.workspace_id)
        .where(_WORKSPACE.c.user_id.is_(None))
    ):
        dead = revoked_at is not None or aware(last_access_at) <= cutoff
        guests[workspace_id] = guests.get(workspace_id, True) and dead
    doomed = [workspace_id for workspace_id, dead in guests.items() if dead]

    for start in range(0, len(doomed), 200):
        chunk = doomed[start : start + 200]
        portfolios = select(Portfolio.id).where(Portfolio.workspace_id.in_(chunk))
        session.execute(delete(Snapshot).where(Snapshot.portfolio_id.in_(portfolios)))
        session.execute(delete(Transaction).where(Transaction.portfolio_id.in_(portfolios)))
        session.execute(delete(Portfolio).where(Portfolio.workspace_id.in_(chunk)))
        session.execute(delete(GuestAccess).where(GuestAccess.workspace_id.in_(chunk)))
        session.execute(delete(Workspace).where(Workspace.id.in_(chunk), Workspace.user_id.is_(None)))

    session.execute(
        delete(LoginTransaction).where(LoginTransaction.expires_at < now - timedelta(days=1))
    )
    return len(doomed)

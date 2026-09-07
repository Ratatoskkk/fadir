"""User session authority inside one caller-owned PostgreSQL root transaction."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
import secrets
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import inspect, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, User, UserSession, Workspace


Clock = Callable[[], datetime]
T = TypeVar("T")
_SESSION = UserSession.__table__
_USER = User.__table__
_WORKSPACE = Workspace.__table__
_INACTIVITY = timedelta(days=30)


class UserSessionError(RuntimeError):
    message = "User session operation failed"

    def __init__(self) -> None:
        super().__init__(self.message)


class UserSessionDenied(UserSessionError):
    message = "User session denied"


class UserSessionBusy(UserSessionError):
    message = "User session is busy"


class UserSessionUnsupported(UserSessionError):
    message = "User sessions require a supported PostgreSQL caller transaction"


class UserSessionPendingChanges(UserSessionError):
    message = "User session has pending security changes"


class UserSessionClockError(UserSessionError):
    message = "User sessions require a trusted nondecreasing UTC clock"


class UserSessionCollision(UserSessionError):
    message = "User session issuance conflict"


class UserSessionUnconfirmed(UserSessionError):
    message = "User session operation is unconfirmed; verify caller state before further work"


class UserSessionAuthority(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: int
    workspace_id: int
    public_id: str

    @property
    def session_id(self) -> str:
        return self.public_id


class IssuedUserSession(UserSessionAuthority):
    secret: SecretStr = Field(exclude=True, repr=False)


class UserSessionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    public_id: str
    created_at: datetime
    last_access_at: datetime

    @property
    def session_id(self) -> str:
        return self.public_id


def _digest(token: str) -> bytes:
    if (
        type(token) is not str
        or len(token) != 43
        or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None
    ):
        raise UserSessionDenied()
    try:
        raw = base64.b64decode(token + "=", altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise UserSessionDenied() from None
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != token:
        raise UserSessionDenied()
    return hashlib.sha256(token.encode("ascii")).digest()


def _public_id(value: str) -> str:
    if (
        type(value) is not str
        or len(value) != 22
        or re.fullmatch(r"[A-Za-z0-9_-]{22}", value) is None
    ):
        raise UserSessionDenied()
    try:
        raw = base64.b64decode(value + "==", altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise UserSessionDenied() from None
    if len(raw) != 16 or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value:
        raise UserSessionDenied()
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise UserSessionClockError()
    return value.astimezone(timezone.utc)


def _time(clock: Clock, row: object | None = None) -> datetime:
    now = _utc(clock())
    if row is not None:
        created = _utc(row["created_at"])
        last_access = _utc(row["last_access_at"])
        if now < created or now < last_access:
            raise UserSessionClockError()
    return now


def _time_for_rows(
    clock: Clock, rows: Sequence[Mapping[str, datetime]]
) -> datetime:
    now = _utc(clock())
    for row in rows:
        if now < _utc(row["created_at"]) or now < _utc(row["last_access_at"]):
            raise UserSessionClockError()
    return now


def _connection(session: Session) -> Connection:
    root = session.get_transaction()
    if root is None or not root.is_active or root.parent is not None or session.in_nested_transaction():
        raise UserSessionUnsupported()
    bind = session.get_bind()
    if (bind.dialect.name, bind.dialect.driver) != ("postgresql", "psycopg"):
        raise UserSessionUnsupported()
    for mapper in Base.registry.mappers:
        if session.get_bind(mapper=mapper) is not bind:
            raise UserSessionUnsupported()
    for obj in (*session.new, *session.dirty, *session.deleted):
        if session.get_bind(mapper=inspect(obj).mapper) is not bind:
            raise UserSessionUnsupported()
    connection = session.connection()
    if connection.closed or connection.invalidated or connection.in_nested_transaction():
        raise UserSessionUnsupported()
    driver = connection.connection.driver_connection
    if driver.autocommit or driver.info.transaction_status.name not in ("IDLE", "INTRANS"):
        raise UserSessionUnsupported()
    if (
        not connection.engine.hide_parameters
        or connection.engine.echo
        or logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.DEBUG)
        or connection.engine.logger.isEnabledFor(logging.DEBUG)
    ):
        raise UserSessionUnsupported()
    if connection.get_isolation_level() != "READ COMMITTED":
        raise UserSessionUnsupported()
    return connection


def _pending_security(
    session: Session,
    user_id: int,
    workspace_id: int | None = None,
    public_id: str | None = None,
) -> None:
    for obj in (*session.new, *session.dirty, *session.deleted):
        state = inspect(obj)
        if isinstance(obj, User):
            key = state.identity[0] if state.identity else state.dict.get("id")
            if key == user_id:
                raise UserSessionPendingChanges()
        elif isinstance(obj, Workspace):
            key = state.identity[0] if state.identity else state.dict.get("id")
            attached_user = state.dict.get("user_id")
            if key == workspace_id or attached_user == user_id:
                raise UserSessionPendingChanges()
        elif isinstance(obj, UserSession):
            original_user_id = state.committed_state.get("user_id")
            original_public_id = state.committed_state.get("public_id")
            old_user_ids = state.attrs.user_id.history.deleted
            old_public_ids = state.attrs.public_id.history.deleted
            if (
                original_user_id == user_id
                or original_public_id == public_id
                or user_id in old_user_ids
                or public_id in old_public_ids
                or state.dict.get("user_id") == user_id
                or state.dict.get("public_id") == public_id
            ):
                raise UserSessionPendingChanges()


def _locked_user_workspace(
    session: Session,
    connection: Connection,
    user_id: int,
    *,
    public_id: str | None = None,
) -> tuple[object, object]:
    user = connection.execute(
        select(_USER).where(_USER.c.id == user_id).with_for_update(nowait=True)
    ).mappings().one_or_none()
    if user is None:
        raise UserSessionDenied()
    workspace = connection.execute(
        select(_WORKSPACE)
        .where(_WORKSPACE.c.user_id == user_id)
        .with_for_update(nowait=True)
    ).mappings().one_or_none()
    if workspace is None or workspace["user_id"] != user_id:
        raise UserSessionDenied()
    _pending_security(session, user_id, workspace["id"], public_id)
    return user, workspace


def _locked_session(
    connection: Connection, public_id: str, user_id: int
) -> object | None:
    return connection.execute(
        select(_SESSION)
        .where(_SESSION.c.public_id == public_id, _SESSION.c.user_id == user_id)
        .with_for_update(nowait=True)
    ).mappings().one_or_none()


def _run(session: Session, operation: Callable[[Connection], T]) -> T:
    error_type: type[UserSessionError] = UserSessionError
    connection: Connection | None = None
    savepoint = None
    try:
        connection = _connection(session)
        try:
            savepoint = connection.begin_nested()
        except Exception:
            raise UserSessionUnconfirmed() from None
        result = operation(connection)
        savepoint.commit()
        return result
    except UserSessionError as error:
        error_type = type(error)
    except IntegrityError as error:
        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            and getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            in {"uq_user_session_public_id", "uq_user_session_secret_digest"}
        ):
            error_type = UserSessionCollision
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            error_type = UserSessionBusy
    except Exception:
        pass
    if savepoint is not None and connection is not None:
        try:
            if not savepoint.is_active or connection.invalidated or connection.closed:
                raise UserSessionUnconfirmed()
            savepoint.rollback()
            if not session.is_active or not connection.in_transaction():
                raise UserSessionUnconfirmed()
        except Exception:
            error_type = UserSessionUnconfirmed
    raise error_type() from None


def issue(session: Session, user_id: int, *, clock: Clock) -> IssuedUserSession:
    """Issue a session for an existing User and its existing Workspace."""
    def operation(connection: Connection) -> IssuedUserSession:
        _, workspace = _locked_user_workspace(session, connection, user_id)
        now = _time(clock)
        public_id = secrets.token_urlsafe(16)
        secret = secrets.token_urlsafe(32)
        digest = _digest(secret)
        connection.execute(
            _SESSION.insert().values(
                user_id=user_id,
                public_id=public_id,
                secret_digest=digest,
                created_at=now,
                last_access_at=now,
                revoked_at=None,
            )
        )
        return IssuedUserSession(
            user_id=user_id,
            workspace_id=workspace["id"],
            public_id=public_id,
            secret=SecretStr(secret),
        )

    return _run(session, operation)


def authenticate(
    session: Session, public_id: str, secret: str, *, clock: Clock
) -> UserSessionAuthority:
    """Authenticate and renew a session only after fresh locked validation."""
    identifier = _public_id(public_id)
    digest = _digest(secret)

    def operation(connection: Connection) -> UserSessionAuthority:
        user_id = connection.scalar(
            select(_SESSION.c.user_id).where(_SESSION.c.public_id == identifier)
        )
        if user_id is None:
            raise UserSessionDenied()
        _, workspace = _locked_user_workspace(
            session, connection, user_id, public_id=identifier
        )
        row = _locked_session(connection, identifier, user_id)
        if row is None or row["secret_digest"] != digest or row["revoked_at"] is not None:
            raise UserSessionDenied()
        now = _time(clock, row)
        if now >= _utc(row["last_access_at"]) + _INACTIVITY:
            raise UserSessionDenied()
        connection.execute(
            update(_SESSION)
            .where(_SESSION.c.id == row["id"])
            .values(last_access_at=now)
        )
        return UserSessionAuthority(
            user_id=user_id, workspace_id=workspace["id"], public_id=identifier
        )

    return _run(session, operation)


def list_active(
    session: Session, user_id: int, *, clock: Clock
) -> list[UserSessionSummary]:
    """List only active public identifiers owned by one User."""
    def operation(connection: Connection) -> list[UserSessionSummary]:
        _user, _workspace = _locked_user_workspace(session, connection, user_id)
        rows = connection.execute(
            select(_SESSION)
            .where(_SESSION.c.user_id == user_id)
            .with_for_update(nowait=True)
            .order_by(_SESSION.c.created_at, _SESSION.c.id)
        ).mappings().all()
        now = _time_for_rows(clock, rows)
        return [
            UserSessionSummary(
                public_id=row["public_id"],
                created_at=_utc(row["created_at"]),
                last_access_at=_utc(row["last_access_at"]),
            )
            for row in rows
            if row["revoked_at"] is None
            and now < _utc(row["last_access_at"]) + _INACTIVITY
        ]

    return _run(session, operation)


def revoke(
    session: Session, user_id: int, public_id: str, *, clock: Clock
) -> bool:
    """Revoke one own session; unknown and cross-User identifiers are a no-op."""
    identifier = _public_id(public_id)

    def operation(connection: Connection) -> bool:
        _locked_user_workspace(session, connection, user_id, public_id=identifier)
        row = _locked_session(connection, identifier, user_id)
        if row is None or row["revoked_at"] is not None:
            return False
        now = _time(clock, row)
        connection.execute(
            update(_SESSION)
            .where(_SESSION.c.id == row["id"])
            .values(revoked_at=now)
        )
        return True

    return _run(session, operation)


def revoke_all(session: Session, user_id: int, *, clock: Clock) -> int:
    """Revoke every active session owned by one User."""
    def operation(connection: Connection) -> int:
        _locked_user_workspace(session, connection, user_id)
        rows = connection.execute(
            select(_SESSION)
            .where(_SESSION.c.user_id == user_id, _SESSION.c.revoked_at.is_(None))
            .with_for_update(nowait=True)
        ).mappings().all()
        if not rows:
            return 0
        now = _time_for_rows(clock, rows)
        connection.execute(
            update(_SESSION)
            .where(_SESSION.c.user_id == user_id, _SESSION.c.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return len(rows)

    return _run(session, operation)

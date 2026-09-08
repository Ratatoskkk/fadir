"""One-use, browser-bound Google login transaction persistence."""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
import secrets

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import inspect, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, LoginTransaction
from app.services.google_identity import VerifiedGoogleIdentity


Clock = Callable[[], datetime]
_TRANSACTION = LoginTransaction.__table__
_TEN_MINUTES = timedelta(minutes=10)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class LoginTransactionError(RuntimeError):
    message = "login transaction rejected"

    def __init__(self) -> None:
        super().__init__(self.message)


class LoginTransactionInvalid(LoginTransactionError):
    message = "login transaction rejected"


class LoginTransactionExpired(LoginTransactionError):
    message = "login transaction rejected"


class LoginTransactionConsumed(LoginTransactionError):
    message = "login transaction rejected"


class LoginTransactionBusy(LoginTransactionError):
    message = "login transaction is busy"


class LoginTransactionUnsupported(LoginTransactionError):
    message = "login transactions require a supported PostgreSQL caller transaction"


class LoginTransactionCollision(LoginTransactionError):
    message = "login transaction issuance conflict"


class LoginTransactionUnconfirmed(LoginTransactionError):
    message = "login transaction is unconfirmed; verify caller state before further work"


class IssuedLoginTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)
    state: SecretStr = Field(exclude=True, repr=False)
    nonce: SecretStr = Field(exclude=True, repr=False)
    created_at: datetime
    expires_at: datetime


class ConsumedLoginTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime
    issuer: str | None = None
    subject: str | None = None


class VerifiedLoginTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)
    issuer: str
    subject: str
    verified_at: datetime
    expires_at: datetime


def _digest(value: str | SecretStr) -> bytes:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise LoginTransactionInvalid()
    try:
        raw = base64.b64decode(value + "=", altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise LoginTransactionInvalid() from None
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value:
        raise LoginTransactionInvalid()
    return hashlib.sha256(value.encode("ascii")).digest()


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LoginTransactionInvalid()
    return value.astimezone(timezone.utc)


def _time(clock: Clock, row: Mapping[str, object] | None = None) -> datetime:
    now = _utc(clock())
    if row is not None and now < _utc(row["created_at"]):  # type: ignore[arg-type]
        raise LoginTransactionInvalid()
    return now


def _connection(session: Session):
    root = session.get_transaction()
    if root is None or not root.is_active or root.parent is not None or session.in_nested_transaction():
        raise LoginTransactionUnsupported()
    bind = session.get_bind()
    if (bind.dialect.name, bind.dialect.driver) != ("postgresql", "psycopg"):
        raise LoginTransactionUnsupported()
    for mapper in Base.registry.mappers:
        if session.get_bind(mapper=mapper) is not bind:
            raise LoginTransactionUnsupported()
    for obj in (*session.new, *session.dirty, *session.deleted):
        if session.get_bind(mapper=inspect(obj).mapper) is not bind:
            raise LoginTransactionUnsupported()
    connection = session.connection()
    if connection.closed or connection.invalidated or connection.in_nested_transaction():
        raise LoginTransactionUnsupported()
    driver = connection.connection.driver_connection
    if driver.autocommit or driver.info.transaction_status.name not in ("IDLE", "INTRANS"):
        raise LoginTransactionUnsupported()
    if (
        not connection.engine.hide_parameters
        or connection.engine.echo
        or logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.DEBUG)
        or connection.engine.logger.isEnabledFor(logging.DEBUG)
    ):
        raise LoginTransactionUnsupported()
    if connection.get_isolation_level() != "READ COMMITTED":
        raise LoginTransactionUnsupported()
    return connection


def _run(session: Session, operation):
    error_type: type[LoginTransactionError] = LoginTransactionError
    connection = None
    savepoint = None
    try:
        connection = _connection(session)
        try:
            savepoint = connection.begin_nested()
        except Exception:
            raise LoginTransactionUnconfirmed() from None
        result = operation(connection)
        savepoint.commit()
        return result
    except LoginTransactionError as error:
        error_type = type(error)
    except IntegrityError:
        error_type = LoginTransactionCollision
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "55P03":
            error_type = LoginTransactionBusy
    except Exception:
        pass
    if savepoint is not None and connection is not None:
        try:
            if not savepoint.is_active or connection.invalidated or connection.closed:
                raise LoginTransactionUnconfirmed()
            savepoint.rollback()
            if not session.is_active or not connection.in_transaction():
                raise LoginTransactionUnconfirmed()
        except Exception:
            error_type = LoginTransactionUnconfirmed
    raise error_type() from None


def issue(session: Session, *, clock: Clock) -> IssuedLoginTransaction:
    """Issue state and nonce inside the caller's active PostgreSQL transaction."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    state_digest = _digest(state)
    nonce_digest = _digest(nonce)

    def operation(connection):
        now = _time(clock)
        expires_at = now + _TEN_MINUTES
        connection.execute(
            _TRANSACTION.insert().values(
                state_digest=state_digest,
                nonce_digest=nonce_digest,
                created_at=now,
                expires_at=expires_at,
                consumed_at=None,
            )
        )
        return IssuedLoginTransaction(
            state=SecretStr(state),
            nonce=SecretStr(nonce),
            created_at=now,
            expires_at=expires_at,
        )

    return _run(session, operation)

def consume(
    session: Session,
    state: str | SecretStr,
    nonce: str | SecretStr,
    *,
    clock: Clock,
) -> ConsumedLoginTransaction:
    """Consume one matching, unexpired transaction inside the caller transaction."""
    state_digest = _digest(state)
    nonce_digest = _digest(nonce)

    def operation(connection):
        row = connection.execute(
            select(_TRANSACTION)
            .where(_TRANSACTION.c.state_digest == state_digest)
            .with_for_update(nowait=True)
        ).mappings().one_or_none()
        if row is None or row["nonce_digest"] != nonce_digest:
            raise LoginTransactionInvalid()
        now = _time(clock, row)
        if row["consumed_at"] is not None:
            raise LoginTransactionConsumed()
        if now >= _utc(row["expires_at"]):
            raise LoginTransactionExpired()
        connection.execute(
            update(_TRANSACTION)
            .where(_TRANSACTION.c.id == row["id"])
            .values(consumed_at=now)
        )
        return ConsumedLoginTransaction(
            created_at=_utc(row["created_at"]),
            expires_at=_utc(row["expires_at"]),
            consumed_at=now,
        )

    return _run(session, operation)


def verify_pending(
    session: Session,
    state: str | SecretStr,
    nonce: str | SecretStr,
    identity: VerifiedGoogleIdentity,
    *,
    clock: Clock,
) -> VerifiedLoginTransaction:
    """Persist a verified identity without consuming the pending transaction."""
    state_digest = _digest(state)
    nonce_digest = _digest(nonce)

    def operation(connection):
        row = connection.execute(
            select(_TRANSACTION)
            .where(_TRANSACTION.c.state_digest == state_digest)
            .with_for_update(nowait=True)
        ).mappings().one_or_none()
        if row is None or row["nonce_digest"] != nonce_digest:
            raise LoginTransactionInvalid()
        now = _time(clock, row)
        if now >= _utc(row["expires_at"]):
            raise LoginTransactionExpired()
        if row["consumed_at"] is not None:
            raise LoginTransactionConsumed()
        if row["verified_issuer"] is not None:
            if (
                row["verified_issuer"] != identity.issuer
                or row["verified_subject"] != identity.subject
            ):
                raise LoginTransactionInvalid()
            verified_at = _utc(row["verified_at"])
        else:
            verified_at = now
            connection.execute(
                update(_TRANSACTION)
                .where(_TRANSACTION.c.id == row["id"])
                .values(
                    verified_issuer=identity.issuer,
                    verified_subject=identity.subject,
                    verified_at=verified_at,
                )
            )
        return VerifiedLoginTransaction(
            issuer=identity.issuer,
            subject=identity.subject,
            verified_at=verified_at,
            expires_at=_utc(row["expires_at"]),
        )

    return _run(session, operation)


def consume_verified(
    session: Session,
    state: str | SecretStr,
    *,
    clock: Clock,
) -> ConsumedLoginTransaction:
    """Consume a previously verified transaction for the later transition lease."""
    state_digest = _digest(state)

    def operation(connection):
        row = connection.execute(
            select(_TRANSACTION)
            .where(_TRANSACTION.c.state_digest == state_digest)
            .with_for_update(nowait=True)
        ).mappings().one_or_none()
        if row is None or row["verified_issuer"] is None or row["verified_subject"] is None:
            raise LoginTransactionInvalid()
        now = _time(clock, row)
        if now >= _utc(row["expires_at"]):
            raise LoginTransactionExpired()
        if row["consumed_at"] is not None:
            raise LoginTransactionConsumed()
        connection.execute(
            update(_TRANSACTION)
            .where(_TRANSACTION.c.id == row["id"])
            .values(consumed_at=now)
        )
        return ConsumedLoginTransaction(
            created_at=_utc(row["created_at"]),
            expires_at=_utc(row["expires_at"]),
            consumed_at=now,
            issuer=row["verified_issuer"],
            subject=row["verified_subject"],
        )

    return _run(session, operation)

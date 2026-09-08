"""Atomic Claim and Portfolio Transfer transitions after Google verification."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app import models
from app.services import guest_access, login_transactions, user_sessions


Clock = Callable[[], datetime]


class AuthorityLike(Protocol):
    mode: str
    workspace_id: int


class GoogleLoginTransitionError(RuntimeError):
    message = "Google login transition rejected"

    def __init__(self) -> None:
        super().__init__(self.message)


class GoogleLoginTransitionUnsupported(GoogleLoginTransitionError):
    message = "Google login transition requires a supported PostgreSQL caller transaction"


class GoogleLoginTransitionBusy(GoogleLoginTransitionError):
    message = "Google login transition is busy"


class GoogleLoginTransitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    action: Literal["claim", "transfer"]
    public_id: str = Field(exclude=True, repr=False)
    secret: SecretStr = Field(exclude=True, repr=False)


_TRANSACTION = models.LoginTransaction.__table__
_IDENTITY = models.LoginIdentity.__table__
_USER = models.User.__table__
_WORKSPACE = models.Workspace.__table__
_GUEST = models.GuestAccess.__table__
_PORTFOLIO = models.Portfolio.__table__


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GoogleLoginTransitionError()
    return value.astimezone(timezone.utc)


def _name(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value or value != value.strip() or len(value) > 128:
        raise GoogleLoginTransitionError()
    return value


def _connection(session: Session):
    root = session.get_transaction()
    if root is None or not root.is_active or root.parent is not None or session.in_nested_transaction():
        raise GoogleLoginTransitionUnsupported()
    connection = session.connection()
    if (
        connection.closed
        or connection.invalidated
        or connection.in_nested_transaction()
        or (connection.engine.dialect.name, connection.engine.dialect.driver)
        != ("postgresql", "psycopg")
        or not connection.engine.hide_parameters
        or connection.engine.echo
        or logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.DEBUG)
        or connection.engine.logger.isEnabledFor(logging.DEBUG)
    ):
        raise GoogleLoginTransitionUnsupported()
    return connection


def _pending_identity(connection, state: str, clock: Clock):
    state_digest = login_transactions._digest(state)
    row = connection.execute(
        select(_TRANSACTION)
        .where(_TRANSACTION.c.state_digest == state_digest)
        .with_for_update(nowait=True)
    ).mappings().one_or_none()
    if (
        row is None
        or row["verified_issuer"] is None
        or row["verified_subject"] is None
        or row["verified_at"] is None
        or row["consumed_at"] is not None
    ):
        raise GoogleLoginTransitionError()
    now = _utc(clock())
    if now < _utc(row["created_at"]) or now >= _utc(row["expires_at"]):
        raise GoogleLoginTransitionError()
    return row, row["verified_issuer"], row["verified_subject"], now


def _guest(connection, authority: AuthorityLike, guest_secret: str, now: datetime):
    if getattr(authority, "mode", None) != "guest":
        raise GoogleLoginTransitionError()
    digest = guest_access._digest(guest_secret)
    workspace = connection.execute(
        select(_WORKSPACE).where(_WORKSPACE.c.id == authority.workspace_id).with_for_update(nowait=True)
    ).mappings().one_or_none()
    guest = connection.execute(
        select(_GUEST).where(_GUEST.c.secret_digest == digest).with_for_update(nowait=True)
    ).mappings().one_or_none()
    if workspace is None or guest is None or guest["workspace_id"] != authority.workspace_id:
        raise GoogleLoginTransitionError()
    if (
        workspace is None
        or workspace["user_id"] is not None
        or guest["revoked_at"] is not None
        or now >= _utc(guest["last_access_at"]) + timedelta(days=90)
    ):
        raise GoogleLoginTransitionError()
    return workspace


def _transfer_portfolios(
    connection, guest_workspace_id: int, user_workspace_id: int, rename: str | None
) -> list[tuple[int, str | None]]:
    guest_rows = connection.execute(
        select(_PORTFOLIO)
        .where(_PORTFOLIO.c.workspace_id == guest_workspace_id)
        .with_for_update(nowait=True)
        .order_by(_PORTFOLIO.c.id)
    ).mappings().all()
    target_rows = connection.execute(
        select(_PORTFOLIO)
        .where(_PORTFOLIO.c.workspace_id == user_workspace_id)
        .with_for_update(nowait=True)
        .order_by(_PORTFOLIO.c.id)
    ).mappings().all()
    target_names = {row["name"] for row in target_rows}
    guest_names = {row["name"] for row in guest_rows}
    conflicts = [row for row in guest_rows if row["name"] in target_names]
    replacement = _name(rename)
    if conflicts:
        if len(conflicts) != 1 or replacement is None or replacement in target_names or replacement in guest_names:
            raise GoogleLoginTransitionError()
        old_name = conflicts[0]["name"]
    elif replacement is not None:
        raise GoogleLoginTransitionError()
    else:
        old_name = None
    return [
        (row["id"], replacement if row["name"] == old_name else None)
        for row in guest_rows
    ]


def transition(
    session: Session,
    authority: AuthorityLike,
    state: str,
    guest_secret: str,
    action: Literal["claim", "transfer"],
    *,
    rename: str | None = None,
    clock: Clock,
) -> GoogleLoginTransitionResult:
    """Apply one explicit transition inside the caller-owned root transaction."""
    connection = _connection(session)
    try:
        row, issuer, subject, now = _pending_identity(connection, state, clock)
        guest_workspace = _guest(connection, authority, guest_secret, now)
        identity = connection.execute(
            select(_IDENTITY).where(
                _IDENTITY.c.issuer == issuer, _IDENTITY.c.subject == subject
            ).with_for_update(nowait=True)
        ).mappings().one_or_none()
        transfer_plan: list[tuple[int, str | None]] = []
        if action == "claim":
            if identity is not None:
                raise GoogleLoginTransitionError()
            replacement = _name(rename)
            if replacement is not None:
                raise GoogleLoginTransitionError()
            user_id = None
        elif action == "transfer":
            if identity is None:
                raise GoogleLoginTransitionError()
            user = connection.execute(
                select(_USER).where(_USER.c.id == identity["user_id"]).with_for_update(nowait=True)
            ).mappings().one_or_none()
            target_workspace = connection.execute(
                select(_WORKSPACE)
                .where(_WORKSPACE.c.user_id == identity["user_id"])
                .with_for_update(nowait=True)
            ).mappings().one_or_none()
            if user is None or target_workspace is None:
                raise GoogleLoginTransitionError()
            transfer_plan = _transfer_portfolios(
                connection, guest_workspace["id"], target_workspace["id"], rename
            )
            user_id = identity["user_id"]
        else:
            raise GoogleLoginTransitionError()

        consumed = login_transactions.consume_verified(session, state, clock=lambda: now)
        if consumed.issuer != issuer or consumed.subject != subject:
            raise GoogleLoginTransitionError()
        guest_access.revoke(session, guest_secret, clock=lambda: now)
        if action == "claim":
            user_id = connection.scalar(
                insert(_USER)
                .values(created_at=now.replace(tzinfo=None), updated_at=now.replace(tzinfo=None))
                .returning(_USER.c.id)
            )
            connection.execute(
                insert(_IDENTITY).values(
                    user_id=user_id,
                    issuer=issuer,
                    subject=subject,
                    created_at=now.replace(tzinfo=None),
                    updated_at=now.replace(tzinfo=None),
                )
            )
            connection.execute(
                update(_WORKSPACE)
                .where(_WORKSPACE.c.id == guest_workspace["id"])
                .values(user_id=user_id, updated_at=now.replace(tzinfo=None))
            )
        else:
            for portfolio_id, new_name in transfer_plan:
                values = {"workspace_id": target_workspace["id"]}
                if new_name is not None:
                    values["name"] = new_name
                connection.execute(
                    update(_PORTFOLIO).where(_PORTFOLIO.c.id == portfolio_id).values(**values)
                )
        issued = user_sessions.issue(session, user_id, clock=lambda: now)
        session.expire_all()
        return GoogleLoginTransitionResult(
            action=action, public_id=issued.public_id, secret=issued.secret
        )
    except GoogleLoginTransitionError:
        raise
    except Exception:
        raise GoogleLoginTransitionError() from None

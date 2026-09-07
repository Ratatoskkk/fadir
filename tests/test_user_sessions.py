from __future__ import annotations

import base64
from datetime import datetime, timezone
import importlib

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import make_engine


VALID_SECRET = base64.urlsafe_b64encode(b"b" * 32).decode("ascii").rstrip("=")


def access_module():
    return importlib.import_module("app.services.user_sessions")


def test_user_session_model_exists() -> None:
    assert hasattr(models, "UserSession"), "UserSession model is absent"


def test_user_session_service_exists() -> None:
    service = access_module()

    assert all(
        callable(getattr(service, name))
        for name in ("issue", "authenticate", "list_active", "revoke", "revoke_all")
    )


def test_user_session_schema_contract() -> None:
    table = models.UserSession.__table__

    assert table.name == "user_session"
    assert {column.name for column in table.columns} == {
        "id",
        "user_id",
        "public_id",
        "secret_digest",
        "created_at",
        "last_access_at",
        "revoked_at",
    }
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_user_session_public_id", "uq_user_session_secret_digest"}
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_user_session_public_id_length",
        "ck_user_session_digest_length",
    }
    assert table.c.created_at.type.timezone
    assert table.c.last_access_at.type.timezone
    assert table.c.revoked_at.type.timezone
    assert not table.c.secret_digest.nullable
    assert table.c.revoked_at.nullable


def test_sqlite_session_constraints_and_user_cascade() -> None:
    engine = make_engine("sqlite:///:memory:")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as session:
            user = models.User()
            workspace = models.Workspace(user=user)
            session.add(workspace)
            session.flush()
            session.add(
                models.UserSession(
                    user_id=user.id,
                    public_id="A" * 22,
                    secret_digest=b"x" * 32,
                    created_at=now,
                    last_access_at=now,
                )
            )
            session.commit()
            with pytest.raises(IntegrityError):
                session.add(
                    models.UserSession(
                        user_id=user.id,
                        public_id="B" * 21,
                        secret_digest=b"y" * 32,
                        created_at=now,
                        last_access_at=now,
                    )
                )
                session.flush()
            session.rollback()
            session.delete(user)
            session.commit()
            assert session.scalars(select(models.UserSession)).all() == []
    finally:
        engine.dispose()


def test_dirty_session_reassignment_is_pending_security_change() -> None:
    service = access_module()
    engine = make_engine("sqlite:///:memory:")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as session:
            first = models.User(workspace=models.Workspace())
            second = models.User(workspace=models.Workspace())
            session.add_all([first, second])
            session.flush()
            first_id = first.id
            first_workspace_id = first.workspace.id
            row = models.UserSession(
                user_id=first.id,
                public_id="A" * 22,
                secret_digest=b"x" * 32,
                created_at=now,
                last_access_at=now,
            )
            session.add(row)
            session.commit()
            row.user_id = second.id
            with pytest.raises(service.UserSessionPendingChanges):
                service._pending_security(session, first_id, first_workspace_id, "A" * 22)
    finally:
        engine.dispose()




@pytest.mark.parametrize(
    ("operation", "arguments"),
    [
        ("issue", (1,)),
        ("authenticate", ("A" * 22, VALID_SECRET)),
        ("list_active", (1,)),
        ("revoke", (1, "A" * 22)),
        ("revoke_all", (1,)),
    ],
)
def test_sqlite_service_is_rejected_without_sql_or_caller_flush(
    operation: str, arguments: tuple[object, ...]
) -> None:
    service = access_module()
    engine = make_engine("sqlite:///:memory:")
    try:
        with Session(engine) as session, session.begin():
            pending = models.User()
            session.add(pending)
            calls: list[bool] = []

            def capture(*_args: object) -> None:
                calls.append(True)

            event.listen(engine, "before_cursor_execute", capture)
            try:
                with pytest.raises(service.UserSessionUnsupported):
                    getattr(service, operation)(
                        session, *arguments, clock=lambda: datetime.now(timezone.utc)
                    )
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            assert calls == []
            assert pending in session.new
            session.expunge(pending)
    finally:
        engine.dispose()

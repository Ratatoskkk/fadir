"""Local schema and rejection proof; access behavior needs real PostgreSQL."""

import importlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import make_engine


def access_module():
    return importlib.import_module("app.services.guest_access")


def test_guest_access_model_exists():
    assert hasattr(models, "GuestAccess"), "GuestAccess model is absent"


def test_guest_access_service_exists():
    service = access_module()
    assert all(callable(getattr(service, name)) for name in ("issue", "require", "revoke"))


def test_guest_schema_contract():
    table = models.GuestAccess.__table__
    assert table.name == "guest_access"
    assert list(table.primary_key.columns.keys()) == ["workspace_id"]
    assert {c.name for c in table.columns} == {
        "workspace_id", "secret_digest", "created_at", "last_access_at", "revoked_at"
    }
    assert {c.name for c in table.constraints if isinstance(c, UniqueConstraint)} == {
        "uq_guest_access_secret_digest"
    }
    assert {c.name for c in table.constraints if isinstance(c, CheckConstraint)} == {
        "ck_guest_access_digest_length"
    }
    for name in ("created_at", "last_access_at", "revoked_at"):
        assert table.c[name].type.timezone
    assert not table.c.secret_digest.nullable
    assert table.c.revoked_at.nullable


@pytest.mark.parametrize("size", [0, 31, 33])
def test_sqlite_digest_length_constraint(size):
    engine = make_engine("sqlite:///:memory:")
    try:
        models.Base.metadata.create_all(engine)
        with Session(engine) as session:
            workspace = models.Workspace()
            session.add(workspace)
            session.flush()
            session.add(models.GuestAccess(workspace_id=workspace.id,
                secret_digest=b"x" * size, created_at=datetime.now(timezone.utc),
                last_access_at=datetime.now(timezone.utc)))
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        engine.dispose()


def test_sqlite_guest_constraints_and_cascade():
    engine = make_engine("sqlite:///:memory:")
    try:
        models.Base.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        with engine.begin() as connection:
            for identifier in (1, 2):
                connection.execute(models.Workspace.__table__.insert(), {"id": identifier})
            connection.execute(models.GuestAccess.__table__.insert(), dict(
                workspace_id=1, secret_digest=b"x" * 32, created_at=now, last_access_at=now))
        for workspace_id, digest in ((2, b"x" * 32), (999, b"y" * 32)):
            with pytest.raises(IntegrityError), engine.begin() as connection:
                connection.execute(models.GuestAccess.__table__.insert(), dict(
                    workspace_id=workspace_id, secret_digest=digest,
                    created_at=now, last_access_at=now))
        with engine.begin() as connection:
            connection.execute(models.Workspace.__table__.delete().where(models.Workspace.id == 1))
            assert connection.execute(models.GuestAccess.__table__.select()).all() == []
    finally:
        engine.dispose()


@pytest.mark.parametrize("operation", ["issue", "require", "revoke"])
def test_sqlite_service_is_rejected_without_sql_or_caller_flush(operation):
    service = access_module()
    engine = make_engine("sqlite:///:memory:")
    try:
        with Session(engine) as session, session.begin():
            pending = models.Workspace()
            session.add(pending)
            calls = []
            event.listen(engine, "before_cursor_execute", lambda *args: calls.append(True))
            with pytest.raises(service.GuestAccessUnsupported):
                if operation == "issue":
                    service.issue(session, clock=lambda: datetime.now(timezone.utc))
                else:
                    getattr(service, operation)(session, "A" * 43,
                                               clock=lambda: datetime.now(timezone.utc))
            assert calls == []
            assert pending in session.new
            session.expunge(pending)
    finally:
        engine.dispose()

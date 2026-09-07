"""Opt-in PostgreSQL proof for internal User Session authority."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import Barrier
import traceback
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Instrument, User, UserSession, Workspace
from app.services import user_sessions as access
from test_postgresql_migrations import _selected_test_url


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


class _CleanupGate:
    def __init__(self) -> None:
        self.call_passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.call_passed = call.excinfo is None


def _drop_owned(connection, schema, marker, oid, database) -> None:
    if re.fullmatch(r"session1_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("Cleanup refused: invalid task schema")
    record = connection.execute(
        text(
            "SELECT current_database(), n.oid, "
            "n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), "
            "pg_catalog.obj_description(n.oid, 'pg_namespace') "
            "FROM pg_catalog.pg_namespace n WHERE nspname=:schema"
        ),
        {"schema": schema},
    ).one_or_none()
    if record is None or tuple(record) != (database, oid, True, marker):
        raise RuntimeError("Cleanup refused: ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def database(monkeypatch, request):
    __tracebackhide__ = True
    url = _selected_test_url()
    schema, marker = "session1_" + uuid4().hex, "SESSION-1:" + uuid4().hex
    engine = create_engine(url, poolclass=None, hide_parameters=True)
    scoped = None
    oid = None
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{marker}'"))
            oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"),
                {"name": schema},
            )
        request.node.user_properties.extend(
            [("schema", schema), ("schema_oid", str(oid)), ("marker", marker)]
        )
        scoped_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog -clock_timeout=2s -cstatement_timeout=5s"}
        )
        with monkeypatch.context() as env:
            env.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "migrations"))
            command.upgrade(config, "head")
        scoped = create_engine(scoped_url, poolclass=None, hide_parameters=True)
        yield scoped
    finally:
        if scoped is not None:
            scoped.dispose()
        try:
            if oid is not None and gate.call_passed:
                with engine.begin() as connection:
                    _drop_owned(connection, schema, marker, oid, url.database)
                with engine.connect() as connection:
                    assert connection.scalar(
                        text("SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname=:name"),
                        {"name": schema},
                    ) == 0
        finally:
            engine.dispose()
            request.config.pluginmanager.unregister(gate)


def issued(database, now=NOW):
    with Session(database) as session, session.begin():
        user = User(workspace=Workspace())
        session.add(user)
        session.flush()
        return access.issue(session, user.id, clock=lambda: now)


def row_state(database, public_id):
    with database.connect() as connection:
        return dict(
            connection.execute(
                select(UserSession.__table__).where(UserSession.public_id == public_id)
            ).mappings().one()
        )


def counts(connection):
    return tuple(
        connection.scalar(select(func.count()).select_from(model))
        for model in (User, Workspace, UserSession)
    )


@pytest.mark.live
def test_issue_is_secret_safe_and_caller_owned(database, caplog):
    with Session(database) as session:
        root = session.begin()
        user = User(workspace=Workspace())
        session.add(user)
        session.flush()
        result = access.issue(session, user.id, clock=lambda: NOW)
        secret = result.secret.get_secret_value()
        assert session.get_transaction() is root and root.is_active
        assert len(result.public_id) == 22 and len(secret) == 43
        assert secret not in repr(result)
        assert "secret" not in result.model_dump()
        assert "secret" not in json.loads(result.model_dump_json())
        assert secret not in caplog.text
        row = session.connection().execute(
            select(UserSession.__table__).where(UserSession.public_id == result.public_id)
        ).mappings().one()
        assert row["secret_digest"] == hashlib.sha256(
            secret.encode("ascii")
        ).digest()
        assert row["created_at"] == NOW
        with database.connect() as connection:
            assert connection.execute(
                select(UserSession.__table__).where(UserSession.public_id == result.public_id)
            ).mappings().one_or_none() is None
        root.rollback()
    with database.connect() as connection:
        assert counts(connection) == (0, 0, 0)


@pytest.mark.live
def test_issue_requires_existing_user_workspace(database):
    with Session(database) as session, session.begin():
        with pytest.raises(access.UserSessionDenied):
            access.issue(session, 999, clock=lambda: NOW)
        user = User()
        session.add(user)
        session.flush()
        with pytest.raises(access.UserSessionDenied):
            access.issue(session, user.id, clock=lambda: NOW)


@pytest.mark.live
@pytest.mark.parametrize(
    "offset",
    [timedelta(days=30) - timedelta(microseconds=1), timedelta(days=30)],
)
def test_exact_inactivity_expiry(database, offset):
    result = issued(database)
    with Session(database) as session, session.begin():
        if offset < timedelta(days=30):
            assert access.authenticate(
                session,
                result.public_id,
                result.secret.get_secret_value(),
                clock=lambda: NOW + offset,
            ).public_id == result.public_id
        else:
            with pytest.raises(access.UserSessionDenied):
                access.authenticate(
                    session,
                    result.public_id,
                    result.secret.get_secret_value(),
                    clock=lambda: NOW + offset,
                )


@pytest.mark.live
def test_authentication_renews_only_successful_access(database):
    result = issued(database)
    with Session(database) as session, session.begin():
        with pytest.raises(access.UserSessionDenied):
            access.authenticate(session, result.public_id, "A" * 43, clock=lambda: NOW)
    assert row_state(database, result.public_id)["last_access_at"] == NOW
    with Session(database) as session, session.begin():
        access.authenticate(
            session,
            result.public_id,
            result.secret.get_secret_value(),
            clock=lambda: NOW + timedelta(days=1),
        )
    assert row_state(database, result.public_id)["last_access_at"] == NOW + timedelta(days=1)


@pytest.mark.live
def test_list_and_revocation_are_user_scoped(database):
    first = issued(database)
    second = issued(database)
    with Session(database) as session, session.begin():
        user = session.scalar(select(User).where(User.id == first.user_id))
        assert user is not None
        listed = access.list_active(session, user.id, clock=lambda: NOW)
        assert [row.public_id for row in listed] == [first.public_id]
        assert access.revoke(session, user.id, second.public_id, clock=lambda: pytest.fail()) is False
        assert access.revoke(session, user.id, "A" * 22, clock=lambda: pytest.fail()) is False
        assert access.revoke(session, user.id, first.public_id, clock=lambda: NOW + timedelta(days=2))
        assert access.revoke(session, user.id, first.public_id, clock=lambda: pytest.fail()) is False
    assert row_state(database, first.public_id)["last_access_at"] == NOW
    assert row_state(database, first.public_id)["revoked_at"] == NOW + timedelta(days=2)
    with Session(database) as session, session.begin():
        assert access.revoke_all(session, second.user_id, clock=lambda: NOW + timedelta(days=3)) == 1
    assert row_state(database, second.public_id)["revoked_at"] == NOW + timedelta(days=3)


@pytest.mark.live
@pytest.mark.parametrize("operation", ["list_active", "revoke_all"])
def test_bulk_operations_reject_backward_clock_without_touch(database, operation):
    result = issued(database)
    with Session(database) as session, session.begin():
        with pytest.raises(access.UserSessionClockError):
            if operation == "list_active":
                access.list_active(
                    session,
                    result.user_id,
                    clock=lambda: NOW - timedelta(microseconds=1),
                )
            else:
                access.revoke_all(
                    session,
                    result.user_id,
                    clock=lambda: NOW - timedelta(microseconds=1),
                )
    state = row_state(database, result.public_id)
    assert state["created_at"] == NOW
    assert state["last_access_at"] == NOW
    assert state["revoked_at"] is None


@pytest.mark.live
@pytest.mark.parametrize("collision", ["public_id", "secret_digest"])
def test_collision_preserves_pending_state(database, monkeypatch, collision):
    first = issued(database)
    distinct_public = base64.urlsafe_b64encode(b"p" * 16).decode("ascii").rstrip("=")
    distinct_secret = base64.urlsafe_b64encode(b"s" * 32).decode("ascii").rstrip("=")

    def token_urlsafe(size):
        if collision == "public_id":
            return first.public_id if size == 16 else distinct_secret
        return distinct_public if size == 16 else first.secret.get_secret_value()

    monkeypatch.setattr(access.secrets, "token_urlsafe", token_urlsafe)
    with Session(database) as session:
        root = session.begin()
        pending = Instrument(
            ticker="PENDING", exchange="SYN", yf_symbol="PENDING", currency="TRY", name="Synthetic"
        )
        session.add(pending)
        with pytest.raises(access.UserSessionCollision) as caught:
            access.issue(session, first.user_id, clock=lambda: NOW)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert first.public_id not in str(caught.value)
        assert pending in session.new and pending.id is None
        assert root.is_active
        root.rollback()


@pytest.mark.live
def test_database_errors_are_sanitized_and_savepoint_recovers(database):
    result = issued(database)
    with Session(database) as session, session.begin():
        connection = session.connection()

        def fail(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.startswith("UPDATE user_session"):
                raise RuntimeError(result.secret.get_secret_value())

        event.listen(connection, "before_cursor_execute", fail)
        try:
            with pytest.raises(access.UserSessionError) as caught:
                access.authenticate(
                    session,
                    result.public_id,
                    result.secret.get_secret_value(),
                    clock=lambda: NOW + timedelta(days=1),
                )
        finally:
            event.remove(connection, "before_cursor_execute", fail)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert result.secret.get_secret_value() not in "".join(
            traceback.format_exception(caught.value)
        )
        assert connection.scalar(select(1)) == 1


@pytest.mark.live
def test_ordered_session_lock_busy_recovery(database):
    result = issued(database)
    barrier = Barrier(2, timeout=8)

    def holder():
        with Session(database) as session, session.begin():
            access.authenticate(
                session, result.public_id, result.secret.get_secret_value(), clock=lambda: NOW
            )
            barrier.wait()
            barrier.wait()

    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(holder)
        barrier.wait()
        with Session(database) as contender, contender.begin():
            with pytest.raises(access.UserSessionBusy):
                access.revoke(contender, result.user_id, result.public_id, clock=lambda: NOW)
            assert contender.connection().scalar(select(1)) == 1
        barrier.wait()
        future.result(timeout=8)


def test_cleanup_rejects_non_task_schema():
    with pytest.raises(RuntimeError, match="invalid task schema"):
        _drop_owned(None, "public", "marker", 1, "fadir_test")


def test_cleanup_removes_only_verified_schema():
    schema = "session1_" + "a" * 32
    connection = MagicMock()
    connection.execute.return_value.one_or_none.return_value = (
        "fadir_test",
        123,
        True,
        "token",
    )
    _drop_owned(connection, schema, "token", 123, "fadir_test")
    assert connection.execute.call_count == 2
    assert str(connection.execute.call_args.args[0]) == f'DROP SCHEMA "{schema}" CASCADE'

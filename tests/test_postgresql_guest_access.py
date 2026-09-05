"""Real PostgreSQL proof for the internal Guest access contract."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import inspect as python_inspect
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
from sqlalchemy import create_engine, event, func, pool, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import GuestAccess, Instrument, User, Workspace, Portfolio
from app.services import guest_access as access
from test_postgresql_migrations import _selected_test_url


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


class _CleanupGate:
    def __init__(self):
        self.call_passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        if call.when == "call":
            self.call_passed = call.excinfo is None


def _drop_owned(connection, schema, marker, oid, database):
    if re.fullmatch(r"id1_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("Cleanup refused: invalid task schema")
    record = connection.execute(text(
        "SELECT current_database(), n.oid, "
        "n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), "
        "pg_catalog.obj_description(n.oid, 'pg_namespace') "
        "FROM pg_catalog.pg_namespace n WHERE nspname=:schema"
    ), {"schema": schema}).one_or_none()
    if record is None or tuple(record) != (database, oid, True, marker):
        raise RuntimeError("Cleanup refused: ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def database(monkeypatch, request):
    __tracebackhide__ = True
    url = _selected_test_url()
    schema, marker = "id1_" + uuid4().hex, "ID-1:" + uuid4().hex
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    scoped = None
    oid = None
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{marker}'"))
            oid = connection.scalar(text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"),
                                    {"name": schema})
        request.node.user_properties.extend([("schema", schema), ("schema_oid", str(oid)), ("marker", marker)])
        scoped_url = url.update_query_dict({"options":
            f"-csearch_path={schema},pg_catalog -clock_timeout=2s -cstatement_timeout=5s"})
        with monkeypatch.context() as env:
            env.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "migrations"))
            command.upgrade(config, "head")
        scoped = create_engine(scoped_url, poolclass=pool.NullPool, hide_parameters=True)
        yield scoped
    finally:
        if scoped is not None:
            scoped.dispose()
        try:
            if oid is not None and gate.call_passed:
                with engine.begin() as connection:
                    _drop_owned(connection, schema, marker, oid, url.database)
                with engine.connect() as connection:
                    assert connection.scalar(text(
                        "SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname=:name"
                    ), {"name": schema}) == 0
        finally:
            engine.dispose()
            request.config.pluginmanager.unregister(gate)


def issued(database, now=NOW):
    with Session(database) as session, session.begin():
        return access.issue(session, clock=lambda: now)


def row_state(database, workspace_id):
    with database.connect() as connection:
        return dict(connection.execute(select(GuestAccess.__table__).where(
            GuestAccess.workspace_id == workspace_id)).mappings().one())


def counts(connection):
    return tuple(connection.scalar(select(func.count()).select_from(model))
                 for model in (User, Workspace, Portfolio, GuestAccess))


@pytest.mark.live
def test_issue_is_secret_safe_and_caller_owned(database, caplog):
    with Session(database) as session:
        root = session.begin()
        result = access.issue(session, clock=lambda: NOW)
        assert session.get_transaction() is root and root.is_active
        assert counts(session.connection()) == (0, 1, 0, 1)
        secret = result.secret.get_secret_value()
        assert len(secret) == 43
        assert secret not in repr(result)
        assert "secret" not in result.model_dump()
        assert "secret" not in json.loads(result.model_dump_json())
        assert secret not in caplog.text
        row = session.connection().execute(select(GuestAccess.__table__)).mappings().one()
        assert row["secret_digest"] == hashlib.sha256(secret.encode("ascii")).digest()
        assert row["created_at"] == row["last_access_at"] == NOW
        root.rollback()
    with database.connect() as connection:
        assert counts(connection) == (0, 0, 0, 0)
    retained = issued(database)
    assert row_state(database, retained.workspace_id)["revoked_at"] is None


@pytest.mark.live
def test_collision_preserves_unrelated_pending_and_flushed_work(database, monkeypatch):
    token = "A" * 43
    monkeypatch.setattr(access.secrets, "token_urlsafe", lambda size: token)
    issued(database)
    with Session(database) as session:
        root = session.begin()
        flushed = User()
        session.add(flushed)
        session.flush()
        pending = Instrument(ticker="PENDING", exchange="SYN", yf_symbol="PENDING",
                             currency="TRY", name="Synthetic")
        session.add(pending)
        with pytest.raises(access.GuestAccessCollision) as caught:
            access.issue(session, clock=lambda: NOW)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        assert token not in str(caught.value)
        assert pending in session.new and pending.id is None
        assert counts(session.connection()) == (1, 1, 0, 1)
        assert root.is_active and session.get_transaction() is root
        root.commit()
    with database.connect() as connection:
        assert counts(connection) == (1, 1, 0, 1)
        assert connection.scalar(select(func.count()).select_from(Instrument)) == 1


@pytest.mark.live
@pytest.mark.parametrize("token", [None, 1, b"A" * 43, "", "A" * 42, "A" * 44,
                                  "A" * 10000, "é" * 43, "+" * 43, "A" * 42 + "B"])
def test_malformed_token_never_reads_security_rows(database, token):
    with Session(database) as session, session.begin():
        statements = []
        event.listen(session.connection(), "before_cursor_execute",
                     lambda conn, cursor, sql, *args: statements.append(sql))
        with pytest.raises(access.GuestAccessDenied):
            access.require(session, token, clock=lambda: NOW)
        assert not any("guest_access" in sql.lower() for sql in statements)
        assert session.connection().scalar(select(1)) == 1


@pytest.mark.live
def test_unknown_token_is_denied(database):
    with Session(database) as session, session.begin():
        with pytest.raises(access.GuestAccessDenied):
            access.require(session, "A" * 43, clock=lambda: NOW)


@pytest.mark.live
@pytest.mark.parametrize("offset,allowed", [(timedelta(days=90) - timedelta(microseconds=1), True),
                                          (timedelta(days=90), False),
                                          (timedelta(days=91), False)])
def test_exact_expiry(database, offset, allowed):
    result = issued(database)
    with Session(database) as session, session.begin():
        if allowed:
            assert access.require(session, result.secret.get_secret_value(),
                                  clock=lambda: NOW + offset).workspace_id == result.workspace_id
        else:
            with pytest.raises(access.GuestAccessDenied):
                access.require(session, result.secret.get_secret_value(), clock=lambda: NOW + offset)
    assert row_state(database, result.workspace_id)["last_access_at"] == (NOW + offset if allowed else NOW)


@pytest.mark.live
def test_sliding_utc_clock_after_locks_and_rollback(database):
    result = issued(database)
    seen = []
    def clock():
        assert len(seen) == 2
        return (NOW + timedelta(days=89)).astimezone(timezone(timedelta(hours=9)))
    with Session(database) as session:
        root = session.begin()
        connection = session.connection()
        connection.execute(text("SET LOCAL TIME ZONE 'Asia/Tokyo'"))
        event.listen(connection, "after_cursor_execute",
                     lambda conn, cursor, sql, *args: seen.append(sql) if "FOR UPDATE" in sql else None)
        access.require(session, result.secret.get_secret_value(), clock=clock)
        root.rollback()
    assert row_state(database, result.workspace_id)["last_access_at"] == NOW
    for days in (89, 178):
        with Session(database) as session, session.begin():
            session.connection().execute(text("SET LOCAL TIME ZONE 'Asia/Tokyo'"))
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=days))
    assert row_state(database, result.workspace_id)["last_access_at"] == NOW + timedelta(days=178)


@pytest.mark.live
@pytest.mark.parametrize("bad_time", [NOW.replace(tzinfo=None), NOW - timedelta(microseconds=1)])
def test_bad_clock_is_rejected_without_touch(database, bad_time):
    result = issued(database)
    with Session(database) as session, session.begin():
        with pytest.raises(access.GuestAccessClockError):
            access.require(session, result.secret.get_secret_value(), clock=lambda: bad_time)
    assert row_state(database, result.workspace_id)["last_access_at"] == NOW


@pytest.mark.live
def test_backward_time_after_touch_is_rejected(database):
    result = issued(database)
    with Session(database) as session, session.begin():
        access.require(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=2))
    with Session(database) as session, session.begin():
        with pytest.raises(access.GuestAccessClockError):
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=1))


@pytest.mark.live
def test_token_self_revoke_is_idempotent_without_touch(database):
    result, other = issued(database), issued(database)
    with Session(database) as session, session.begin():
        assert access.revoke(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=91))
    with Session(database) as session, session.begin():
        assert access.revoke(session, result.secret.get_secret_value(), clock=lambda: pytest.fail("clock called")) is False
        with pytest.raises(access.GuestAccessDenied):
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW)
        access.require(session, other.secret.get_secret_value(), clock=lambda: NOW)
    assert row_state(database, result.workspace_id)["last_access_at"] == NOW
    assert row_state(database, other.workspace_id)["revoked_at"] is None


def simulate_claim(session, identifier):
    connection = session.connection()
    connection.execute(select(Workspace.id).where(Workspace.id == identifier).with_for_update(nowait=True))
    connection.execute(select(GuestAccess.workspace_id).where(
        GuestAccess.workspace_id == identifier).with_for_update(nowait=True))
    user_id = connection.scalar(User.__table__.insert().values().returning(User.id))
    connection.execute(update(Workspace.__table__).where(Workspace.id == identifier).values(user_id=user_id))
    connection.execute(update(GuestAccess.__table__).where(
        GuestAccess.workspace_id == identifier).values(revoked_at=NOW + timedelta(days=1)))


@pytest.mark.live
@pytest.mark.parametrize("change", ["revoke", "claim", "attach_only"])
def test_stale_orm_cache_cannot_authorize(database, change):
    result = issued(database)
    with Session(database, expire_on_commit=False) as stale:
        workspace = stale.get(Workspace, result.workspace_id)
        guest = stale.get(GuestAccess, result.workspace_id)
        stale.commit()
        with Session(database) as writer, writer.begin():
            if change == "revoke":
                access.revoke(writer, result.secret.get_secret_value(), clock=lambda: NOW)
            else:
                simulate_claim(writer, result.workspace_id)
                if change == "attach_only":
                    writer.connection().execute(update(GuestAccess.__table__).values(revoked_at=None))
        assert workspace.user_id is None and guest.revoked_at is None
        with stale.begin():
            with pytest.raises(access.GuestAccessDenied):
                access.require(stale, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=1))


@pytest.mark.live
@pytest.mark.parametrize("model", [Workspace, GuestAccess, "move_guest"])
def test_affected_pending_changes_are_preserved_and_rejected(database, model):
    result = issued(database)
    with Session(database) as session:
        root = session.begin()
        row = session.get(GuestAccess if model == "move_guest" else model, result.workspace_id)
        if model == "move_guest":
            row.workspace = Workspace()
        elif model is Workspace:
            row.updated_at = NOW + timedelta(days=2)
        else:
            row.last_access_at = NOW + timedelta(days=2)
        with pytest.raises(access.GuestAccessPendingChanges):
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW)
        assert row in session.dirty and root.is_active
        root.rollback()
    assert row_state(database, result.workspace_id)["last_access_at"] == NOW


@pytest.mark.live
@pytest.mark.parametrize("mode", ["no_root", "nested", "autocommit", "repeatable_read",
                                  "invalidated", "multiple_binds", "visible_parameters"])
def test_unsafe_modes_fail_without_caller_transaction_change(database, mode):
    result = issued(database)
    second = None
    with Session(database) as session:
        root = None if mode == "no_root" else session.begin()
        if mode == "nested":
            nested = session.begin_nested()
        if mode in ("autocommit", "repeatable_read"):
            session.connection(execution_options={"isolation_level":
                "AUTOCOMMIT" if mode == "autocommit" else "REPEATABLE READ"})
        if mode == "invalidated":
            session.connection().invalidate()
        if mode == "multiple_binds":
            second = create_engine(database.url, hide_parameters=True)
            session.bind_mapper(Portfolio, second)
        if mode == "visible_parameters":
            database.hide_parameters = False
        try:
            with pytest.raises(access.GuestAccessUnsupported):
                access.require(session, result.secret.get_secret_value(), clock=lambda: NOW)
            assert session.get_transaction() is root
            if root:
                assert root.is_active
        finally:
            database.hide_parameters = True
            session.rollback()
            if second:
                second.dispose()


@pytest.mark.live
def test_database_errors_are_sanitized_and_savepoint_recovers(database):
    result = issued(database)
    with Session(database) as session, session.begin():
        connection = session.connection()
        def fail(conn, cursor, statement, parameters, context, many):
            if statement.startswith("UPDATE guest_access"):
                raise RuntimeError(result.secret.get_secret_value())
        event.listen(connection, "before_cursor_execute", fail)
        with pytest.raises(access.GuestAccessError) as caught:
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
        formatted = "".join(traceback.format_exception(caught.value))
        assert result.secret.get_secret_value() not in formatted
        assert connection.scalar(select(1)) == 1


@pytest.mark.live
def test_failed_savepoint_recovery_reports_unconfirmed(database):
    result = issued(database)
    with Session(database) as session:
        session.begin()
        connection = session.connection()
        def fail(*args):
            raise RuntimeError("Synthetic recovery failure")
        event.listen(connection, "rollback_savepoint", fail)
        with pytest.raises(access.GuestAccessUnconfirmed) as caught:
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=90))
        assert caught.value.__context__ is None
        event.remove(connection, "rollback_savepoint", fail)
        session.rollback()
    assert row_state(database, result.workspace_id)["last_access_at"] == NOW


@pytest.mark.live
@pytest.mark.parametrize("change", ["revoke", "claim"])
@pytest.mark.parametrize("first", ["authorize", "change"])
def test_ordered_concurrency_and_busy_recovery(database, change, first):
    result = issued(database)
    barrier = Barrier(2, timeout=8)
    def change_state(session):
        if change == "revoke":
            access.revoke(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=1))
        else:
            simulate_claim(session, result.workspace_id)
    def holder():
        with Session(database) as session, session.begin():
            if first == "authorize":
                access.require(session, result.secret.get_secret_value(), clock=lambda: NOW)
            else:
                change_state(session)
            barrier.wait()
            barrier.wait()
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(holder)
        barrier.wait()
        with Session(database) as contender:
            root = contender.begin()
            sentinel = User()
            contender.add(sentinel)
            contender.flush()
            if first == "authorize" and change == "claim":
                savepoint = contender.connection().begin_nested()
                with pytest.raises(DBAPIError) as caught:
                    simulate_claim(contender, result.workspace_id)
                assert caught.value.orig.sqlstate == "55P03"
                savepoint.rollback()
            else:
                with pytest.raises(access.GuestAccessBusy):
                    if first == "authorize":
                        access.revoke(contender, result.secret.get_secret_value(), clock=lambda: NOW)
                    else:
                        access.require(contender, result.secret.get_secret_value(), clock=lambda: NOW)
            assert contender.connection().scalar(select(User.id).where(User.id == sentinel.id)) == sentinel.id
            assert root.is_active
            root.rollback()
        barrier.wait()
        future.result(timeout=8)
    with Session(database) as session, session.begin():
        if first == "authorize":
            change_state(session)
        with pytest.raises(access.GuestAccessDenied):
            access.require(session, result.secret.get_secret_value(), clock=lambda: NOW + timedelta(days=1))


@pytest.mark.live
def test_repeated_authorization_retains_locks_until_caller_end(database):
    result = issued(database)
    with Session(database) as first, first.begin():
        for _ in range(3):
            access.require(first, result.secret.get_secret_value(), clock=lambda: NOW)
        with Session(database) as second, second.begin():
            with pytest.raises(access.GuestAccessBusy):
                access.require(second, result.secret.get_secret_value(), clock=lambda: NOW)
    with Session(database) as second, second.begin():
        access.require(second, result.secret.get_secret_value(), clock=lambda: NOW)


@pytest.mark.live
def test_postgresql_digest_constraints_and_cascade(database):
    result = issued(database)
    for digest in (b"x" * 31, b"x" * 33):
        with pytest.raises(IntegrityError), database.begin() as connection:
            connection.execute(update(GuestAccess.__table__).values(secret_digest=digest))
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(GuestAccess.__table__.insert(), dict(workspace_id=999,
            secret_digest=b"y" * 32, created_at=NOW, last_access_at=NOW))
    with database.begin() as connection:
        connection.execute(Workspace.__table__.delete().where(Workspace.id == result.workspace_id))
        assert counts(connection) == (0, 0, 0, 0)


def test_cleanup_rejects_non_task_schema():
    with pytest.raises(RuntimeError, match="invalid task schema"):
        _drop_owned(None, "public", "marker", 1, "fadir_test")


def test_failed_call_retains_schema_when_pytest_resumes_yield_fixture(monkeypatch):
    from sqlalchemy.engine import make_url
    monkeypatch.setattr(__import__(__name__), "_selected_test_url",
                        lambda: make_url("postgresql+psycopg:///fadir_test"))
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value.scalar.side_effect = ["fadir_test", 123]
    engine.connect.return_value.__enter__.return_value.scalar.return_value = 0
    monkeypatch.setattr(__import__(__name__), "create_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(command, "upgrade", lambda *args: None)
    dropped = []
    monkeypatch.setattr(__import__(__name__), "_drop_owned", lambda *args: dropped.append(args))
    plugins = []
    request = SimpleNamespace(node=SimpleNamespace(user_properties=[]), config=SimpleNamespace(pluginmanager=SimpleNamespace(
        register=lambda plugin: plugins.append(plugin), unregister=lambda plugin: None)))
    fixture = database.__wrapped__
    arguments = {"monkeypatch": monkeypatch}
    if "request" in python_inspect.signature(fixture).parameters:
        arguments["request"] = request
    iterator = fixture(**arguments)
    next(iterator)
    for plugin in plugins:
        plugin.pytest_runtest_makereport(item=None, call=SimpleNamespace(
            when="call", excinfo=SimpleNamespace(value=access.GuestAccessUnconfirmed())))
    with pytest.raises(StopIteration):
        next(iterator)
    assert dropped == [], "A failed test must retain its schema after normal yield-fixture teardown"

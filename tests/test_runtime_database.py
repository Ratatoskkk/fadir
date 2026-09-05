from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import make_url


POSTGRESQL_URL = "postgresql+psycopg://fadir@db.example/fadir_test"
ROOT = Path(__file__).resolve().parents[1]


def _live_url():
    if os.environ.get("FADIR_RUN_POSTGRESQL_MIGRATIONS") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_MIGRATIONS=1 for approved live proof")
    raw = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw or not database:
        raise ValueError("An explicit synthetic PostgreSQL URL and database are required")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != database
        or database != "fadir_test"
        or url.query
    ):
        raise ValueError("The live proof requires the approved synthetic PostgreSQL target")
    return url


def _drop_owned(connection, schema: str, marker: str, oid: int, database: str) -> None:
    if re.fullmatch(r"id2_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("invalid task schema")
    record = connection.execute(
        text(
            "SELECT current_database(), n.oid, "
            "n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), "
            "pg_catalog.obj_description(n.oid, 'pg_namespace') "
            "FROM pg_catalog.pg_namespace n WHERE n.nspname=:schema"
        ),
        {"schema": schema},
    ).one_or_none()
    if record is None or tuple(record) != (database, oid, True, marker):
        raise RuntimeError("task schema ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_database_url_takes_precedence_without_sqlite_fallback(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setenv("FADIR_DATABASE_URL", POSTGRESQL_URL)
    monkeypatch.setenv("FADIR_DB_PATH", str(tmp_path / "must-not-use.db"))
    config.get_settings.cache_clear()

    settings = config.load_settings()

    assert settings.database_url == POSTGRESQL_URL
    assert settings.database_target == POSTGRESQL_URL


@pytest.mark.parametrize("value", ["", "not a url", "mysql://fadir@db.example/fadir_test"])
def test_invalid_database_url_fails_without_sqlite_fallback(monkeypatch, value, tmp_path):
    from app.db import resolve_database_target

    monkeypatch.setenv("FADIR_DATABASE_URL", value)
    monkeypatch.setenv("FADIR_DB_PATH", str(tmp_path / "must-not-use.db"))

    with pytest.raises(RuntimeError, match="database configuration") as caught:
        resolve_database_target()

    assert "must-not-use.db" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert not (tmp_path / "must-not-use.db").exists()


def test_startup_checks_heads_without_creating_tables(monkeypatch):
    from app import main

    async def idle_refresh():
        await asyncio.sleep(3600)

    monkeypatch.setattr(main, "_auto_refresh", idle_refresh)
    init_calls = []
    monkeypatch.setattr(main, "init_db", lambda engine: init_calls.append(engine), raising=False)
    check_calls = []
    monkeypatch.setattr(main, "check_migration_heads", lambda engine: check_calls.append(engine), raising=False)
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    monkeypatch.setattr(main, "get_engine", lambda: engine, raising=False)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(db_path=Path("synthetic.db")),
    )

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())
    assert init_calls == []
    assert check_calls == [engine]


def test_fresh_sqlite_startup_initializes_local_schema(monkeypatch, tmp_path):
    from app import main
    from app.db import make_engine

    async def idle_refresh():
        await asyncio.sleep(3600)

    monkeypatch.setattr(main, "_auto_refresh", idle_refresh)
    monkeypatch.setattr(
        main,
        "check_migration_heads",
        lambda engine: pytest.fail("SQLite startup must not check migration heads"),
        raising=False,
    )
    engine = make_engine(tmp_path / "startup.db")
    monkeypatch.setattr(main, "get_engine", lambda: engine, raising=False)

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())
    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='instrument'")
        ) == 1


def test_readiness_failure_stops_refresh(monkeypatch):
    from app import main

    refresh_calls = []

    async def unexpected_refresh():
        refresh_calls.append(True)
        await asyncio.sleep(3600)

    monkeypatch.setattr(main, "_auto_refresh", unexpected_refresh)
    class BrokenEngine:
        dialect = SimpleNamespace(name="postgresql")

        def connect(self):
            raise RuntimeError("password=secret")

    engine = BrokenEngine()
    monkeypatch.setattr(main, "get_engine", lambda: engine, raising=False)

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError, match="migration head check failed") as caught:
        asyncio.run(run_lifespan())
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "secret" not in str(caught.value)
    assert refresh_calls == []


def test_startup_engine_error_is_sanitized_before_readiness(monkeypatch, tmp_path):
    from app import db, main

    secret_query_value = "synthetic-private-value"
    fallback = tmp_path / "must-not-fallback.db"
    monkeypatch.setenv(
        "FADIR_DATABASE_URL",
        POSTGRESQL_URL + f"?port={secret_query_value}",
    )
    monkeypatch.setenv("FADIR_DB_PATH", str(fallback))
    db.reset_engine()
    db.get_settings.cache_clear()

    refresh_calls = []

    async def unexpected_refresh():
        refresh_calls.append(True)
        await asyncio.sleep(3600)

    monkeypatch.setattr(main, "_auto_refresh", unexpected_refresh)

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    try:
        with pytest.raises(RuntimeError, match="database startup failed") as caught:
            asyncio.run(run_lifespan())
    finally:
        db.reset_engine()
        db.get_settings.cache_clear()

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert secret_query_value not in str(caught.value)
    assert not fallback.exists()
    assert refresh_calls == []


def test_postgresql_engine_hides_parameters():
    from app.db import make_engine

    with patch("app.db.create_engine") as create_engine:
        make_engine(POSTGRESQL_URL)

    assert create_engine.call_args.kwargs["hide_parameters"] is True


def test_postgresql_url_options_pass_unchanged_without_sqlite_options():
    from app.db import make_engine

    url = POSTGRESQL_URL + "?sslmode=require&application_name=id2"
    with patch("app.db.create_engine") as create_engine:
        make_engine(url)

    create_engine.assert_called_once_with(url, future=True, hide_parameters=True)
    assert "connect_args" not in create_engine.call_args.kwargs


def test_missing_migration_head_fails_without_connection_error_details(tmp_path):
    from app.db import check_migration_heads

    engine = create_engine(f"sqlite:///{tmp_path / 'missing-head.db'}")
    with pytest.raises(RuntimeError, match="migration head check failed") as caught:
        check_migration_heads(engine)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_init_db_preserves_existing_migration_version(tmp_path):
    from app.db import init_db

    engine = create_engine(f"sqlite:///{tmp_path / 'version.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(35) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version(version_num) VALUES ('sentinel')"))

    init_db(engine)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "sentinel"


def test_settings_repr_does_not_show_database_url_or_query_secret(monkeypatch):
    from app.config import load_settings

    secret_url = "postgresql+psycopg://fadir:secret@db.example/fadir_test?password=also-secret"
    monkeypatch.setenv("FADIR_DATABASE_URL", secret_url)
    settings = load_settings()

    rendered = repr(settings)
    assert secret_url not in rendered
    assert "secret" not in rendered
    assert "also-secret" not in rendered
    assert "database_url='<configured>'" in rendered


def test_head_check_sanitizes_engine_creation_errors(monkeypatch):
    from app import db

    monkeypatch.setattr(db, "get_engine", lambda: (_ for _ in ()).throw(RuntimeError("password=secret")))

    with pytest.raises(RuntimeError, match="migration head check failed") as caught:
        db.check_migration_heads()
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "secret" not in str(caught.value)


def test_public_failure_does_not_return_or_log_exception_text(caplog):
    from app.main import unhandled_exception_handler

    request = SimpleNamespace(url=SimpleNamespace(path="/health"))
    secret_error = RuntimeError("password=secret")

    response = asyncio.run(unhandled_exception_handler(request, secret_error))

    assert response.body == b'{"detail":"internal server error"}'
    assert "secret" not in caplog.text


@pytest.mark.live
def test_postgresql_startup_head_check_is_read_only(monkeypatch):
    from app import db

    url = _live_url()
    schema = "id2_" + uuid4().hex
    marker = "ID-2:" + uuid4().hex
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    scoped = None
    readonly = None
    oid = None
    cleanup_confirmed = False
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{marker}'"))
            oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:schema"),
                {"schema": schema},
            )
        scoped_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog -cstatement_timeout=5s"}
        )
        monkeypatch.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        monkeypatch.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
        command.upgrade(config, "head")
        scoped = create_engine(scoped_url, poolclass=pool.NullPool, hide_parameters=True)

        db.check_migration_heads(scoped)
        readonly_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog -cdefault_transaction_read_only=on -cstatement_timeout=5s"}
        )
        readonly = create_engine(readonly_url, poolclass=pool.NullPool, hide_parameters=True)
        with readonly.connect() as connection:
            assert connection.scalar(text("SHOW transaction_read_only")) == "on"
            db.check_migration_heads(readonly)
        with scoped.begin() as connection:
            version = connection.scalar(text("SELECT version_num FROM alembic_version"))
            connection.execute(text("UPDATE alembic_version SET version_num='0003_portfolio_ownership_keys'"))
        with pytest.raises(RuntimeError, match="migration head check failed") as caught:
            db.check_migration_heads(scoped)
        assert caught.value.__cause__ is None
        assert "db.example" not in str(caught.value)
        with scoped.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num=:version"), {"version": version})
        cleanup_confirmed = True
    finally:
        if readonly is not None:
            readonly.dispose()
        if scoped is not None:
            scoped.dispose()
        if cleanup_confirmed and oid is not None:
            with engine.begin() as connection:
                _drop_owned(connection, schema, marker, oid, url.database)
        elif oid is not None:
            print(f"preserved synthetic schema={schema} marker={marker} oid={oid}")
        engine.dispose()

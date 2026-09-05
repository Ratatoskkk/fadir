"""Opt-in PostgreSQL proof in a fresh DB-6A schema, never the default schema."""

from __future__ import annotations

import os
from pathlib import Path
import re
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, pool, text
from sqlalchemy.engine import URL, make_url


ROOT = Path(__file__).resolve().parents[1]
APPLICATION_TABLES = {
    "instrument",
    "transaction",
    "price_cache",
    "fx_cache",
    "corporate_action",
    "snapshot",
    "user",
    "workspace",
    "portfolio",
    "guest_access",
}


def _selected_test_url() -> URL:
    __tracebackhide__ = True
    if os.environ.get("FADIR_RUN_POSTGRESQL_MIGRATIONS") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_MIGRATIONS=1 for approved live proof")
    raw_url = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw_url or not database:
        raise ValueError("An explicit synthetic URL and database are required")
    try:
        url = make_url(raw_url)
    except Exception:
        raise ValueError("The synthetic URL is invalid") from None
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != database
        or re.fullmatch(r"fadir_test(?:_[a-z0-9_]+)?", database) is None
        or url.query
    ):
        raise ValueError(
            "Select a matching synthetic PostgreSQL database without URL options"
        )
    return url


def _drop_owned_schema(connection, schema, marker, schema_oid, database) -> None:
    if re.fullmatch(r"db6a_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("Cleanup refused: invalid task schema")
    record = connection.execute(
        text(
            "SELECT current_database(), n.oid, "
            "n.nspowner = (SELECT oid FROM pg_catalog.pg_roles "
            "WHERE rolname = current_user), "
            "pg_catalog.obj_description(n.oid, 'pg_namespace') "
            "FROM pg_catalog.pg_namespace AS n WHERE n.nspname = :schema"
        ),
        {"schema": schema},
    ).one_or_none()
    if record is None or tuple(record) != (database, schema_oid, True, marker):
        raise RuntimeError("Cleanup refused: task schema ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _assert_head(engine, schema: str, head: str) -> None:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        inspector = inspect(connection)
        assert set(inspector.get_table_names(schema=schema)) == (
            APPLICATION_TABLES | {"alembic_version"}
        )
        columns = inspector.get_columns("alembic_version", schema=schema)
        assert str(columns[0]["type"]) == "TEXT"
        assert inspector.get_pk_constraint("alembic_version", schema=schema)[
            "constrained_columns"
        ] == ["version_num"]
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == head


@pytest.mark.live
def test_postgresql_upgrade_downgrade_and_second_upgrade(monkeypatch) -> None:
    __tracebackhide__ = True
    url = _selected_test_url()
    schema = "db6a_" + uuid4().hex
    marker = "DB-6A:" + uuid4().hex
    schema_oid = None
    engine = None
    scoped_engine = None
    failure = None
    stage = "connection"
    try:
        engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
        stage = "schema creation"
        with engine.begin() as connection:
            if connection.scalar(text("SELECT current_database()")) != url.database:
                raise RuntimeError("Synthetic database mismatch")
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{marker}'"))
            created_oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = :schema"),
                {"schema": schema},
            )
        schema_oid = created_oid
        scoped_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog"}
        )
        monkeypatch.setenv(
            "FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False)
        )
        scoped_engine = create_engine(
            scoped_url, poolclass=pool.NullPool, hide_parameters=True
        )
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        head = ScriptDirectory.from_config(config).get_current_head()
        stage = "upgrade"
        command.upgrade(config, "head")
        _assert_head(scoped_engine, schema, head)
        stage = "downgrade"
        command.downgrade(config, "base")
        with scoped_engine.connect() as connection:
            assert set(inspect(connection).get_table_names(schema=schema)) == {
                "alembic_version"
            }
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).all() == []
        stage = "second upgrade"
        command.upgrade(config, "head")
        _assert_head(scoped_engine, schema, head)
    except Exception as error:
        failure = (
            f"PostgreSQL proof failed during {stage}: {type(error).__name__}; "
            f"task schema {schema}"
        )
    finally:
        if scoped_engine is not None:
            scoped_engine.dispose()
        if engine is not None:
            try:
                if schema_oid is not None:
                    with engine.begin() as connection:
                        _drop_owned_schema(
                            connection, schema, marker, schema_oid, url.database
                        )
            except Exception:
                cleanup_failure = f"Cleanup refused or failed for task schema {schema}"
                failure = f"{failure}; {cleanup_failure}" if failure else cleanup_failure
            finally:
                engine.dispose()
    if failure:
        pytest.fail(failure, pytrace=False)


def test_postgresql_proof_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("FADIR_RUN_POSTGRESQL_MIGRATIONS", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _selected_test_url()


def test_postgresql_proof_has_no_default_url(monkeypatch) -> None:
    monkeypatch.setenv("FADIR_RUN_POSTGRESQL_MIGRATIONS", "1")
    monkeypatch.setenv("FADIR_DATABASE_URL", "sqlite:///private-must-not-be-used.db")
    monkeypatch.delenv("FADIR_TEST_POSTGRESQL_URL", raising=False)
    monkeypatch.delenv("FADIR_TEST_POSTGRESQL_DATABASE", raising=False)
    with pytest.raises(ValueError, match="explicit synthetic URL"):
        _selected_test_url()


@pytest.mark.parametrize(
    ("url", "database"),
    [
        ("sqlite:///fadir_test", "fadir_test"),
        ("postgresql+psycopg:///production", "production"),
        ("postgresql+psycopg:///fadir_test", "fadir_test_other"),
        ("postgresql+psycopg:///fadir_test?options=unexpected", "fadir_test"),
    ],
)
def test_postgresql_proof_rejects_unsafe_selection(monkeypatch, url, database) -> None:
    monkeypatch.setenv("FADIR_RUN_POSTGRESQL_MIGRATIONS", "1")
    monkeypatch.setenv("FADIR_TEST_POSTGRESQL_URL", url)
    monkeypatch.setenv("FADIR_TEST_POSTGRESQL_DATABASE", database)
    with pytest.raises(ValueError, match="matching synthetic PostgreSQL"):
        _selected_test_url()


@pytest.mark.parametrize(
    "record",
    [
        None,
        ("other", 123, True, "token"),
        ("fadir_test", 124, True, "token"),
        ("fadir_test", 123, False, "token"),
        ("fadir_test", 123, True, "other"),
    ],
)
def test_cleanup_refuses_foreign_schema(record) -> None:
    connection = MagicMock()
    connection.execute.return_value.one_or_none.return_value = record
    with pytest.raises(RuntimeError, match="ownership mismatch"):
        _drop_owned_schema(connection, "db6a_" + "a" * 32, "token", 123, "fadir_test")
    assert connection.execute.call_count == 1


def test_cleanup_refuses_public_schema() -> None:
    connection = MagicMock()
    with pytest.raises(RuntimeError, match="invalid task schema"):
        _drop_owned_schema(connection, "public", "token", 123, "fadir_test")
    connection.execute.assert_not_called()


def test_cleanup_removes_only_the_verified_schema() -> None:
    schema = "db6a_" + "a" * 32
    connection = MagicMock()
    connection.execute.return_value.one_or_none.return_value = (
        "fadir_test", 123, True, "token"
    )
    _drop_owned_schema(connection, schema, "token", 123, "fadir_test")
    assert connection.execute.call_count == 2
    assert str(connection.execute.call_args.args[0]) == f'DROP SCHEMA "{schema}" CASCADE'


def test_postgresql_proof_accepts_explicit_synthetic_selection(monkeypatch) -> None:
    monkeypatch.setenv("FADIR_RUN_POSTGRESQL_MIGRATIONS", "1")
    monkeypatch.setenv("FADIR_TEST_POSTGRESQL_URL", "postgresql+psycopg:///fadir_test")
    monkeypatch.setenv("FADIR_TEST_POSTGRESQL_DATABASE", "fadir_test")
    assert _selected_test_url().database == "fadir_test"

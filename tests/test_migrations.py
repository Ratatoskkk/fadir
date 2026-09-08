from __future__ import annotations

from pathlib import Path
import re
from unittest.mock import MagicMock, patch

import pytest
from alembic import command, context
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql

from app.models import Base


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"
BASELINE_REVISION = (
    ROOT / "migrations" / "versions" / "0001_current_schema_baseline.py"
)
DOMAIN_ROOT_REVISION = (
    ROOT / "migrations" / "versions" / "0002_user_workspace_portfolio_roots.py"
)
OWNERSHIP_REVISION = (
    ROOT / "migrations" / "versions" / "0003_portfolio_ownership_keys.py"
)
SESSION_REVISION = ROOT / "migrations" / "versions" / "0005_user_sessions.py"
LOGIN_IDENTITY_REVISION = ROOT / "migrations" / "versions" / "0006_login_identities.py"
LOGIN_TRANSACTION_REVISION = ROOT / "migrations" / "versions" / "0007_login_transactions.py"
LOGIN_TRANSACTION_VERIFICATION_REVISION = ROOT / "migrations" / "versions" / "0008_login_transaction_verification.py"
FEE_CURRENCY_REVISION = ROOT / "migrations" / "versions" / "0009_fee_currency.py"
BASELINE_TABLES = {
    "instrument",
    "transaction",
    "price_cache",
    "fx_cache",
    "corporate_action",
    "snapshot",
}
DOMAIN_ROOT_TABLES = {"user", "workspace", "portfolio"}
APPLICATION_TABLES = BASELINE_TABLES | DOMAIN_ROOT_TABLES | {
    "guest_access",
    "user_session",
    "login_identity",
    "login_transaction",
    "tax_profile",
}
POSTGRESQL_URL = "postgresql+psycopg://fadir@db.example/fadir_test"


def _alembic_config() -> Config:
    assert ALEMBIC_INI.is_file(), "migration framework is absent: alembic.ini"
    return Config(str(ALEMBIC_INI))


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def _column_shape(column, dialect) -> tuple[str, str, bool, bool]:
    return (
        column.name,
        column.type.compile(dialect=dialect).upper(),
        column.nullable,
        column.primary_key,
    )


def _reflected_column_shape(column, dialect) -> tuple[str, str, bool, bool]:
    return (
        column["name"],
        column["type"].compile(dialect=dialect).upper(),
        column["nullable"],
        column["primary_key"],
    )


def _normalized_sql(expression: str) -> str:
    return " ".join(expression.split())


def _assert_schema_matches_models(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == APPLICATION_TABLES | {
            "alembic_version"
        }

        for table_name in sorted(APPLICATION_TABLES):
            model_table = Base.metadata.tables[table_name]
            expected_columns = {
                _column_shape(column, engine.dialect) for column in model_table.columns
            }
            actual_columns = {
                _reflected_column_shape(column, engine.dialect)
                for column in inspector.get_columns(table_name)
            }
            assert actual_columns == expected_columns

            expected_primary_key = tuple(
                column.name for column in model_table.primary_key.columns
            )
            actual_primary_key = tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"]
            )
            assert actual_primary_key == expected_primary_key

            expected_foreign_keys = {
                (
                    tuple(constraint.column_keys),
                    constraint.referred_table.name,
                    tuple(element.column.name for element in constraint.elements),
                    constraint.ondelete,
                )
                for constraint in model_table.foreign_key_constraints
            }
            actual_foreign_keys = {
                (
                    tuple(constraint["constrained_columns"]),
                    constraint["referred_table"],
                    tuple(constraint["referred_columns"]),
                    constraint["options"].get("ondelete"),
                )
                for constraint in inspector.get_foreign_keys(table_name)
            }
            assert actual_foreign_keys == expected_foreign_keys

            expected_unique_constraints = {
                (constraint.name, tuple(constraint.columns.keys()))
                for constraint in model_table.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            }
            actual_unique_constraints = {
                (constraint["name"], tuple(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table_name)
            }
            assert actual_unique_constraints == expected_unique_constraints

            expected_checks = {
                (constraint.name, _normalized_sql(str(constraint.sqltext)))
                for constraint in model_table.constraints
                if constraint.__class__.__name__ == "CheckConstraint"
            }
            actual_checks = {
                (constraint["name"], _normalized_sql(constraint["sqltext"]))
                for constraint in inspector.get_check_constraints(table_name)
            }
            assert actual_checks == expected_checks

            expected_indexes = {
                (
                    index.name,
                    tuple(column.name for column in index.columns),
                    index.unique,
                )
                for index in model_table.indexes
            }
            actual_indexes = {
                (
                    index["name"],
                    tuple(index["column_names"]),
                    index["unique"],
                )
                for index in inspector.get_indexes(table_name)
            }
            assert actual_indexes == expected_indexes
    finally:
        engine.dispose()


def test_migrations_require_database_url(monkeypatch) -> None:
    monkeypatch.delenv("FADIR_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="FADIR_DATABASE_URL is required"):
        command.upgrade(_alembic_config(), "head")


def test_guest_revision_cycle_preserves_existing_tables(tmp_path, monkeypatch):
    database_url = _sqlite_url(tmp_path / "guest-migration.db")
    monkeypatch.setenv("FADIR_DATABASE_URL", database_url)
    config = _alembic_config()
    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)
    command.downgrade(config, "0003_portfolio_ownership_keys")
    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == (
            BASELINE_TABLES | DOMAIN_ROOT_TABLES | {"alembic_version"}
        )
    finally:
        engine.dispose()
    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)


def test_guest_revision_is_static():
    source = (ROOT / "migrations/versions/0004_guest_access.py").read_text(encoding="utf-8")
    assert "0003_portfolio_ownership_keys" in source
    assert "Base" not in source
    assert "metadata" not in source
    assert source.count("op.create_table(") == 1
    assert source.count("op.drop_table(") == 1


def test_sqlite_upgrade_downgrade_and_second_upgrade(tmp_path, monkeypatch) -> None:
    database_url = _sqlite_url(tmp_path / "migration.db")
    monkeypatch.setenv("FADIR_DATABASE_URL", database_url)
    config = _alembic_config()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    try:
        assert APPLICATION_TABLES.isdisjoint(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)


def test_domain_root_downgrade_and_second_upgrade(tmp_path, monkeypatch) -> None:
    database_url = _sqlite_url(tmp_path / "domain-root-migration.db")
    monkeypatch.setenv("FADIR_DATABASE_URL", database_url)
    config = _alembic_config()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)

    command.downgrade(config, "0001_current_schema_baseline")
    engine = create_engine(database_url)
    try:
        table_names = set(inspect(engine).get_table_names())
        assert DOMAIN_ROOT_TABLES.isdisjoint(table_names)
        assert BASELINE_TABLES <= table_names
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)


def test_ownership_migration_preserves_unowned_rows(tmp_path, monkeypatch) -> None:
    database_url = _sqlite_url(tmp_path / "ownership-migration.db")
    monkeypatch.setenv("FADIR_DATABASE_URL", database_url)
    config = _alembic_config()

    command.upgrade(config, "0002_user_workspace_portfolio_roots")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO instrument
                        (id, ticker, exchange, yf_symbol, currency, name, active)
                    VALUES
                        (1, 'SYN', 'TEST', 'SYN.TEST', 'USD', 'Synthetic', 1)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO "transaction"
                        (id, instrument_id, trade_date, side, quantity,
                         price_native, fees_native, fx_rate_to_try, fx_rate_date,
                         fx_provider, note, created_at, updated_at)
                    VALUES
                        (1, 1, '2026-01-02', 'BUY', 1, 10, 0, 35,
                         '2026-01-02', 'synthetic', NULL,
                         '2026-01-02 00:00:00', '2026-01-02 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO snapshot
                        (snapshot_date, payload_json, created_at)
                    VALUES
                        ('2026-01-02', '{}', '2026-01-02 00:00:00')
                    """
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "portfolio_id" in {
            column["name"] for column in inspector.get_columns("transaction")
        }
        assert "portfolio_id" in {
            column["name"] for column in inspector.get_columns("snapshot")
        }

        indexes = {
            index["name"]: tuple(index["column_names"])
            for table_name in ("transaction", "snapshot")
            for index in inspector.get_indexes(table_name)
        }
        assert indexes["ix_transaction_portfolio_instrument_date"] == (
            "portfolio_id",
            "instrument_id",
            "trade_date",
        )
        assert indexes["ix_snapshot_portfolio_date"] == (
            "portfolio_id",
            "snapshot_date",
        )

        foreign_keys = {
            constraint["name"]: constraint
            for table_name in ("transaction", "snapshot")
            for constraint in inspector.get_foreign_keys(table_name)
        }
        assert foreign_keys["fk_transaction_portfolio_id_portfolio"][
            "referred_table"
        ] == "portfolio"
        assert foreign_keys["fk_snapshot_portfolio_id_portfolio"][
            "referred_table"
        ] == "portfolio"

        with engine.connect() as connection:
            transaction = connection.execute(
                text('SELECT id, portfolio_id FROM "transaction" WHERE id = 1')
            ).one()
            snapshot = connection.execute(
                text(
                    "SELECT snapshot_date, portfolio_id FROM snapshot "
                    "WHERE snapshot_date = '2026-01-02'"
                )
            ).one()
        assert transaction == (1, None)
        assert snapshot[1] is None
    finally:
        engine.dispose()

    command.downgrade(config, "0002_user_workspace_portfolio_roots")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "portfolio_id" not in {
            column["name"] for column in inspector.get_columns("transaction")
        }
        assert "portfolio_id" not in {
            column["name"] for column in inspector.get_columns("snapshot")
        }
        with engine.connect() as connection:
            assert connection.scalar(
                text('SELECT count(*) FROM "transaction" WHERE id = 1')
            ) == 1
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM snapshot "
                    "WHERE snapshot_date = '2026-01-02'"
                )
            ) == 1
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)


def test_postgresql_upgrade_sql_is_offline(monkeypatch, capsys) -> None:
    monkeypatch.setenv("FADIR_DATABASE_URL", POSTGRESQL_URL)

    with patch(
        "sqlalchemy.engine.create.create_engine",
        side_effect=AssertionError("offline migration tried to create an engine"),
    ):
        command.upgrade(_alembic_config(), "head", sql=True)

    sql = capsys.readouterr().out.replace('"', "")
    for table_name in APPLICATION_TABLES:
        assert f"CREATE TABLE {table_name}" in sql
    assert sql.count("ADD COLUMN portfolio_id") == 2
    assert "fk_transaction_portfolio_id_portfolio" in sql
    assert "fk_snapshot_portfolio_id_portfolio" in sql
    assert "ix_transaction_portfolio_instrument_date" in sql
    assert "ix_snapshot_portfolio_date" in sql


def test_postgresql_version_storage_fits_revision_chain(monkeypatch, capsys) -> None:
    monkeypatch.setenv("FADIR_DATABASE_URL", POSTGRESQL_URL)
    config = _alembic_config()
    revisions = tuple(ScriptDirectory.from_config(config).walk_revisions())
    required_length = max(len(revision.revision) for revision in revisions)

    with patch(
        "sqlalchemy.engine.create.create_engine",
        side_effect=AssertionError("offline migration tried to create an engine"),
    ):
        command.upgrade(config, "head", sql=True)

    sql = capsys.readouterr().out
    declaration = re.search(r"version_num (TEXT|VARCHAR\((\d+)\))", sql)
    assert declaration is not None
    if declaration.group(2) is not None:
        capacity = int(declaration.group(2))
        assert capacity >= required_length, (
            f"PostgreSQL version storage accepts {capacity} characters; "
            f"the unchanged revision chain requires {required_length}"
        )
    assert "PRIMARY KEY (version_num)" in sql
    for revision in revisions:
        assert revision.revision in sql


def test_online_postgresql_uses_version_table_extension(monkeypatch) -> None:
    monkeypatch.setenv("FADIR_DATABASE_URL", POSTGRESQL_URL)
    connection = MagicMock()
    connection.dialect = postgresql.dialect()
    connection.in_transaction.return_value = False
    observed = []

    def inspect_version_table() -> None:
        implementation = context.get_context().impl
        for primary_key in (True, False):
            table = implementation.version_table_impl(
                version_table="synthetic_version",
                version_table_schema="synthetic_schema",
                version_table_pk=primary_key,
            )
            assert table.name == "synthetic_version"
            assert table.schema == "synthetic_schema"
            assert not table.c.version_num.nullable
            assert bool(table.primary_key.columns) is primary_key
            observed.append(table.c.version_num.type.compile(connection.dialect))

    with (
        patch("sqlalchemy.engine_from_config") as factory,
        patch("alembic.context.run_migrations", side_effect=inspect_version_table),
    ):
        factory.return_value.connect.return_value.__enter__.return_value = connection
        command.upgrade(_alembic_config(), "head")

    assert observed == ["TEXT", "TEXT"]


def test_baseline_revision_is_static() -> None:
    assert BASELINE_REVISION.is_file(), "migration baseline is absent"
    source = BASELINE_REVISION.read_text(encoding="utf-8")

    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
    assert "drop_all" not in source


def test_domain_root_revision_is_static() -> None:
    assert DOMAIN_ROOT_REVISION.is_file(), "second migration revision is absent"
    source = DOMAIN_ROOT_REVISION.read_text(encoding="utf-8")

    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
    assert "drop_all" not in source


def test_ownership_revision_is_static() -> None:
    assert OWNERSHIP_REVISION.is_file(), "third migration revision is absent"
    source = OWNERSHIP_REVISION.read_text(encoding="utf-8")

    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
    assert "drop_all" not in source


def test_user_session_revision_is_static() -> None:
    assert SESSION_REVISION.is_file(), "user session revision is absent"
    source = SESSION_REVISION.read_text(encoding="utf-8")

    assert "0004_guest_access" in source
    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
    assert "drop_all" not in source
    assert source.count('op.create_table(') == 1
    assert source.count('op.drop_table(') == 1


def test_login_identity_revision_is_static() -> None:
    assert LOGIN_IDENTITY_REVISION.is_file(), "login identity revision is absent"
    source = LOGIN_IDENTITY_REVISION.read_text(encoding="utf-8")

    assert "0005_user_sessions" in source
    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
    assert "drop_all" not in source
    assert source.count('op.create_table(') == 1
    assert source.count('op.drop_table(') == 1


def test_login_identity_revision_cycle(tmp_path, monkeypatch) -> None:
    database_url = _sqlite_url(tmp_path / "login-identity-migration.db")
    monkeypatch.setenv("FADIR_DATABASE_URL", database_url)
    config = _alembic_config()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        assert "login_identity" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.downgrade(config, "0005_user_sessions")
    engine = create_engine(database_url)
    try:
        assert "login_identity" not in inspect(engine).get_table_names()
        assert "user_session" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)


def test_login_transaction_revision_is_static() -> None:
    assert LOGIN_TRANSACTION_REVISION.is_file(), "login transaction revision is absent"
    source = LOGIN_TRANSACTION_REVISION.read_text(encoding="utf-8")

    assert "0006_login_identities" in source
    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source
    assert "drop_all" not in source
    assert source.count("op.create_table(") == 1
    assert source.count("op.drop_table(") == 1


def test_login_transaction_verification_revision_is_static() -> None:
    assert LOGIN_TRANSACTION_VERIFICATION_REVISION.is_file(), (
        "login transaction verification revision is absent"
    )
    source = LOGIN_TRANSACTION_VERIFICATION_REVISION.read_text(encoding="utf-8")
    assert "0007_login_transactions" in source
    assert "from app.models import Base" not in source
    assert "Base.metadata" not in source
    assert "create_all" not in source


def test_fee_currency_revision_is_additive_and_nullable() -> None:
    source = FEE_CURRENCY_REVISION.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0008_login_transaction_verification"' in source
    assert source.count('op.add_column("transaction"') == 4
    assert "nullable=True" in source
    assert "UPDATE" not in source
    assert "drop_all" not in source


def test_login_transaction_verification_revision_cycle(tmp_path, monkeypatch) -> None:
    database_url = _sqlite_url(tmp_path / "login-transaction-verification-migration.db")
    monkeypatch.setenv("FADIR_DATABASE_URL", database_url)
    config = _alembic_config()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        columns = {
            column["name"]
            for column in inspect(engine).get_columns("login_transaction")
        }
        assert {"verified_issuer", "verified_subject", "verified_at"} <= columns
    finally:
        engine.dispose()

    command.downgrade(config, "0007_login_transactions")
    engine = create_engine(database_url)
    try:
        columns = {
            column["name"]
            for column in inspect(engine).get_columns("login_transaction")
        }
        assert {"verified_issuer", "verified_subject", "verified_at"}.isdisjoint(columns)
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    _assert_schema_matches_models(database_url)

"""Synthetic source and connection-boundary proof for DB-6B."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, select

from app.db import make_engine
from app.models import Base, Side, ActionKind
from app.services.private_migration_adapters import (
    SQLiteMigrationSource,
    PostgresqlMigrationTarget,
)


ROOT = Path(__file__).resolve().parents[1]
TABLES = ("instrument", "price_cache", "fx_cache", "corporate_action",
          "transaction", "snapshot")
STAMP = datetime(2026, 1, 2, 3, 4, 5, 123456)
DAY = date(2026, 1, 2)


def synthetic_rows():
    return {
        "instrument": [dict(id=i, ticker=f"SYN{i}", exchange="SYN",
                            yf_symbol=f"SYN{i}", currency="TRY",
                            name="Sentetik Türkçe", active=i == 11)
                       for i in (12, 11)],
        "price_cache": [dict(id=21, instrument_id=11, price_date=DAY,
                             close_native=Decimal("12.12500000"),
                             is_adjusted=False, fetched_at=STAMP)],
        "fx_cache": [dict(id=31, base="USD", quote="TRY", rate_date=DAY,
                          rate=Decimal("32.1250000000"), provider="synthetic",
                          fetched_at=STAMP)],
        "corporate_action": [dict(id=41, instrument_id=11, action_date=DAY,
                                  kind=ActionKind.SPLIT,
                                  ratio=Decimal("2.0000000000"),
                                  applied_to_transactions=False, fetched_at=STAMP)],
        "transaction": [dict(id=i, instrument_id=11, trade_date=DAY,
                             side=Side.BUY if i == 51 else Side.SELL,
                             quantity=Decimal("1.25000000"),
                             price_native=Decimal("100.125000000000"),
                             fees_native=Decimal("0.00000000"),
                             fee_currency=None, fee_fx_rate_to_try=None,
                             fee_fx_rate_date=None, fee_fx_provider=None,
                             fx_rate_to_try=Decimal("32.1250000000"),
                             fx_rate_date=DAY, fx_provider="synthetic",
                             note=None if i == 51 else "Türkçe\ntext",
                             created_at=STAMP, updated_at=STAMP)
                        for i in (52, 51)],
        "snapshot": [dict(snapshot_date=DAY, payload_json=' {"synthetic": true} ',
                          created_at=STAMP)],
    }


def synthetic_source(tmp_path, monkeypatch, revision="head"):
    path = tmp_path / "synthetic-source.db"
    monkeypatch.setenv("FADIR_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, revision)
    engine = make_engine(path)
    with engine.begin() as connection:
        for name, rows in synthetic_rows().items():
            physical = {column["name"] for column in inspect(connection).get_columns(name)}
            values = [{key: value for key, value in row.items() if key in physical} for row in rows]
            connection.execute(Base.metadata.tables[name].insert(), values)
    return engine


@pytest.mark.parametrize("revision", ["0001_current_schema_baseline", "head"])
def test_source_reads_legacy_and_head_without_ownership(tmp_path, monkeypatch, revision):
    engine = synthetic_source(tmp_path, monkeypatch, revision)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            transaction = connection.get_transaction()
            source = SQLiteMigrationSource(connection)
            actual = (*source.read_shared_rows(), *source.read_private_rows())
            expected = tuple(
                {"table": name, **row}
                for name, rows in synthetic_rows().items()
                for row in sorted(rows, key=lambda r: r.get("id", r.get("snapshot_date")))
            )
            assert actual == expected
            assert all("portfolio_id" not in row for row in actual)
            assert source.read_private_rows() == source.read_private_rows()
            assert connection.get_transaction() is transaction
            assert transaction.is_active
            assert not connection.closed
            if revision != "head":
                assert "portfolio" not in inspect(connection).get_table_names()
            for row in actual:
                for key, value in row.items():
                    if isinstance(value, Decimal):
                        column = Base.metadata.tables[row["table"]].c[key]
                        assert value.as_tuple().exponent == -column.type.scale
            assert type(actual[0]["active"]) is bool
            assert type(actual[-1]["snapshot_date"]) is date
            assert actual[-1]["created_at"] == STAMP
    finally:
        engine.dispose()


def test_target_rejects_sqlite_without_touching_caller_transaction():
    engine = make_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            with pytest.raises(ValueError, match="PostgreSQL"):
                PostgresqlMigrationTarget(connection).begin()
            assert connection.get_transaction() is transaction
            assert transaction.is_active
    finally:
        engine.dispose()


def test_source_rejects_closed_connection():
    engine = make_engine("sqlite:///:memory:")
    connection = engine.connect()
    connection.close()
    try:
        with pytest.raises(ValueError, match="open"):
            SQLiteMigrationSource(connection)
    finally:
        engine.dispose()


def test_source_requires_real_sqlite_snapshot():
    engine = make_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(select(1))
            assert not connection.connection.driver_connection.in_transaction
            with pytest.raises(ValueError, match="real SQLite snapshot"):
                SQLiteMigrationSource(connection)
            assert connection.get_transaction() is transaction
            connection.exec_driver_sql("BEGIN")
            SQLiteMigrationSource(connection)
            assert connection.get_transaction() is transaction
    finally:
        engine.dispose()

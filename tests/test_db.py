from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import Column, MetaData, Numeric, Table, insert, select, text

from app.db import make_engine


POSTGRESQL_URL = "postgresql+psycopg://fadir@db.example/fadir_test"


def test_make_engine_keeps_postgresql_url_and_omits_sqlite_options() -> None:
    with (
        patch("app.db.create_engine") as create_engine,
        patch("app.db._register_decimal_adapters") as register_decimal_adapters,
        patch("app.db.event.listens_for") as listens_for,
    ):
        engine = make_engine(POSTGRESQL_URL)

    assert engine is create_engine.return_value
    create_engine.assert_called_once_with(
        POSTGRESQL_URL, future=True, hide_parameters=True
    )
    register_decimal_adapters.assert_not_called()
    listens_for.assert_not_called()


@pytest.mark.parametrize("use_string", [False, True], ids=["path", "path-string"])
def test_make_engine_keeps_sqlite_file_behavior(tmp_path, use_string: bool) -> None:
    database_path = tmp_path / f"database-{use_string}.db"
    engine = make_engine(str(database_path) if use_string else database_path)
    metadata = MetaData()
    decimal_probe = Table(
        "decimal_probe",
        metadata,
        Column("value", Numeric(18, 4), nullable=False),
    )

    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(insert(decimal_probe).values(value=Decimal("12.3400")))
            value = connection.scalar(select(decimal_probe.c.value))
            foreign_keys = connection.scalar(text("PRAGMA foreign_keys"))
            journal_mode = connection.scalar(text("PRAGMA journal_mode"))

        assert engine.dialect.name == "sqlite"
        assert isinstance(value, Decimal)
        assert value == Decimal("12.3400")
        assert foreign_keys == 1
        assert journal_mode == "wal"
    finally:
        engine.dispose()

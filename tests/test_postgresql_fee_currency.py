from __future__ import annotations

import os
import re
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


@pytest.mark.live
def test_postgresql_fee_currency_round_trip() -> None:
    if os.environ.get("FADIR_RUN_POSTGRESQL_FEE_CURRENCY") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_FEE_CURRENCY=1 for approved live proof")
    raw = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw or not database:
        raise ValueError("explicit synthetic PostgreSQL URL and database are required")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg" or url.database != database or url.query:
        raise ValueError("synthetic PostgreSQL URL mismatch")
    schema = "fee1_" + uuid4().hex
    marker = "FEE1:" + uuid4().hex
    engine = create_engine(url)
    schema_oid = None
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            schema_oid = connection.scalar(text("SELECT oid FROM pg_namespace WHERE nspname=:schema"), {"schema": schema})
        scoped = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog"})
        scoped_engine = create_engine(scoped)
        try:
            os.environ["FADIR_DATABASE_URL"] = scoped.render_as_string(hide_password=False)
            config = Config("alembic.ini")
            config.set_main_option("script_location", "migrations")
            command.upgrade(config, "head")
            with scoped_engine.begin() as connection:
                columns = {c["name"] for c in inspect(connection).get_columns("transaction")}
                assert {"fee_currency", "fee_fx_rate_to_try", "fee_fx_rate_date", "fee_fx_provider"} <= columns
        finally:
            scoped_engine.dispose()
    finally:
        with engine.begin() as connection:
            record = connection.execute(text("SELECT current_database(), n.oid, pg_catalog.obj_description(n.oid,'pg_namespace') FROM pg_namespace n WHERE n.nspname=:schema"), {"schema": schema}).one_or_none()
            if schema_oid is not None and record is not None and tuple(record) == (database, schema_oid, marker):
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()

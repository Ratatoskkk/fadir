from __future__ import annotations

import os
from pathlib import Path
import re
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.api import routes
from app.api.request_authority import GUEST_COOKIE_NAME


ROOT = Path(routes.__file__).resolve().parents[2]


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_GUEST_BOOTSTRAP") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_GUEST_BOOTSTRAP=1 for approved live proof")
    raw = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw or not database:
        raise ValueError("An explicit synthetic URL and database are required")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg" or url.database != database or url.query:
        raise ValueError("Select a matching synthetic PostgreSQL database without URL options")
    if re.fullmatch(r"fadir_test(?:_[a-z0-9_]+)?", database) is None:
        raise ValueError("Synthetic database selection is unsafe")
    return url


@pytest.mark.live
def test_postgresql_guest_bootstrap_issue_revalidate_and_cleanup(monkeypatch) -> None:
    url = _selected_url()
    schema = "guestboot1_" + uuid4().hex
    marker = "GUEST-BOOTSTRAP-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    schema_oid = None
    scoped_engine = None
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            schema_oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = :schema"),
                {"schema": schema},
            )
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog"})
        monkeypatch.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(config, "head")
        scoped_engine = create_engine(scoped_url, hide_parameters=True)
        application = FastAPI()
        application.state.session_factory = lambda: Session(scoped_engine)
        application.state.configured_origin = "https://ratatosk.dev"
        application.include_router(routes.private_router)
        with TestClient(application, base_url="https://ratatosk.dev") as client:
            first = client.post("/api/guest/bootstrap", headers={"Origin": "https://ratatosk.dev"})
            assert first.status_code == 201
            assert first.json()["created"] is True
            assert first.json()["user"] is None and first.json()["portfolios"] == []
            token = client.cookies.get(GUEST_COOKIE_NAME)
            assert token

            with scoped_engine.begin() as connection:
                workspace_id = connection.scalar(text("SELECT id FROM workspace LIMIT 1"))
                connection.execute(
                    text(
                        "INSERT INTO portfolio (workspace_id, name, base_currency, created_at, updated_at) "
                        "VALUES (:workspace_id, 'Synthetic', 'TRY', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"workspace_id": workspace_id},
                )
            second = client.post("/api/guest/bootstrap", headers={"Origin": "https://ratatosk.dev"})
            assert second.status_code == 200
            assert second.json()["created"] is False
            assert second.json()["guest"]["notice_due"] is True

            with TestClient(application, base_url="https://ratatosk.dev") as invalid_client:
                invalid = invalid_client.post(
                    "/api/guest/bootstrap",
                    headers={"Origin": "https://ratatosk.dev"},
                    cookies={GUEST_COOKIE_NAME: "bad"},
                )
            assert invalid.status_code == 401
            assert "Max-Age=0" in invalid.headers.get("set-cookie", "")

        with scoped_engine.connect() as connection:
            assert inspect(connection).get_table_names(schema=schema)
    finally:
        if scoped_engine is not None:
            scoped_engine.dispose()
        try:
            with engine.begin() as connection:
                record = connection.execute(
                    text(
                        "SELECT current_database(), n.oid, n.nspowner = "
                        "(SELECT oid FROM pg_catalog.pg_roles WHERE rolname = current_user), "
                        "pg_catalog.obj_description(n.oid, 'pg_namespace') "
                        "FROM pg_catalog.pg_namespace AS n WHERE n.nspname = :schema"
                    ),
                    {"schema": schema},
                ).one_or_none()
                if record != (url.database, schema_oid, True, marker):
                    raise RuntimeError("Cleanup refused: synthetic schema ownership mismatch")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            engine.dispose()


def test_postgresql_guest_bootstrap_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("FADIR_RUN_POSTGRESQL_GUEST_BOOTSTRAP", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _selected_url()

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.api import routes
from app.api.csrf import issue_csrf_token
from app.services import guest_access


ROOT = Path(__file__).resolve().parents[1]


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_START") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_START=1 for approved live proof")
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
def test_postgresql_google_login_start_registered_route(monkeypatch) -> None:
    url = _selected_url()
    schema = "reqauth1_" + uuid4().hex
    marker = "GOOGLE-LOGIN-START-1:" + uuid4().hex
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
        now = datetime.now(timezone.utc)
        with Session(scoped_engine) as session, session.begin():
            issued_guest = guest_access.issue(session, clock=lambda: now)
            guest_token = issued_guest.secret.get_secret_value()
        monkeypatch.setattr(
            routes,
            "get_settings",
            lambda: SimpleNamespace(
                google=SimpleNamespace(web_client_id="synthetic-web-client")
            ),
        )
        application = FastAPI()
        application.state.session_factory = lambda: Session(scoped_engine)
        application.state.authority_session_factory = lambda: Session(scoped_engine)
        application.state.configured_origin = "https://ratatosk.dev"
        application.include_router(routes.private_router)
        with TestClient(application, base_url="https://ratatosk.dev") as client:
            csrf = issue_csrf_token()
            result = client.post(
                "/api/auth/google/start",
                headers={"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf},
                cookies={"__Host-fadir-csrf": csrf, "__Host-fadir-guest": guest_token},
            )
        assert result.status_code == 200
        payload = result.json()
        assert payload["client_id"] == "synthetic-web-client"
        assert payload["nonce"]
        assert "state" not in payload
        cookie = result.headers.get("set-cookie", "")
        assert "__Host-fadir-google-state=" in cookie
        assert "HttpOnly" in cookie and "Secure" in cookie
        assert "Max-Age=600" in cookie and "Path=/" in cookie
        assert "SameSite=lax" in cookie and "Domain=" not in cookie
        with scoped_engine.connect() as connection:
            row = connection.execute(
                text("SELECT state_digest, nonce_digest FROM login_transaction")
            ).one()
            assert row[1] == hashlib.sha256(payload["nonce"].encode()).digest()
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


def test_postgresql_google_login_start_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_START", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _selected_url()

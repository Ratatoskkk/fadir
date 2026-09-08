from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
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
from app.models import LoginTransaction
from app.services import guest_access
from app.services.google_identity import VerifiedGoogleIdentity


ROOT = Path(__file__).resolve().parents[1]


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_VERIFICATION") != "1":
        pytest.skip(
            "Set FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_VERIFICATION=1 for approved live proof"
        )
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
def test_postgresql_google_verify_stages_identity_and_is_idempotent(monkeypatch) -> None:
    url = _selected_url()
    schema = "gverify1_" + uuid4().hex
    marker = "GOOGLE-LOGIN-VERIFICATION-1:" + uuid4().hex
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

        with Session(scoped_engine) as session, session.begin():
            issued = guest_access.issue(
                session, clock=lambda: datetime(2026, 9, 8, tzinfo=timezone.utc)
            )
            guest_token = issued.secret.get_secret_value()
            workspace_id = issued.workspace_id

        settings = type("Settings", (), {"google": type("Google", (), {
            "web_client_id": "synthetic-client",
            "verification_timeout_seconds": 1.0,
        })()})()
        monkeypatch.setattr(routes, "get_settings", lambda: settings)
        monkeypatch.setattr(
            routes,
            "verify_google_identity_from_settings",
            lambda credential, **kwargs: VerifiedGoogleIdentity(
                issuer="https://accounts.google.com", subject="synthetic-subject"
            ),
        )
        app = FastAPI()
        app.state.session_factory = lambda: Session(scoped_engine)
        app.state.authority_session_factory = lambda: Session(scoped_engine)
        app.state.configured_origin = "https://ratatosk.dev"
        app.include_router(routes.private_router)

        with TestClient(app, base_url="https://ratatosk.dev") as client:
            csrf = issue_csrf_token()
            client.cookies.set("__Host-fadir-csrf", csrf)
            client.cookies.set("__Host-fadir-guest", guest_token)
            headers = {"Origin": "https://ratatosk.dev", "X-CSRF-Token": csrf}
            started = client.post("/api/auth/google/start", headers=headers)
            assert started.status_code == 200
            nonce = started.json()["nonce"]
            verified = client.post(
                "/api/auth/google/verify",
                headers=headers,
                json={"credential": "synthetic-credential", "nonce": nonce},
            )
            assert verified.status_code == 200
            assert set(verified.json()) == {"expires_at", "choice_needed"}
            repeated = client.post(
                "/api/auth/google/verify",
                headers=headers,
                json={"credential": "synthetic-credential", "nonce": nonce},
            )
            assert repeated.status_code == 200

        with Session(scoped_engine) as session:
            row = session.query(LoginTransaction).one()
            assert row.verified_issuer == "https://accounts.google.com"
            assert row.verified_subject == "synthetic-subject"
            assert row.verified_at is not None
            assert row.consumed_at is None
            assert workspace_id > 0
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


def test_postgresql_google_login_verification_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("FADIR_RUN_POSTGRESQL_GOOGLE_LOGIN_VERIFICATION", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _selected_url()

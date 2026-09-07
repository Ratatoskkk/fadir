"""Opt-in PostgreSQL acceptance proof for request authority."""

from __future__ import annotations

import os
from pathlib import Path
import re
from datetime import datetime, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.request_authority import (
    GUEST_COOKIE_NAME,
    USER_COOKIE_NAME,
    get_request_authority,
)
from app.api.request_transaction import RequestTransactionRoute, request_session
from app.models import Instrument, User, Workspace
from app.services import guest_access, user_sessions


ROOT = Path(__file__).resolve().parents[1]


def _selected_test_url():
    if os.environ.get("FADIR_RUN_POSTGRESQL_REQUEST_AUTHORITY") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_REQUEST_AUTHORITY=1 for approved live proof")
    raw = os.environ.get("FADIR_DATABASE_URL")
    if not raw:
        pytest.skip("FADIR_DATABASE_URL is not configured for live proof")
    url = make_url(raw)
    if (url.get_backend_name(), url.drivername) != ("postgresql", "postgresql+psycopg"):
        pytest.skip("live proof requires postgresql+psycopg")
    if url.database != "fadir_test":
        pytest.skip("live proof requires the approved synthetic database")
    return url


class _CleanupGate:
    def __init__(self) -> None:
        self.call_passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.call_passed = call.excinfo is None


def _drop_owned(connection, schema: str, marker: str, oid: int, database: str) -> None:
    if re.fullmatch(r"reqauth1_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("Cleanup refused: invalid task schema")
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
        raise RuntimeError("Cleanup refused: task schema ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def database(monkeypatch, request):
    url = _selected_test_url()
    schema = "reqauth1_" + uuid4().hex
    marker = "REQUEST-AUTH-1A:" + uuid4().hex
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    engine = create_engine(url, hide_parameters=True)
    scoped = None
    oid = None
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{marker}'"))
            oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"),
                {"name": schema},
            )
        scoped_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog -clock_timeout=2s -cstatement_timeout=5s"}
        )
        with monkeypatch.context() as env:
            env.setenv("FADIR_DATABASE_URL", scoped_url.render_as_string(hide_password=False))
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "migrations"))
            command.upgrade(config, "head")
        scoped = create_engine(scoped_url, hide_parameters=True)
        yield scoped
    finally:
        if scoped is not None:
            scoped.dispose()
        if oid is not None and gate.call_passed:
            with engine.begin() as connection:
                _drop_owned(connection, schema, marker, oid, url.database)
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _client(database, endpoint) -> TestClient:
    app = FastAPI()
    app.state.session_factory = lambda: Session(database)
    router = APIRouter(route_class=RequestTransactionRoute)
    router.add_api_route("/private", endpoint, methods=["GET"])
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_client_does_not_install_catch_all_exception_handler() -> None:
    client = _client(None, lambda: {"ok": True})
    assert Exception not in client.app.exception_handlers


@pytest.mark.live
def test_user_and_guest_cookies_resolve_through_actual_route(database) -> None:
    with Session(database) as session, session.begin():
        user = User(workspace=Workspace())
        session.add(user)
        session.flush()
        issued = user_sessions.issue(
            session, user.id, clock=lambda: datetime.now(timezone.utc)
        )
        last_access_before = session.scalar(
            select(user_sessions.UserSession.last_access_at).where(
                user_sessions.UserSession.public_id == issued.public_id
            )
        )
        workspace_id = user.workspace.id

    def endpoint(authority=Depends(get_request_authority)):
        return {"mode": authority.mode, "workspace_id": authority.workspace_id}

    response = _client(database, endpoint).get(
        "/private",
        cookies={
            USER_COOKIE_NAME: f"{issued.public_id}.{issued.secret.get_secret_value()}",
            GUEST_COOKIE_NAME: "malformed",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "user", "workspace_id": workspace_id}

    with Session(database) as session:
        refreshed = session.scalar(
            select(user_sessions.UserSession.last_access_at).where(
                user_sessions.UserSession.public_id == issued.public_id
            )
        )
        assert last_access_before is not None
        assert refreshed is not None and refreshed > last_access_before


@pytest.mark.live
def test_guest_cookie_resolves_through_actual_route(database) -> None:
    with Session(database) as session, session.begin():
        issued = guest_access.issue(
            session,
            clock=lambda: datetime.now(timezone.utc),
        )
        authority = guest_access.require(
            session,
            issued.secret.get_secret_value(),
            clock=lambda: datetime.now(timezone.utc),
        )
        guest_token = issued.secret.get_secret_value()
        workspace_id = authority.workspace_id

    def endpoint(authority=Depends(get_request_authority)):
        return {"mode": authority.mode, "workspace_id": authority.workspace_id}

    response = _client(database, endpoint).get(
        "/private", cookies={GUEST_COOKIE_NAME: guest_token}
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "guest", "workspace_id": workspace_id}


@pytest.mark.live
def test_route_rollback_flushes_and_removes_pending_write(database) -> None:
    with Session(database) as session, session.begin():
        user = User(workspace=Workspace())
        session.add(user)
        session.flush()
        issued = user_sessions.issue(
            session, user.id, clock=lambda: datetime.now(timezone.utc)
        )

    def endpoint(
        session=Depends(request_session), authority=Depends(get_request_authority)
    ):
        session.add(
            Instrument(
                ticker="ROLLBACK", exchange="SYN", yf_symbol="ROLLBACK",
                currency="TRY", name="Rollback",
            )
        )
        session.flush()
        raise RuntimeError("synthetic failure")

    response = _client(database, endpoint).get(
        "/private",
        cookies={USER_COOKIE_NAME: f"{issued.public_id}.{issued.secret.get_secret_value()}"},
    )
    assert response.status_code == 500
    assert response.headers.get("cache-control") == "no-store"
    with Session(database) as session:
        assert session.scalar(select(Instrument.id).where(Instrument.ticker == "ROLLBACK")) is None

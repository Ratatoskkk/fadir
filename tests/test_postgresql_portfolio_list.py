from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.api.csrf import CSRF_COOKIE_NAME, issue_csrf_token
from app.api.request_authority import GUEST_COOKIE_NAME
from app.main import app
from app.models import Portfolio
from app.services import guest_access


ROOT = Path(__file__).resolve().parents[1]


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_PORTFOLIO_LIST") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_PORTFOLIO_LIST=1 for approved live proof")
    raw = os.environ.get("FADIR_TEST_POSTGRESQL_URL")
    database = os.environ.get("FADIR_TEST_POSTGRESQL_DATABASE")
    if not raw or database != "fadir_test":
        raise ValueError("An explicit synthetic PostgreSQL database is required")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg" or url.database != database or url.query:
        raise ValueError("Select the password-free synthetic PostgreSQL URL")
    return url


class _CleanupGate:
    def __init__(self) -> None:
        self.passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.passed = call.excinfo is None


@pytest.fixture
def database(monkeypatch, request):
    url = _selected_url()
    schema = "portfoliolist1_" + uuid4().hex
    marker = "PORTFOLIO-LIST-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    oid = None
    scoped = None
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            oid = connection.scalar(
                text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"),
                {"name": schema},
            )
        scoped_url = url.update_query_dict(
            {"options": f"-csearch_path={schema},pg_catalog -cstatement_timeout=5s"}
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
        if gate.passed and oid is not None:
            with engine.begin() as connection:
                record = connection.execute(
                    text(
                        "SELECT current_database(), n.oid, "
                        "n.nspowner=(SELECT oid FROM pg_catalog.pg_roles "
                        "WHERE rolname=current_user), "
                        "pg_catalog.obj_description(n.oid, 'pg_namespace') "
                        "FROM pg_catalog.pg_namespace n WHERE n.nspname=:name"
                    ),
                    {"name": schema},
                ).one_or_none()
                if record is None or tuple(record) != (url.database, oid, True, marker):
                    raise RuntimeError("Cleanup refused: schema ownership mismatch")
                if re.fullmatch(r"portfoliolist1_[0-9a-f]{32}", schema) is None:
                    raise RuntimeError("Cleanup refused: invalid schema")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _seed(database) -> tuple[str, str, str, int, int]:
    now = datetime.now(timezone.utc)
    with Session(database) as session, session.begin():
        first = guest_access.issue(session, clock=lambda: now)
        empty = guest_access.issue(session, clock=lambda: now)
        other = guest_access.issue(session, clock=lambda: now)
        session.add_all(
            [
                Portfolio(workspace_id=first.workspace_id, name="Later", base_currency="USD"),
                Portfolio(workspace_id=first.workspace_id, name="Earlier", base_currency="TRY"),
            ]
        )
        session.flush()
        other_portfolio = Portfolio(
            workspace_id=other.workspace_id, name="Other", base_currency="EUR"
        )
        session.add(other_portfolio)
        session.flush()
        return (
            first.secret.get_secret_value(),
            empty.secret.get_secret_value(),
            other.secret.get_secret_value(),
            empty.workspace_id,
            other_portfolio.id,
        )


def _client(database, token: str) -> TestClient:
    app.state.session_factory = lambda: Session(database)
    app.state.authority_session_factory = lambda: Session(database)
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(GUEST_COOKIE_NAME, token)
    csrf = issue_csrf_token()
    client.cookies.set(CSRF_COOKIE_NAME, csrf)
    return client


@pytest.mark.live
def test_postgresql_portfolio_list_is_scoped_ordered_and_non_mutating(database) -> None:
    first_token, empty_token, other_token, empty_workspace_id, other_portfolio_id = _seed(database)
    with TestClient(app, raise_server_exceptions=False) as unauthenticated:
        rejected = unauthenticated.get("/api/portfolios")
    assert rejected.status_code == 401
    assert rejected.headers["cache-control"] == "no-store"

    first_client = _client(database, first_token)
    try:
        listed = first_client.get("/api/portfolios")
        assert listed.status_code == 200, listed.text
        assert listed.headers["cache-control"] == "no-store"
        assert [item["name"] for item in listed.json()] == ["Later", "Earlier"]
        assert all("workspace_id" not in item for item in listed.json())
        cross = first_client.get("/api/portfolios", params={"portfolio_id": other_portfolio_id})
        assert cross.status_code == 200
        assert [item["name"] for item in cross.json()] == ["Later", "Earlier"]
    finally:
        first_client.close()

    other_client = _client(database, other_token)
    try:
        isolated = other_client.get("/api/portfolios")
        assert isolated.status_code == 200
        assert isolated.json() == [
            {"id": other_portfolio_id, "name": "Other", "base_currency": "EUR"}
        ]
    finally:
        other_client.close()

    with Session(database) as session:
        before = session.scalar(
            select(Portfolio.id).where(Portfolio.workspace_id == empty_workspace_id).limit(1)
        )
    empty_client = _client(database, empty_token)
    try:
        assert empty_client.get("/api/portfolios").json() == []
    finally:
        empty_client.close()
    with Session(database) as session:
        after = session.scalar(
            select(Portfolio.id).where(Portfolio.workspace_id == empty_workspace_id).limit(1)
        )
    assert before is None and after is None

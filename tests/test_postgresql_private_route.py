from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.api.request_authority import GUEST_COOKIE_NAME
from app.db import make_engine
from app.main import app
from app.models import FxCache, Instrument, Portfolio, PriceCache, Transaction, Workspace
from app.providers.base import FxQuote
from app.services import guest_access


ROOT = Path(__file__).resolve().parents[1]


def _selected_url():
    if os.environ.get("FADIR_RUN_POSTGRESQL_PRIVATE_ROUTE") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_PRIVATE_ROUTE=1 for approved live proof")
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
        self.passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.passed = call.excinfo is None


def _drop_owned(connection, schema: str, marker: str, oid: int, database: str) -> None:
    if re.fullmatch(r"reqauth1_[0-9a-f]{32}", schema) is None:
        raise RuntimeError("cleanup refused: invalid task schema")
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
        raise RuntimeError("cleanup refused: task schema ownership mismatch")
    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def database(monkeypatch, request):
    url = _selected_url()
    schema = "reqauth1_" + uuid4().hex
    marker = "PRIVATE-ROUTE-1:" + uuid4().hex
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
        if oid is not None and gate.passed:
            with engine.begin() as connection:
                _drop_owned(connection, schema, marker, oid, url.database)
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _guest(database: object) -> tuple[str, int]:
    with Session(database) as session, session.begin():
        issued = guest_access.issue(session, clock=lambda: datetime.now(timezone.utc))
        return issued.secret.get_secret_value(), issued.workspace_id


def _seed(database: object) -> tuple[str, int, int]:
    guest_token, workspace_id = _guest(database)
    with Session(database) as session, session.begin():
        instrument = Instrument(
            ticker="SYN",
            exchange="TEST",
            yf_symbol="SYN.TEST",
            currency="USD",
            name="Synthetic",
        )
        other_workspace = Workspace(portfolios=[Portfolio(name="Other")])
        session.add_all([instrument, other_workspace])
        session.flush()
        session.add_all(
            [
                PriceCache(
                    instrument_id=instrument.id,
                    price_date=date(2026, 1, 1),
                    close_native="10",
                ),
                FxCache(
                    base="USD",
                    quote="TRY",
                    rate_date=date(2026, 1, 1),
                    rate=Decimal("35"),
                    provider="synthetic",
                ),
            ]
        )
        return guest_token, other_workspace.portfolios[0].id, instrument.id


def _client(database: object, guest_token: str) -> TestClient:
    app.state.session_factory = lambda: Session(database)
    app.state.authority_session_factory = lambda: Session(database)
    client = TestClient(app, raise_server_exceptions=False)
    csrf = issue_csrf_token()
    client.cookies.set(GUEST_COOKIE_NAME, guest_token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf)
    client.headers.update({"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: csrf})
    return client


@pytest.mark.live
def test_guest_private_route_scope_and_first_save(database) -> None:
    guest_token, other_portfolio_id, instrument_id = _seed(database)
    client = _client(database, guest_token)
    try:
        listed = client.get("/api/transactions")
        assert listed.status_code == 200
        assert listed.json() == []

        cross = client.get(
            "/api/transactions", params={"portfolio_id": other_portfolio_id}
        )
        assert cross.status_code == 404
        assert cross.json() == {"detail": "request rejected"}

        created = client.post(
            "/api/transactions",
            json={
                "ticker": "SYN",
                "trade_date": "2026-02-01",
                "side": "BUY",
                "quantity": "1",
                "price_native": "10",
                "fx_rate_override": "35",
            },
        )
        assert created.status_code == 201, created.text
    finally:
        client.close()

    with Session(database) as session:
        portfolio = session.scalar(
            select(Portfolio).where(Portfolio.workspace_id == _seed_workspace(database, guest_token))
        )
        assert portfolio is not None
        assert portfolio.name == "Ana Portföy"
        txn = session.scalar(select(Transaction).where(Transaction.instrument_id == instrument_id))
        assert txn is not None and txn.portfolio_id == portfolio.id


def _seed_workspace(database: object, guest_token: str) -> int:
    with Session(database) as session:
        digest = guest_access._digest(guest_token)
        return session.scalar(
            select(guest_access.Workspace.id).join(guest_access.GuestAccess).where(
                guest_access.GuestAccess.secret_digest == digest
            )
        )


@pytest.mark.live
def test_guest_empty_workspace_and_csrf_rejection(database) -> None:
    guest_token, workspace_id = _guest(database)
    client = _client(database, guest_token)
    try:
        assert client.get("/api/transactions").json() == []
        with Session(database) as session:
            assert session.scalar(
                select(Portfolio.id).where(Portfolio.workspace_id == workspace_id)
            ) is None

        rejected = client.post(
            "/api/transactions",
            headers={"Origin": "https://evil.example"},
            json={},
        )
        assert rejected.status_code == 403
        assert rejected.headers["cache-control"] == "no-store"
    finally:
        client.close()


@pytest.mark.live
def test_credentialed_cors_is_origin_scoped(database) -> None:
    client = _client(database, "invalid")
    try:
        allowed = client.options(
            "/api/transactions",
            headers={
                "Origin": "https://ratatosk.dev",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert allowed.headers["access-control-allow-origin"] == "https://ratatosk.dev"
        assert allowed.headers["access-control-allow-credentials"] == "true"

        denied = client.options(
            "/api/transactions",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in denied.headers
    finally:
        client.close()


@pytest.mark.live
def test_provider_work_can_acquire_workspace_lock_during_route(database, monkeypatch) -> None:
    guest_token, workspace_id = _guest(database)
    with Session(database) as session, session.begin():
        session.add(
            Instrument(
                ticker="SYN",
                exchange="TEST",
                yf_symbol="SYN.TEST",
                currency="USD",
                name="Synthetic",
            )
        )
    client = _client(database, guest_token)
    lock_acquired = False

    def quote(_service, currency, on, *, allow_fetch=True):
        nonlocal lock_acquired
        with Session(database) as other:
            try:
                with other.begin():
                    other.execute(
                        select(Workspace)
                        .where(Workspace.id == workspace_id)
                        .with_for_update(nowait=True)
                    ).one()
            except DBAPIError:
                return FxQuote(
                    base=currency,
                    quote="TRY",
                    rate=Decimal("35"),
                    rate_date=on,
                    requested_date=on,
                    provider="synthetic",
                )
            lock_acquired = True
        return FxQuote(
            base=currency,
            quote="TRY",
            rate=Decimal("35"),
            rate_date=on,
            requested_date=on,
            provider="synthetic",
        )

    monkeypatch.setattr("app.api.routes.FxService.quote", quote)
    try:
        response = client.post(
            "/api/transactions",
            json={
                "ticker": "SYN",
                "trade_date": "2026-02-01",
                "side": "BUY",
                "quantity": "1",
                "price_native": "10",
            },
        )
        assert response.status_code == 201
    finally:
        client.close()
    assert lock_acquired

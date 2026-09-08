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
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app import models
from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.api.request_authority import GUEST_COOKIE_NAME, USER_COOKIE_NAME
from app.main import app
from app.services import guest_access, user_sessions


ROOT = Path(__file__).resolve().parents[1]


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_PRIVACY") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_PRIVACY=1 for approved live proof")
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
    schema = "privacy1_" + uuid4().hex
    marker = "DATA-PORTABILITY-DELETION-1:" + uuid4().hex
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
                if re.fullmatch(r"privacy1_[0-9a-f]{32}", schema) is None:
                    raise RuntimeError("Cleanup refused: invalid schema")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _seed(database) -> tuple[int, int, int, int, int, str, str]:
    now = datetime.now(timezone.utc)
    with Session(database) as session, session.begin():
        user = models.User(workspace=models.Workspace())
        other_user = models.User(workspace=models.Workspace())
        guest = guest_access.issue(session, clock=lambda: now)
        own = models.Portfolio(workspace=user.workspace, name="Private", base_currency="TRY")
        remaining = models.Portfolio(workspace=user.workspace, name="Remaining", base_currency="USD")
        other = models.Portfolio(workspace=other_user.workspace, name="Other", base_currency="EUR")
        instrument = models.Instrument(
            ticker="SYN", exchange="TEST", yf_symbol="SYN.TEST", currency="USD", name="Synthetic"
        )
        session.add_all([user, other_user, own, remaining, other, instrument])
        session.flush()
        session.add_all(
            [
                models.Transaction(
                    portfolio=own,
                    instrument=instrument,
                    trade_date=date(2026, 1, 2),
                    side=models.Side.BUY,
                    quantity=Decimal("2"),
                    price_native=Decimal("10.25"),
                    fees_native=Decimal("0.50"),
                    fx_rate_to_try=Decimal("35"),
                    fx_rate_date=date(2026, 1, 2),
                    fx_provider="synthetic",
                    note="private",
                ),
                models.Snapshot(
                    portfolio=own,
                    snapshot_date=date(2026, 1, 2),
                    payload_json='{"value":"20.50"}',
                ),
                models.LoginIdentity(user=user, issuer="synthetic", subject="privacy-user"),
                models.TaxProfile(
                    user=user,
                    jurisdiction="TR",
                    tax_year=2026,
                    currency="TRY",
                    source_url="https://example.invalid/source",
                    source_version="synthetic",
                    assumptions_json="[]",
                    disclaimer="synthetic",
                ),
            ]
        )
        session.flush()
        issued = user_sessions.issue(session, user.id, clock=lambda: now)
        return (
            user.id,
            user.workspace.id,
            own.id,
            remaining.id,
            other.id,
            f"{issued.public_id}.{issued.secret.get_secret_value()}",
            guest.secret.get_secret_value(),
        )


@pytest.mark.live
def test_postgresql_privacy_export_and_deletion_boundaries(database) -> None:
    user_id, workspace_id, portfolio_id, remaining_id, other_portfolio_id, user_cookie, guest_cookie = _seed(database)
    with TestClient(app, raise_server_exceptions=False) as unauthenticated:
        assert unauthenticated.get(f"/api/portfolios/{portfolio_id}/export").status_code == 401
        unauthenticated.cookies.set(GUEST_COOKIE_NAME, guest_cookie)
        assert unauthenticated.get(f"/api/portfolios/{portfolio_id}/export").status_code == 401
    app.state.session_factory = lambda: Session(database)
    app.state.authority_session_factory = lambda: Session(database)
    csrf = issue_csrf_token()
    with TestClient(app, base_url="https://ratatosk.dev", raise_server_exceptions=False) as client:
        client.cookies.set(USER_COOKIE_NAME, user_cookie)
        client.cookies.set(CSRF_COOKIE_NAME, csrf)
        client.headers.update({"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: csrf})
        exported = client.get(f"/api/portfolios/{portfolio_id}/export?format=json")
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        assert "secret" not in exported.text.lower()
        assert exported.json()["transactions"][0]["ticker"] == "SYN"
        assert exported.json()["transactions"][0]["currency"] == "USD"
        csv_export = client.get(f"/api/portfolios/{portfolio_id}/export?format=csv")
        assert csv_export.status_code == 200
        assert "SYN" in csv_export.text and "USD" in csv_export.text
        assert client.get(f"/api/portfolios/{other_portfolio_id}/export").status_code == 404
        deleted = client.delete(f"/api/portfolios/{portfolio_id}")
        assert deleted.status_code == 204
        with Session(database) as session:
            assert session.scalar(select(models.Transaction).where(models.Transaction.portfolio_id == portfolio_id)) is None
            assert session.scalar(select(models.Snapshot).where(models.Snapshot.portfolio_id == portfolio_id)) is None
        account = client.delete("/api/account")
        assert account.status_code == 204
        assert "__Host-fadir-user=" in account.headers.get("set-cookie", "")

    with Session(database) as session:
        assert session.get(models.User, user_id) is None
        assert session.get(models.Workspace, workspace_id) is None
        assert session.get(models.Portfolio, remaining_id) is None
        assert session.scalar(select(models.LoginIdentity).where(models.LoginIdentity.user_id == user_id)) is None
        assert session.scalar(select(models.TaxProfile).where(models.TaxProfile.user_id == user_id)) is None
        assert session.scalar(select(models.UserSession).where(models.UserSession.user_id == user_id)) is None

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import re
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app import models
from app.api import routes
from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.api.request_authority import GUEST_COOKIE_NAME, USER_COOKIE_NAME
from app.services import guest_access, user_sessions


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


def _selected_url() -> URL:
    if os.environ.get("FADIR_RUN_POSTGRESQL_MERGE_HTTP") != "1":
        pytest.skip("Set FADIR_RUN_POSTGRESQL_MERGE_HTTP=1 for approved live proof")
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


class _CleanupGate:
    def __init__(self) -> None:
        self.passed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call) -> None:
        if call.when == "call":
            self.passed = call.excinfo is None


@pytest.fixture
def http_database(monkeypatch, request):
    url = _selected_url()
    schema = "mhttp1_" + uuid4().hex
    marker = "MERGE-HTTP-BRIDGE-1:" + uuid4().hex
    engine = create_engine(url, hide_parameters=True)
    scoped = None
    oid = None
    gate = _CleanupGate()
    request.config.pluginmanager.register(gate)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'COMMENT ON SCHEMA "{schema}" IS \'{marker}\''))
            oid = connection.scalar(text("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=:name"), {"name": schema})
        scoped_url = url.update_query_dict({"options": f"-csearch_path={schema},pg_catalog -cstatement_timeout=5s"})
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
                record = connection.execute(text("SELECT current_database(), n.oid, n.nspowner=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user), pg_catalog.obj_description(n.oid, 'pg_namespace') FROM pg_catalog.pg_namespace n WHERE nspname=:name"), {"name": schema}).one_or_none()
                if record is None or tuple(record) != (url.database, oid, True, marker):
                    raise RuntimeError("Cleanup refused: schema ownership mismatch")
                if re.fullmatch(r"mhttp1_[0-9a-f]{32}", schema) is None:
                    raise RuntimeError("Cleanup refused: invalid schema")
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
        request.config.pluginmanager.unregister(gate)


def _setup(database):
    with Session(database, expire_on_commit=False) as session, session.begin():
        user = models.User(workspace=models.Workspace())
        session.add(user)
        session.flush()
        guest = guest_access.issue(session, clock=lambda: NOW)
        source = models.Portfolio(workspace_id=guest.workspace_id, name="Guest", base_currency="USD")
        target = models.Portfolio(workspace_id=user.workspace.id, name="Target", base_currency="TRY")
        instrument = models.Instrument(ticker="HTTP", exchange="SYN", yf_symbol="HTTP", currency="USD", name="Synthetic")
        session.add_all([source, target, instrument])
        session.flush()

        def add(portfolio, *, fees, note):
            row = models.Transaction(
                portfolio_id=portfolio.id,
                instrument_id=instrument.id,
                trade_date=date(2026, 1, 1),
                side=models.Side.BUY,
                quantity=Decimal("2"),
                price_native=Decimal("10"),
                fees_native=Decimal(fees),
                fx_rate_to_try=Decimal("30"),
                fx_rate_date=date(2026, 1, 1),
                fx_provider="manual",
                note=note,
            )
            session.add(row)
            session.flush()
            return row

        source_one = add(source, fees="1", note="one")
        source_two = add(source, fees="2", note="two")
        target_one = add(target, fees="9", note="target-one")
        target_two = add(target, fees="2", note="target-two")
        user_session = user_sessions.issue(session, user.id, clock=lambda: NOW)
        return user.id, user.workspace.id, guest, source, target, source_one, source_two, target_one, target_two, user_session


@pytest.mark.live
def test_http_options_preview_confirm_use_real_authority_and_guest(http_database):
    user_id, workspace_id, guest, source, target, source_one, source_two, _target_one, _target_two, user_session = _setup(http_database)
    app = FastAPI()
    app.state.session_factory = lambda: Session(http_database)
    app.state.authority_session_factory = lambda: Session(http_database)
    app.state.configured_origin = "https://ratatosk.dev"
    app.include_router(routes.private_router)
    user_cookie = f"{user_session.public_id}.{user_session.secret.get_secret_value()}"
    guest_cookie = guest.secret.get_secret_value()
    try:
        with TestClient(app, base_url="https://ratatosk.dev") as client:
            client.cookies.set(USER_COOKIE_NAME, user_cookie)
            client.cookies.set(GUEST_COOKIE_NAME, guest_cookie)
            csrf = issue_csrf_token()
            client.cookies.set(CSRF_COOKIE_NAME, csrf)
            client.headers.update({"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: csrf})
            options = client.get("/api/portfolio/merge/options")
            assert options.status_code == 200, options.text
            assert options.headers["cache-control"] == "no-store"
            body = options.json()
            assert {item["id"] for item in body["source"]} == {source.id}
            assert {item["id"] for item in body["target"]} == {target.id}
            assert "workspace_id" not in options.text and guest_cookie not in options.text
            preview = client.post("/api/portfolio/merge/preview", json={"source_portfolio_id": source.id, "target_portfolio_id": target.id})
            assert preview.status_code == 200, preview.text
            stale_token = preview.json()["revision_token"]
            with Session(http_database) as mutate:
                mutate.execute(update(models.Transaction).where(models.Transaction.id == source_one.id).values(note="changed"))
                mutate.commit()
            stale = client.post("/api/portfolio/merge/confirm", json={"source_portfolio_id": source.id, "target_portfolio_id": target.id, "revision_token": stale_token, "decisions": [{"source_transaction_id": source_one.id, "action": "keep"}, {"source_transaction_id": source_two.id, "action": "skip"}]})
            assert stale.status_code == 409
            fresh = client.post("/api/portfolio/merge/preview", json={"source_portfolio_id": source.id, "target_portfolio_id": target.id})
            token = fresh.json()["revision_token"]
            confirmed = client.post("/api/portfolio/merge/confirm", json={"source_portfolio_id": source.id, "target_portfolio_id": target.id, "revision_token": token, "decisions": [{"source_transaction_id": source_one.id, "action": "keep"}, {"source_transaction_id": source_two.id, "action": "skip"}]})
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.headers["cache-control"] == "no-store"
            cross = client.post("/api/portfolio/merge/preview", json={"source_portfolio_id": source.id, "target_portfolio_id": source.id})
            assert cross.status_code == 409
        with Session(http_database) as check:
            kept = check.get(models.Transaction, source_one.id)
            skipped = check.get(models.Transaction, source_two.id)
            assert kept.portfolio_id == target.id and kept.price_native == Decimal("10") and kept.note == "changed"
            assert skipped.portfolio_id == source.id and skipped.note == "two"
            source_portfolio = check.get(models.Portfolio, source.id)
            assert source_portfolio.workspace_id == guest.workspace_id
            assert check.get(models.Workspace, guest.workspace_id).user_id is None
            assert check.get(models.Workspace, workspace_id).user_id == user_id
            guest_access_row = check.get(models.GuestAccess, guest.workspace_id)
            assert guest_access_row is not None and guest_access_row.revoked_at is None
    finally:
        pass

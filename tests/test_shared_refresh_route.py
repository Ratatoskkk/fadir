from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.api.request_authority import RequestAuthority, get_request_authority
from app.models import CorporateAction, FxCache, Instrument, Portfolio, PriceCache, Side, Transaction, Workspace
from app.providers import fx_service as fx_service_module
from app.providers import price_service as price_service_module
from app.providers.base import SplitEvent


class StubFxProvider:
    name = "fixture"

    def is_triangulated(self, currency: str) -> bool:
        return False

    def provenance(self, currency: str) -> str:
        return self.name

    def rate(self, base: str, quote: str, on: date) -> Decimal:
        return Decimal("5.50")

    def series(self, base: str, quote: str, start: date, end: date) -> dict[date, Decimal]:
        return {end: Decimal("5.50")}


def _seed_refresh_state(session):
    workspace = Workspace(
        portfolios=[Portfolio(name="First"), Portfolio(name="Second")]
    )
    instruments = [
        Instrument(
            ticker="GOOD",
            exchange="NYSE",
            yf_symbol="GOOD.TEST",
            currency="EUR",
            name="Good Synthetic",
        ),
        Instrument(
            ticker="BROKEN",
            exchange="NYSE",
            yf_symbol="BROKEN.TEST",
            currency="EUR",
            name="Broken Synthetic",
        ),
    ]
    session.add_all([workspace, *instruments])
    session.flush()
    for portfolio in workspace.portfolios:
        for instrument in instruments:
            session.add(
                Transaction(
                    portfolio_id=portfolio.id,
                    instrument_id=instrument.id,
                    trade_date=date(2026, 5, 1),
                    side=Side.BUY,
                    quantity=Decimal("10"),
                    price_native=Decimal("100"),
                    fees_native=Decimal("2"),
                    fx_rate_to_try=Decimal("40"),
                    fx_rate_date=date(2026, 5, 1),
                    fx_provider="fixture",
                )
            )
    session.commit()
    session.expire_all()
    return workspace, instruments


def _stub_providers(monkeypatch, calls: list[str] | None = None) -> None:
    def fetch_batch(symbols, start, end):
        if calls is not None:
            calls.append("prices")
        return {"GOOD.TEST": {date.today(): Decimal("101.25")}, "BROKEN.TEST": {}}

    def fetch_splits(symbol):
        if calls is not None:
            calls.append(f"splits:{symbol}")
        if symbol == "GOOD.TEST":
            return [SplitEvent(action_date=date(2026, 6, 1), ratio=Decimal("2"))]
        return []

    monkeypatch.setattr(
        price_service_module.yf_client,
        "fetch_close_series_batch",
        fetch_batch,
    )
    monkeypatch.setattr(price_service_module.yf_client, "fetch_splits", fetch_splits)
    monkeypatch.setattr(
        fx_service_module,
        "build_providers",
        lambda settings: {"yfinance": StubFxProvider(), "tcmb": StubFxProvider()},
    )


def _private_sql(statements: list[str]) -> list[str]:
    return [
        statement
        for statement in statements
        if '"transaction"' in statement or '"portfolio"' in statement
    ]


@pytest.fixture
def authorized_refresh_client(session, monkeypatch):
    from app.main import app

    workspace, instruments = _seed_refresh_state(session)
    authority = RequestAuthority(mode="guest", user_id=None, workspace_id=workspace.id)
    app.dependency_overrides[get_request_authority] = lambda: authority
    try:
        with TestClient(app) as client:
            token = issue_csrf_token()
            client.cookies.set(CSRF_COOKIE_NAME, token)
            client.headers.update(
                {"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: token}
            )
            yield client, session, workspace, instruments
    finally:
        app.dependency_overrides.pop(get_request_authority, None)


def test_refresh_requires_private_request_authority(tmp_db, monkeypatch):
    from app.main import app
    from app.providers import yf_client

    monkeypatch.setattr(yf_client, "fetch_close_series_batch", lambda *args, **kwargs: {})
    monkeypatch.setattr(yf_client, "fetch_splits", lambda *args, **kwargs: [])

    with TestClient(app) as client:
        response = client.post("/api/refresh")

    assert response.status_code == 401


def test_authorized_refresh_updates_shared_rows_only(authorized_refresh_client, monkeypatch):
    client, session, _workspace, instruments = authorized_refresh_client
    _stub_providers(monkeypatch)
    statements: list[str] = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(session.bind, "before_cursor_execute", record_sql)
    try:
        response = client.post("/api/refresh")
    finally:
        event.remove(session.bind, "before_cursor_execute", record_sql)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "ok",
        "price_rows_written",
        "splits_found",
        "splits_applied",
        "errors",
        "per_instrument",
    }
    assert body["splits_applied"] == 0
    assert body["per_instrument"]["GOOD"]["ok"] is True
    assert body["per_instrument"]["BROKEN"]["ok"] is False
    assert _private_sql(statements) == []

    session.expire_all()
    rows = list(session.scalars(select(Transaction).order_by(Transaction.id)))
    assert all(row.quantity == Decimal("10") for row in rows)
    assert all(row.price_native == Decimal("100") for row in rows)
    assert session.scalar(select(PriceCache).where(PriceCache.instrument_id == instruments[0].id))
    assert session.scalar(select(CorporateAction).where(CorporateAction.instrument_id == instruments[0].id))
    assert session.scalar(select(FxCache).where(FxCache.base == "EUR"))


def test_refresh_handler_leaves_shared_writes_for_caller_rollback(session, monkeypatch):
    from app.api.routes import refresh
    from app.config import get_settings

    workspace, instruments = _seed_refresh_state(session)
    _stub_providers(monkeypatch)
    authority = RequestAuthority(mode="guest", user_id=None, workspace_id=workspace.id)

    def fail_commit():
        raise AssertionError("the refresh handler must not commit")

    monkeypatch.setattr(session, "commit", fail_commit)
    result = refresh(session, get_settings(), authority)

    assert result.splits_applied == 0
    assert session.scalar(select(PriceCache).where(PriceCache.instrument_id == instruments[0].id))
    assert session.scalar(select(CorporateAction).where(CorporateAction.instrument_id == instruments[0].id))
    assert session.scalar(select(FxCache).where(FxCache.base == "EUR"))

    session.rollback()

    assert session.scalar(select(PriceCache)) is None
    assert session.scalar(select(CorporateAction)) is None
    assert session.scalar(select(FxCache)) is None

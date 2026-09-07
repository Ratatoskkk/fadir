from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import event, select

from app.models import FxCache, Instrument, Portfolio, PriceCache, Side, Transaction, Workspace
from app.providers import fx_service as fx_service_module
from app.providers import price_service as price_service_module


class StubFxProvider:
    name = "fixture"

    def provenance(self, currency: str) -> str:
        return self.name

    def rate(self, base: str, quote: str, on: date) -> Decimal:
        return Decimal("1.50")

    def series(self, base: str, quote: str, start: date, end: date) -> dict[date, Decimal]:
        return {end: Decimal("1.50")}


def _seed_private_state(session) -> Instrument:
    workspace = Workspace(
        portfolios=[Portfolio(name="First"), Portfolio(name="Second")]
    )
    instrument = Instrument(
        ticker="SHARED",
        exchange="NYSE",
        yf_symbol="SHARED.TEST",
        currency="USD",
        name="Shared Test Instrument",
        active=True,
    )
    session.add_all([workspace, instrument])
    session.flush()
    for portfolio in workspace.portfolios:
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
    return instrument


def test_background_refresh_warms_shared_rows_without_private_sql(
    session, monkeypatch
):
    instrument = _seed_private_state(session)
    before = list(session.scalars(select(Transaction).order_by(Transaction.id)))

    monkeypatch.setattr(
        price_service_module.yf_client,
        "fetch_close_series_batch",
        lambda symbols, start, end: {
            instrument.yf_symbol: {date.today(): Decimal("101.25")}
        },
    )
    monkeypatch.setattr(
        price_service_module.yf_client,
        "fetch_splits",
        lambda symbol: [],
    )
    monkeypatch.setattr(
        fx_service_module,
        "build_providers",
        lambda settings: {"yfinance": StubFxProvider(), "tcmb": StubFxProvider()},
    )

    statements: list[str] = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(session.bind, "before_cursor_execute", record_sql)
    try:
        from app.main import _refresh_once

        assert _refresh_once() == 1
    finally:
        event.remove(session.bind, "before_cursor_execute", record_sql)

    private_statements = [
        statement
        for statement in statements
        if '"transaction"' in statement or '"portfolio"' in statement
    ]
    assert private_statements == []

    session.expire_all()
    after = list(session.scalars(select(Transaction).order_by(Transaction.id)))
    assert [(row.quantity, row.price_native) for row in after] == [
        (row.quantity, row.price_native) for row in before
    ]
    assert session.scalar(select(PriceCache).where(PriceCache.instrument_id == instrument.id))
    assert session.scalar(select(FxCache).where(FxCache.base == "USD"))

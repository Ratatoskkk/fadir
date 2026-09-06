from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session, selectinload

from app.calc.tax import TaxConfig
from app.config import Settings
from app.db import make_engine
from app.models import Instrument, Portfolio, Side, Transaction, User, Workspace
from app.providers.base import FxQuote
from app.services.portfolio import PortfolioService
from app.services.portfolio_scope import (
    PortfolioScope,
    PortfolioScopeNotFound,
    PortfolioScopeViolation,
)


class StubPrices:
    def last_two_cached_closes(self, instrument_id: int):
        return (
            (Decimal("12"), date(2026, 1, 2)),
            (Decimal("11"), date(2026, 1, 1)),
        )

    def cached_closes(self, instrument_id: int, start: date, end: date):
        return {
            date(2026, 1, 2): Decimal("12"),
            date(2026, 1, 3): Decimal("13"),
        }


class StubFx:
    def _quote(self, on: date) -> FxQuote:
        return FxQuote(
            base="USD",
            quote="TRY",
            rate=Decimal("35"),
            rate_date=on,
            requested_date=on,
            provider="synthetic",
        )

    def current(self, currency: str, *, force: bool = False) -> FxQuote:
        return self._quote(date(2026, 1, 2))

    def quote(self, currency: str, on: date, *, allow_fetch: bool = True) -> FxQuote:
        return self._quote(on)

    def published_series(self, currency: str, start: date, end: date):
        return {
            day: Decimal("35")
            for day in (date(2026, 1, 2), date(2026, 1, 3))
        }


class StubIntraday:
    def prices(self, symbols: list[str], interval: str, *, force: bool, errors: list[str]):
        stamp = datetime(2026, 1, 2, 10, tzinfo=timezone.utc)
        return {symbol: {stamp: Decimal("12")} for symbol in symbols}

    def fx(self, currencies: list[str], interval: str, *, force: bool, errors: list[str]):
        stamp = datetime(2026, 1, 2, 10, tzinfo=timezone.utc)
        return {currency: {stamp: Decimal("35")} for currency in currencies}


@pytest.fixture
def scoped_fixture(tmp_path):
    from app import models

    engine = make_engine(tmp_path / "portfolio-service-scope.db")
    models.Base.metadata.create_all(engine)
    session = Session(engine)

    first = Workspace(portfolios=[Portfolio(name="First"), Portfolio(name="Second")])
    second = Workspace(portfolios=[Portfolio(name="Third"), Portfolio(name="Empty")])
    session.add_all([User(), first, second])
    session.flush()

    first_portfolio, second_portfolio = first.portfolios
    third_portfolio, empty_portfolio = second.portfolios
    shared = Instrument(
        ticker="SYN",
        exchange="TEST",
        yf_symbol="SYN.TEST",
        currency="USD",
        name="Synthetic Shared Instrument",
    )
    other = Instrument(
        ticker="OTHER",
        exchange="TEST",
        yf_symbol="OTHER.TEST",
        currency="USD",
        name="Other Instrument",
    )
    inactive = Instrument(
        ticker="OLD",
        exchange="TEST",
        yf_symbol="OLD.TEST",
        currency="USD",
        name="Inactive Instrument",
        active=False,
    )
    session.add_all([shared, other, inactive])
    session.flush()

    transactions = [
        Transaction(
            instrument_id=shared.id,
            portfolio_id=first_portfolio.id,
            trade_date=date(2026, 1, 2),
            side=Side.BUY,
            quantity=Decimal("2"),
            price_native=Decimal("10"),
            fees_native=Decimal("1"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 2),
            fx_provider="synthetic",
        ),
        Transaction(
            instrument_id=shared.id,
            portfolio_id=second_portfolio.id,
            trade_date=date(2026, 1, 3),
            side=Side.BUY,
            quantity=Decimal("5"),
            price_native=Decimal("20"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 3),
            fx_provider="synthetic",
        ),
        Transaction(
            instrument_id=other.id,
            portfolio_id=second_portfolio.id,
            trade_date=date(2026, 1, 2),
            side=Side.BUY,
            quantity=Decimal("1"),
            price_native=Decimal("30"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 2),
            fx_provider="synthetic",
        ),
        Transaction(
            instrument_id=shared.id,
            portfolio_id=None,
            trade_date=date(2026, 1, 1),
            side=Side.BUY,
            quantity=Decimal("100"),
            price_native=Decimal("1"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 1),
            fx_provider="synthetic",
        ),
        Transaction(
            instrument_id=inactive.id,
            portfolio_id=first_portfolio.id,
            trade_date=date(2026, 1, 2),
            side=Side.BUY,
            quantity=Decimal("3"),
            price_native=Decimal("4"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 2),
            fx_provider="synthetic",
        ),
        Transaction(
            instrument_id=shared.id,
            portfolio_id=third_portfolio.id,
            trade_date=date(2026, 1, 4),
            side=Side.BUY,
            quantity=Decimal("7"),
            price_native=Decimal("25"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 4),
            fx_provider="synthetic",
        ),
    ]
    session.add_all(transactions)
    session.commit()

    # Contaminate relationship collections before the facade runs.
    session.scalars(
        select(Instrument).options(selectinload(Instrument.transactions))
    ).all()

    settings = Settings(tax=TaxConfig(enabled=False))
    service = PortfolioService(
        session,
        settings,
        fx_service=StubFx(),
        price_service=StubPrices(),
        intraday_service=StubIntraday(),
    )
    data = SimpleNamespace(
        engine=engine,
        session=session,
        service=service,
        first_workspace_id=first.id,
        second_workspace_id=second.id,
        first_portfolio_id=first_portfolio.id,
        second_portfolio_id=second_portfolio.id,
        third_portfolio_id=third_portfolio.id,
        empty_portfolio_id=empty_portfolio.id,
        first_transaction_id=transactions[0].id,
    )
    yield data
    session.close()
    engine.dispose()


def test_scoped_facade_is_present_and_filters_private_rows(scoped_fixture):
    data = scoped_fixture
    scope = PortfolioScope.require(
        data.session,
        workspace_id=data.first_workspace_id,
        portfolio_id=data.first_portfolio_id,
    )
    data.session.expire_all()

    scoped = data.service.scoped(scope)
    assert scoped.inception() == date(2026, 1, 2)
    with pytest.raises(PortfolioScopeViolation):
        scoped.refresh()

    view = scoped.build_view(now_utc=datetime(2026, 1, 2, tzinfo=timezone.utc))

    assert [position.ticker for position in view.positions] == ["SYN"]
    assert view.positions[0].quantity == Decimal("2")
    assert view.positions[0].average_purchase_price_native == Decimal("10.5")


def test_scoped_history_and_intraday_keep_shared_inputs_without_relationship_mutation(
    scoped_fixture,
):
    data = scoped_fixture
    scope = PortfolioScope.require(
        data.session,
        workspace_id=data.first_workspace_id,
        portfolio_id=data.first_portfolio_id,
    )
    scoped = data.service.scoped(scope)

    before = {
        row.id: (row.portfolio_id, row.quantity, row.price_native)
        for row in data.session.scalars(select(Transaction))
    }
    history = scoped.build_history(date(2026, 1, 2), date(2026, 1, 2))
    intraday, warnings, available = scoped.build_intraday()
    data.session.flush()

    assert history[0].cost_basis_try == Decimal("735")
    assert len(intraday) == 1
    assert intraday[0].value_try == Decimal("840")
    assert warnings == []
    assert available == 1
    assert {
        row.id: (row.portfolio_id, row.quantity, row.price_native)
        for row in data.session.scalars(select(Transaction))
    } == before


def test_scoped_tickers_use_one_not_found_result_and_empty_portfolio_is_safe(
    scoped_fixture,
):
    data = scoped_fixture
    scope = PortfolioScope.require(
        data.session,
        workspace_id=data.first_workspace_id,
        portfolio_id=data.first_portfolio_id,
    )
    scoped = data.service.scoped(scope)

    errors = []
    for ticker in ("NOPE", "OTHER"):
        with pytest.raises(PortfolioScopeNotFound) as caught:
            scoped.build_history(
                date(2026, 1, 2), date(2026, 1, 2), tickers=[ticker]
            )
        errors.append((type(caught.value), str(caught.value)))
    assert errors[0] == errors[1]

    empty_scope = PortfolioScope.require(
        data.session,
        workspace_id=data.second_workspace_id,
        portfolio_id=data.empty_portfolio_id,
    )
    empty = data.service.scoped(empty_scope)
    assert empty.build_view().positions == []
    assert empty.build_history(date(2026, 1, 2), date(2026, 1, 2)) == []
    assert empty.build_intraday() == ([], [], 0)


def test_scoped_facade_rejects_missing_cross_session_and_detached_scope(scoped_fixture):
    data = scoped_fixture

    with pytest.raises(PortfolioScopeViolation):
        data.service.scoped(None)  # type: ignore[arg-type]

    other_session = Session(data.engine)
    try:
        other_scope = PortfolioScope.require(
            other_session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )
        with pytest.raises(PortfolioScopeViolation):
            data.service.scoped(other_scope)
    finally:
        other_session.close()

    detached = PortfolioScope.require(
        data.session,
        workspace_id=data.first_workspace_id,
        portfolio_id=data.first_portfolio_id,
    )
    data.session.expunge(detached.portfolio)
    with pytest.raises(PortfolioScopeViolation):
        data.service.scoped(detached)


def test_scoped_transaction_sql_has_a_portfolio_predicate(scoped_fixture):
    data = scoped_fixture
    scope = PortfolioScope.require(
        data.session,
        workspace_id=data.first_workspace_id,
        portfolio_id=data.first_portfolio_id,
    )
    data.session.expire_all()
    statements: list[tuple[str, object]] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append((statement.lower(), _parameters))

    event.listen(data.engine, "before_cursor_execute", capture)
    try:
        data.service.scoped(scope).build_view()
    finally:
        event.remove(data.engine, "before_cursor_execute", capture)

    transaction_reads = [
        entry
        for entry in statements
        if "transaction" in entry[0] and entry[0].lstrip().startswith("select")
    ]
    assert transaction_reads, statements
    assert all(
        "portfolio_id" in " ".join(statement.split()).split(" where ", 1)[1]
        for statement, _parameters in transaction_reads
    )
    assert any(
        str(data.first_portfolio_id) in str(parameters)
        for _statement, parameters in transaction_reads
    )

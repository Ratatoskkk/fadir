"""Shared market refresh must not mutate private Portfolio rows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.config import get_settings
from app.models import CorporateAction, Instrument, Portfolio, Transaction, Workspace
from app.providers import price_service as price_service_module
from app.providers.base import SplitEvent
from app.providers.price_service import PriceService


def _shared_instrument(session) -> Instrument:
    instrument = Instrument(
        ticker="SHARED",
        exchange="NYSE",
        yf_symbol="SHARED",
        currency="USD",
        name="Shared Test Instrument",
        active=True,
    )
    session.add(instrument)
    session.flush()
    return instrument


def _private_portfolio(session, name: str) -> Portfolio:
    workspace = Workspace()
    session.add(workspace)
    session.flush()
    portfolio = Portfolio(workspace_id=workspace.id, name=name, base_currency="TRY")
    session.add(portfolio)
    session.flush()
    return portfolio


def _private_transaction(session, portfolio: Portfolio, instrument: Instrument) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio.id,
        instrument_id=instrument.id,
        trade_date=date(2026, 5, 1),
        side="BUY",
        quantity=Decimal("10"),
        price_native=Decimal("100"),
        fees_native=Decimal("2"),
        fx_rate_to_try=Decimal("40"),
        fx_rate_date=date(2026, 5, 1),
        fx_provider="fixture",
    )
    session.add(transaction)
    session.flush()
    return transaction


def _stub_shared_provider(monkeypatch, *, calls: list[str] | None = None) -> None:
    def fetch_batch(symbols, start, end):
        if calls is not None:
            calls.append("prices")
        return {"SHARED": {date(2026, 9, 4): Decimal("101.25")}}

    def fetch_splits(symbol):
        if calls is not None:
            calls.append("splits")
        return [SplitEvent(action_date=date(2026, 6, 1), ratio=Decimal("2"))]

    monkeypatch.setattr(
        price_service_module.yf_client,
        "fetch_close_series_batch",
        fetch_batch,
    )
    monkeypatch.setattr(price_service_module.yf_client, "fetch_splits", fetch_splits)


def _commit_fixture(session, instrument, first, second):
    _private_transaction(session, first, instrument)
    _private_transaction(session, second, instrument)
    session.commit()
    session.expire_all()


def test_shared_force_refresh_does_not_read_or_mutate_private_rows(
    session, monkeypatch
):
    instrument = _shared_instrument(session)
    first = _private_portfolio(session, "First")
    second = _private_portfolio(session, "Second")
    _commit_fixture(session, instrument, first, second)
    before = list(
        session.scalars(
            select(Transaction).order_by(Transaction.portfolio_id)
        )
    )
    instrument_id = instrument.id
    session.expunge_all()
    instrument = session.get(Instrument, instrument_id)
    _stub_shared_provider(monkeypatch)

    statements: list[str] = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(session.bind, "before_cursor_execute", record_sql)
    try:
        report = PriceService(session, get_settings()).refresh_shared(
            [instrument], date(2026, 9, 1), date(2026, 9, 6), force=True
        )
    finally:
        event.remove(session.bind, "before_cursor_execute", record_sql)

    assert report.splits_found == 1
    assert report.splits_applied == 0
    private_statements = [
        statement
        for statement in statements
        if " transaction " in f" {statement} "
        or ' transaction.' in statement
        or '"transaction"' in statement
    ]
    assert private_statements == []

    after = list(
        session.scalars(
            select(Transaction).order_by(Transaction.portfolio_id)
        )
    )
    assert [(row.quantity, row.price_native, row.fees_native) for row in after] == [
        (row.quantity, row.price_native, row.fees_native) for row in before
    ]
    assert session.scalar(select(CorporateAction).limit(1)) is not None


def test_shared_force_refresh_updates_only_shared_rows(session, monkeypatch):
    instrument = _shared_instrument(session)
    first = _private_portfolio(session, "First")
    second = _private_portfolio(session, "Second")
    _commit_fixture(session, instrument, first, second)
    _stub_shared_provider(monkeypatch)

    report = PriceService(session, get_settings()).refresh_shared(
        [instrument], date(2026, 9, 1), date(2026, 9, 6), force=True
    )

    assert report.price_rows_written == 1
    price_row = session.execute(
        select(price_service_module.PriceCache.close_native)
    ).scalar_one()
    assert price_row == Decimal("101.25")
    action = session.scalar(select(CorporateAction))
    assert action is not None
    assert action.applied_to_transactions is False


def test_shared_refresh_rejects_pending_writes_before_provider_call(session, monkeypatch):
    instrument = _shared_instrument(session)
    portfolio = _private_portfolio(session, "Pending")
    session.commit()
    session.expire_all()
    pending = _private_transaction(session, portfolio, instrument)
    pending.note = "pending"
    calls: list[str] = []
    _stub_shared_provider(monkeypatch, calls=calls)

    with pytest.raises(ValueError, match="clean"):
        PriceService(session, get_settings()).refresh_shared(
            [instrument], date(2026, 9, 1), date(2026, 9, 6), force=True
        )

    assert pending in session.dirty
    assert calls == []


def test_shared_refresh_changes_are_reversible_by_caller_rollback(session, monkeypatch):
    instrument = _shared_instrument(session)
    first = _private_portfolio(session, "First")
    second = _private_portfolio(session, "Second")
    _commit_fixture(session, instrument, first, second)
    _stub_shared_provider(monkeypatch)

    PriceService(session, get_settings()).refresh_shared(
        [instrument], date(2026, 9, 1), date(2026, 9, 6), force=True
    )
    assert session.scalar(select(CorporateAction)) is not None

    session.rollback()

    assert session.scalar(select(CorporateAction)) is None
    assert session.scalar(select(price_service_module.PriceCache)) is None

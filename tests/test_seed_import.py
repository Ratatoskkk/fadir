"""Seed import (SPEC Epic 1: US-1.1, US-1.2).

The app ships with an empty registry and no transaction CSV, so these run against
`examples/seed_transactions.example.csv` — the worked example a new user copies into
`data/`. Its shape is what the tests below assert: 13 transactions, 6 instruments, four
currencies, and four weekend trade dates that force the FX carry-forward path.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Instrument, Transaction
from app.providers.base import FxProvider
from app.registry import RegistryEntry
from app.services.seed import (
    EXAMPLE_SEED_CSV,
    ensure_instruments,
    import_seed_csv,
    instrument_from_row,
)


class FakeFxProvider(FxProvider):
    """Publishes rates on weekdays only, so weekend carry-forward is exercised."""

    name = "fake"

    RATES = {"USD": "40.0", "SEK": "4.2", "EUR": "48.0", "TWD": "1.3"}

    def provenance(self, base: str) -> str:
        return self.name

    def is_triangulated(self, base: str) -> bool:
        return False

    def rate(self, base, quote, on):
        return self.series(base, quote, on, on)[on]

    def series(self, base, quote, start, end):
        base = base.upper()
        out = {}
        day = start
        while day <= end:
            if day.weekday() < 5:  # weekdays only
                out[day] = Decimal(self.RATES[base])
            day += timedelta(days=1)
        return out


@pytest.fixture
def fx(session):
    from app.providers.fx_service import FxService

    return FxService(session, get_settings(), providers={"yfinance": FakeFxProvider()})


@pytest.fixture
def seed(session, fx):
    """Import the worked example."""

    def _run():
        return import_seed_csv(session, get_settings(), EXAMPLE_SEED_CSV, fx_service=fx)

    return _run


# -- the registry is a starting set, not a requirement --------------------------------


def test_registry_ships_empty_so_the_app_starts_blank(session):
    """Nothing is assumed about what you hold."""
    assert ensure_instruments(session) == 0
    assert session.query(Instrument).count() == 0


def test_registry_entries_are_created_once_when_present(session, monkeypatch):
    from app.services import seed as seed_module

    monkeypatch.setattr(
        seed_module,
        "REGISTRY",
        (RegistryEntry("AAPL", "NASDAQ", "AAPL", "USD", "Apple Inc"),),
    )
    assert ensure_instruments(session) == 1
    assert set(session.execute(select(Instrument.ticker)).scalars()) == {"AAPL"}
    # Idempotent.
    assert ensure_instruments(session) == 0


# -- the CSV declares its own instruments ---------------------------------------------


def test_a_csv_row_can_describe_an_instrument(session):
    row = {
        "ticker": "SAP",
        "exchange": "ETR",
        "yf_symbol": "SAP.DE",
        "currency": "eur",
        "name": "SAP SE",
    }
    instrument = instrument_from_row(row)
    assert instrument is not None
    assert (instrument.ticker, instrument.yf_symbol, instrument.currency) == (
        "SAP",
        "SAP.DE",
        "EUR",
    )


def test_a_row_missing_its_symbol_describes_nothing():
    assert instrument_from_row({"ticker": "SAP", "exchange": "ETR"}) is None


def test_import_creates_every_instrument_the_csv_names(session, seed):
    report = seed()
    assert report.instruments_created == 6
    assert set(session.execute(select(Instrument.ticker)).scalars()) == {
        "AAPL",
        "KO",
        "IBM",
        "ERIC",
        "SAP",
        "2330",
    }


# -- US-1.1: native currency, and an FX rate on every row ------------------------------


def test_seed_import_creates_thirteen_transactions(session, seed):
    """US-1.1: 'Given the seed CSV, when imported, then 13 transactions exist.'"""
    report = seed()
    assert report.transactions_created == 13
    assert report.errors == []
    assert session.query(Transaction).count() == 13


def test_every_transaction_has_a_non_null_fx_rate(session, seed):
    """US-1.1: '...and every one has a non-null FX rate.'"""
    seed()
    for txn in session.execute(select(Transaction)).scalars():
        assert txn.fx_rate_to_try is not None
        assert txn.fx_rate_to_try > 0
        assert txn.fx_rate_date is not None
        assert txn.fx_provider


def test_first_lot_is_stored_in_native_currency(session, seed):
    """US-1.1: BUY 10 AAPL at 243.85 USD on 2025-01-06 stores native values."""
    seed()
    txn = session.execute(
        select(Transaction)
        .join(Instrument)
        .where(Instrument.ticker == "AAPL", Transaction.trade_date == date(2025, 1, 6))
    ).scalar_one()

    assert txn.price_native == Decimal("243.85")
    assert txn.instrument.currency == "USD"
    assert txn.quantity == Decimal("10")
    assert txn.fx_rate_to_try == Decimal("40.0")
    # No TRY total is stored anywhere on the row (SPEC §0).
    assert not any("try" in c.name and c.name not in {"fx_rate_to_try", "fee_fx_rate_to_try"} for c in txn.__table__.columns)


def test_fees_are_read_in_native_currency(session, seed):
    seed()
    txn = session.execute(
        select(Transaction)
        .join(Instrument)
        .where(Instrument.ticker == "ERIC", Transaction.trade_date == date(2025, 2, 15))
    ).scalar_one()
    assert txn.fees_native == Decimal("29.00")


def test_a_sell_row_is_imported_as_a_disposal(session, seed):
    seed()
    sells = [t for t in session.execute(select(Transaction)).scalars() if t.side.value == "SELL"]
    assert len(sells) == 1
    assert sells[0].quantity == Decimal("5")


# -- SPEC §3: weekend trades carry the last published rate forward ---------------------


def test_weekend_trades_carry_fx_forward_and_are_flagged(session, seed):
    """SPEC §3: a trade date with no published rate walks back, and says so."""
    report = seed()

    weekend_rows = [
        t
        for t in session.execute(select(Transaction)).scalars()
        if t.trade_date.weekday() >= 5
    ]
    assert len(weekend_rows) == 4

    for txn in weekend_rows:
        assert txn.fx_carried_forward
        assert txn.fx_rate_date < txn.trade_date
        # Weekend trades take Friday's rate: never interpolated, never averaged.
        assert txn.fx_rate_date.weekday() == 4
        assert (txn.trade_date - txn.fx_rate_date).days <= 7

    assert len(report.fx_carried_forward) == 4


def test_weekday_trades_use_same_day_rate(session, seed):
    seed()
    weekday_rows = [
        t
        for t in session.execute(select(Transaction)).scalars()
        if t.trade_date.weekday() < 5
    ]
    assert len(weekday_rows) == 9
    for txn in weekday_rows:
        assert not txn.fx_carried_forward
        assert txn.fx_rate_date == txn.trade_date


def test_import_is_idempotent(session, seed):
    seed()
    second = seed()
    assert second.transactions_created == 0
    assert second.skipped_existing == 13
    assert session.query(Transaction).count() == 13


# -- a blank slate is a normal state, not a failure ------------------------------------


def test_a_missing_csv_starts_empty_rather_than_failing(session, fx, tmp_path):
    """A fresh install has no CSV. It must produce an empty portfolio, not an error."""
    report = import_seed_csv(session, get_settings(), tmp_path / "absent.csv", fx_service=fx)

    assert report.errors == []
    assert report.transactions_created == 0
    assert session.query(Transaction).count() == 0


# -- US-1.2: recompute totals, never trust them ----------------------------------------


def test_stated_total_discrepancy_is_recomputed_and_logged(session, fx, tmp_path):
    """US-1.2 (docs/FINDINGS.md F-6).

    The example CSV has no total column, so this fixture supplies one carrying 18,373.00
    against a true 800 x 22.97 = 18,376.00.
    """
    csv_path = tmp_path / "with_totals.csv"
    csv_path.write_text(
        "trade_date,side,ticker,exchange,yf_symbol,currency,quantity,price_native,total_native\n"
        "2025-04-15,BUY,ERIC,STO,ERIC-B.ST,SEK,800,22.97,18373.00\n",
        encoding="utf-8",
    )

    report = import_seed_csv(session, get_settings(), csv_path, fx_service=fx)

    assert report.transactions_created == 1
    assert len(report.discrepancies) == 1
    assert "18373.00" in report.discrepancies[0]
    assert "18376.00" in report.discrepancies[0]

    txn = session.execute(select(Transaction)).scalar_one()
    # The recomputed figure is what governs.
    assert txn.quantity * txn.price_native == Decimal("18376.00")


def test_matching_stated_total_produces_no_discrepancy(session, fx, tmp_path):
    csv_path = tmp_path / "ok_totals.csv"
    csv_path.write_text(
        "trade_date,side,ticker,exchange,yf_symbol,currency,quantity,price_native,total_native\n"
        "2025-04-15,BUY,ERIC,STO,ERIC-B.ST,SEK,800,22.97,18376.00\n",
        encoding="utf-8",
    )
    report = import_seed_csv(session, get_settings(), csv_path, fx_service=fx)
    assert report.discrepancies == []


def test_an_undescribed_ticker_is_reported_not_fatal(session, fx, tmp_path):
    """A row too thin to create an instrument fails alone; the rest still import."""
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "trade_date,side,ticker,exchange,yf_symbol,currency,quantity,price_native\n"
        "2025-04-15,BUY,ZZZZ,,,USD,10,1.00\n"
        "2025-04-15,BUY,ERIC,STO,ERIC-B.ST,SEK,800,22.97\n",
        encoding="utf-8",
    )
    report = import_seed_csv(session, get_settings(), csv_path, fx_service=fx)
    assert report.transactions_created == 1
    assert len(report.errors) == 1
    assert "ZZZZ" in report.errors[0]


def test_example_csv_shape_matches_expectations():
    """Guard against the worked example changing shape underneath the tests above."""
    import csv as _csv

    with EXAMPLE_SEED_CSV.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(_csv.DictReader(handle))

    assert len(rows) == 13
    assert {r["ticker"] for r in rows} == {"AAPL", "KO", "IBM", "ERIC", "SAP", "2330"}
    assert {r["currency"] for r in rows} == {"USD", "SEK", "EUR", "TWD"}
    assert {r["side"] for r in rows} == {"BUY", "SELL"}
    # Every row must be able to describe its own instrument.
    assert all(instrument_from_row(r) is not None for r in rows)

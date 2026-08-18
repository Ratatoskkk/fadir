from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.calc.types import MarketQuote, Side, TxnInput  # noqa: E402


def txn(
    id: int,
    ticker: str,
    currency: str,
    trade_date: str,
    side: Side,
    quantity: str,
    price: str,
    fx: str,
    fees: str = "0",
    fx_rate_date: str | None = None,
    fx_provider: str = "yfinance",
) -> TxnInput:
    """Terse TxnInput factory for fixtures."""
    return TxnInput(
        id=id,
        ticker=ticker,
        currency=currency,
        trade_date=date.fromisoformat(trade_date),
        side=side,
        quantity=Decimal(quantity),
        price_native=Decimal(price),
        fees_native=Decimal(fees),
        fx_rate_to_try=Decimal(fx),
        fx_rate_date=date.fromisoformat(fx_rate_date or trade_date),
        fx_provider=fx_provider,
    )


def quote(
    ticker: str,
    currency: str,
    price: str,
    fx: str,
    price_date: str = "2026-08-01",
    fx_rate_date: str | None = None,
    ok: bool = True,
    session: str = "closed",
    stale: bool = False,
    error: str | None = None,
    fx_carried_forward: bool = False,
    prev_price: str | None = None,
    prev_fx: str | None = None,
    prev_price_date: str | None = None,
) -> MarketQuote:
    return MarketQuote(
        ticker=ticker,
        currency=currency,
        price_native=Decimal(price),
        price_date=date.fromisoformat(price_date),
        fx_rate_to_try=Decimal(fx),
        fx_rate_date=date.fromisoformat(fx_rate_date or price_date),
        fx_provider="yfinance",
        ok=ok,
        session=session,
        stale=stale,
        error=error,
        fx_carried_forward=fx_carried_forward,
        prev_price_native=Decimal(prev_price) if prev_price is not None else None,
        prev_fx_rate_to_try=Decimal(prev_fx) if prev_fx is not None else None,
        prev_price_date=(
            date.fromisoformat(prev_price_date) if prev_price_date else None
        ),
    )


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """A fresh SQLite database per test."""
    from app import config, db

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FADIR_DB_PATH", str(db_path))
    config.get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield db_path
    db.reset_engine()
    config.get_settings.cache_clear()


@pytest.fixture
def session(tmp_db):
    from app.db import get_sessionmaker

    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: hits real network endpoints; excluded from the default run"
    )

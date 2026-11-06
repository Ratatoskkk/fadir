"""What a Portfolio holds on a date, and the rule that a sale cannot exceed it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Instrument, Side, Transaction


class Oversold(ValueError):
    def __init__(self, ticker: str, trade_date: date, available: Decimal) -> None:
        super().__init__(f"{ticker}: sale on {trade_date} exceeds the {available} shares held")
        self.ticker = ticker
        self.trade_date = trade_date
        self.available = available


@dataclass(frozen=True)
class Holding:
    instrument: Instrument
    quantity: Decimal


def _ordered(transactions: list[Transaction]) -> list[Transaction]:
    # Same order as the FIFO lot book: date, buys before sells, then id.
    return sorted(transactions, key=lambda t: (t.trade_date, 0 if t.side is Side.BUY else 1, t.id))


def holdings(session: Session, portfolio_id: int, as_of: date) -> list[Holding]:
    transactions = session.scalars(
        select(Transaction)
        .options(selectinload(Transaction.instrument))
        .where(Transaction.portfolio_id == portfolio_id, Transaction.trade_date <= as_of)
    )
    held: dict[int, Holding] = {}
    for txn in transactions:
        signed = txn.quantity if txn.side is Side.BUY else -txn.quantity
        current = held.get(txn.instrument_id)
        held[txn.instrument_id] = Holding(txn.instrument, (current.quantity if current else Decimal("0")) + signed)
    return sorted((h for h in held.values() if h.quantity > 0), key=lambda h: h.instrument.ticker)


def check_no_oversell(session: Session, portfolio_id: int, instrument_id: int) -> None:
    """Raise Oversold if any sale of this instrument exceeds what was held at that point."""
    transactions = list(
        session.scalars(
            select(Transaction)
            .options(selectinload(Transaction.instrument))
            .where(Transaction.portfolio_id == portfolio_id, Transaction.instrument_id == instrument_id)
        )
    )
    running = Decimal("0")
    for txn in _ordered(transactions):
        if txn.side is Side.SELL and txn.quantity > running:
            raise Oversold(txn.instrument.ticker, txn.trade_date, running)
        running += txn.quantity if txn.side is Side.BUY else -txn.quantity

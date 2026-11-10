"""Price fetching, caching and split handling (SPEC §5, §8).

Prices are stored **unadjusted**. yfinance's default `history()` back-adjusts, which
silently rewrites pre-split history and would make a cost basis recorded at raw prices
look catastrophically wrong. Instead: fetch with `auto_adjust=False`, pull `Ticker.splits`
separately, persist them, and adjust the *stored transactions* — never the market price.

Per SPEC §8, one failing symbol degrades one row rather than the page: every fetch is
isolated and failures are recorded per instrument.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.providers import backfill
from app.models import (
    PRICE_SCALE,
    ActionKind,
    CorporateAction,
    Instrument,
    PriceCache,
    utcnow,
)
from app.providers import market_hours, yf_client

log = logging.getLogger(__name__)


@contextmanager
def savepoint(session: Session) -> Iterator[None]:
    """`session.begin_nested()` that also nests properly on SQLite.

    pysqlite defers BEGIN to the first DML, so a SAVEPOINT opened first becomes the
    outer transaction and its RELEASE commits it, which would defeat the caller's
    rollback. Opening the transaction explicitly first keeps the savepoint nested.
    """
    connection = session.connection()
    if connection.dialect.name == "sqlite":
        raw = connection.connection.driver_connection
        if not raw.in_transaction:
            raw.execute("BEGIN")
    with session.begin_nested():
        yield


@dataclass
class PriceStatus:
    """Per-instrument fetch outcome, surfaced on the position row (SPEC §8)."""

    ticker: str
    ok: bool
    last_close: Decimal | None = None
    last_traded: date | None = None
    session: str = "closed"
    stale: bool = False
    error: str | None = None


@dataclass
class RefreshReport:
    price_rows_written: int = 0
    splits_found: int = 0
    splits_applied: int = 0
    per_instrument: dict[str, PriceStatus] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class PriceService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    # -- cache reads ---------------------------------------------------------------

    def cached_closes(
        self, instrument_ids: list[int], start: date, end: date
    ) -> dict[int, dict[date, Decimal]]:
        """Stored closes in [start, end] for every instrument, in one query."""
        out: dict[int, dict[date, Decimal]] = {i: {} for i in instrument_ids}
        if not instrument_ids:
            return out
        stmt = select(PriceCache.instrument_id, PriceCache.price_date, PriceCache.close_native).where(
            PriceCache.instrument_id.in_(instrument_ids),
            PriceCache.price_date >= start,
            PriceCache.price_date <= end,
        )
        for instrument_id, d, close in self.session.execute(stmt):
            out[instrument_id][d] = close
        return out

    def last_cached_close(self, instrument_id: int) -> tuple[Decimal, date] | None:
        stmt = (
            select(PriceCache.close_native, PriceCache.price_date)
            .where(PriceCache.instrument_id == instrument_id)
            .order_by(PriceCache.price_date.desc())
            .limit(1)
        )
        row = self.session.execute(stmt).first()
        return (row[0], row[1]) if row else None

    def last_two_cached_closes(
        self, instrument_ids: list[int]
    ) -> dict[int, tuple[tuple[Decimal, date] | None, tuple[Decimal, date] | None]]:
        """The newest close and the one before it per instrument, for the daily change.

        Maps each id to (latest, previous). `previous` is None when only one session is
        on file, which is the signal not to report a daily figure at all. "The one before
        it" is the previous *stored* session, not literally yesterday: for a market that
        has been shut for days that is the last day which actually traded, and the
        caller surfaces the date so the comparison is never mislabelled.
        """
        out: dict[int, tuple[tuple[Decimal, date] | None, tuple[Decimal, date] | None]] = {
            i: (None, None) for i in instrument_ids
        }
        if not instrument_ids:
            return out
        rank = (
            func.row_number()
            .over(partition_by=PriceCache.instrument_id, order_by=PriceCache.price_date.desc())
            .label("rank")
        )
        ranked = (
            select(PriceCache.instrument_id, PriceCache.close_native, PriceCache.price_date, rank)
            .where(PriceCache.instrument_id.in_(instrument_ids))
            .subquery()
        )
        stmt = select(ranked.c.instrument_id, ranked.c.close_native, ranked.c.price_date, ranked.c.rank).where(ranked.c.rank <= 2)
        for instrument_id, close, d, n in self.session.execute(stmt):
            latest, previous = out[instrument_id]
            if n == 1:
                out[instrument_id] = ((close, d), previous)
            else:
                out[instrument_id] = (latest, (close, d))
        return out

    #: Days of overlap re-requested either side of the newest cached close. Covers a
    #: session that was still open when it was last stored, and any short gap Yahoo
    #: backfills after the fact.
    REFETCH_OVERLAP_DAYS = 5

    def shared_refresh_start(self, instrument: Instrument, today: date, cold_start: date) -> date:
        """First day a shared refresh must request for `instrument`, including any hole."""
        cached = list(
            self.session.execute(
                select(PriceCache.price_date)
                .where(
                    PriceCache.instrument_id == instrument.id,
                    PriceCache.price_date >= today - timedelta(days=backfill.MAX_BACKFILL_DAYS),
                )
                .order_by(PriceCache.price_date)
            ).scalars()
        )
        return backfill.refresh_start(
            f"price:{instrument.id}", cached, today, cold_start, self.REFETCH_OVERLAP_DAYS
        )

    # -- cache writes --------------------------------------------------------------

    def _store_closes(self, instrument_id: int, closes: dict[date, Decimal]) -> int:
        if not closes:
            return 0

        # Fetched as ORM rows, so today's row — the only one that can need updating — is
        # already in hand rather than requiring a second query for it.
        existing_stmt = select(PriceCache).where(
            PriceCache.instrument_id == instrument_id,
            PriceCache.price_date.in_(list(closes)),
        )
        existing = {row.price_date: row for row in self.session.execute(existing_stmt).scalars()}

        today = date.today()
        written = 0
        for price_date, close in closes.items():
            row = existing.get(price_date)
            if row is not None:
                # Settled closes are immutable (SPEC §8); today's is still moving.
                if price_date == today:
                    row.close_native = close
                    row.fetched_at = utcnow()
                continue
            self.session.add(
                PriceCache(
                    instrument_id=instrument_id,
                    price_date=price_date,
                    close_native=close,
                    is_adjusted=False,
                )
            )
            written += 1
        self.session.flush()
        return written

    # -- splits (SPEC §5) ----------------------------------------------------------

    def sync_splits(self, instrument: Instrument) -> int:
        """Fetch and persist split events. Returns the number newly recorded.

        Idempotent by construction: `(instrument_id, action_date, kind)` is unique, so a
        split already on file is skipped rather than duplicated.
        """
        events = yf_client.fetch_splits(instrument.yf_symbol)
        if not events:
            return 0

        known_stmt = select(CorporateAction.action_date).where(
            CorporateAction.instrument_id == instrument.id,
            CorporateAction.kind == ActionKind.SPLIT,
        )
        known = set(self.session.execute(known_stmt).scalars())

        added = 0
        for event in events:
            if event.action_date in known:
                continue
            self.session.add(
                CorporateAction(
                    instrument_id=instrument.id,
                    action_date=event.action_date,
                    kind=ActionKind.SPLIT,
                    ratio=event.ratio,
                    applied_to_transactions=False,
                )
            )
            known.add(event.action_date)
            added += 1
        self.session.flush()
        return added

    def apply_pending_splits(self, instrument: Instrument) -> int:
        """Apply unapplied splits to affected transactions (SPEC §5 steps 3-5).

        A split affects only transactions dated strictly *before* the split: a trade on
        or after the ex-date is already on the post-split basis. Quantity is multiplied
        by the ratio and price divided by it, so `quantity x price_native` — the total
        cost basis in native currency — is invariant. That invariance is the assertion
        that catches the bug (SPEC §5.5, US-2.2).

        Idempotent: `applied_to_transactions` is flipped in the same transaction, so a
        second run is a no-op.

        Returns the number of transactions adjusted.
        """
        pending_stmt = (
            select(CorporateAction)
            .where(
                CorporateAction.instrument_id == instrument.id,
                CorporateAction.kind == ActionKind.SPLIT,
                CorporateAction.applied_to_transactions.is_(False),
            )
            .order_by(CorporateAction.action_date)
        )
        pending = list(self.session.execute(pending_stmt).scalars())
        if not pending:
            return 0

        adjusted = 0
        for action in pending:
            affected = [
                t
                for t in instrument.transactions
                if t.trade_date < action.action_date
            ]
            for txn in affected:
                before = txn.quantity * txn.price_native

                # Quantity scales exactly; price is quantized to the stored scale, so the
                # guard below sees the value that will actually be persisted rather than
                # a full-precision intermediate that hides the storage rounding.
                txn.quantity = txn.quantity * action.ratio
                txn.price_native = (txn.price_native / action.ratio).quantize(
                    PRICE_SCALE, rounding=ROUND_HALF_EVEN
                )
                after = txn.quantity * txn.price_native

                # SPEC §5.5: total cost basis in native currency must be invariant.
                # A ratio like 3 makes exact invariance impossible in any finite decimal,
                # so the bar is money-level: a relative tolerance that stays far below a
                # cent at realistic sizes, with an absolute floor for small positions.
                tolerance = max(Decimal("1e-8"), abs(before) * Decimal("1e-12"))
                if abs(after - before) > tolerance:
                    raise AssertionError(
                        f"split adjustment changed cost basis for transaction {txn.id}: "
                        f"{before} -> {after} (tolerance {tolerance})"
                    )
                adjusted += 1

            action.applied_to_transactions = True
            log.info(
                "applied %s-for-1 split dated %s to %d %s transaction(s)",
                action.ratio,
                action.action_date,
                len(affected),
                instrument.ticker,
            )

        self.session.flush()
        return adjusted

    def _require_clean_session(self) -> None:
        if self.session.new or self.session.dirty or self.session.deleted:
            raise ValueError("shared refresh requires a clean caller Session")

    def refresh_shared(
        self,
        instruments: list[Instrument],
        start: date,
        end: date,
        *,
        force: bool = False,
        now_utc: datetime | None = None,
    ) -> RefreshReport:
        """Refresh shared market rows without touching private transactions.

        This entry point stores prices and corporate actions only. The caller retains
        transaction ownership and can commit or roll back the flushed shared rows.
        """
        self._require_clean_session()

        report = RefreshReport()
        if not instruments:
            return report

        now_utc = now_utc or datetime.now(timezone.utc)
        symbols = [i.yf_symbol for i in instruments]

        try:
            batch = yf_client.fetch_close_series_batch(symbols, start, end)
        except Exception as exc:  # noqa: BLE001 - never fail the whole dashboard
            log.error("batch price fetch failed entirely: %s", exc)
            report.errors.append(f"batch fetch failed: {exc}")
            batch = {}

        for instrument in instruments:
            ticker = instrument.ticker
            status = PriceStatus(ticker=ticker, ok=False)
            try:
                # A SAVEPOINT per instrument: one failed flush (say a concurrent insert
                # hitting a unique key) rolls back only this instrument's rows instead of
                # leaving the whole Session in pending-rollback for everything after it.
                with savepoint(self.session):
                    closes = batch.get(instrument.yf_symbol) or {}
                    written = self._store_closes(instrument.id, closes)
                    splits = self.sync_splits(instrument) if force else 0
                report.price_rows_written += written
                report.splits_found += splits

                latest = self.last_cached_close(instrument.id)
                if latest is None:
                    status.error = "no price data available"
                    report.errors.append(f"{ticker}: no price data")
                else:
                    close, traded = latest
                    status.ok = True
                    status.last_close = close
                    status.last_traded = traded
                    status.session = market_hours.session_state(instrument.exchange, now_utc)
                    status.stale = status.session == "closed" or traded < date.today()
            except Exception as exc:  # noqa: BLE001 - isolate per instrument
                # Database errors quote the failing SQL and its parameters; keep that
                # out of a report that is returned to the client.
                detail = type(exc).__name__ if isinstance(exc, SQLAlchemyError) else str(exc)
                log.error("shared refresh failed for %s: %s", ticker, detail)
                status.error = detail
                report.errors.append(f"{ticker}: {detail}")

            report.per_instrument[instrument.ticker] = status

        return report

    # -- refresh -------------------------------------------------------------------

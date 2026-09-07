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
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
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
        self, instrument_id: int, start: date, end: date
    ) -> dict[date, Decimal]:
        stmt = select(PriceCache.price_date, PriceCache.close_native).where(
            PriceCache.instrument_id == instrument_id,
            PriceCache.price_date >= start,
            PriceCache.price_date <= end,
        )
        return {d: r for d, r in self.session.execute(stmt)}

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
        self, instrument_id: int
    ) -> tuple[tuple[Decimal, date] | None, tuple[Decimal, date] | None]:
        """The newest close and the one before it, for the daily change.

        Returns (latest, previous). `previous` is None when only one session is on file,
        which is the signal not to report a daily figure at all. "The one before it" is
        the previous *stored* session, not literally yesterday: for a market that has
        been shut for days that is the last day which actually traded, and the caller
        surfaces the date so the comparison is never mislabelled.
        """
        stmt = (
            select(PriceCache.close_native, PriceCache.price_date)
            .where(PriceCache.instrument_id == instrument_id)
            .order_by(PriceCache.price_date.desc())
            .limit(2)
        )
        rows = self.session.execute(stmt).all()
        if not rows:
            return None, None
        latest = (rows[0][0], rows[0][1])
        previous = (rows[1][0], rows[1][1]) if len(rows) > 1 else None
        return latest, previous

    #: Days of overlap re-requested either side of the newest cached close. Covers a
    #: session that was still open when it was last stored, and any short gap Yahoo
    #: backfills after the fact.
    REFETCH_OVERLAP_DAYS = 5

    def incremental_start(self, instruments: list[Instrument], full_start: date) -> date:
        """Earliest date the next refresh actually needs to ask for.

        Settled closes are immutable, so `_store_closes` discards every row it already
        holds — re-downloading the whole history on each refresh costs a growing
        download to write, at most, one row per symbol. This narrows the window to what
        is genuinely missing: back to just before the *oldest* newest-close across the
        instruments, or the full window if any instrument has no data at all.
        """
        newest: list[date] = []
        for instrument in instruments:
            latest = self.last_cached_close(instrument.id)
            if latest is None:
                return full_start  # a cold instrument needs its whole history
            newest.append(latest[1])

        if not newest:
            return full_start
        candidate = min(newest) - timedelta(days=self.REFETCH_OVERLAP_DAYS)
        return max(full_start, candidate)

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
            status = PriceStatus(ticker=instrument.ticker, ok=False)
            try:
                closes = batch.get(instrument.yf_symbol) or {}
                report.price_rows_written += self._store_closes(instrument.id, closes)

                if force:
                    report.splits_found += self.sync_splits(instrument)

                latest = self.last_cached_close(instrument.id)
                if latest is None:
                    status.error = "no price data available"
                    report.errors.append(f"{instrument.ticker}: no price data")
                else:
                    close, traded = latest
                    status.ok = True
                    status.last_close = close
                    status.last_traded = traded
                    status.session = market_hours.session_state(instrument.exchange, now_utc)
                    status.stale = status.session == "closed" or traded < date.today()
            except Exception as exc:  # noqa: BLE001 - isolate per instrument
                log.error("shared refresh failed for %s: %s", instrument.ticker, exc)
                status.error = str(exc)
                report.errors.append(f"{instrument.ticker}: {exc}")

            report.per_instrument[instrument.ticker] = status

        return report

    # -- refresh -------------------------------------------------------------------

    def refresh(
        self,
        instruments: list[Instrument],
        start: date,
        end: date,
        *,
        force: bool = False,
        now_utc: datetime | None = None,
    ) -> RefreshReport:
        """Batch-refresh prices for all instruments (SPEC §8).

        All symbols go out in a single `yf.download` call. A symbol that fails is
        recorded against its own instrument and the rest proceed.
        """
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
            status = PriceStatus(ticker=instrument.ticker, ok=False)
            try:
                closes = batch.get(instrument.yf_symbol) or {}
                report.price_rows_written += self._store_closes(instrument.id, closes)

                if force:
                    report.splits_found += self.sync_splits(instrument)
                    report.splits_applied += self.apply_pending_splits(instrument)

                latest = self.last_cached_close(instrument.id)
                if latest is None:
                    status.error = "no price data available"
                    report.errors.append(f"{instrument.ticker}: no price data")
                else:
                    close, traded = latest
                    status.ok = True
                    status.last_close = close
                    status.last_traded = traded
                    status.session = market_hours.session_state(instrument.exchange, now_utc)
                    # Stale = the market is shut, or open but we have nothing from today.
                    status.stale = status.session == "closed" or traded < date.today()
            except Exception as exc:  # noqa: BLE001 - isolate per instrument
                log.error("refresh failed for %s: %s", instrument.ticker, exc)
                status.error = str(exc)
                report.errors.append(f"{instrument.ticker}: {exc}")

            report.per_instrument[instrument.ticker] = status

        return report

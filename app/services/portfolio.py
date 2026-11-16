"""Portfolio assembly: DB + providers -> pure calc engine (SPEC §6, §7, §8).

The calc engine takes no I/O, so this module is where the DB rows and provider responses
are turned into its plain input types. Nothing here does arithmetic on money beyond
building those inputs — all of that lives in `app.calc`.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.calc import (
    LiquidationSummary,
    MarketQuote,
    PortfolioTotals,
    PositionMetrics,
    build_history,
    build_lot_book,
    liquidation,
    summarise_portfolio,
)
from app.calc.attribution import position_metrics
from app.calc.fifo import InsufficientLots
from app.calc.history import HistoryPoint, PositionHistoryInput
from app.calc.intraday import IntradayPoint, build_grid, build_intraday_series
from app.calc.rebase import TRY, cross, cross_daily, cross_intraday, last_at
from app.calc.tax import TaxEstimate, disabled_estimate, estimate_tax
from app.calc.tax_sources import with_official_brackets
from app.calc.types import Side as CalcSide
from app.calc.types import TxnInput
from app.config import Settings
from app.models import Instrument, Transaction
from app.providers import market_hours
from app.providers.base import ProviderError
from app.providers.fx_service import FxService
from app.providers.intraday import IntradayService, latest_session_bounds, session_days
from app.providers.price_service import PriceService, RefreshReport, savepoint
from app.services.portfolio_scope import (
    PortfolioScope,
    PortfolioScopeNotFound,
    PortfolioScopeViolation,
)

#: Shared across requests so the short-lived intraday cache is actually reused; it is
#: bounded by (symbols x intervals) and replaced wholesale on refetch.
_intraday_service = IntradayService()

log = logging.getLogger(__name__)


@dataclass
class PortfolioView:
    as_of: datetime
    positions: list[PositionMetrics]
    totals: PortfolioTotals
    liquidation: LiquidationSummary
    tax: TaxEstimate
    warnings: list[str]
    #: When every exchange is shut, the next time one opens (UTC). Lets the frontend
    #: sleep until then instead of polling for prices that cannot move (SPEC §8).
    next_market_open: datetime | None = None
    #: The instruments behind `positions`, keyed by ticker. Carried on the view so the
    #: serialisation layer can label rows without re-querying what was just loaded.
    instruments: dict[str, Instrument] = field(default_factory=dict)
    #: The tax in lira, as the Turkish estimate works it out, when `tax` is shown in
    #: another Base Currency; None for a TRY Portfolio.
    tax_in_lira: Decimal | None = None


def load_instruments(session: Session, *, active_only: bool = True) -> list[Instrument]:
    stmt = select(Instrument).options(selectinload(Instrument.transactions))
    if active_only:
        stmt = stmt.where(Instrument.active.is_(True))
    return list(session.execute(stmt).scalars())


def _held_active_filter():
    """Active instruments at least one Transaction references; nothing else needs refreshing."""
    return (
        Instrument.active.is_(True),
        Instrument.id.in_(select(Transaction.instrument_id)),
    )


#: A forced shared refresh goes to the providers for every held instrument, and
#: `POST /api/refresh` is reachable by any signed-in user. At most one runs at a time,
#: and one that follows another within the cooldown is downgraded to a normal refresh.
FORCED_REFRESH_COOLDOWN_SECONDS = 60.0
_FORCED_REFRESH_LOCK = threading.Lock()
_last_forced_refresh: float | None = None


def reset_forced_refresh_state() -> None:
    """Test hook: forget the last forced refresh."""
    global _last_forced_refresh
    _last_forced_refresh = None


def _claim_forced_refresh(force: bool) -> bool:
    """Whether this call may run forced; if so the caller holds `_FORCED_REFRESH_LOCK`."""
    global _last_forced_refresh
    if not force:
        return False
    if not _FORCED_REFRESH_LOCK.acquire(blocking=False):
        return False  # another forced refresh is running; do a normal one instead
    now = time.monotonic()
    if _last_forced_refresh is not None and now - _last_forced_refresh < FORCED_REFRESH_COOLDOWN_SECONDS:
        _FORCED_REFRESH_LOCK.release()
        return False
    _last_forced_refresh = now
    return True


def load_shared_instruments(session: Session) -> list[Instrument]:
    stmt = select(Instrument).where(*_held_active_filter()).order_by(Instrument.id)
    return list(session.scalars(stmt))


def load_shared_exchanges(session: Session) -> set[str]:
    stmt = select(Instrument.exchange).where(*_held_active_filter()).distinct()
    return set(session.scalars(stmt))


def to_txn_input(txn: Transaction, ticker: str, currency: str) -> TxnInput:
    return TxnInput(
        id=txn.id,
        ticker=ticker,
        currency=currency,
        trade_date=txn.trade_date,
        side=CalcSide(txn.side.value),
        quantity=txn.quantity,
        price_native=txn.price_native,
        fees_native=txn.fees_native or Decimal("0"),
        fx_rate_to_try=txn.fx_rate_to_try,
        fx_rate_date=txn.fx_rate_date,
        fx_provider=txn.fx_provider,
        fee_currency=txn.fee_currency,
        fee_fx_rate_to_try=txn.fee_fx_rate_to_try,
        fee_fx_rate_date=txn.fee_fx_rate_date,
        fee_fx_provider=txn.fee_fx_provider,
    )


class PortfolioService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        fx_service: FxService | None = None,
        price_service: PriceService | None = None,
        intraday_service: IntradayService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.fx = fx_service or FxService(session, settings)
        self.prices = price_service or PriceService(session, settings)
        self.intraday = intraday_service or _intraday_service
        self._scope: PortfolioScope | None = None
        # Base Currency rates for this request: B/TRY by date, and the current one.
        self._base_rates: dict[date, Decimal] = {}
        self._base_current: Decimal | None = None

    def scoped(self, scope: PortfolioScope) -> PortfolioService:
        self._validate_scope(scope)
        scoped = PortfolioService(
            self.session,
            self.settings,
            fx_service=self.fx,
            price_service=self.prices,
            intraday_service=self.intraday,
        )
        scoped._scope = scope
        return scoped

    def _validate_scope(self, scope: PortfolioScope | None) -> PortfolioScope:
        if not isinstance(scope, PortfolioScope):
            raise PortfolioScopeViolation("Portfolio scope is required")
        if getattr(scope, "_session", None) is not self.session:
            raise PortfolioScopeViolation("Portfolio scope belongs to another Session")
        state = sa_inspect(scope.portfolio)
        if state.session is not self.session or not state.persistent or state.deleted:
            raise PortfolioScopeViolation("Portfolio scope is detached")
        return scope

    def _required_scope(self) -> PortfolioScope:
        return self._validate_scope(self._scope)

    def _calculation_inputs(
        self,
    ) -> tuple[list[Instrument], dict[int, list[Transaction]]]:
        if self._scope is None:
            instruments = load_instruments(self.session)
            return instruments, {
                instrument.id: list(instrument.transactions)
                for instrument in instruments
            }

        scope = self._required_scope()
        transactions = list(
            self.session.scalars(
                select(Transaction)
                .where(Transaction.portfolio_id == scope.portfolio.id)
                .order_by(Transaction.trade_date, Transaction.id)
            )
        )
        instrument_ids = {transaction.instrument_id for transaction in transactions}
        if not instrument_ids:
            return [], {}

        instruments = list(
            self.session.scalars(
                select(Instrument)
                .where(
                    Instrument.id.in_(instrument_ids),
                    Instrument.active.is_(True),
                )
                .order_by(Instrument.id)
            )
        )
        active_ids = {instrument.id for instrument in instruments}
        transactions_by_instrument: dict[int, list[Transaction]] = {}
        for transaction in transactions:
            if transaction.instrument_id in active_ids:
                transactions_by_instrument.setdefault(transaction.instrument_id, []).append(
                    transaction
                )
        return instruments, transactions_by_instrument

    def _select_instruments(
        self, instruments: list[Instrument], tickers: list[str] | None
    ) -> list[Instrument]:
        if not tickers:
            return instruments
        wanted = {ticker.upper() for ticker in tickers}
        selected = [instrument for instrument in instruments if instrument.ticker.upper() in wanted]
        if self._scope is not None and {instrument.ticker.upper() for instrument in selected} != wanted:
            raise PortfolioScopeNotFound("Ticker not found")
        return selected

    # -- Base Currency (ADR 0006) ----------------------------------------------------
    #
    # The engine values in whatever its rates are to. Rates are stored and fetched to
    # TRY; for a Portfolio in another Base Currency B each one is crossed to B through
    # TRY on its own date (app.calc.rebase), so every view comes out in B without any
    # transaction being rewritten. The Turkey tax estimate stays in TRY (beta brief): it
    # is worked out from a TRY run and shown in B at the matching date's rate.

    @property
    def base_currency(self) -> str:
        return self._scope.portfolio.base_currency.upper() if self._scope is not None else TRY

    def _base_rate(self, on: date) -> Decimal:
        if on not in self._base_rates:
            self._base_rates[on] = self.fx.quote(self.base_currency, on).rate
        return self._base_rates[on]

    def _base_now(self) -> Decimal:
        if self._base_current is None:
            self._base_current = self.fx.current(self.base_currency).rate
        return self._base_current

    def _rebased(self, txn: TxnInput) -> TxnInput:
        """A transaction's trade-date rates to TRY as rates to the Base Currency."""
        if self.base_currency == TRY:
            return txn
        fee_rate = txn.fee_fx_rate_to_try
        if fee_rate is not None and txn.fee_fx_rate_date is not None:
            fee_rate = cross(fee_rate, self._base_rate(txn.fee_fx_rate_date))
        return replace(
            txn,
            fx_rate_to_try=cross(txn.fx_rate_to_try, self._base_rate(txn.fx_rate_date)),
            fee_fx_rate_to_try=fee_rate,
        )

    def _rebased_quote(self, quote: MarketQuote) -> MarketQuote:
        """A current quote's rates (now, and the previous session's) to the Base Currency."""
        if self.base_currency == TRY or not quote.ok:
            return quote
        prev = quote.prev_fx_rate_to_try
        if prev is not None and quote.prev_price_date is not None:
            prev = cross(prev, self._base_rate(quote.prev_price_date))
        return replace(quote, fx_rate_to_try=cross(quote.fx_rate_to_try, self._base_now()), prev_fx_rate_to_try=prev)

    def _tax_in_base(self, tax: TaxEstimate) -> TaxEstimate:
        """The TRY tax estimate's amounts in the Base Currency at today's rate."""
        if self.base_currency == TRY:
            return tax
        rate = self._base_now()
        return replace(tax, **{
            name: cross(getattr(tax, name), rate)
            for name in tax.__dataclass_fields__
            if name.endswith("_try")
        })

    # -- inception -----------------------------------------------------------------

    def inception(self) -> date:
        """The first date the daily series covers.

        `history.start_date` in `config.yaml` wins when it is set. Otherwise the earliest
        transaction held decides, so a fresh install charts from its own first trade
        rather than from a date baked into the code. With no transactions at all there is
        nothing to chart, and today is the only honest answer.
        """
        configured = self.settings.history.start_date
        if configured is not None:
            return configured
        if self._scope is not None:
            _, transactions_by_instrument = self._calculation_inputs()
            earliest = min(
                (
                    transaction.trade_date
                    for rows in transactions_by_instrument.values()
                    for transaction in rows
                ),
                default=None,
            )
            return earliest or date.today()
        earliest = self.session.execute(
            select(Transaction.trade_date).order_by(Transaction.trade_date).limit(1)
        ).scalar_one_or_none()
        return earliest or date.today()

    # -- refresh -------------------------------------------------------------------

    def refresh_shared(self, *, force: bool = False) -> RefreshReport:
        """Refresh shared market rows without reading or changing private rows."""
        if self._scope is not None:
            raise PortfolioScopeViolation("Shared refresh is not available for a scoped service")
        if self.session.new or self.session.dirty or self.session.deleted:
            raise ValueError("shared refresh requires a clean caller Session")

        force = _claim_forced_refresh(force)
        try:
            return self._refresh_shared(force)
        finally:
            if force:
                _FORCED_REFRESH_LOCK.release()

    def _refresh_shared(self, force: bool) -> RefreshReport:
        instruments = load_shared_instruments(self.session)
        end = date.today()
        full_start = end - timedelta(days=10)
        start = min(
            (self.prices.shared_refresh_start(i, end, full_start) for i in instruments),
            default=full_start,
        )
        report = self.prices.refresh_shared(instruments, start, end, force=force)

        for currency in sorted({instrument.currency for instrument in instruments}):
            try:
                with savepoint(self.session):
                    self.fx.warm(
                        currency, self.fx.shared_refresh_start(currency, end, full_start), end
                    )
            except ProviderError as exc:
                log.error("shared FX refresh failed for %s: %s", currency, exc)
                report.errors.append(f"FX {currency}: {exc}")
            except SQLAlchemyError as exc:
                log.error("shared FX refresh failed for %s: %s", currency, type(exc).__name__)
                report.errors.append(f"FX {currency}: {type(exc).__name__}")

        return report

    # -- current view --------------------------------------------------------------

    def _current_quote(
        self,
        instrument: Instrument,
        now_utc: datetime,
        warnings: list[str],
        closes: tuple[tuple[Decimal, date] | None, tuple[Decimal, date] | None],
    ) -> MarketQuote:
        """Build a MarketQuote, degrading this one position rather than the page."""
        session_state = market_hours.session_state(instrument.exchange, now_utc)

        def failed(price: Decimal, on: date, error: str) -> MarketQuote:
            return MarketQuote(
                ticker=instrument.ticker,
                currency=instrument.currency,
                price_native=price,
                price_date=on,
                fx_rate_to_try=Decimal("0"),
                fx_rate_date=on,
                fx_provider="none",
                ok=False,
                session=session_state,
                stale=True,
                error=error,
            )

        price_row, prev_row = closes
        if price_row is None:
            warnings.append(f"{instrument.ticker}: no price available")
            return failed(Decimal("0"), date.today(), "no price data")

        close, price_date = price_row

        try:
            fx_quote = self.fx.current(instrument.currency)
        except ProviderError as exc:
            warnings.append(f"{instrument.ticker}: no FX rate ({exc})")
            return failed(close, price_date, f"no FX rate: {exc}")

        # The previous session, valued at the FX rate published on *that* day, so the
        # day's move separates into a price part and a currency part. A missing rate
        # only costs the daily figure — the position itself is unaffected.
        prev_close: Decimal | None = None
        prev_date: date | None = None
        prev_rate: Decimal | None = None
        if prev_row is not None:
            prev_close, prev_date = prev_row
            try:
                prev_rate = self.fx.quote(
                    instrument.currency, prev_date, allow_fetch=False
                ).rate
            except ProviderError:
                log.info(
                    "no %s/TRY rate for %s; skipping daily change for %s",
                    instrument.currency,
                    prev_date,
                    instrument.ticker,
                )
                prev_close = prev_date = None

        return MarketQuote(
            ticker=instrument.ticker,
            currency=instrument.currency,
            price_native=close,
            price_date=price_date,
            fx_rate_to_try=fx_quote.rate,
            fx_rate_date=fx_quote.rate_date,
            fx_provider=fx_quote.provider,
            ok=True,
            session=session_state,
            # A price from before today, or a shut market, is not live (SPEC §8).
            stale=session_state == "closed" or price_date < date.today(),
            fx_carried_forward=fx_quote.carried_forward,
            prev_price_native=prev_close,
            prev_price_date=prev_date,
            prev_fx_rate_to_try=prev_rate,
        )

    def build_view(self, *, now_utc: datetime | None = None) -> PortfolioView:
        now_utc = now_utc or datetime.now(timezone.utc)
        warnings: list[str] = []
        instruments, transactions_by_instrument = self._calculation_inputs()
        latest_closes = self.prices.last_two_cached_closes([i.id for i in instruments])
        quotes = {
            i.id: self._current_quote(i, now_utc, warnings, latest_closes[i.id])
            for i in instruments
            if transactions_by_instrument.get(i.id)
        }
        rebase = self.base_currency != TRY
        positions = self._positions(instruments, transactions_by_instrument, quotes, warnings, rebase=rebase)
        # The tax estimate is Turkish and in TRY, so it is worked out from a TRY run.
        try_positions = (
            self._positions(instruments, transactions_by_instrument, quotes, [], rebase=False)
            if rebase
            else positions
        )

        # Open positions first, then fully-closed ones that still carry realized PnL.
        positions.sort(key=lambda p: (p.quantity == 0, -p.market_value_try, p.ticker))

        totals = summarise_portfolio(positions)
        liq = liquidation(totals, self.settings.liquidation.haircut_pct)
        try_totals = summarise_portfolio(try_positions) if rebase else totals
        try_liq = liquidation(try_totals, self.settings.liquidation.haircut_pct) if rebase else liq

        tax_config = with_official_brackets(self.settings.tax)
        tax = (
            estimate_tax(
                try_liq.net_proceeds_try,
                try_liq.total_invested_try,
                tax_config,
                # So the estimate can report how much of the bill is the currency move.
                price_effect_try=try_totals.price_effect_try,
                fx_effect_try=try_totals.fx_effect_try,
            )
            if tax_config.enabled
            else disabled_estimate(try_liq.net_proceeds_try)
        )
        tax_in_lira = tax.tax_try if rebase else None
        if rebase:
            try:
                tax = self._tax_in_base(tax)
            except (ProviderError, DecimalException) as exc:
                warnings.append(f"{self.base_currency}: no FX rate ({exc})")
                tax = disabled_estimate(liq.net_proceeds_try)

        # Only meaningful when nothing is trading; otherwise the frontend polls normally.
        exchanges = {
            instrument.exchange
            for instrument in instruments
            if transactions_by_instrument.get(instrument.id)
        }
        any_open = any(market_hours.is_open(e, now_utc) for e in exchanges)
        next_open = None if any_open else market_hours.next_open(exchanges, now_utc)

        return PortfolioView(
            as_of=now_utc,
            positions=positions,
            totals=totals,
            liquidation=liq,
            tax=tax,
            warnings=warnings,
            next_market_open=next_open,
            instruments={i.ticker: i for i in instruments},
            tax_in_lira=tax_in_lira,
        )

    def _positions(
        self,
        instruments: list[Instrument],
        transactions_by_instrument: dict[int, list[Transaction]],
        quotes: dict[int, MarketQuote],
        warnings: list[str],
        *,
        rebase: bool,
    ) -> list[PositionMetrics]:
        """Each position's metrics, in the Base Currency when `rebase`, else in TRY."""
        positions: list[PositionMetrics] = []
        for instrument in instruments:
            transactions = transactions_by_instrument.get(instrument.id, [])
            if not transactions:
                continue

            quote = quotes[instrument.id]
            try:
                txns = [
                    to_txn_input(t, instrument.ticker, instrument.currency)
                    for t in transactions
                ]
                if rebase:
                    txns = [self._rebased(t) for t in txns]
                    quote = self._rebased_quote(quote)
                book = build_lot_book(instrument.ticker, instrument.currency, txns)
            except (InsufficientLots, ValueError, DecimalException, ProviderError) as exc:
                # One malformed position must not take the whole dashboard down —
                # otherwise the screen that can fix the bad row refuses to load.
                log.error("portfolio position failed for %s: %s", instrument.ticker, exc)
                warnings.append(f"{instrument.ticker}: {exc}")
                book = build_lot_book(instrument.ticker, instrument.currency, [])
                error = (
                    f"lot uyuşmazlığı: {exc}"
                    if isinstance(exc, InsufficientLots)
                    else f"veri uyumsuzluğu: {exc}"
                )
                positions.append(
                    position_metrics(
                        book,
                        replace(quote, ok=False, stale=True, error=error),
                    )
                )
                continue

            try:
                positions.append(position_metrics(book, quote))
            except DecimalException as exc:
                log.error("portfolio position failed for %s: %s", instrument.ticker, exc)
                warnings.append(f"{instrument.ticker}: {exc}")
                empty_book = build_lot_book(instrument.ticker, instrument.currency, [])
                positions.append(
                    position_metrics(
                        empty_book,
                        replace(
                            quote,
                            ok=False,
                            stale=True,
                            error=f"veri uyumsuzluğu: {exc}",
                        ),
                    )
                )
        return positions

    # -- history -------------------------------------------------------------------

    def build_history(
        self,
        start: date | None = None,
        end: date | None = None,
        freq: str = "D",
        tickers: list[str] | None = None,
    ) -> list[HistoryPoint]:
        """The daily series. `tickers` narrows it to a subset of the portfolio.

        Filtering the *inputs* rather than the output is what makes a single-instrument
        chart identical in shape to the portfolio one: the same builder, the same
        decomposition, the same carry-forward — just fewer positions folded in.
        """
        start = start or self.inception()
        end = end or date.today()

        instruments, transactions_by_instrument = self._calculation_inputs()
        instruments = self._select_instruments(instruments, tickers)
        if self._scope is not None and not instruments and not tickers:
            return []
        positions: list[PositionHistoryInput] = []
        closes: dict[str, dict[date, Decimal]] = {}
        currencies: set[str] = set()

        lookback = self.settings.fx.max_lookback_days
        stored_closes = self.prices.cached_closes(
            [i.id for i in instruments], start - timedelta(days=lookback), end
        )

        for instrument in instruments:
            transactions = transactions_by_instrument.get(instrument.id, [])
            if not transactions:
                continue
            try:
                txns = [
                    to_txn_input(t, instrument.ticker, instrument.currency)
                    for t in transactions
                ]
                build_lot_book(instrument.ticker, instrument.currency, txns)
            except (InsufficientLots, ValueError) as exc:
                log.error("history position failed for %s: %s", instrument.ticker, exc)
                continue
            positions.append(
                PositionHistoryInput(
                    ticker=instrument.ticker,
                    currency=instrument.currency,
                    transactions=txns,
                )
            )
            closes[instrument.ticker] = stored_closes[instrument.id]
            currencies.add(instrument.currency)

        fx_rates: dict[str, dict[date, Decimal]] = {}
        for currency in sorted(currencies):
            try:
                # Published rates only, in one query. `build_history` owns the
                # carry-forward policy so it is applied in exactly one place.
                fx_rates[currency] = self.fx.published_series(
                    currency, start - timedelta(days=lookback), end
                )
            except ProviderError as exc:
                log.error("history FX unavailable for %s: %s", currency, exc)
                fx_rates[currency] = {}

        tax_config = with_official_brackets(self.settings.tax)
        try_points = build_history(
            positions,
            closes,
            fx_rates,
            start,
            end,
            freq=freq,
            max_lookback_days=lookback,
            tax_config=tax_config,
        )
        if self.base_currency == TRY:
            return try_points

        # The same series in the Base Currency; its after-tax line is the TRY run's tax
        # at each date's rate.
        try:
            base_series = self.fx.published_series(
                self.base_currency, start - timedelta(days=lookback), end, allow_fetch=True
            )
            rebased_positions = []
            for position in positions:
                try:
                    rebased_positions.append(
                        replace(position, transactions=[self._rebased(t) for t in position.transactions])
                    )
                except ProviderError as exc:
                    log.error("history rebase failed for %s: %s", position.ticker, exc)
        except ProviderError as exc:
            log.error("history FX unavailable for %s: %s", self.base_currency, exc)
            return []
        points = build_history(
            rebased_positions,
            closes,
            {c: cross_daily(c, fx_rates.get(c, {}), base_series) for c in currencies},
            start,
            end,
            freq=freq,
            max_lookback_days=lookback,
        )
        tax_on = {p.point_date: p.tax_try for p in try_points}
        base_on = last_at(base_series)
        return [
            _with_tax(point, tax_on.get(point.point_date, 0), base_on(point.point_date))
            for point in points
        ]

    # -- intraday ------------------------------------------------------------------

    def build_intraday(
        self,
        interval: str = "5m",
        *,
        force: bool = False,
        tickers: list[str] | None = None,
        session_offset: int = 0,
    ) -> tuple[list[IntradayPoint], list[str], int]:
        """The 1G view: the portfolio valued through the most recent trading day.

        Returns (points, warnings). Frames itself on the last day with any data, so on a
        weekend it shows Friday's session rather than an empty grid. `tickers` narrows it
        to a subset, exactly as `build_history` does.
        """
        instruments, transactions_by_instrument = self._calculation_inputs()
        instruments = [
            instrument
            for instrument in self._select_instruments(instruments, tickers)
            if transactions_by_instrument.get(instrument.id)
        ]
        if not instruments:
            return [], [], 0

        positions = [
            PositionHistoryInput(
                ticker=i.ticker,
                currency=i.currency,
                transactions=[
                    to_txn_input(t, i.ticker, i.currency)
                    for t in transactions_by_instrument[i.id]
                ],
            )
            for i in instruments
        ]

        # Fresh per call: the service is shared across requests, so a warning must not
        # outlive the request that produced it.
        errors: list[str] = []

        symbol_of = {i.yf_symbol: i.ticker for i in instruments}
        raw_prices = self.intraday.prices(
            list(symbol_of), interval, force=force, errors=errors
        )
        prices = {symbol_of[sym]: series for sym, series in raw_prices.items()}
        base = self.base_currency
        currencies = {i.currency for i in instruments}
        fetched = self.intraday.fx(
            sorted(currencies | ({base} if base != TRY else set())),
            interval,
            force=force,
            errors=errors,
        )
        fx_rates = {c: series for c, series in fetched.items() if c in currencies}

        combined = {**prices, **fx_rates}
        available = len(session_days(combined))
        bounds = latest_session_bounds(combined, session_offset)
        if bounds is None:
            note = (
                "daha eski gün içi veri yok"
                if available and session_offset >= available
                else "intraday veri alınamadı"
            )
            return [], errors + [note], available

        step = {"5m": 5, "15m": 15, "1h": 60}.get(interval, 5)
        grid = build_grid(bounds[0], bounds[1], step)

        try_points = build_intraday_series(
            positions, prices, fx_rates, grid, tax_config=with_official_brackets(self.settings.tax)
        )
        if base == TRY:
            return try_points, errors, available

        base_series = fetched.get(base, {})
        try:
            rebased_positions = [
                replace(p, transactions=[self._rebased(t) for t in p.transactions]) for p in positions
            ]
        except ProviderError as exc:
            return [], errors + [f"{base}: {exc}"], available
        points = build_intraday_series(
            rebased_positions,
            prices,
            {c: cross_intraday(c, fx_rates.get(c, {}), base_series) for c in currencies},
            grid,
        )
        tax_at = {p.at: p.value_try - p.value_after_tax_try for p in try_points}
        base_at = last_at(base_series)
        return [
            _with_tax(point, tax_at.get(point.at, 0), base_at(point.at))
            for point in points
        ], errors, available


def _with_tax(point, tax_try: Decimal, base_rate: Decimal | None):
    """A Base Currency point whose after-tax value takes off the TRY tax at `base_rate`."""
    if not tax_try or base_rate is None or point.value_try <= 0:
        return point
    return replace(point, value_after_tax_try=point.value_try - cross(tax_try, base_rate))

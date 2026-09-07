"""Portfolio assembly: DB + providers -> pure calc engine (SPEC §6, §7, §8).

The calc engine takes no I/O, so this module is where the DB rows and provider responses
are turned into its plain input types. Nothing here does arithmetic on money beyond
building those inputs — all of that lives in `app.calc`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import inspect as sa_inspect, select
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
from app.calc.tax import TaxEstimate, disabled_estimate, estimate_tax
from app.calc.types import Side as CalcSide
from app.calc.types import TxnInput
from app.config import Settings
from app.models import Instrument, Transaction
from app.providers import market_hours
from app.providers.base import ProviderError
from app.providers.fx_service import FxService
from app.providers.intraday import IntradayService, latest_session_bounds, session_days
from app.providers.price_service import PriceService, RefreshReport
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


def load_instruments(session: Session, *, active_only: bool = True) -> list[Instrument]:
    stmt = select(Instrument).options(selectinload(Instrument.transactions))
    if active_only:
        stmt = stmt.where(Instrument.active.is_(True))
    return list(session.execute(stmt).scalars())


def load_shared_instruments(session: Session) -> list[Instrument]:
    stmt = (
        select(Instrument)
        .where(Instrument.active.is_(True))
        .order_by(Instrument.id)
    )
    return list(session.scalars(stmt))


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

    def refresh(self, *, force: bool = False) -> RefreshReport:
        """Refetch prices and FX. Partial failure is expected and tolerated (SPEC §8)."""
        if self._scope is not None:
            raise PortfolioScopeViolation("Refresh is not available for a scoped service")
        instruments = load_instruments(self.session)
        full_start = self.inception() - timedelta(days=10)
        end = date.today()

        # Only ask for what is actually missing. Settled closes never change, so the
        # rows already held would be discarded on arrival anyway.
        start = self.prices.incremental_start(instruments, full_start)

        report = self.prices.refresh(instruments, start, end, force=force)

        for currency in sorted({i.currency for i in instruments}):
            try:
                self.fx.current(currency, force=force)
            except ProviderError as exc:
                log.error("FX refresh failed for %s: %s", currency, exc)
                report.errors.append(f"FX {currency}: {exc}")

        return report

    def refresh_shared(self, *, force: bool = False) -> RefreshReport:
        """Refresh shared market rows without reading or changing private rows."""
        if self._scope is not None:
            raise PortfolioScopeViolation("Shared refresh is not available for a scoped service")
        if self.session.new or self.session.dirty or self.session.deleted:
            raise ValueError("shared refresh requires a clean caller Session")

        instruments = load_shared_instruments(self.session)
        end = date.today()
        full_start = end - timedelta(days=10)
        start = self.prices.incremental_start(instruments, full_start)
        report = self.prices.refresh_shared(instruments, start, end, force=force)

        for currency in sorted({instrument.currency for instrument in instruments}):
            try:
                self.fx.warm(currency, full_start, end)
            except ProviderError as exc:
                log.error("shared FX refresh failed for %s: %s", currency, exc)
                report.errors.append(f"FX {currency}: {exc}")

        return report

    # -- current view --------------------------------------------------------------

    def _current_quote(
        self, instrument: Instrument, now_utc: datetime, warnings: list[str]
    ) -> MarketQuote:
        """Build a MarketQuote, degrading this one position rather than the page."""
        session_state = market_hours.session_state(instrument.exchange, now_utc)

        price_row, prev_row = self.prices.last_two_cached_closes(instrument.id)
        if price_row is None:
            warnings.append(f"{instrument.ticker}: no price available")
            return MarketQuote(
                ticker=instrument.ticker,
                currency=instrument.currency,
                price_native=Decimal("0"),
                price_date=date.today(),
                fx_rate_to_try=Decimal("0"),
                fx_rate_date=date.today(),
                fx_provider="none",
                ok=False,
                session=session_state,
                stale=True,
                error="no price data",
            )

        close, price_date = price_row

        try:
            fx_quote = self.fx.current(instrument.currency)
        except ProviderError as exc:
            warnings.append(f"{instrument.ticker}: no FX rate ({exc})")
            return MarketQuote(
                ticker=instrument.ticker,
                currency=instrument.currency,
                price_native=close,
                price_date=price_date,
                fx_rate_to_try=Decimal("0"),
                fx_rate_date=price_date,
                fx_provider="none",
                ok=False,
                session=session_state,
                stale=True,
                error=f"no FX rate: {exc}",
            )

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
        positions: list[PositionMetrics] = []
        instruments, transactions_by_instrument = self._calculation_inputs()

        for instrument in instruments:
            txns = [
                to_txn_input(t, instrument.ticker, instrument.currency)
                for t in transactions_by_instrument.get(instrument.id, [])
            ]
            if not txns:
                continue

            try:
                book = build_lot_book(instrument.ticker, instrument.currency, txns)
            except InsufficientLots as exc:
                # A SELL that exceeds the lots on file cannot be valued, but it must not
                # take the whole dashboard down with it — otherwise the one screen that
                # can fix the bad row is the screen that refuses to load. Degrade this
                # position and keep the rest, exactly as a dead symbol is handled
                # (SPEC §8).
                log.error("lot matching failed for %s: %s", instrument.ticker, exc)
                warnings.append(f"{instrument.ticker}: {exc}")
                book = build_lot_book(instrument.ticker, instrument.currency, [])
                quote = self._current_quote(instrument, now_utc, warnings)
                positions.append(
                    position_metrics(
                        book,
                        replace(quote, ok=False, stale=True, error=f"lot uyuşmazlığı: {exc}"),
                    )
                )
                continue

            quote = self._current_quote(instrument, now_utc, warnings)
            positions.append(position_metrics(book, quote))

        # Open positions first, then fully-closed ones that still carry realized PnL.
        positions.sort(key=lambda p: (p.quantity == 0, -p.market_value_try, p.ticker))

        totals = summarise_portfolio(positions)
        liq = liquidation(totals, self.settings.liquidation.haircut_pct)

        tax_config = self.settings.tax
        tax = (
            estimate_tax(
                liq.net_proceeds_try,
                liq.total_invested_try,
                tax_config,
                # So the estimate can report how much of the bill is the currency move.
                price_effect_try=totals.price_effect_try,
                fx_effect_try=totals.fx_effect_try,
            )
            if tax_config.enabled
            else disabled_estimate(liq.net_proceeds_try)
        )

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
        )

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

        for instrument in instruments:
            transactions = transactions_by_instrument.get(instrument.id, [])
            if not transactions:
                continue
            positions.append(
                PositionHistoryInput(
                    ticker=instrument.ticker,
                    currency=instrument.currency,
                    transactions=[
                        to_txn_input(t, instrument.ticker, instrument.currency)
                        for t in transactions
                    ],
                )
            )
            closes[instrument.ticker] = self.prices.cached_closes(
                instrument.id, start - timedelta(days=lookback), end
            )
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

        return build_history(
            positions,
            closes,
            fx_rates,
            start,
            end,
            freq=freq,
            max_lookback_days=lookback,
            tax_config=self.settings.tax,
        )

    # -- intraday ------------------------------------------------------------------

    def _filtered_instruments(self, tickers: list[str] | None) -> list[Instrument]:
        instruments, _ = self._calculation_inputs()
        return self._select_instruments(instruments, tickers)

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
        fx_rates = self.intraday.fx(
            sorted({i.currency for i in instruments}), interval, force=force, errors=errors
        )

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

        points = build_intraday_series(
            positions, prices, fx_rates, grid, tax_config=self.settings.tax
        )
        return points, errors, available

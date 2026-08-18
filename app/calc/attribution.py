"""Return attribution and portfolio totals (SPEC §6).

The headline feature. Total return in TRY is the *product* of local price return and FX
return, and the two must be decomposable, not blended:

    local_return  = market_value_native / cost_native
    fx_return     = current_fx_rate / weighted_avg_cost_fx_rate
    total_return  = local_return x fx_return          == mv_try / cost_try

    price_effect_try = (market_value_native - cost_native) x weighted_avg_cost_fx_rate
    fx_effect_try    = market_value_native x (current_fx_rate - weighted_avg_cost_fx_rate)

Both identities are *exact* here, not approximate, because `weighted_avg_cost_fx_rate` is
defined as `cost_try / cost_native` (weighted by native cost, per SPEC §6) and no
intermediate is rounded. Expanding the effects:

    price_effect + fx_effect
      = (mv_n - c_n)·w + mv_n·(f - w)
      = mv_n·w - c_n·w + mv_n·f - mv_n·w
      = mv_n·f - c_n·w
      = mv_try - cost_try
      = pnl_try

Rounding happens only at the serialisation boundary, never inside the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from app.calc.fifo import LotBook, RealizedPnl
from app.calc.types import CALC_PRECISION, ZERO, MarketQuote

__all__ = [
    "CALC_PRECISION",
    "NO_DAILY_CHANGE",
    "Attribution",
    "DailyChange",
    "LiquidationSummary",
    "PortfolioTotals",
    "PositionMetrics",
    "attribute",
    "daily_change",
    "liquidation",
    "position_metrics",
    "summarise_portfolio",
]


@dataclass(frozen=True)
class Attribution:
    """The price/FX decomposition for one position or for the portfolio."""

    #: None when there is no cost basis to divide by (a fully closed or empty position).
    local_return: Decimal | None
    fx_return: Decimal | None
    total_return: Decimal | None
    price_effect_try: Decimal
    fx_effect_try: Decimal
    weighted_avg_cost_fx_rate: Decimal | None
    current_fx_rate: Decimal


@dataclass(frozen=True)
class DailyChange:
    """The move since the previous session, split into price and FX exactly as §6 does.

    Quantity is held constant across both valuations. A position opened today would
    otherwise show its entire purchase as a day's gain, and the day's *move* is the
    question being asked, not the day's trading.

        prev_value_try = quantity x prev_close x prev_rate
        value_try      = quantity x close      x rate

        price_effect   = quantity x (close - prev_close) x prev_rate
        fx_effect      = quantity x close x (rate - prev_rate)

    The two effects sum to `pnl_try` exactly, by the same expansion as the lifetime
    attribution above:

        q·(c−pc)·pr + q·c·(r−pr) = q·c·pr − q·pc·pr + q·c·r − q·c·pr = q·c·r − q·pc·pr
    """

    #: False when there is no earlier session on file. Every figure below is then zero
    #: and must not be rendered — "no data" and "no movement" are different claims.
    available: bool
    #: The session being compared against. Not necessarily yesterday: for a shut market
    #: it is the last day that actually traded, which is what the UI has to label.
    reference_date: date | None
    pnl_try: Decimal
    price_effect_try: Decimal
    fx_effect_try: Decimal
    #: The move in the instrument's own currency — no FX component by construction.
    pnl_native: Decimal
    #: value / prev_value. None when the previous valuation was zero.
    return_ratio: Decimal | None


NO_DAILY_CHANGE = DailyChange(
    available=False,
    reference_date=None,
    pnl_try=ZERO,
    price_effect_try=ZERO,
    fx_effect_try=ZERO,
    pnl_native=ZERO,
    return_ratio=None,
)


def daily_change(quantity: Decimal, quote: MarketQuote) -> DailyChange:
    """The since-previous-session move for one position."""
    if (
        not quote.ok
        or quote.prev_price_native is None
        or quote.prev_fx_rate_to_try is None
        or quantity <= ZERO
    ):
        return NO_DAILY_CHANGE

    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        close, rate = quote.price_native, quote.fx_rate_to_try
        prev_close, prev_rate = quote.prev_price_native, quote.prev_fx_rate_to_try

        value = quantity * close * rate
        prev_value = quantity * prev_close * prev_rate

        return DailyChange(
            available=True,
            reference_date=quote.prev_price_date,
            pnl_try=value - prev_value,
            price_effect_try=quantity * (close - prev_close) * prev_rate,
            fx_effect_try=quantity * close * (rate - prev_rate),
            pnl_native=quantity * (close - prev_close),
            return_ratio=(value / prev_value) if prev_value != ZERO else None,
        )


@dataclass(frozen=True)
class PositionMetrics:
    ticker: str
    currency: str
    quantity: Decimal

    cost_native: Decimal
    cost_try: Decimal
    market_value_native: Decimal
    market_value_try: Decimal

    pnl_native: Decimal
    pnl_try: Decimal

    attribution: Attribution
    realized: RealizedPnl
    daily: DailyChange

    price_native: Decimal
    price_date: date
    fx_rate_to_try: Decimal
    fx_rate_date: date
    fx_provider: str

    #: Per-position failure isolation (SPEC §8): one bad symbol degrades one row.
    ok: bool = True
    session: str = "closed"
    stale: bool = False
    error: str | None = None
    fx_carried_forward: bool = False
    lot_count: int = 0


@dataclass(frozen=True)
class PortfolioTotals:
    cost_try: Decimal
    market_value_try: Decimal
    pnl_try: Decimal
    price_effect_try: Decimal
    fx_effect_try: Decimal
    total_return: Decimal | None
    realized_pnl_try: Decimal
    realized_price_effect_try: Decimal
    realized_fx_effect_try: Decimal
    #: Aggregated across positions that have a previous session on file.
    daily: DailyChange = NO_DAILY_CHANGE


@dataclass(frozen=True)
class LiquidationSummary:
    """SPEC §6 top-line card. An estimate; excludes tax."""

    gross_proceeds_try: Decimal
    haircut_pct: Decimal
    haircut_try: Decimal
    net_proceeds_try: Decimal
    total_invested_try: Decimal
    net_pnl_try: Decimal
    net_return: Decimal | None
    excludes_tax: bool = True


def attribute(book: LotBook, quote: MarketQuote) -> Attribution:
    """Decompose a position's unrealized return into price and FX components."""
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        cost_native = book.cost_native
        wavg = book.weighted_avg_cost_fx_rate
        current_fx = quote.fx_rate_to_try
        mv_native = book.quantity * quote.price_native

        if cost_native == ZERO or wavg is None:
            # No basis to divide by: a closed or empty position has no return to report,
            # and reporting 0% would be a different (false) claim than reporting nothing.
            return Attribution(
                local_return=None,
                fx_return=None,
                total_return=None,
                price_effect_try=ZERO,
                fx_effect_try=ZERO,
                weighted_avg_cost_fx_rate=wavg,
                current_fx_rate=current_fx,
            )

        local_return = mv_native / cost_native
        fx_return = current_fx / wavg

        return Attribution(
            local_return=local_return,
            fx_return=fx_return,
            total_return=local_return * fx_return,
            price_effect_try=(mv_native - cost_native) * wavg,
            fx_effect_try=mv_native * (current_fx - wavg),
            weighted_avg_cost_fx_rate=wavg,
            current_fx_rate=current_fx,
        )


def position_metrics(book: LotBook, quote: MarketQuote) -> PositionMetrics:
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        quantity = book.quantity
        cost_native = book.cost_native
        cost_try = book.cost_try
        mv_native = quantity * quote.price_native
        mv_try = mv_native * quote.fx_rate_to_try

        return PositionMetrics(
            ticker=book.ticker,
            currency=book.currency,
            quantity=quantity,
            cost_native=cost_native,
            cost_try=cost_try,
            market_value_native=mv_native,
            market_value_try=mv_try,
            pnl_native=mv_native - cost_native,
            pnl_try=mv_try - cost_try,
            attribution=attribute(book, quote),
            realized=book.realized,
            daily=daily_change(quantity, quote),
            price_native=quote.price_native,
            price_date=quote.price_date,
            fx_rate_to_try=quote.fx_rate_to_try,
            fx_rate_date=quote.fx_rate_date,
            fx_provider=quote.fx_provider,
            ok=quote.ok,
            session=quote.session,
            stale=quote.stale,
            error=quote.error,
            fx_carried_forward=quote.fx_carried_forward,
            lot_count=len(book.open_lots),
        )


def summarise_portfolio(positions: list[PositionMetrics]) -> PortfolioTotals:
    """Aggregate positions.

    Only positions with a usable price contribute to value totals — a failed symbol
    must not silently count as zero market value, which would read as a total loss on
    that position (SPEC §8, US-5.3).
    """
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        priced = [p for p in positions if p.ok]

        cost_try = sum((p.cost_try for p in priced), ZERO)
        mv_try = sum((p.market_value_try for p in priced), ZERO)
        price_effect = sum((p.attribution.price_effect_try for p in priced), ZERO)
        fx_effect = sum((p.attribution.fx_effect_try for p in priced), ZERO)

        # Realized PnL is independent of current prices, so every position counts.
        realized_pnl = sum((p.realized.pnl_try for p in positions), ZERO)
        realized_price = sum((p.realized.price_effect_try for p in positions), ZERO)
        realized_fx = sum((p.realized.fx_effect_try for p in positions), ZERO)

        # A position with no previous session on file contributes nothing rather than a
        # zero, so the portfolio figure never dilutes the day's move with rows that
        # simply have no history to compare against.
        moving = [p for p in priced if p.daily.available]
        daily_pnl = sum((p.daily.pnl_try for p in moving), ZERO)
        daily_price = sum((p.daily.price_effect_try for p in moving), ZERO)
        daily_fx = sum((p.daily.fx_effect_try for p in moving), ZERO)
        prev_value = sum((p.market_value_try for p in moving), ZERO) - daily_pnl
        daily = (
            DailyChange(
                available=True,
                # The *earliest* session represented, not the latest. Constituent
                # reference dates legitimately disagree — exchanges close at different
                # times, and a dropped NaN close (docs/FINDINGS.md F-4) can push one
                # instrument's previous session back several days. Taking the latest
                # would label the aggregate with a window shorter than it really covers;
                # the earliest states the span honestly, and per-position dates are on
                # the rows.
                reference_date=min(
                    (p.daily.reference_date for p in moving if p.daily.reference_date),
                    default=None,
                ),
                pnl_try=daily_pnl,
                price_effect_try=daily_price,
                fx_effect_try=daily_fx,
                # Meaningless across mixed currencies; the TRY figure is the portfolio view.
                pnl_native=ZERO,
                return_ratio=(
                    (prev_value + daily_pnl) / prev_value if prev_value != ZERO else None
                ),
            )
            if moving
            else NO_DAILY_CHANGE
        )

        return PortfolioTotals(
            cost_try=cost_try,
            market_value_try=mv_try,
            pnl_try=mv_try - cost_try,
            price_effect_try=price_effect,
            fx_effect_try=fx_effect,
            total_return=(mv_try / cost_try) if cost_try != ZERO else None,
            realized_pnl_try=realized_pnl,
            realized_price_effect_try=realized_price,
            realized_fx_effect_try=realized_fx,
            daily=daily,
        )


def liquidation(
    totals: PortfolioTotals, haircut_pct: Decimal = ZERO
) -> LiquidationSummary:
    """Total TRY proceeds if everything were sold and converted back today (SPEC §6).

    The haircut approximates FX spread and commission on a full exit. Default 0%.
    Clearly an estimate, and it excludes tax.
    """
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        gross = totals.market_value_try
        haircut = gross * haircut_pct
        net = gross - haircut
        invested = totals.cost_try
        net_pnl = net - invested

        return LiquidationSummary(
            gross_proceeds_try=gross,
            haircut_pct=haircut_pct,
            haircut_try=haircut,
            net_proceeds_try=net,
            total_invested_try=invested,
            net_pnl_try=net_pnl,
            net_return=(net / invested) if invested != ZERO else None,
        )

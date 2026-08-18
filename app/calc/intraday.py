"""Intraday portfolio series (the 1G view).

Same decomposition as the daily history in `app.calc.history` — value in TRY, value at
constant FX, cost basis, and value after estimated tax — but sampled on a timestamp grid
instead of a calendar.

The wrinkle intraday introduces is that the four exchanges are almost never open at once.
At 16:00 Istanbul, New York has not opened and Taipei closed hours ago. So each
instrument's last known price is carried forward across the grid exactly as a weekend is
handled daily: the position keeps its last traded value rather than vanishing or being
interpolated. Without that, the portfolio curve would collapse and spike as each market
came in and out of session.

Pure: every price and rate is passed in.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext

from app.calc.fifo import LotBook, _sort_key
from app.calc.history import PositionHistoryInput
from app.calc.tax import TaxConfig, net_after_tax
from app.calc.types import CALC_PRECISION, ZERO


@dataclass(frozen=True)
class IntradayPoint:
    at: datetime
    value_try: Decimal
    value_constant_fx_try: Decimal
    cost_basis_try: Decimal
    value_after_tax_try: Decimal
    #: Tickers with no bar at or before this instant.
    missing: tuple[str, ...] = ()
    #: True when at least one instrument is being carried forward from a shut market.
    carried_forward: bool = False

    @property
    def pnl_try(self) -> Decimal:
        return self.value_try - self.cost_basis_try

    @property
    def price_effect_try(self) -> Decimal:
        return self.value_constant_fx_try - self.cost_basis_try

    @property
    def fx_effect_try(self) -> Decimal:
        return self.value_try - self.value_constant_fx_try


class _Stepper:
    """Last-known-value lookup over a sorted timestamp series.

    The grid and the series both advance forwards, so a binary search per step keeps the
    whole sweep O(grid x log bars) instead of rescanning the series each time.
    """

    __slots__ = ("stamps", "values")

    def __init__(self, series: dict[datetime, Decimal]) -> None:
        self.stamps = sorted(series)
        self.values = [series[s] for s in self.stamps]

    def at(self, moment: datetime) -> tuple[Decimal | None, bool]:
        """(value, is_carried_forward) — the last bar at or before `moment`."""
        if not self.stamps:
            return None, False
        index = bisect_right(self.stamps, moment) - 1
        if index < 0:
            return None, False
        return self.values[index], self.stamps[index] != moment


def build_grid(start: datetime, end: datetime, step_minutes: int) -> list[datetime]:
    step = timedelta(minutes=step_minutes)
    grid: list[datetime] = []
    moment = start
    while moment <= end:
        grid.append(moment)
        moment += step
    return grid


def build_intraday_series(
    positions: list[PositionHistoryInput],
    prices: dict[str, dict[datetime, Decimal]],
    fx_rates: dict[str, dict[datetime, Decimal]],
    grid: list[datetime],
    *,
    tax_config: TaxConfig | None = None,
) -> list[IntradayPoint]:
    """Value the portfolio at each instant on `grid`."""
    if not grid:
        return []

    price_steppers = {ticker: _Stepper(series) for ticker, series in prices.items()}
    fx_steppers = {ccy: _Stepper(series) for ccy, series in fx_rates.items()}

    points: list[IntradayPoint] = []
    as_of_date = grid[-1].date()

    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        # Holdings are fixed across an intraday window unless a trade lands inside it,
        # so each book is built once rather than per grid step.
        books: dict[str, LotBook] = {}
        for position in positions:
            book = LotBook(ticker=position.ticker, currency=position.currency)
            for txn in sorted(position.transactions, key=_sort_key):
                if txn.trade_date <= as_of_date:
                    book.apply(txn)
            books[position.ticker] = book

        for moment in grid:
            value_try = ZERO
            value_const = ZERO
            cost_try = ZERO
            missing: list[str] = []
            carried = False

            for position in positions:
                book = books[position.ticker]
                if book.quantity <= ZERO:
                    continue

                price_stepper = price_steppers.get(position.ticker)
                fx_stepper = fx_steppers.get(position.currency)
                if price_stepper is None or fx_stepper is None:
                    missing.append(position.ticker)
                    continue

                close, price_carried = price_stepper.at(moment)
                rate, rate_carried = fx_stepper.at(moment)
                if close is None or rate is None:
                    missing.append(position.ticker)
                    continue

                carried = carried or price_carried or rate_carried

                mv_native = book.quantity * close
                wavg = book.weighted_avg_cost_fx_rate or rate

                value_try += mv_native * rate
                value_const += mv_native * wavg
                cost_try += book.cost_try

            after_tax = value_try
            if tax_config is not None and tax_config.enabled and value_try > ZERO:
                after_tax = net_after_tax(value_try, cost_try, tax_config)

            points.append(
                IntradayPoint(
                    at=moment,
                    value_try=value_try,
                    value_constant_fx_try=value_const,
                    cost_basis_try=cost_try,
                    value_after_tax_try=after_tax,
                    missing=tuple(missing),
                    carried_forward=carried,
                )
            )

    return points

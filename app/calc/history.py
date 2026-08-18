"""Daily portfolio history (SPEC §6, "Historical series").

For each date, value **only the lots held on that date**, at that date's close and that
date's FX rate. Three series are emitted:

1. `value_try`            — market value converted at each day's actual FX rate
2. `value_constant_fx_try` — the same holdings with FX frozen at cost
3. `cost_basis_try`        — what was actually invested, in TRY, as at that date

The gap between (1) and (2) *is* the FX contribution, and the gap between (2) and (3) is
the local price contribution — the same decomposition as the point-in-time attribution,
so the chart and the attribution bar can never disagree.

Non-trading days carry the prior close forward and are flagged (US-4.1). Pure: all price
and FX data is passed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext

from app.calc.attribution import CALC_PRECISION
from app.calc.fifo import LotBook, _sort_key
from app.calc.tax import TaxConfig, net_after_tax
from app.calc.types import ZERO, TxnInput


@dataclass(frozen=True)
class PositionHistoryInput:
    ticker: str
    currency: str
    transactions: list[TxnInput]


@dataclass(frozen=True)
class HistoryPoint:
    point_date: date
    value_try: Decimal
    value_constant_fx_try: Decimal
    cost_basis_try: Decimal
    #: Value net of the estimated tax on that day's gain. Equals `value_try` when tax
    #: estimation is disabled, so the series is always present and always plottable.
    value_after_tax_try: Decimal = ZERO
    #: True when at least one instrument used a close from an earlier session.
    price_carried_forward: bool = False
    #: True when at least one currency used a rate published before this date.
    fx_carried_forward: bool = False
    #: Tickers held on this date that had no usable price at all.
    missing: tuple[str, ...] = ()

    @property
    def pnl_try(self) -> Decimal:
        return self.value_try - self.cost_basis_try

    @property
    def price_effect_try(self) -> Decimal:
        return self.value_constant_fx_try - self.cost_basis_try

    @property
    def fx_effect_try(self) -> Decimal:
        return self.value_try - self.value_constant_fx_try

    @property
    def tax_try(self) -> Decimal:
        return self.value_try - self.value_after_tax_try

    @property
    def pnl_after_tax_try(self) -> Decimal:
        return self.value_after_tax_try - self.cost_basis_try


def _forward_fill(
    published: dict[date, Decimal],
    start: date,
    end: date,
    max_lookback_days: int,
) -> dict[date, tuple[Decimal, bool]]:
    """Dense day -> (value, carried_forward) map over [start, end].

    One linear sweep replaces a backwards probe per day: the previous published value
    and its age are carried along, so the cost is O(days) rather than
    O(days x lookback). Carry-forward stops once the value is older than the window,
    which is what makes a gap surface as missing data instead of a stale guess.
    """
    if not published:
        return {}

    # Prime from the last value published before the window, so day one can carry
    # forward like any other day rather than falsely reading as missing.
    last_date: date | None = max((d for d in published if d < start), default=None)
    last_value: Decimal | None = published[last_date] if last_date else None

    out: dict[date, tuple[Decimal, bool]] = {}
    day = start
    while day <= end:
        if day in published:
            last_value = published[day]
            last_date = day
            out[day] = (last_value, False)
        elif last_value is not None and (day - last_date).days <= max_lookback_days:
            out[day] = (last_value, True)
        day += timedelta(days=1)

    return out


def build_history(
    positions: list[PositionHistoryInput],
    closes: dict[str, dict[date, Decimal]],
    fx_rates: dict[str, dict[date, Decimal]],
    start: date,
    end: date,
    *,
    freq: str = "D",
    max_lookback_days: int = 7,
    tax_config: TaxConfig | None = None,
) -> list[HistoryPoint]:
    """Build the three series over [start, end].

    `closes` is keyed by ticker, `fx_rates` by currency (rates to TRY). Both hold only
    published values; carry-forward is applied here so the policy has one implementation.
    """
    if start > end:
        return []

    # Dense day -> (value, carried_forward) lookups, built once per series instead of
    # probed backwards per position per day.
    price_lookup = {
        ticker: _forward_fill(published, start, end, max_lookback_days)
        for ticker, published in closes.items()
    }
    fx_lookup = {
        currency: _forward_fill(published, start, end, max_lookback_days)
        for currency, published in fx_rates.items()
    }

    calendar: list[date] = []
    day = start
    while day <= end:
        calendar.append(day)
        day += timedelta(days=1)

    # Accumulators indexed by position in `calendar`.
    n = len(calendar)
    value_try = [ZERO] * n
    value_const = [ZERO] * n
    cost_try = [ZERO] * n
    price_cf = [False] * n
    fx_cf = [False] * n
    missing: list[list[str]] = [[] for _ in range(n)]

    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION

        for position in positions:
            ordered = sorted(position.transactions, key=_sort_key)
            book = LotBook(ticker=position.ticker, currency=position.currency)
            cursor = 0

            prices = price_lookup.get(position.ticker, {})
            rates = fx_lookup.get(position.currency, {})

            # Fold in everything that happened before the window opens.
            while cursor < len(ordered) and ordered[cursor].trade_date < start:
                book.apply(ordered[cursor])
                cursor += 1

            for index, current in enumerate(calendar):
                # Apply the day's transactions, then value what is held at its close.
                while cursor < len(ordered) and ordered[cursor].trade_date == current:
                    book.apply(ordered[cursor])
                    cursor += 1

                quantity = book.quantity
                if quantity <= ZERO:
                    continue

                price_entry = prices.get(current)
                rate_entry = rates.get(current)
                if price_entry is None or rate_entry is None:
                    missing[index].append(position.ticker)
                    # Cost basis is still known even when the price is not, but adding
                    # it without a matching market value would invent a loss. Skip the
                    # position entirely and report it.
                    continue

                close, close_carried = price_entry
                rate, rate_carried = rate_entry
                price_cf[index] = price_cf[index] or close_carried
                fx_cf[index] = fx_cf[index] or rate_carried

                mv_native = quantity * close
                wavg = book.weighted_avg_cost_fx_rate or rate

                value_try[index] += mv_native * rate
                value_const[index] += mv_native * wavg
                cost_try[index] += book.cost_try

    taxing = tax_config is not None and tax_config.enabled

    points = [
        HistoryPoint(
            point_date=calendar[i],
            value_try=value_try[i],
            value_constant_fx_try=value_const[i],
            cost_basis_try=cost_try[i],
            value_after_tax_try=(
                net_after_tax(value_try[i], cost_try[i], tax_config)
                if taxing and value_try[i] > ZERO
                else value_try[i]
            ),
            price_carried_forward=price_cf[i],
            fx_carried_forward=fx_cf[i],
            missing=tuple(missing[i]),
        )
        for i in range(n)
    ]

    return _resample(points, freq)


def _resample(points: list[HistoryPoint], freq: str) -> list[HistoryPoint]:
    """Downsample by taking the last point in each bucket. 'D' is a no-op."""
    freq = (freq or "D").upper()
    if freq == "D" or not points:
        return points

    if freq == "W":
        key = lambda p: p.point_date.isocalendar()[:2]  # noqa: E731
    elif freq == "M":
        key = lambda p: (p.point_date.year, p.point_date.month)  # noqa: E731
    else:
        return points

    buckets: dict[tuple, HistoryPoint] = {}
    for point in points:
        buckets[key(point)] = point  # later points overwrite; last wins
    return [buckets[k] for k in sorted(buckets)]

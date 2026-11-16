"""Rates to TRY turned into rates to a Portfolio's Base Currency (ADR 0006).

Every stored and fetched rate is `CCY/TRY`. A Portfolio in another Base Currency `B`
is valued by crossing through TRY on the same date or instant:

    CCY/B = (CCY/TRY) / (B/TRY)

so the calc engine, which only multiplies native amounts by "the rate", values the
Portfolio in `B` unchanged. TRY itself has no series (its rate to TRY is 1), so a TRY
instrument's rate to `B` is `1 / (B/TRY)`. Pure: no I/O.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime
from decimal import Decimal, localcontext

from app.calc.types import CALC_PRECISION

TRY = "TRY"
ONE = Decimal(1)
#: Stored rates carry 10 decimals; a crossed one keeps 12, so a TRY rate to USD near
#: 0.026 still holds 10 significant digits without dragging 50-digit tails into totals.
CROSS_QUANTUM = Decimal("1e-12")


def cross(rate_to_try: Decimal, base_to_try: Decimal) -> Decimal:
    """One rate to TRY as a rate to the base, both taken on the same date."""
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        return (rate_to_try / base_to_try).quantize(CROSS_QUANTUM)


def cross_daily(
    currency: str, series: dict[date, Decimal], base: dict[date, Decimal]
) -> dict[date, Decimal]:
    """A published daily `currency`/TRY series as `currency`/base.

    Only dates both sides published are crossed; the history builder carries rates
    forward itself, so a date one side skipped surfaces as carried, not as a guess.
    """
    if currency == TRY:
        return {day: cross(ONE, rate) for day, rate in base.items()}
    return {day: cross(rate, base[day]) for day, rate in series.items() if day in base}


def cross_intraday(
    currency: str, series: dict[datetime, Decimal], base: dict[datetime, Decimal]
) -> dict[datetime, Decimal]:
    """An intraday `currency`/TRY series as `currency`/base.

    Bars of two FX pairs rarely share timestamps, so each instant on either side takes
    the other side's last bar at or before it; instants before the other side's first
    bar are dropped.
    """
    if not base:
        return {}
    if currency == TRY:
        return {at: cross(ONE, rate) for at, rate in base.items()}
    stamps = sorted(series.keys() | base.keys())
    own_at, base_at = sorted(series), sorted(base)
    out: dict[datetime, Decimal] = {}
    for at in stamps:
        i, j = bisect_right(own_at, at), bisect_right(base_at, at)
        if i and j:
            out[at] = cross(series[own_at[i - 1]], base[base_at[j - 1]])
    return out


def last_at(series: dict):
    """A lookup of the series' last value at or before a date or instant (None before it)."""
    keys = sorted(series)

    def at(when) -> Decimal | None:
        i = bisect_right(keys, when)
        return series[keys[i - 1]] if i else None

    return at

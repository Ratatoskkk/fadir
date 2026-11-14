"""Price bars for any Yahoo symbol, for the Ticker view.

Each range fetches more bars than it shows. The bars before `warmup` exist so the
view's indicators (a 25-bar ADX needs about 50 bars to settle) are already valid at the
left edge of the window instead of starting blank.

Like `intraday.py`, nothing here is persisted: a small in-process cache, bounded by
entry count, keeps a polling chart from turning every poll into a Yahoo round trip.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.providers import yf_client


@dataclass(frozen=True)
class ChartRange:
    interval: str
    period: str
    #: Shown window: the last `sessions` trading days, or the last `days` calendar days.
    sessions: int | None = None
    days: int | None = None
    ttl_seconds: int = 15


RANGES: dict[str, ChartRange] = {
    "1D": ChartRange("5m", "5d", sessions=1),
    "5D": ChartRange("15m", "1mo", sessions=5),
    "1M": ChartRange("1h", "6mo", days=31, ttl_seconds=60),
    "6M": ChartRange("1d", "2y", days=183, ttl_seconds=300),
    "1Y": ChartRange("1d", "2y", days=366, ttl_seconds=300),
    "5Y": ChartRange("1wk", "10y", days=5 * 366, ttl_seconds=900),
}

MAX_ENTRIES = 128
#: Lead-in bars kept before the window: enough for a 250-bar average or a settled
#: 25-bar ADX. A 24-hour market would otherwise ship months of hourly bars nobody sees.
MAX_WARMUP = 300


class ChartUnavailable(LookupError):
    """Yahoo returned no bars for the symbol."""


@dataclass(frozen=True)
class Chart:
    symbol: str
    range: str
    interval: str
    series: yf_client.BarSeries
    warmup: int

    def market_open(self, now: datetime) -> bool:
        start, end = self.series.session_start, self.series.session_end
        return start is not None and end is not None and start <= now < end


def first_shown(bars: list[yf_client.Bar], spec: ChartRange) -> int:
    """Index of the first bar inside the shown window."""
    if not bars:
        return 0
    if spec.sessions is not None:
        # Bars carry the exchange's own zone, so a local date is one trading session.
        days = sorted({b.at.date() for b in bars})[-spec.sessions :]
        first_day = days[0]
        return next(i for i, b in enumerate(bars) if b.at.date() >= first_day)
    cutoff = bars[-1].at - timedelta(days=spec.days or 0)
    return next(i for i, b in enumerate(bars) if b.at >= cutoff)


_cache: OrderedDict[tuple[str, str], tuple[float, Chart]] = OrderedDict()
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def chart(symbol: str, range_key: str) -> Chart:
    spec = RANGES[range_key]
    key = (symbol, range_key)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is not None and now - hit[0] < spec.ttl_seconds:
            _cache.move_to_end(key)
            return hit[1]

    series = yf_client.fetch_bars(symbol, spec.interval, spec.period)
    if series is None:
        if hit is not None:
            return hit[1]  # a slightly old chart beats an error mid-poll
        raise ChartUnavailable(f"no price data for {symbol}")

    shown = first_shown(series.bars, spec)
    lead = min(shown, MAX_WARMUP)
    result = Chart(
        symbol=symbol,
        range=range_key,
        interval=spec.interval,
        series=replace(series, bars=series.bars[shown - lead :]),
        warmup=lead,
    )
    with _lock:
        _cache[key] = (now, result)
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
    return result

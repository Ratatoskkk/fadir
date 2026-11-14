"""Price bars for any Yahoo symbol, for the Ticker view.

Each request fetches more bars than it shows. The shown bars are `segments`, index
ranges into the bars; the bars before each segment exist so the view's indicators (a
25-bar ADX needs about 50 bars to settle) are already valid where a segment starts
instead of starting blank. A fixed range has one segment. A week selection has one per
run of consecutive selected weeks, and bars in long gaps between them are dropped down
to a lead-in for the next segment.

Like `intraday.py`, nothing here is persisted: a small in-process cache, bounded by
entry count, keeps a polling chart from turning every poll into a Yahoo round trip.
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

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
#: Lead-in bars kept before a segment: enough for a 250-bar average or a settled
#: 25-bar ADX. A 24-hour market would otherwise ship months of hourly bars nobody sees.
MAX_WARMUP = 300

MAX_WEEKS = 20
WEEK_PATTERN = re.compile(r"(\d{4})-W(\d{2})")
#: Week bars by how far back the earliest selected week starts. Yahoo serves 15-minute
#: bars for about 60 days and hourly bars for about 730; older weeks fall back to days.
#: Each row: (oldest week age in days, interval, lead-in calendar days, Yahoo's limit).
WEEK_INTERVALS = (
    (45, "15m", 20, 58),
    (690, "1h", 60, 728),
    (None, "1d", 450, None),
)
#: A week that is over cannot change, so it is cached far longer than a live window.
PAST_WEEKS_TTL_SECONDS = 3600

Segment = tuple[int, int]


class ChartUnavailable(LookupError):
    """Yahoo returned no bars for the symbol."""


class InvalidWeeks(ValueError):
    """The week selection is malformed, empty, too long, or in the future."""


@dataclass(frozen=True)
class Chart:
    symbol: str
    range: str
    interval: str
    series: yf_client.BarSeries
    #: Shown bars, as [start, end) index ranges into `series.bars`, in time order.
    segments: tuple[Segment, ...]
    #: False when the shown window is entirely in the past (a finished week), so the
    #: chart is not live even while the exchange trades.
    reaches_now: bool = True

    @property
    def warmup(self) -> int:
        return self.segments[0][0]

    def market_open(self, now: datetime) -> bool:
        start, end = self.series.session_start, self.series.session_end
        in_session = start is not None and end is not None and start <= now < end
        return in_session and self.reaches_now


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


def parse_weeks(values: list[str], today: date) -> list[tuple[int, int]]:
    """ISO weeks like "2026-W03", sorted and deduplicated. Rejects future weeks."""
    weeks: set[tuple[int, int]] = set()
    for value in values:
        match = WEEK_PATTERN.fullmatch(value.strip().upper())
        if match is None:
            raise InvalidWeeks(f"invalid week {value!r}")
        year, week = int(match[1]), int(match[2])
        try:
            monday = date.fromisocalendar(year, week, 1)
        except ValueError as exc:  # week 53 in a 52-week year, week 0, ...
            raise InvalidWeeks(f"invalid week {value!r}") from exc
        if monday > today:
            raise InvalidWeeks(f"week {value} has not started")
        weeks.add((year, week))
    if not weeks:
        raise InvalidWeeks("no week selected")
    if len(weeks) > MAX_WEEKS:
        raise InvalidWeeks(f"select at most {MAX_WEEKS} weeks")
    return sorted(weeks)


def week_interval(first_monday: date, today: date) -> tuple[str, date]:
    """The bar interval for weeks starting at `first_monday`, and where to start fetching."""
    age = (today - first_monday).days
    for max_age, interval, lead_days, limit_days in WEEK_INTERVALS:
        if max_age is None or age <= max_age:
            start = first_monday - timedelta(days=lead_days)
            if limit_days is not None:
                start = max(start, today - timedelta(days=limit_days))
            return interval, start
    raise AssertionError("unreachable: the last row has no age limit")


def week_segments(bars: list[yf_client.Bar], weeks: list[tuple[int, int]]) -> list[Segment]:
    """Index ranges of bars inside the selected weeks, by the exchange's local calendar."""
    wanted = set(weeks)
    segments: list[Segment] = []
    for i, bar in enumerate(bars):
        iso = bar.at.isocalendar()
        if (iso[0], iso[1]) not in wanted:
            continue
        if segments and segments[-1][1] == i:
            segments[-1] = (segments[-1][0], i + 1)
        else:
            segments.append((i, i + 1))
    return segments


def trim_lead_in(bars: list[yf_client.Bar], segments: list[Segment]) -> tuple[list[yf_client.Bar], tuple[Segment, ...]]:
    """Keep each segment and at most MAX_WARMUP bars before it; drop the rest.

    Dropping the middle of a long gap leaves a jump in the series, but it sits at least
    MAX_WARMUP bars before the next segment, beyond the reach of any indicator window,
    and a Wilder average has forgotten it by then.
    """
    kept: list[yf_client.Bar] = []
    out: list[Segment] = []
    covered = 0
    for start, end in segments:
        lead_from = max(covered, start - MAX_WARMUP)
        kept.extend(bars[lead_from:end])
        out.append((len(kept) - (end - start), len(kept)))
        covered = end
    return kept, tuple(out)


_cache: OrderedDict[tuple[str, str], tuple[float, Chart]] = OrderedDict()
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _cached(key: tuple[str, str], ttl_seconds: int) -> tuple[Chart | None, Chart | None]:
    """(fresh hit, any hit). The stale hit stands in when Yahoo fails mid-poll."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is None:
            return None, None
        _cache.move_to_end(key)
        return (hit[1] if now - hit[0] < ttl_seconds else None), hit[1]


def _store(key: tuple[str, str], result: Chart) -> Chart:
    with _lock:
        _cache[key] = (time.monotonic(), result)
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
    return result


def chart(symbol: str, range_key: str) -> Chart:
    spec = RANGES[range_key]
    key = (symbol, range_key)
    fresh, stale = _cached(key, spec.ttl_seconds)
    if fresh is not None:
        return fresh

    series = yf_client.fetch_bars(symbol, spec.interval, period=spec.period)
    if series is None:
        if stale is not None:
            return stale  # a slightly old chart beats an error mid-poll
        raise ChartUnavailable(f"no price data for {symbol}")

    shown = first_shown(series.bars, spec)
    lead = min(shown, MAX_WARMUP)
    bars = series.bars[shown - lead :]
    return _store(key, Chart(
        symbol=symbol,
        range=range_key,
        interval=spec.interval,
        series=replace(series, bars=bars),
        segments=((lead, len(bars)),),
    ))


def week_chart(symbol: str, weeks: list[tuple[int, int]], today: date) -> Chart:
    """Bars for the selected ISO weeks (from `parse_weeks`), one segment per run of weeks."""
    first_monday = date.fromisocalendar(*weeks[0], 1)
    last_sunday = date.fromisocalendar(*weeks[-1], 7)
    reaches_now = last_sunday >= today
    key = (symbol, "W:" + ",".join(f"{y}-W{w:02d}" for y, w in weeks))
    ttl = RANGES["5D"].ttl_seconds if reaches_now else PAST_WEEKS_TTL_SECONDS
    fresh, stale = _cached(key, ttl)
    if fresh is not None:
        return fresh

    interval, start = week_interval(first_monday, today)
    # Yahoo's `end` is exclusive; one day past the selection's Sunday (or today).
    end = min(last_sunday, today) + timedelta(days=1)
    series = yf_client.fetch_bars(symbol, interval, start=start, end=end)
    if series is None:
        if stale is not None:
            return stale
        raise ChartUnavailable(f"no price data for {symbol}")
    segments = week_segments(series.bars, weeks)
    if not segments:
        raise ChartUnavailable(f"no {symbol} trading in the selected weeks")

    bars, trimmed = trim_lead_in(series.bars, segments)
    return _store(key, Chart(
        symbol=symbol,
        range="W",
        interval=interval,
        series=replace(series, bars=bars),
        segments=trimmed,
        reaches_now=reaches_now,
    ))

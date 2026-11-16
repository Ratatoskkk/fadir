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
from datetime import date, datetime, time as day_time, timedelta

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
    # The live ranges are cached no longer than the shortest poll (5s), so every poll can
    # move the line.
    "1D": ChartRange("5m", "5d", sessions=1, ttl_seconds=5),
    "5D": ChartRange("15m", "1mo", sessions=5, ttl_seconds=5),
    "1M": ChartRange("1h", "6mo", days=31, ttl_seconds=60),
    "6M": ChartRange("1d", "2y", days=183, ttl_seconds=300),
    "1Y": ChartRange("1d", "2y", days=366, ttl_seconds=300),
    "5Y": ChartRange("1wk", "10y", days=5 * 366, ttl_seconds=900),
}

MAX_ENTRIES = 128
#: Week selections are open-ended, so they get their own share of the cache and can
#: never push the live ranges out.
MAX_WEEK_ENTRIES = 32
#: After Yahoo fails for a chart, it is not asked again for this long; the last good
#: chart (or the error) stands in, so polls from every viewer don't pile onto Yahoo.
FAILURE_BACKOFF_SECONDS = 30
#: A cached chart older than this is not served in place of a failed fetch.
MAX_STALE_SECONDS = 6 * 3600
#: The official previous close (closing auction included) comes from daily bars, which
#: change once a day, so they are cached far longer than the 1D chart itself.
PREV_CLOSE_TTL_SECONDS = 300
#: Lead-in bars kept before a segment: enough for a 250-bar average or a settled
#: 25-bar ADX. A 24-hour market would otherwise ship months of hourly bars nobody sees.
MAX_WARMUP = 300

#: A typed From–To range can span a whole year; consecutive weeks are one segment.
MAX_WEEKS = 53
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
    #: 1D only: the previous session's official close (Yahoo's daily bar), which the
    #: last 5-minute bar can miss by the closing auction. None when unavailable.
    previous_close: float | None = None

    @property
    def warmup(self) -> int:
        return self.segments[0][0]

    def day_session(self) -> tuple[datetime, datetime] | None:
        """The shown trading day, open to close, for a 1D chart: from the pre-market open
        to the after-hours close where the listing trades outside its regular session.

        Yahoo reports the current session, which after the close can already be the next
        day's; its hours are moved onto the shown bars' local date. None when Yahoo gives
        no session or the chart is not 1D.
        """
        start = self.series.extended_start or self.series.session_start
        end = self.series.extended_end or self.series.session_end
        bars = self.series.bars
        if self.range != "1D" or start is None or end is None or not bars:
            return None
        last = bars[-1].at
        zone = last.tzinfo
        length = end - start
        if not timedelta(0) < length <= timedelta(days=1):
            return None
        opens = datetime.combine(last.date(), start.astimezone(zone).time(), tzinfo=zone)
        if opens > last:
            # The session opened the evening before (futures, some FX): its open is on
            # the previous local date.
            opens = datetime.combine(last.date() - timedelta(days=1), start.astimezone(zone).time(), tzinfo=zone)
        first = bars[self.warmup].at if self.warmup < len(bars) else last
        return min(opens, first), max(opens + length, last)

    def market_open(self, now: datetime) -> bool:
        start, end = self.series.session_start, self.series.session_end
        in_session = start is not None and end is not None and start <= now < end
        return in_session and self.reaches_now

    def extended_session(self, now: datetime) -> str | None:
        """"pre" or "post" while the listing trades before or after its regular session."""
        s = self.series
        if not self.reaches_now or None in (s.extended_start, s.extended_end, s.session_start, s.session_end):
            return None
        if s.extended_start <= now < s.session_start:
            return "pre"
        if s.session_end <= now < s.extended_end:
            return "post"
        return None


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


def follow_quote(series: yf_client.BarSeries) -> list[yf_client.Bar]:
    """The bars with the newest regular one ending at Yahoo's latest quote.

    The quote moves with every trade, while the newest bar's close can lag it, and after
    the close the quote includes the closing auction the bars miss. Only a bar inside the
    reported session follows it, so a quote never lands on a past day's bar. The quote is
    the regular session's, so pre-market and after-hours bars keep their own closes.
    """
    bars, price = series.bars, series.price
    start, end = series.session_start, series.session_end
    at = next((i for i in range(len(bars) - 1, -1, -1) if bars[i].extended is None), None)
    if at is None or price is None or start is None or end is None:
        return bars
    last = bars[at]
    # An intraday bar inside the session, or a daily bar (stamped at local midnight) for
    # the session's own date. Weekly bars and past days never follow the quote.
    zone = last.at.tzinfo
    daily_today = last.at.time() == day_time(0) and last.at.date() == start.astimezone(zone).date()
    if not (start <= last.at < end or daily_today):
        return bars
    followed = replace(last, close=price, high=max(last.high, price), low=min(last.low, price))
    return [*bars[:at], followed, *bars[at + 1 :]]


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


_cache: OrderedDict[tuple[str, str], tuple[float, object]] = OrderedDict()
_lock = threading.Lock()
#: When Yahoo last failed for a key, for the back-off.
_failed: dict[tuple[str, str], float] = {}
#: One fetch per key at a time: concurrent polls of a chart wait for it and reuse it.
_key_locks: dict[tuple[str, str], threading.Lock] = {}


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _failed.clear()
        _key_locks.clear()


def _cached(key: tuple[str, str], ttl_seconds: int):
    """(fresh hit, a stale hit still young enough to stand in for a failed fetch)."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is None:
            return None, None
        _cache.move_to_end(key)
        age = now - hit[0]
        return (hit[1] if age < ttl_seconds else None), (hit[1] if age < MAX_STALE_SECONDS else None)


def _store(key: tuple[str, str], result):
    with _lock:
        _cache[key] = (time.monotonic(), result)
        _cache.move_to_end(key)
        weeks = [k for k in _cache if k[1].startswith("W:")]
        for old in weeks[: max(0, len(weeks) - MAX_WEEK_ENTRIES)]:
            del _cache[old]
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
        for k in [k for k in _key_locks if k not in _cache]:
            if not _key_locks[k].locked():
                del _key_locks[k]
    return result


def _through_cache(key: tuple[str, str], ttl_seconds: int, build):
    """The cached value for `key`, or `build()`'s, fetching at most once at a time.

    `build` returns None when Yahoo fails; the last good value stands in (up to
    MAX_STALE_SECONDS old), else ChartUnavailable. After a failure Yahoo is not asked
    again for FAILURE_BACKOFF_SECONDS.
    """
    fresh, stale = _cached(key, ttl_seconds)
    if fresh is not None:
        return fresh
    with _lock:
        key_lock = _key_locks.setdefault(key, threading.Lock())
    with key_lock:
        fresh, stale = _cached(key, ttl_seconds)  # another request may have just fetched
        if fresh is not None:
            return fresh
        with _lock:
            failed_at = _failed.get(key)
        if failed_at is not None and time.monotonic() - failed_at < FAILURE_BACKOFF_SECONDS:
            if stale is not None:
                return stale
            raise ChartUnavailable(f"no price data for {key[0]}")
        result = build()
        with _lock:
            if result is None:
                _failed[key] = time.monotonic()
            else:
                _failed.pop(key, None)
        if result is None:
            if stale is not None:
                return stale  # a slightly old chart beats an error mid-poll
            raise ChartUnavailable(f"no price data for {key[0]}")
        return _store(key, result)


def previous_close(symbol: str, day: date) -> float | None:
    """The official close of the last session before `day`, from Yahoo's daily bars."""
    def build():
        series = yf_client.fetch_bars(symbol, "1d", period="5d")
        return None if series is None else tuple((b.at.date(), b.close) for b in series.bars)

    try:
        closes = _through_cache((symbol, "prev-close"), PREV_CLOSE_TTL_SECONDS, build)
    except ChartUnavailable:
        return None
    before = [close for on, close in closes if on < day]
    return before[-1] if before else None


def intraday(interval: str) -> bool:
    """Minute and hour bars, the ones that can hold pre-market and after-hours trading."""
    return interval.endswith(("m", "h"))


def chart(symbol: str, range_key: str) -> Chart:
    spec = RANGES[range_key]

    def build() -> Chart | None:
        series = yf_client.fetch_bars(symbol, spec.interval, period=spec.period, prepost=intraday(spec.interval))
        if series is None:
            return None
        shown = first_shown(series.bars, spec)
        lead = min(shown, MAX_WARMUP)
        bars = follow_quote(series)[shown - lead :]
        return Chart(
            symbol=symbol,
            range=range_key,
            interval=spec.interval,
            series=replace(series, bars=bars),
            segments=((lead, len(bars)),),
            previous_close=previous_close(symbol, bars[-1].at.date()) if range_key == "1D" else None,
        )

    return _through_cache((symbol, range_key), spec.ttl_seconds, build)


def week_chart(symbol: str, weeks: list[tuple[int, int]], today: date) -> Chart:
    """Bars for the selected ISO weeks (from `parse_weeks`), one segment per run of weeks."""
    first_monday = date.fromisocalendar(*weeks[0], 1)
    last_sunday = date.fromisocalendar(*weeks[-1], 7)
    reaches_now = last_sunday >= today
    key = (symbol, "W:" + ",".join(f"{y}-W{w:02d}" for y, w in weeks))
    ttl = RANGES["5D"].ttl_seconds if reaches_now else PAST_WEEKS_TTL_SECONDS
    interval, start = week_interval(first_monday, today)
    # Yahoo's `end` is exclusive; one day past the selection's Sunday (or today).
    end = min(last_sunday, today) + timedelta(days=1)

    def build() -> Chart | None:
        series = yf_client.fetch_bars(symbol, interval, start=start, end=end, prepost=intraday(interval))
        if series is None:
            return None
        segments = week_segments(series.bars, weeks)
        if not segments:
            raise ChartUnavailable(f"no {symbol} trading in the selected weeks")
        # A selection that runs to today ends at the latest quote, like a live range.
        source = follow_quote(series) if reaches_now else series.bars
        bars, trimmed = trim_lead_in(source, segments)
        return Chart(
            symbol=symbol,
            range="W",
            interval=interval,
            series=replace(series, bars=bars),
            segments=trimmed,
            reaches_now=reaches_now,
        )

    return _through_cache(key, ttl, build)

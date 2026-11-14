"""The Ticker view's bars: window selection, caching and the /api/market routes. Offline."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.providers import market_chart, yf_client
from tests.test_api import client  # noqa: F401 - fixture

NY = ZoneInfo("America/New_York")


def _bars(start: datetime, count: int, step: timedelta) -> list[yf_client.Bar]:
    return [
        yf_client.Bar(at=start + i * step, open=10 + i, high=11 + i, low=9 + i, close=10.5 + i)
        for i in range(count)
    ]


def _series(bars, *, price=None, session=None) -> yf_client.BarSeries:
    start, end = session or (None, None)
    return yf_client.BarSeries(
        bars=bars, name="Apple Inc.", currency="USD", exchange="NMS",
        session_start=start, session_end=end, price=price,
    )


@pytest.fixture(autouse=True)
def _fresh_cache():
    market_chart.clear_cache()
    yield
    market_chart.clear_cache()


def test_session_window_starts_at_the_last_local_trading_day():
    """Bars are grouped by the exchange's own date, so one session is one local day."""
    days = [datetime(2026, 11, d, 9, 30, tzinfo=NY) for d in (11, 12, 13)]
    bars = [b for day in days for b in _bars(day, 4, timedelta(minutes=5))]
    assert market_chart.first_shown(bars, market_chart.RANGES["1D"]) == 8
    assert market_chart.first_shown(bars, market_chart.RANGES["5D"]) == 0


def test_day_window_counts_back_from_the_last_bar():
    bars = _bars(datetime(2026, 1, 1, tzinfo=NY), 400, timedelta(days=1))
    shown = market_chart.first_shown(bars, market_chart.RANGES["6M"])
    assert bars[-1].at - bars[shown].at <= timedelta(days=183)
    assert bars[-1].at - bars[shown - 1].at > timedelta(days=183)


def test_lead_in_is_capped(monkeypatch):
    bars = _bars(datetime(2020, 1, 1, tzinfo=NY), 2000, timedelta(hours=1))
    monkeypatch.setattr(yf_client, "fetch_bars", lambda *a, **k: _series(bars))
    result = market_chart.chart("BTC-USD", "1M")
    assert result.warmup == market_chart.MAX_WARMUP
    assert result.series.bars[-1] == bars[-1]


def test_chart_is_cached_and_a_failed_refetch_keeps_the_last_bars(monkeypatch):
    calls = []
    bars = _bars(datetime(2026, 11, 13, 9, 30, tzinfo=NY), 10, timedelta(minutes=5))

    def fetch(*args, **kwargs):
        calls.append(args)
        return _series(bars) if len(calls) == 1 else None

    clock = [1e9]
    monkeypatch.setattr(market_chart.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(yf_client, "fetch_bars", fetch)
    first = market_chart.chart("AAPL", "1D")
    assert market_chart.chart("AAPL", "1D") is first
    assert len(calls) == 1

    clock[0] += 3600
    assert market_chart.chart("AAPL", "1D") is first
    assert len(calls) == 2


def test_unknown_symbol_is_404_and_bad_input_is_422(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(yf_client, "fetch_bars", lambda *a, **k: None)
    assert client.get("/api/market/chart", params={"symbol": "NOPE"}).status_code == 404
    assert client.get("/api/market/chart", params={"symbol": "A B"}).status_code == 422
    assert client.get("/api/market/chart", params={"symbol": "AAPL", "range": "2D"}).status_code == 422


def test_chart_route_returns_bars_in_utc_with_the_session_state(client, monkeypatch):  # noqa: F811
    bars = _bars(datetime(2026, 11, 13, 9, 30, tzinfo=NY), 10, timedelta(minutes=5))
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        yf_client, "fetch_bars",
        lambda *a, **k: _series(bars, session=(now - timedelta(hours=1), now + timedelta(hours=1))),
    )
    body = client.get("/api/market/chart", params={"symbol": "aapl", "range": "1D"}).json()
    assert (body["symbol"], body["exchange"], body["interval"], body["market_open"]) == ("AAPL", "NASDAQ", "5m", True)
    assert body["price"] == bars[-1].close  # no quote from Yahoo: the last close stands in
    assert body["warmup"] == 0
    assert body["bars"][0]["at"].startswith("2026-11-13T14:30:00")
    assert body["bars"][0]["high"] == 11


def test_market_search_also_finds_indices_and_futures(client, monkeypatch):  # noqa: F811
    quotes = [
        {"symbol": "^GSPC", "shortname": "S&P 500", "exchange": "SNP", "quoteType": "INDEX"},
        {"symbol": "ES=F", "shortname": "E-Mini S&P 500", "exchange": "CME", "quoteType": "FUTURE"},
        {"symbol": "SPY", "longname": "SPDR S&P 500 ETF", "exchange": "PCX", "quoteType": "ETF"},
        {"symbol": "SPX-OPT", "shortname": "an option", "exchange": "OPR", "quoteType": "OPTION"},
    ]

    class FakeSearch:
        def __init__(self, *a, **k):
            self.quotes = quotes

    monkeypatch.setattr(yf_client.yf, "Search", FakeSearch)
    yf_client._search_cache.clear()
    market = [r["yf_symbol"] for r in client.get("/api/market/search", params={"q": "s&p"}).json()]
    holdable = [r["yf_symbol"] for r in client.get("/api/instruments/search", params={"q": "s&p"}).json()]
    assert market == ["^GSPC", "ES=F", "SPY"]
    assert holdable == ["SPY"]


# -- week selection ----------------------------------------------------------------------

TODAY = datetime(2026, 11, 14).date()


def test_weeks_are_parsed_sorted_and_deduplicated():
    assert market_chart.parse_weeks(["2026-w05", "2026-W03", "2026-W05"], TODAY) == [(2026, 3), (2026, 5)]


@pytest.mark.parametrize("values", [[], ["2026-3"], ["2025-W53"], ["2026-W47"], [f"{y}-W{w:02d}" for y in (2024, 2025) for w in range(1, 28)]])
def test_bad_week_selections_are_rejected(values):
    """Malformed, a week 53 the year lacks, not started yet, or more than MAX_WEEKS."""
    with pytest.raises(market_chart.InvalidWeeks):
        market_chart.parse_weeks(values, TODAY)


def test_week_interval_follows_yahoo_retention():
    assert market_chart.week_interval(TODAY - timedelta(days=12), TODAY)[0] == "15m"
    assert market_chart.week_interval(TODAY - timedelta(days=200), TODAY)[0] == "1h"
    assert market_chart.week_interval(TODAY - timedelta(days=900), TODAY)[0] == "1d"
    # The lead-in never asks Yahoo for 15-minute bars older than it keeps.
    _, start = market_chart.week_interval(TODAY - timedelta(days=44), TODAY)
    assert start >= TODAY - timedelta(days=58)


def _hourly(start: datetime, days: int) -> list[yf_client.Bar]:
    return _bars(start, days * 24, timedelta(hours=1))


def test_segments_follow_the_exchange_calendar_and_merge_adjacent_weeks():
    bars = _hourly(datetime(2026, 1, 5, tzinfo=NY), 35)  # Mon 2026-W02 through W06
    segments = market_chart.week_segments(bars, [(2026, 3), (2026, 4), (2026, 6)])
    assert len(segments) == 2
    (a, b), (c, d) = segments
    assert bars[a].at.isocalendar()[1] == 3 and bars[b - 1].at.isocalendar()[1] == 4
    assert {bars[i].at.isocalendar()[1] for i in range(c, d)} == {6}


def test_long_gaps_keep_only_a_lead_in_before_each_segment():
    bars = _hourly(datetime(2026, 1, 5, tzinfo=NY), 70)
    segments = market_chart.week_segments(bars, [(2026, 2), (2026, 11)])
    kept, trimmed = market_chart.trim_lead_in(bars, segments)
    (a, b), (c, d) = trimmed
    assert a == 0  # nothing before the first week was fetched in this fixture
    assert c - b == market_chart.MAX_WARMUP
    assert [x.at for x in kept[c:d]] == [x.at for x in bars[segments[1][0]:segments[1][1]]]


def test_week_route_returns_segments_and_is_not_live_for_a_past_week(client, monkeypatch):  # noqa: F811
    year, week, _ = (date.today() - timedelta(days=7)).isocalendar()
    monday = datetime.combine(date.fromisocalendar(year, week, 1), datetime.min.time(), tzinfo=NY)
    bars = _hourly(monday - timedelta(days=14), 21)
    now = datetime.now(timezone.utc)
    asked = {}

    def fetch(symbol, interval, period=None, *, start=None, end=None):
        asked.update(interval=interval, start=start, end=end)
        return _series(bars, session=(now - timedelta(hours=1), now + timedelta(hours=1)))

    monkeypatch.setattr(yf_client, "fetch_bars", fetch)
    r = client.get("/api/market/chart", params={"symbol": "AAPL", "range": "W", "week": f"{year}-W{week:02d}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["range"] == "W" and asked["interval"] == "15m"
    [[start, end]] = body["segments"]
    assert end - start == 7 * 24 and body["warmup"] == start
    assert body["market_open"] is False  # the exchange trades, but the week is over


def test_week_route_rejects_a_future_week(client):  # noqa: F811
    r = client.get("/api/market/chart", params={"symbol": "AAPL", "range": "W", "week": "2099-W01"})
    assert r.status_code == 422

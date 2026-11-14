"""The Ticker view's bars: window selection, caching and the /api/market routes. Offline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    monkeypatch.setattr(yf_client, "fetch_bars", lambda *a: _series(bars))
    result = market_chart.chart("BTC-USD", "1M")
    assert result.warmup == market_chart.MAX_WARMUP
    assert result.series.bars[-1] == bars[-1]


def test_chart_is_cached_and_a_failed_refetch_keeps_the_last_bars(monkeypatch):
    calls = []
    bars = _bars(datetime(2026, 11, 13, 9, 30, tzinfo=NY), 10, timedelta(minutes=5))

    def fetch(*args):
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
    monkeypatch.setattr(yf_client, "fetch_bars", lambda *a: None)
    assert client.get("/api/market/chart", params={"symbol": "NOPE"}).status_code == 404
    assert client.get("/api/market/chart", params={"symbol": "A B"}).status_code == 422
    assert client.get("/api/market/chart", params={"symbol": "AAPL", "range": "2D"}).status_code == 422


def test_chart_route_returns_bars_in_utc_with_the_session_state(client, monkeypatch):  # noqa: F811
    bars = _bars(datetime(2026, 11, 13, 9, 30, tzinfo=NY), 10, timedelta(minutes=5))
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        yf_client, "fetch_bars",
        lambda *a: _series(bars, session=(now - timedelta(hours=1), now + timedelta(hours=1))),
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

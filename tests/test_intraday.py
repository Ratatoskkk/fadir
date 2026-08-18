"""Intraday series (the 1G view) — app/calc/intraday.py and the cache in providers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.calc.history import PositionHistoryInput
from app.calc.intraday import _Stepper, build_grid, build_intraday_series
from app.calc.tax import TaxConfig
from app.calc.types import Side
from tests.conftest import txn

UTC = timezone.utc


def ts(hour: int, minute: int = 0, day: int = 31) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=UTC)


def _positions():
    return [
        PositionHistoryInput(
            "AAPL",
            "USD",
            [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00")],
        )
    ]


# -- the last-known-value stepper ----------------------------------------------------


def test_stepper_returns_the_bar_at_the_instant():
    s = _Stepper({ts(9): Decimal("10"), ts(10): Decimal("11")})
    assert s.at(ts(10)) == (Decimal("11"), False)


def test_stepper_carries_the_last_bar_forward():
    """A shut market keeps its last price rather than vanishing."""
    s = _Stepper({ts(9): Decimal("10"), ts(10): Decimal("11")})
    value, carried = s.at(ts(15))
    assert value == Decimal("11")
    assert carried is True


def test_stepper_never_looks_forward():
    """Before the first bar there is no knowable price — not the next one."""
    s = _Stepper({ts(10): Decimal("11")})
    assert s.at(ts(9)) == (None, False)


def test_stepper_on_empty_series():
    assert _Stepper({}).at(ts(10)) == (None, False)


# -- the grid --------------------------------------------------------------------------


def test_grid_is_inclusive_and_evenly_spaced():
    grid = build_grid(ts(9, 0), ts(9, 20), 5)
    assert grid == [ts(9, 0), ts(9, 5), ts(9, 10), ts(9, 15), ts(9, 20)]


def test_grid_of_a_single_instant():
    assert build_grid(ts(9), ts(9), 5) == [ts(9)]


# -- the series ------------------------------------------------------------------------


def test_values_each_instant_from_its_own_bar():
    prices = {"AAPL": {ts(9): Decimal("100"), ts(10): Decimal("110")}}
    fx = {"USD": {ts(9): Decimal("40"), ts(10): Decimal("42")}}

    points = build_intraday_series(_positions(), prices, fx, [ts(9), ts(10)])

    assert points[0].value_try == Decimal("10") * Decimal("100") * Decimal("40")
    assert points[1].value_try == Decimal("10") * Decimal("110") * Decimal("42")


def test_decomposition_holds_at_every_instant():
    prices = {"AAPL": {ts(9): Decimal("100"), ts(10): Decimal("130")}}
    fx = {"USD": {ts(9): Decimal("40"), ts(10): Decimal("45")}}

    for point in build_intraday_series(_positions(), prices, fx, [ts(9), ts(10)]):
        assert point.price_effect_try + point.fx_effect_try == point.pnl_try
        assert point.value_try - point.value_constant_fx_try == point.fx_effect_try


def test_closed_market_is_carried_forward_and_flagged():
    """The four exchanges are almost never open together; the curve must not collapse."""
    prices = {"AAPL": {ts(9): Decimal("100")}}  # one bar, then the market shuts
    fx = {"USD": {ts(9): Decimal("40"), ts(14): Decimal("41")}}

    points = build_intraday_series(_positions(), prices, fx, build_grid(ts(9), ts(14), 60))

    assert points[0].carried_forward is False
    assert all(p.value_try > 0 for p in points)  # never collapses to zero
    assert points[-1].carried_forward is True
    # Still valued at the last traded price, revalued at the newer rate.
    assert points[-1].value_try == Decimal("10") * Decimal("100") * Decimal("41")


def test_instrument_with_no_bar_yet_is_reported_missing():
    prices = {"AAPL": {ts(12): Decimal("100")}}
    fx = {"USD": {ts(9): Decimal("40"), ts(12): Decimal("40")}}

    points = build_intraday_series(_positions(), prices, fx, [ts(9), ts(12)])

    assert points[0].missing == ("AAPL",)
    assert points[0].value_try == Decimal("0")
    assert points[1].missing == ()


def test_after_tax_line_sits_below_value_when_in_profit():
    prices = {"AAPL": {ts(9): Decimal("200")}}
    fx = {"USD": {ts(9): Decimal("50")}}

    point = build_intraday_series(
        _positions(), prices, fx, [ts(9)], tax_config=TaxConfig()
    )[0]

    assert point.value_after_tax_try < point.value_try
    assert point.value_try - point.value_after_tax_try > 0


def test_after_tax_equals_value_at_a_loss():
    prices = {"AAPL": {ts(9): Decimal("50")}}
    fx = {"USD": {ts(9): Decimal("35")}}

    point = build_intraday_series(
        _positions(), prices, fx, [ts(9)], tax_config=TaxConfig()
    )[0]

    assert point.pnl_try < 0
    assert point.value_after_tax_try == point.value_try


def test_after_tax_equals_value_when_tax_is_disabled():
    prices = {"AAPL": {ts(9): Decimal("200")}}
    fx = {"USD": {ts(9): Decimal("50")}}

    point = build_intraday_series(_positions(), prices, fx, [ts(9)], tax_config=None)[0]
    assert point.value_after_tax_try == point.value_try


def test_lots_bought_after_the_session_are_excluded():
    positions = [
        PositionHistoryInput(
            "AAPL",
            "USD",
            [
                txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00"),
                txn(2, "AAPL", "USD", "2026-12-01", Side.BUY, "99", "100.00", "40.00"),
            ],
        )
    ]
    prices = {"AAPL": {ts(9): Decimal("100")}}
    fx = {"USD": {ts(9): Decimal("40")}}

    point = build_intraday_series(positions, prices, fx, [ts(9)])
    # Only the 10 shares held during the session are valued.
    assert point[0].value_try == Decimal("10") * Decimal("100") * Decimal("40")


def test_empty_grid_returns_nothing():
    assert build_intraday_series(_positions(), {}, {}, []) == []


# -- the cache -------------------------------------------------------------------------


def test_intraday_cache_serves_within_ttl_and_refetches_after(monkeypatch):
    from app.providers import intraday as mod

    calls = {"n": 0}

    def fake(symbol, interval="5m", period=None):
        calls["n"] += 1
        return {ts(9): Decimal("100")}

    monkeypatch.setattr(mod.yf_client, "fetch_intraday_closes", fake)

    service = mod.IntradayService(ttl_seconds=300)
    service.prices(["AAPL"])
    service.prices(["AAPL"])
    assert calls["n"] == 1  # second read served from cache

    service.prices(["AAPL"], force=True)
    assert calls["n"] == 2  # force bypasses the TTL


def test_intraday_cache_is_bounded_by_symbol_not_by_uptime(monkeypatch):
    """Entries are replaced wholesale, so repeated refresh cannot grow the cache."""
    from app.providers import intraday as mod

    monkeypatch.setattr(
        mod.yf_client, "fetch_intraday_closes", lambda s, i="5m", p=None: {ts(9): Decimal("1")}
    )
    service = mod.IntradayService(ttl_seconds=0)
    for _ in range(50):
        service.prices(["AAPL", "IBM"])
    assert len(service._cache) == 2


def test_intraday_failure_falls_back_to_the_stale_copy(monkeypatch):
    """A slightly old curve beats no curve, and one bad symbol must not break the chart."""
    from app.providers import intraday as mod

    state = {"fail": False}

    def flaky(symbol, interval="5m", period=None):
        if state["fail"]:
            raise RuntimeError("Yahoo down")
        return {ts(9): Decimal("100")}

    monkeypatch.setattr(mod.yf_client, "fetch_intraday_closes", flaky)

    service = mod.IntradayService(ttl_seconds=0)
    assert service.prices(["AAPL"])["AAPL"]

    state["fail"] = True
    errors: list[str] = []
    assert service.prices(["AAPL"], errors=errors)["AAPL"] == {ts(9): Decimal("100")}
    assert errors


def test_intraday_errors_belong_to_the_caller_not_the_service(monkeypatch):
    """The service is shared across requests; a warning must not outlive its request.

    Accumulating errors on the instance meant one dead symbol was replayed as a warning
    to every later caller, and the list grew for the lifetime of the process.
    """
    from app.providers import intraday as mod

    monkeypatch.setattr(
        mod.yf_client,
        "fetch_intraday_closes",
        lambda s, i="5m", p=None: (_ for _ in ()).throw(RuntimeError("Yahoo down")),
    )
    service = mod.IntradayService(ttl_seconds=0)

    first: list[str] = []
    service.prices(["AAPL"], errors=first)
    assert len(first) == 1

    second: list[str] = []
    service.prices(["AAPL"], errors=second)
    assert len(second) == 1  # not 2 — the first call's error stayed with the first call


def test_triangulated_intraday_fx_matches_the_daily_route(monkeypatch):
    """docs/FINDINGS.md F-2 applies intraday too: SEK has no TRY pair at any granularity."""
    from app.providers import intraday as mod

    series = {
        "SEKUSD=X": {ts(9): Decimal("0.105"), ts(10): Decimal("0.106")},
        "USDTRY=X": {ts(9): Decimal("47.50")},  # one leg missing at 10:00
    }
    monkeypatch.setattr(
        mod.yf_client, "fetch_intraday_closes", lambda s, i="5m", p=None: series.get(s, {})
    )

    out = mod.IntradayService(ttl_seconds=300).fx(["SEK"])
    # Only the timestamp where both legs published survives — never a guessed pairing.
    assert list(out["SEK"]) == [ts(9)]
    assert out["SEK"][ts(9)] == (Decimal("0.105") * Decimal("47.50")).quantize(
        Decimal("0.00000001")
    )


def test_latest_session_bounds_picks_the_most_recent_day_with_data():
    from app.providers.intraday import latest_session_bounds

    bounds = latest_session_bounds(
        {
            "A": {ts(9, 0, day=30): Decimal("1"), ts(9, 0, day=31): Decimal("1")},
            "B": {ts(17, 0, day=31): Decimal("1")},
        }
    )
    assert bounds == (ts(9, 0, day=31), ts(17, 0, day=31))


def test_latest_session_bounds_on_no_data():
    from app.providers.intraday import latest_session_bounds

    assert latest_session_bounds({"A": {}}) is None


# -- session paging ---------------------------------------------------------------------


def test_session_bounds_page_back_through_retained_days():
    """`offset` walks back through the days Yahoo already returned in one request.

    5-minute bars come back as a ~5 day window, so the earlier sessions are in hand
    before anyone asks for them — paging back costs nothing but choosing another day.
    """
    from datetime import datetime, timedelta, timezone

    from app.providers.intraday import latest_session_bounds, session_days

    def day(offset_days: int, hour: int) -> datetime:
        return datetime(2026, 8, 5, hour, 0, tzinfo=timezone.utc) - timedelta(days=offset_days)

    series = {
        "AAPL": {
            day(0, 14): Decimal("1"), day(0, 20): Decimal("2"),
            day(1, 14): Decimal("3"), day(1, 19): Decimal("4"),
            day(3, 15): Decimal("5"),
        }
    }

    assert [d.isoformat() for d in session_days(series)] == [
        "2026-08-05", "2026-08-04", "2026-08-02",
    ]

    # offset 0 is the newest session, and the bounds span only that day.
    start, end = latest_session_bounds(series, 0)
    assert start.date().isoformat() == "2026-08-05"
    assert (start.hour, end.hour) == (14, 20)

    # offset 1 steps back one *session with data*, not one calendar day.
    start, end = latest_session_bounds(series, 1)
    assert start.date().isoformat() == "2026-08-04"
    assert (start.hour, end.hour) == (14, 19)

    # A gap in the calendar is skipped rather than returning an empty day.
    assert latest_session_bounds(series, 2)[0].date().isoformat() == "2026-08-02"

    # Past the retained window there is nothing to show, and that is not an error.
    assert latest_session_bounds(series, 3) is None
    assert latest_session_bounds(series, 99) is None

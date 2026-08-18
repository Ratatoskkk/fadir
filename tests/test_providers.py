"""Provider behaviour (SPEC §3, §8, §12).

Network is mocked throughout: `respx` for TCMB's HTTP calls, monkeypatched yfinance for
the rest. The single live test is marked and excluded from the default run.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from app.config import FxConfig, Settings, get_settings
from app.providers.base import ProviderError, RateUnavailable, UnsupportedCurrencyPair
from app.providers.fx_service import FxService
from app.providers.fx_tcmb import EVDS_BASE_URL, TcmbFxProvider
from app.providers.fx_yfinance import YFinanceFxProvider

# -- TCMB ---------------------------------------------------------------------------


def test_tcmb_raises_unsupported_for_twd():
    """SPEC §3: the load-bearing rule. No fallback, no triangulation, just a refusal."""
    provider = TcmbFxProvider(api_key="key")
    with pytest.raises(UnsupportedCurrencyPair) as exc:
        provider.series("TWD", "TRY", date(2026, 5, 4), date(2026, 5, 4))
    message = str(exc.value)
    assert "TWD" in message
    assert "does not publish" in message


def test_tcmb_twd_refusal_also_applies_to_single_rate_lookup():
    provider = TcmbFxProvider(api_key="key")
    with pytest.raises(UnsupportedCurrencyPair):
        provider.rate("TWD", "TRY", date(2026, 5, 4))


def test_tcmb_never_triangulates():
    """Even asked for a currency it lacks, it must not reach for USD."""
    provider = TcmbFxProvider(api_key="key")
    assert provider.is_triangulated("TWD") is False
    assert provider.is_triangulated("USD") is False
    with respx.mock:
        route = respx.get(url__startswith=EVDS_BASE_URL).mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        with pytest.raises(UnsupportedCurrencyPair):
            provider.series("TWD", "TRY", date(2026, 5, 1), date(2026, 5, 4))
        assert not route.called  # no request was even attempted


def test_tcmb_rejects_non_try_quote():
    provider = TcmbFxProvider(api_key="key")
    with pytest.raises(UnsupportedCurrencyPair):
        provider.series("USD", "EUR", date(2026, 5, 1), date(2026, 5, 4))


def test_tcmb_requires_an_api_key():
    provider = TcmbFxProvider(api_key=None)
    with pytest.raises(ProviderError, match="API key"):
        provider.series("USD", "TRY", date(2026, 5, 1), date(2026, 5, 4))


@respx.mock
def test_tcmb_parses_series_and_skips_nulls():
    """TCMB emits null on non-business days; those become gaps, not zeros."""
    respx.get(url__startswith=EVDS_BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"Tarih": "01-05-2026", "TP_DK_USD_S_YTL": "47.1234"},
                    {"Tarih": "02-05-2026", "TP_DK_USD_S_YTL": None},
                    {"Tarih": "04-05-2026", "TP_DK_USD_S_YTL": "47.5678"},
                ]
            },
        )
    )
    provider = TcmbFxProvider(api_key="key")
    series = provider.series("USD", "TRY", date(2026, 5, 1), date(2026, 5, 4))

    assert series == {
        date(2026, 5, 1): Decimal("47.1234"),
        date(2026, 5, 4): Decimal("47.5678"),
    }
    assert date(2026, 5, 2) not in series


@respx.mock
def test_tcmb_http_error_surfaces_as_provider_error():
    respx.get(url__startswith=EVDS_BASE_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderError):
        TcmbFxProvider(api_key="key").series("USD", "TRY", date(2026, 5, 1), date(2026, 5, 4))


# -- yfinance FX --------------------------------------------------------------------


def test_yfinance_direct_pairs_are_not_labelled_triangulated():
    provider = YFinanceFxProvider()
    assert provider.provenance("USD") == "yfinance"
    assert provider.provenance("EUR") == "yfinance"
    assert provider.is_triangulated("USD") is False


def test_yfinance_triangulated_pairs_carry_an_explicit_route_label():
    """docs/FINDINGS.md F-2: triangulation is permitted, silence is not."""
    provider = YFinanceFxProvider()
    assert provider.provenance("SEK") == "yfinance:SEKUSD=X*USDTRY=X"
    assert provider.provenance("TWD") == "yfinance:TWDUSD=X*USDTRY=X"
    assert provider.is_triangulated("SEK") is True
    assert provider.is_triangulated("TWD") is True


def test_yfinance_rejects_unknown_currency():
    with pytest.raises(UnsupportedCurrencyPair):
        YFinanceFxProvider().series("JPY", "TRY", date(2026, 5, 1), date(2026, 5, 4))


def test_yfinance_triangulation_multiplies_the_legs(monkeypatch):
    from app.providers import fx_yfinance

    legs = {
        "SEKUSD=X": {date(2026, 5, 1): Decimal("0.10516")},
        "USDTRY=X": {date(2026, 5, 1): Decimal("47.5078")},
    }
    monkeypatch.setattr(
        fx_yfinance, "fetch_close_series", lambda sym, s, e, **k: legs.get(sym, {})
    )

    series = YFinanceFxProvider().series("SEK", "TRY", date(2026, 5, 1), date(2026, 5, 1))
    expected = (Decimal("0.10516") * Decimal("47.5078")).quantize(Decimal("0.00000001"))
    assert series[date(2026, 5, 1)] == expected


def test_triangulation_skips_dates_where_one_leg_is_missing(monkeypatch):
    """A gap in one leg must produce a gap, never an invented rate."""
    from app.providers import fx_yfinance

    legs = {
        "SEKUSD=X": {date(2026, 5, 1): Decimal("0.105"), date(2026, 5, 2): Decimal("0.106")},
        "USDTRY=X": {date(2026, 5, 1): Decimal("47.50")},
    }
    monkeypatch.setattr(
        fx_yfinance, "fetch_close_series", lambda sym, s, e, **k: legs.get(sym, {})
    )

    series = YFinanceFxProvider().series("SEK", "TRY", date(2026, 5, 1), date(2026, 5, 2))
    assert list(series) == [date(2026, 5, 1)]


# -- FxService: routing and carry-forward --------------------------------------------


class StubProvider:
    """Publishes on weekdays only."""

    name = "stub"

    def __init__(self, rate: str = "40.0"):
        self.rate_value = Decimal(rate)
        self.calls: list[tuple] = []

    def provenance(self, base):
        return self.name

    def is_triangulated(self, base):
        return False

    def rate(self, base, quote, on):
        return self.series(base, quote, on, on)[on]

    def series(self, base, quote, start, end):
        self.calls.append((base, start, end))
        out, day = {}, start
        while day <= end:
            if day.weekday() < 5:
                out[day] = self.rate_value
            day += timedelta(days=1)
        return out


def _settings_with(overrides: dict[str, str], lookback: int = 7) -> Settings:
    base = get_settings()
    return Settings(
        fx=FxConfig(
            default_provider="yfinance", overrides=overrides, max_lookback_days=lookback
        ),
        liquidation=base.liquidation,
        cache=base.cache,
        refresh=base.refresh,
        history=base.history,
        db_path=base.db_path,
    )


def test_sunday_trade_uses_friday_rate_and_records_the_date(session):
    """SPEC §3: most recent prior published rate, never interpolated forward."""
    service = FxService(session, _settings_with({}), providers={"yfinance": StubProvider()})
    sunday = date(2026, 3, 29)
    quote = service.quote("USD", sunday)

    assert quote.rate == Decimal("40.0")
    assert quote.rate_date == date(2026, 3, 27)  # Friday
    assert quote.carried_forward is True
    assert quote.days_carried == 2


def test_weekday_trade_is_not_carried_forward(session):
    service = FxService(session, _settings_with({}), providers={"yfinance": StubProvider()})
    quote = service.quote("USD", date(2026, 4, 15))  # Wednesday
    assert quote.carried_forward is False
    assert quote.rate_date == date(2026, 4, 15)


def test_carry_forward_fails_loudly_past_the_lookback_window(session):
    """Never interpolate, never average — raise instead."""

    class NeverPublishes(StubProvider):
        def series(self, base, quote, start, end):
            return {}

    service = FxService(
        session, _settings_with({}), providers={"yfinance": NeverPublishes()}
    )
    with pytest.raises(RateUnavailable) as exc:
        service.quote("USD", date(2026, 4, 15))
    assert "Refusing to interpolate" in str(exc.value)


def test_lookback_window_is_configurable(session):
    class OnlyOneDay(StubProvider):
        def series(self, base, quote, start, end):
            day = date(2026, 4, 1)
            return {day: Decimal("40.0")} if start <= day <= end else {}

    service = FxService(
        session, _settings_with({}, lookback=3), providers={"yfinance": OnlyOneDay()}
    )
    # Three days later is inside the window.
    assert service.quote("USD", date(2026, 4, 4)).rate_date == date(2026, 4, 1)
    # Ten days later is not.
    with pytest.raises(RateUnavailable):
        service.quote("USD", date(2026, 4, 11))


def test_per_currency_provider_routing(session):
    """SPEC §3: config resolves TCMB's TWD gap by routing that currency elsewhere."""
    yf_stub, tcmb_stub = StubProvider("40.0"), StubProvider("41.0")
    settings = _settings_with({"USD": "tcmb", "EUR": "tcmb", "SEK": "tcmb"})
    service = FxService(session, settings, providers={"yfinance": yf_stub, "tcmb": tcmb_stub})

    assert service.provider_for("USD") is tcmb_stub
    assert service.provider_for("SEK") is tcmb_stub
    # TWD is absent from the overrides, so it falls to the default provider.
    assert service.provider_for("TWD") is yf_stub


def test_unregistered_provider_name_raises(session):
    settings = _settings_with({"USD": "nope"})
    service = FxService(session, settings, providers={"yfinance": StubProvider()})
    with pytest.raises(ProviderError, match="not registered"):
        service.provider_for("USD")


def test_historical_rates_are_cached_permanently(session):
    """SPEC §8: a settled rate is fetched once."""
    stub = StubProvider()
    service = FxService(session, _settings_with({}), providers={"yfinance": stub})

    service.quote("USD", date(2026, 4, 15))
    calls_after_first = len(stub.calls)
    service.quote("USD", date(2026, 4, 15))
    assert len(stub.calls) == calls_after_first  # served from cache


def test_try_to_try_is_identity(session):
    service = FxService(session, _settings_with({}), providers={"yfinance": StubProvider()})
    quote = service.quote("TRY", date(2026, 4, 15))
    assert quote.rate == Decimal("1")
    assert quote.provider == "identity"


def test_current_rate_ttl_survives_a_market_that_published_nothing_today(session):
    """The TTL must measure when we last *asked*, not when the rate was last published.

    Every weekend and every holiday, the newest published rate predates today. If
    staleness is read off that row's `fetched_at` and the row is never re-stamped, the
    cache looks permanently expired: `current()` refetches on every call, and since
    `build_view` resolves a rate per position, one page load turns into one Yahoo round
    trip per position. This pins the fix.
    """
    from app.models import FxCache

    yesterday = date.today() - timedelta(days=1)

    class ClosedSinceYesterday(StubProvider):
        """Publishes nothing on or after today — a weekend, seen from Saturday."""

        def series(self, base, quote, start, end):
            self.calls.append((base, start, end))
            out, day = {}, start
            while day <= min(end, yesterday):
                out[day] = self.rate_value
                day += timedelta(days=1)
            return out

    stub = ClosedSinceYesterday()
    service = FxService(session, _settings_with({}), providers={"yfinance": stub})

    # A rate published yesterday and fetched an hour ago — i.e. genuinely past the TTL,
    # with nothing newer for the provider to return. The Saturday-morning situation.
    session.add(
        FxCache(
            base="USD",
            quote="TRY",
            rate_date=yesterday,
            rate=Decimal("40.0"),
            provider="stub",
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
        )
    )
    session.flush()

    service.current("USD")
    after_first = len(stub.calls)
    assert after_first >= 1  # the stale row is refreshed once, as it should be

    service.current("USD")
    assert len(stub.calls) == after_first, (
        "second call within the TTL refetched; the provider is being asked for the same "
        "rate on every single request"
    )


def test_series_fills_every_calendar_day_via_carry_forward(session):
    service = FxService(session, _settings_with({}), providers={"yfinance": StubProvider()})
    series = service.series("USD", date(2026, 4, 13), date(2026, 4, 19))  # Mon..Sun

    assert len(series) == 7
    assert series[date(2026, 4, 18)].carried_forward is True  # Saturday
    assert series[date(2026, 4, 18)].rate_date == date(2026, 4, 17)  # Friday
    assert series[date(2026, 4, 13)].carried_forward is False


# -- market hours --------------------------------------------------------------------


def test_market_hours_across_the_four_exchanges():
    """SPEC §8: don't present a Taipei close as live at 20:00 Istanbul time."""
    from app.providers import market_hours

    # 2026-05-06 is a Wednesday. 17:00 UTC = 20:00 Istanbul, 01:00 next day in Taipei.
    evening = datetime(2026, 5, 6, 17, 0, tzinfo=timezone.utc)
    assert market_hours.is_open("TPE", evening) is False
    assert market_hours.is_open("NYSE", evening) is True  # 13:00 New York
    assert market_hours.is_open("STO", evening) is False  # 19:00 Stockholm

    # 03:00 UTC = 11:00 Taipei.
    morning = datetime(2026, 5, 6, 3, 0, tzinfo=timezone.utc)
    assert market_hours.is_open("TPE", morning) is True
    assert market_hours.is_open("NYSE", morning) is False


def test_weekends_are_closed_everywhere():
    from app.providers import market_hours

    saturday = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)
    for exchange in ("STO", "ETR", "TPE", "NYSE", "NASDAQ"):
        assert market_hours.is_open(exchange, saturday) is False


def test_next_open_is_later_than_now_and_lands_on_the_open_bell():
    from app.providers import market_hours

    # Friday 20:00 UTC - New York has closed for the week.
    friday_evening = datetime(2026, 5, 8, 20, 0, tzinfo=timezone.utc)
    nxt = market_hours.next_open_for("NYSE", friday_evening)

    assert nxt > friday_evening
    local = nxt.astimezone(ZoneInfo("America/New_York"))
    assert local.weekday() == 0  # Monday, skipping the weekend
    assert (local.hour, local.minute) == (9, 30)


def test_next_open_same_day_when_the_bell_has_not_rung_yet():
    from app.providers import market_hours

    # Wednesday 11:00 UTC = 07:00 New York, before the open.
    early = datetime(2026, 5, 6, 11, 0, tzinfo=timezone.utc)
    nxt = market_hours.next_open_for("NYSE", early)
    local = nxt.astimezone(ZoneInfo("America/New_York"))
    assert local.date() == datetime(2026, 5, 6).date()
    assert (local.hour, local.minute) == (9, 30)


def test_next_open_across_exchanges_picks_the_earliest():
    """This is what the frontend sleeps until, so it must be the soonest bell."""
    from app.providers import market_hours

    # Saturday: everything shut. Taipei (UTC+8) opens well before New York.
    saturday = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)
    soonest = market_hours.next_open(["NYSE", "STO", "TPE", "ETR"], saturday)

    assert soonest == market_hours.next_open_for("TPE", saturday)
    assert soonest < market_hours.next_open_for("NYSE", saturday)
    assert soonest > saturday


def test_next_open_ignores_unknown_exchanges():
    from app.providers import market_hours

    saturday = datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)
    assert market_hours.next_open_for("MARS", saturday) is None
    # An unknown code alongside a known one must not poison the result.
    assert market_hours.next_open(["MARS", "NYSE"], saturday) == market_hours.next_open_for(
        "NYSE", saturday
    )
    assert market_hours.next_open(["MARS"], saturday) is None


def test_unknown_exchange_is_treated_as_closed():
    """Assume closed rather than imply a live price."""
    from app.providers import market_hours

    assert market_hours.is_open("MARS", datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)) is False


# -- yfinance client robustness -------------------------------------------------------


def test_nan_closes_are_dropped(monkeypatch):
    """docs/FINDINGS.md F-4: a NaN close must never reach the calc engine."""
    import pandas as pd

    from app.providers import yf_client

    frame = pd.DataFrame(
        {"Close": [10.0, float("nan"), 12.0]},
        index=pd.to_datetime(["2026-07-29", "2026-07-30", "2026-07-31"]),
    )
    closes = yf_client._closes_from_frame(frame)

    assert len(closes) == 2
    assert date(2026, 7, 30) not in closes
    assert closes[date(2026, 7, 31)] == Decimal("12.0000")


def test_float32_noise_is_quantized_away():
    """Yahoo's 14.19999981 must be stored as 14.20."""
    from app.providers import yf_client

    assert yf_client._to_decimal(14.19999981, yf_client.PRICE_QUANTUM) == Decimal("14.2000")
    assert yf_client._to_decimal(190.41000366, yf_client.PRICE_QUANTUM) == Decimal("190.4100")


def test_backoff_retries_then_gives_up(monkeypatch):
    from app.providers import yf_client

    monkeypatch.setattr(yf_client.time, "sleep", lambda _s: None)
    attempts = {"n": 0}

    def always_fails():
        attempts["n"] += 1
        raise RuntimeError("Yahoo is down")

    assert yf_client._with_backoff(always_fails, "test") is None
    assert attempts["n"] == yf_client.MAX_ATTEMPTS


def test_backoff_succeeds_on_a_later_attempt(monkeypatch):
    from app.providers import yf_client

    monkeypatch.setattr(yf_client.time, "sleep", lambda _s: None)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert yf_client._with_backoff(flaky, "test") == "ok"
    assert attempts["n"] == 2


# -- live -----------------------------------------------------------------------------


@pytest.mark.live
def test_live_symbols_and_fx_resolve():
    """SPEC §12: one live test, excluded from the default run.

    Run with:  pytest -m live
    """
    from app.providers import yf_client
    from app.registry import FX_DIRECT, FX_SYMBOL, FX_VIA_USD, REGISTRY

    for entry in REGISTRY:
        result = yf_client.fetch_last_close(entry.yf_symbol, lookback_days=14)
        assert result is not None, f"{entry.ticker} ({entry.yf_symbol}) returned no price"
        close, traded = result
        assert close > 0
        assert (date.today() - traded).days <= 14

    for currency in FX_DIRECT:
        assert yf_client.fetch_last_close(FX_SYMBOL[currency]) is not None

    for currency, leg in FX_VIA_USD.items():
        assert yf_client.fetch_last_close(leg) is not None, f"{currency} leg {leg} is dead"

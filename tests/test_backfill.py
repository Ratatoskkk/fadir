"""A shared refresh after an outage must request the missing window, not just recent days."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from freezegun import freeze_time

from app.config import get_settings
from app.models import FxCache, Instrument, PriceCache
from app.providers import backfill
from app.providers import price_service as price_service_module
from app.providers.fx_service import FxService
from app.services.portfolio import PortfolioService


def _weekdays(start: date, end: date) -> list[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def test_hole_is_requested_once_and_bounded(monkeypatch):
    monkeypatch.setattr(backfill, "_requested", set())
    today = date(2026, 11, 6)
    cached = _weekdays(date(2026, 6, 1), date(2026, 9, 11)) + _weekdays(date(2026, 10, 27), date(2026, 11, 5))

    assert backfill.refresh_start("p", cached, today, today, 5) == date(2026, 9, 11)
    assert backfill.refresh_start("p", cached, today, today, 5) == date(2026, 10, 31)
    assert backfill.refresh_start("q", [], today, date(2026, 10, 27), 5) == date(2026, 10, 27)
    old = [date(2020, 1, 1), date(2020, 3, 1), date(2026, 11, 5)]
    assert backfill.refresh_start("r", old, today, today, 5) == today - timedelta(days=backfill.MAX_BACKFILL_DAYS)


@freeze_time("2026-11-06")
def test_shared_refresh_backfills_outage_for_prices_and_fx(session, monkeypatch):
    monkeypatch.setattr(backfill, "_requested", set())
    instrument = Instrument(ticker="GAP", exchange="NYSE", yf_symbol="GAP", currency="USD", name="Gap", active=True)
    session.add(instrument)
    session.flush()
    held = _weekdays(date(2026, 6, 1), date(2026, 9, 11)) + _weekdays(date(2026, 10, 27), date(2026, 11, 5))
    session.add_all(PriceCache(instrument_id=instrument.id, price_date=d, close_native=Decimal("10")) for d in held)
    session.add_all(FxCache(base="USD", quote="TRY", rate_date=d, rate=Decimal("40"), provider="fixture") for d in held)
    session.commit()

    requested: dict[str, date] = {}
    monkeypatch.setattr(
        price_service_module.yf_client,
        "fetch_close_series_batch",
        lambda symbols, start, end: requested.setdefault("prices", start) and {},
    )
    monkeypatch.setattr(FxService, "warm", lambda self, currency, start, end: requested.setdefault("fx", start) and 0)

    PortfolioService(session, get_settings()).refresh_shared()

    assert requested == {"prices": date(2026, 9, 11), "fx": date(2026, 9, 11)}

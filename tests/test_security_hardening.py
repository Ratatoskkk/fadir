"""Hardening: secret leakage, background-loop resilience, shared-refresh isolation, request limits."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.config import FxConfig
from app.providers.base import ProviderError
from app.providers.fx_tcmb import TcmbFxProvider

# -- 1. TCMB key never leaves the provider ---------------------------------------------


def test_tcmb_http_error_text_does_not_carry_the_api_key(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert "key" not in params
        assert headers["key"] == "DUMMYKEY123"
        request = httpx.Request("GET", url, params=params, headers=headers)
        return httpx.Response(403, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(ProviderError) as excinfo:
        TcmbFxProvider("DUMMYKEY123").series("USD", "TRY", date(2026, 5, 4), date(2026, 5, 4))
    assert "DUMMYKEY123" not in str(excinfo.value)
    assert str(excinfo.value) == "TCMB request failed for USD/TRY: HTTP 403"


def test_tcmb_transport_error_text_does_not_carry_the_api_key(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        raise httpx.ConnectError(f"cannot reach {url} with key {headers['key']}")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(ProviderError) as excinfo:
        TcmbFxProvider("DUMMYKEY123").series("USD", "TRY", date(2026, 5, 4), date(2026, 5, 4))
    assert "DUMMYKEY123" not in str(excinfo.value)
    assert "ConnectError" in str(excinfo.value)


def test_fx_config_repr_hides_the_tcmb_key():
    assert "DUMMYKEY123" not in repr(FxConfig(tcmb_api_key="DUMMYKEY123"))


def test_httpx_request_logging_is_not_at_info():
    import app.main  # noqa: F401

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


# -- 7/8. Host validation and request body limit ----------------------------------------


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_foreign_host_header_is_rejected_and_loopback_is_served():
    client = _client()
    assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
    assert client.get("/api/health", headers={"Host": "127.0.0.1:8000"}).status_code != 400
    assert client.get("/api/health", headers={"Host": "ratatosk.dev"}).status_code != 400


def test_declared_oversize_body_gets_413():
    response = _client().post("/api/refresh", content=b"x" * (256 * 1024 + 1))
    assert response.status_code == 413


def _run_asgi(app, headers, chunks):
    sent: list[dict] = []
    queue = list(chunks)

    async def receive():
        if queue:
            body = queue.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(queue)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}
    asyncio.run(app(scope, receive, send))
    return sent


def test_chunked_body_without_content_length_stops_at_the_limit():
    from app.main import BodyLimitMiddleware

    consumed: list[int] = []

    async def downstream(scope, receive, send):
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return
            consumed.append(len(message["body"]))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    chunk = b"x" * (100 * 1024)
    sent = _run_asgi(BodyLimitMiddleware(downstream), [], [chunk] * 10)
    assert sent[0]["status"] == 413
    assert len(consumed) == 2  # the third chunk crosses 256 KiB and is never delivered

    sent = _run_asgi(BodyLimitMiddleware(downstream), [], [chunk, chunk])
    assert sent[0]["status"] == 200


# -- 2/3. Background loop survives a DB error; guest purge runs once a day ---------------


def _loop_harness(monkeypatch, *, session_failures: int):
    from contextlib import contextmanager

    from sqlalchemy.exc import OperationalError

    import app.main as main
    from app.config import RefreshConfig, Settings

    counts = {"scope": 0, "refresh": 0, "purge": 0}

    @contextmanager
    def fake_scope():
        counts["scope"] += 1
        if counts["scope"] <= session_failures:
            raise OperationalError("select 1", {}, Exception("pool timeout"))
        yield object()

    monkeypatch.setattr(
        main, "get_settings", lambda: Settings(refresh=RefreshConfig(0, 0))
    )
    monkeypatch.setattr(main, "session_scope", fake_scope)
    monkeypatch.setattr(main, "load_shared_exchanges", lambda session: set())
    monkeypatch.setattr(main, "_refresh_once", lambda: counts.__setitem__("refresh", counts["refresh"] + 1) or 0)
    monkeypatch.setattr(main, "_purge_once", lambda: counts.__setitem__("purge", counts["purge"] + 1) or 0)
    return main, counts


async def _run_briefly(main, counts, *, until_refreshes: int):
    task = asyncio.create_task(main._auto_refresh())
    try:
        for _ in range(500):
            if counts["refresh"] >= until_refreshes:
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_auto_refresh_survives_a_db_error_and_runs_the_next_cycle(monkeypatch):
    main, counts = _loop_harness(monkeypatch, session_failures=1)
    asyncio.run(_run_briefly(main, counts, until_refreshes=2))
    assert counts["scope"] >= 3 and counts["refresh"] >= 2


def test_guest_purge_runs_once_then_waits_a_day(monkeypatch):
    main, counts = _loop_harness(monkeypatch, session_failures=0)
    asyncio.run(_run_briefly(main, counts, until_refreshes=4))
    assert counts["refresh"] >= 4
    assert counts["purge"] == 1

    # A day later it is due again.
    main2, counts2 = _loop_harness(monkeypatch, session_failures=0)
    clock = {"now": 1000.0}
    monkeypatch.setattr(main2.time, "monotonic", lambda: clock["now"])

    async def scenario():
        last = await main2._maybe_purge(None)
        again = await main2._maybe_purge(last)
        clock["now"] += main2.PURGE_INTERVAL_SECONDS + 1
        later = await main2._maybe_purge(again)
        return last, again, later

    last, again, later = asyncio.run(scenario())
    assert (last, again) == (1000.0, 1000.0)
    assert later == 1000.0 + main2.PURGE_INTERVAL_SECONDS + 1
    assert counts2["purge"] == 2


def test_shared_refresh_set_excludes_instruments_no_portfolio_holds(session):
    from app.models import Instrument, Portfolio, Side, Transaction, Workspace
    from app.services.portfolio import load_shared_exchanges, load_shared_instruments

    held = Instrument(ticker="HELD", exchange="NYSE", yf_symbol="HELD", currency="USD", name="h", active=True)
    orphan = Instrument(ticker="ORPH", exchange="LSE", yf_symbol="ORPH", currency="GBP", name="o", active=True)
    workspace = Workspace(portfolios=[Portfolio(name="P")])
    session.add_all([held, orphan, workspace])
    session.flush()
    session.add(
        Transaction(
            portfolio_id=workspace.portfolios[0].id, instrument_id=held.id,
            trade_date=date(2026, 5, 1), side=Side.BUY, quantity=Decimal("1"),
            price_native=Decimal("1"), fees_native=Decimal("0"), fx_rate_to_try=Decimal("40"),
            fx_rate_date=date(2026, 5, 1), fx_provider="fixture",
        )
    )
    session.commit()
    assert [i.ticker for i in load_shared_instruments(session)] == ["HELD"]
    assert load_shared_exchanges(session) == {"NYSE"}


# -- 4. One instrument's DB failure does not poison the shared refresh -------------------


def _instrument(session, ticker):
    from app.models import Instrument

    row = Instrument(ticker=ticker, exchange="NYSE", yf_symbol=ticker, currency="USD", name=ticker, active=True)
    session.add(row)
    session.flush()
    return row


def test_one_instruments_flush_error_does_not_block_the_next(session, monkeypatch):
    from sqlalchemy import select

    from app.config import get_settings
    from app.models import PriceCache
    from app.providers import price_service as ps
    from app.providers.price_service import PriceService

    first, second = _instrument(session, "AAA"), _instrument(session, "BBB")
    session.commit()
    day = date(2026, 9, 4)
    monkeypatch.setattr(
        ps.yf_client,
        "fetch_close_series_batch",
        lambda symbols, start, end: {s: {day: Decimal("5")} for s in symbols},
    )
    original = PriceService._store_closes

    def flaky(self, instrument_id, closes):
        if instrument_id == first.id:
            for _ in range(2):  # same (instrument, date) twice: a real unique violation
                self.session.add(PriceCache(instrument_id=instrument_id, price_date=day, close_native=Decimal("1")))
            self.session.flush()
        return original(self, instrument_id, closes)

    monkeypatch.setattr(PriceService, "_store_closes", flaky)
    report = PriceService(session, get_settings()).refresh_shared([first, second], day, day)
    session.commit()

    assert report.per_instrument["AAA"].ok is False
    assert report.per_instrument["BBB"].ok is True
    assert report.errors[0] == "AAA: IntegrityError"
    stored = session.scalars(select(PriceCache.instrument_id)).all()
    assert stored == [second.id]


def test_two_split_events_on_one_date_insert_one_row(session, monkeypatch):
    from sqlalchemy import func, select

    from app.config import get_settings
    from app.models import CorporateAction
    from app.providers import price_service as ps
    from app.providers.base import SplitEvent
    from app.providers.price_service import PriceService

    row = _instrument(session, "SPL")
    event = SplitEvent(action_date=date(2026, 6, 1), ratio=Decimal("2"))
    monkeypatch.setattr(ps.yf_client, "fetch_splits", lambda symbol: [event, event])
    assert PriceService(session, get_settings()).sync_splits(row) == 1
    assert session.scalar(select(func.count()).select_from(CorporateAction)) == 1


# -- 5b. Forced shared refresh is rate limited ------------------------------------------


def test_forced_shared_refresh_is_throttled_to_one_per_minute(session, monkeypatch):
    from app.config import get_settings
    from app.providers.price_service import PriceService, RefreshReport
    from app.services import portfolio as portfolio_module
    from app.services.portfolio import PortfolioService

    seen: list[bool] = []

    def fake(self, instruments, start, end, *, force=False, now_utc=None):
        seen.append(force)
        return RefreshReport()

    monkeypatch.setattr(PriceService, "refresh_shared", fake)
    service = PortfolioService(session, get_settings())
    service.refresh_shared(force=True)
    service.refresh_shared(force=True)
    service.refresh_shared(force=False)
    portfolio_module.reset_forced_refresh_state()
    service.refresh_shared(force=True)
    assert seen == [True, False, False, True]


def test_concurrent_forced_refresh_is_downgraded(session, monkeypatch):
    from app.config import get_settings
    from app.providers.price_service import PriceService, RefreshReport
    from app.services import portfolio as portfolio_module
    from app.services.portfolio import PortfolioService

    seen: list[bool] = []
    monkeypatch.setattr(
        PriceService, "refresh_shared",
        lambda self, instruments, start, end, *, force=False, now_utc=None: seen.append(force) or RefreshReport(),
    )
    with portfolio_module._FORCED_REFRESH_LOCK:  # another forced refresh is in flight
        PortfolioService(session, get_settings()).refresh_shared(force=True)
    assert seen == [False]


# -- 6. FX negative cache ----------------------------------------------------------------


class _CountingProvider:
    name = "counting"

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def provenance(self, currency):
        return self.name

    def series(self, base, quote, start, end):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _fx_service(session, provider):
    from app.config import FxConfig, Settings
    from app.providers.fx_service import FxService

    settings = Settings(fx=FxConfig(default_provider="counting"))
    return FxService(session, settings, providers={"counting": provider})


def test_empty_fx_fetch_is_not_repeated_within_ten_minutes(session):
    from app.providers.base import RateUnavailable

    provider = _CountingProvider({})
    for _ in range(2):
        with pytest.raises(RateUnavailable):
            _fx_service(session, provider).quote("USD", date(2026, 5, 4))
    assert provider.calls == 1


def test_failed_fx_fetch_is_not_repeated_within_ten_minutes(session):
    from app.providers.base import RateUnavailable

    provider = _CountingProvider(ProviderError("down"))
    with pytest.raises(ProviderError):
        _fx_service(session, provider).quote("USD", date(2026, 5, 4))
    with pytest.raises(RateUnavailable):
        _fx_service(session, provider).quote("USD", date(2026, 5, 4))
    assert provider.calls == 1


def test_fx_fetch_is_retried_after_the_negative_ttl(session, monkeypatch):
    from app.providers import fx_service
    from app.providers.base import RateUnavailable

    provider = _CountingProvider({})
    now = {"t": 1000.0}
    monkeypatch.setattr(fx_service.time, "monotonic", lambda: now["t"])
    with pytest.raises(RateUnavailable):
        _fx_service(session, provider).quote("USD", date(2026, 5, 4))
    now["t"] += fx_service.NEGATIVE_TTL_SECONDS + 1
    with pytest.raises(RateUnavailable):
        _fx_service(session, provider).quote("USD", date(2026, 5, 4))
    assert provider.calls == 2


def test_current_serves_the_stale_row_without_refetching_after_an_empty_answer(session):
    from datetime import timedelta

    from app.models import FxCache, utcnow

    today = date.today()
    session.add(
        FxCache(
            base="USD", quote="TRY", rate_date=today, rate=Decimal("40"), provider="counting",
            fetched_at=utcnow().replace(tzinfo=None) - timedelta(days=1),
        )
    )
    session.commit()
    provider = _CountingProvider({})
    for _ in range(3):
        assert _fx_service(session, provider).current("USD").rate == Decimal("40")
    assert provider.calls == 1

"""A Portfolio valued in its Base Currency (ADR 0006): rates to TRY crossed to it. Offline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.calc.rebase import cross, cross_daily, cross_intraday, last_at
from app.calc.tax import TaxConfig
from app.config import Settings
from app.db import make_engine
from app.models import Instrument, Portfolio, Side, Transaction, Workspace
from app.providers.base import FxQuote
from app.services.portfolio import PortfolioService
from app.services.portfolio_scope import PortfolioScope
from tests.test_api import client  # noqa: F401 - fixture

D1, D2 = date(2026, 1, 2), date(2026, 1, 5)
#: Synthetic rates to TRY: USD 35 on the trade date and 40 now; EUR 38 then, 44 now.
TO_TRY = {("USD", D1): Decimal("35"), ("USD", D2): Decimal("40"), ("EUR", D1): Decimal("38"), ("EUR", D2): Decimal("44")}


# -- the cross itself --------------------------------------------------------------


def test_a_rate_to_try_crosses_to_the_base_on_the_same_date():
    assert cross(Decimal("38"), Decimal("35")) == Decimal("1.085714285714")


def test_daily_cross_keeps_dates_both_sides_published_and_handles_try():
    eur = {D1: Decimal("38"), D2: Decimal("44")}
    usd = {D1: Decimal("35")}
    assert cross_daily("EUR", eur, usd) == {D1: Decimal("1.085714285714")}
    assert cross_daily("TRY", {}, usd) == {D1: Decimal("0.028571428571")}
    assert cross_daily("USD", usd, usd) == {D1: Decimal("1")}


def test_intraday_cross_takes_the_other_sides_last_bar():
    t = [datetime(2026, 1, 2, 10, m, tzinfo=timezone.utc) for m in (0, 5, 10)]
    eur = {t[0]: Decimal("38"), t[2]: Decimal("39")}
    usd = {t[1]: Decimal("35")}
    # t[0] precedes the first USD bar, so it is dropped rather than guessed.
    assert cross_intraday("EUR", eur, usd) == {
        t[1]: Decimal("1.085714285714"),
        t[2]: Decimal("1.114285714286"),
    }
    assert cross_intraday("EUR", eur, {}) == {}


def test_last_at_reads_the_value_at_or_before():
    at = last_at({D1: Decimal("35")})
    assert at(D1) == at(D2) == Decimal("35")
    assert at(date(2026, 1, 1)) is None


# -- the service --------------------------------------------------------------------


class StubFx:
    def _q(self, currency: str, on: date) -> FxQuote:
        return FxQuote(base=currency, quote="TRY", rate=TO_TRY[(currency, on)], rate_date=on, requested_date=on, provider="synthetic")

    def current(self, currency: str, *, force: bool = False) -> FxQuote:
        return self._q(currency, D2)

    def quote(self, currency: str, on: date, *, allow_fetch: bool = True) -> FxQuote:
        return self._q(currency, on)


class StubPrices:
    def last_two_cached_closes(self, ids):
        return {i: ((Decimal("12"), D2), None) for i in ids}


def _service(tmp_path, base: str, *, tax: bool = False):
    engine = make_engine(tmp_path / f"base-{base}.db")
    from app import models

    models.Base.metadata.create_all(engine)
    session = Session(engine)
    portfolio = Portfolio(name="P", base_currency=base)
    session.add(Workspace(portfolios=[portfolio]))
    usd = Instrument(ticker="U", exchange="TEST", yf_symbol="U.TEST", currency="USD", name="U")
    eur = Instrument(ticker="E", exchange="TEST", yf_symbol="E.TEST", currency="EUR", name="E")
    session.add_all([usd, eur])
    session.flush()
    for inst, rate in ((usd, "35"), (eur, "38")):
        session.add(Transaction(
            instrument_id=inst.id, portfolio_id=portfolio.id, trade_date=D1, side=Side.BUY,
            quantity=Decimal("10"), price_native=Decimal("10"), fees_native=Decimal("0"),
            fx_rate_to_try=Decimal(rate), fx_rate_date=D1, fx_provider="synthetic",
        ))
    session.flush()
    settings = Settings(tax=TaxConfig(enabled=tax))
    service = PortfolioService(session, settings, fx_service=StubFx(), price_service=StubPrices())
    return service.scoped(PortfolioScope(session, portfolio))


def test_a_usd_portfolio_is_valued_in_usd(tmp_path):
    view = _service(tmp_path, "USD").build_view(now_utc=datetime(2026, 1, 5, 12, tzinfo=timezone.utc))
    by = {p.ticker: p for p in view.positions}
    # A USD holding: cost and value in its own dollars; the lira's fall is no FX effect.
    assert by["U"].cost_try == Decimal("100")
    assert by["U"].market_value_try == Decimal("120")
    assert by["U"].attribution.fx_effect_try == 0
    # A EUR holding: crossed at EUR/USD on each date (38/35 then 44/40).
    assert by["E"].cost_try == Decimal("108.57142857140")
    assert by["E"].market_value_try == Decimal("132.0000000000")


def test_a_try_portfolio_is_unchanged(tmp_path):
    view = _service(tmp_path, "TRY").build_view(now_utc=datetime(2026, 1, 5, 12, tzinfo=timezone.utc))
    by = {p.ticker: p for p in view.positions}
    assert by["U"].cost_try == Decimal("3500")
    assert by["U"].market_value_try == Decimal("4800")


def test_the_turkey_tax_stays_in_try_and_shows_in_the_base(tmp_path):
    now = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    usd_tax = _service(tmp_path, "USD", tax=True).build_view(now_utc=now).tax
    try_tax = _service(tmp_path, "TRY", tax=True).build_view(now_utc=now).tax
    # Measured in lira the holdings gained, so Turkish tax is due even where they did not in dollars.
    assert try_tax.tax_try > 0
    assert usd_tax.tax_try == cross(try_tax.tax_try, Decimal("40"))
    assert usd_tax.effective_rate == try_tax.effective_rate


# -- the API ------------------------------------------------------------------------


def test_base_currency_can_be_changed_and_is_kept(client):  # noqa: F811
    pid = client.get("/api/portfolios").json()[0]["id"]
    changed = client.patch(f"/api/portfolios/{pid}", json={"base_currency": "EUR"})
    assert changed.status_code == 200 and changed.json()["base_currency"] == "EUR"
    assert client.get("/api/portfolios").json()[0]["base_currency"] == "EUR"
    assert client.get("/api/portfolio").json()["base_currency"] == "EUR"
    assert client.patch(f"/api/portfolios/{pid}", json={"base_currency": "JPY"}).status_code == 422
    assert client.patch("/api/portfolios/999999", json={"base_currency": "USD"}).status_code == 404


def test_a_new_portfolio_starts_in_usd(client):  # noqa: F811
    created = client.post("/api/portfolios", json={"name": "Yeni"})
    assert created.status_code == 201 and created.json()["base_currency"] == "USD"


def test_the_lira_tax_rides_along_in_another_base(tmp_path):
    now = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
    usd = _service(tmp_path, "USD", tax=True).build_view(now_utc=now)
    try_view = _service(tmp_path, "TRY", tax=True).build_view(now_utc=now)
    assert usd.tax_in_lira == try_view.tax.tax_try
    assert try_view.tax_in_lira is None


def test_a_first_save_rejects_a_currency_the_app_cannot_price(client):  # noqa: F811
    from tests.test_api import TODAY

    sale = {"ticker": "AAPL", "trade_date": TODAY.isoformat(), "side": "SELL", "quantity": "1",
            "price_native": "200.00", "fees_native": "0", "fx_rate_override": "47.50"}
    assert client.post("/api/transactions", params={"base_currency": "JPY"}, json=sale).status_code == 422
    assert client.post("/api/transactions", params={"base_currency": "USD"}, json=sale).status_code == 201


class GappyFx(StubFx):
    """No USD/TRY on the previous session's date."""

    def quote(self, currency, on, *, allow_fetch=True):
        if currency == "USD" and on == D1 and getattr(self, "gap", False):
            from app.providers.base import ProviderError
            raise ProviderError("no rate")
        return super().quote(currency, on)


def test_a_missing_previous_day_base_rate_costs_only_the_daily_figure(tmp_path):
    service = _service(tmp_path, "USD")
    from app.calc import MarketQuote
    fx = GappyFx()
    service.fx = fx
    quote = MarketQuote(
        ticker="U", currency="USD", price_native=Decimal("12"), price_date=D2,
        fx_rate_to_try=Decimal("40"), fx_rate_date=D2, fx_provider="synthetic",
        prev_price_native=Decimal("11"), prev_price_date=D1, prev_fx_rate_to_try=Decimal("35"),
    )
    fx.gap = True
    rebased = service._rebased_quote(quote)
    assert rebased.ok and rebased.fx_rate_to_try == Decimal("1")
    assert rebased.prev_price_date is None and rebased.prev_fx_rate_to_try is None

from datetime import date
from decimal import Decimal

import pytest

from app.calc.jurisdictions import JURISDICTIONS, Gain, estimate
from app.models import Instrument, Portfolio, Side, Transaction, User, Workspace
from app.services.tax_profile import TaxProfileService

D = Decimal


def gain(amount, held_days=400):
    return Gain(proceeds=D(amount) + D(1000), cost=D(1000), held_days=held_days)


def tax(code, year, *gains):
    return estimate(code, year, list(gains))[0]


def test_uk_applies_exempt_amount_then_basic_and_higher_rates():
    assert tax("GB", 2026, gain(13000)).tax == D("1800")
    result = tax("GB", 2026, gain(50000))
    assert result.taxable_gain == D("47000")
    assert result.tax == D("37700") * D("0.18") + D("9300") * D("0.24")
    assert result.marginal_rate == D("0.24")


def test_uk_tax_year_runs_april_to_april():
    assert JURISDICTIONS["GB"].period(2025) == (date(2025, 4, 6), date(2026, 4, 5))
    assert JURISDICTIONS["DE"].period(2025) == (date(2025, 1, 1), date(2025, 12, 31))


def test_germany_flat_rate_with_solidarity_after_saver_allowance():
    result = tax("DE", 2026, gain(5000))
    assert result.taxable_gain == D("4000")
    assert result.tax == D("1055.000")
    assert tax("DE", 2026, gain(800)).tax == 0


def test_france_flat_tax_includes_2026_social_levies():
    assert tax("FR", 2026, gain(1000)).tax == D("314.000")


def test_losses_offset_gains_and_never_create_negative_tax():
    assert tax("DE", 2026, gain(5000), gain(-6000)).tax == 0
    assert tax("FR", 2026, gain(-100)).taxable_gain == 0


def test_us_long_term_gain_inside_zero_bracket_after_standard_deduction():
    assert tax("US", 2026, gain(60000)).tax == 0


def test_us_long_term_gain_stacks_into_fifteen_percent():
    result = tax("US", 2026, gain(100000))
    assert result.taxable_gain == D("83900")
    assert result.tax == (D("83900") - D("49450")) * D("0.15")


def test_us_short_term_gain_uses_ordinary_brackets():
    result = tax("US", 2026, gain(30000, held_days=100))
    assert result.tax == D("12400") * D("0.10") + D("1500") * D("0.12")


def test_us_short_term_loss_offsets_long_term_gain():
    assert tax("US", 2026, gain(-10000, held_days=30), gain(30000)).tax == 0


def test_us_adds_net_investment_income_tax_above_threshold():
    result = tax("US", 2026, gain(300000))
    expected = (D("283900") - D("49450")) * D("0.15") + D("100000") * D("0.038")
    assert result.tax == expected


@pytest.mark.parametrize("code", ["GB", "DE", "US", "FR"])
def test_every_year_cites_an_official_source(code):
    for rules in JURISDICTIONS[code].years.values():
        assert rules.source_url.startswith("https://")
        assert rules.source_version


def test_gains_are_valued_in_the_jurisdiction_currency_on_each_date(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One")]))
    instrument = Instrument(ticker="AAA", exchange="X", yf_symbol="AAA", currency="USD", name="A")
    session.add_all([user, instrument])
    session.flush()
    portfolio = user.workspace.portfolios[0]

    def txn(day, side, price, fx):
        return Transaction(
            portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date=day, side=side,
            quantity=D(1), price_native=D(price), fees_native=D(0), fx_rate_to_try=D(fx),
            fx_rate_date=day, fx_provider="stored",
        )

    session.add_all([
        txn(date(2025, 3, 1), Side.BUY, 100, 30),
        txn(date(2026, 5, 1), Side.SELL, 100, 40),
    ])
    session.flush()
    # EUR/TRY: 30 on the purchase date, 40 on the sale date, so USD/EUR stays 1:1 and a
    # flat price leaves no gain in euros even though the lira moved.
    rates = {date(2025, 3, 1): D(30), date(2026, 5, 1): D(40)}
    gains = TaxProfileService(session).jurisdiction_gains(user.id, "DE", 2026, lambda ccy, on: rates[on])
    assert len(gains) == 1
    assert gains[0].amount == 0
    assert gains[0].held_days == 426
    # Same native currency: no conversion at all.
    usd = TaxProfileService(session).jurisdiction_gains(user.id, "US", 2026, lambda ccy, on: 1 / 0)
    assert usd[0].proceeds == D(100) and usd[0].cost == D(100)


def test_jurisdiction_list_and_estimate_require_a_user(tmp_db):
    from fastapi.testclient import TestClient

    from app.api.request_authority import RequestAuthority, get_request_authority
    from app.main import app

    with TestClient(app) as client:
        listed = client.get("/api/tax/jurisdictions").json()
        assert {j["code"] for j in listed} == {"TR", "GB", "DE", "US", "FR"}
        assert next(j for j in listed if j["code"] == "GB")["currency"] == "GBP"

        app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(mode="guest", user_id=None, workspace_id=1)
        try:
            assert client.get("/api/tax/estimates?jurisdiction=GB&year=2026").status_code == 403
        finally:
            app.dependency_overrides.pop(get_request_authority, None)


def test_estimate_for_a_signed_in_user_without_sales_is_zero(session):
    from fastapi.testclient import TestClient

    from app.api.request_authority import RequestAuthority, get_request_authority
    from app.main import app

    user = User(workspace=Workspace(portfolios=[Portfolio(name="One")]))
    session.add(user)
    session.commit()
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(mode="user", user_id=user.id, workspace_id=user.workspace.id)
    try:
        with TestClient(app) as client:
            response = client.get("/api/tax/estimates?jurisdiction=DE&year=2026")
            assert response.status_code == 200
            body = response.json()
            assert body["currency"] == "EUR" and Decimal(body["tax"]) == 0
            assert body["assumptions"] == ["de.flat", "de.allowance", "de.no_church"]
            assert client.get("/api/tax/estimates?jurisdiction=FR&year=2025").status_code == 404
            assert client.get("/api/tax/estimates?jurisdiction=XX&year=2026").status_code == 404
    finally:
        app.dependency_overrides.pop(get_request_authority, None)

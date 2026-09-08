from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import TaxProfile, User, Workspace, Portfolio, Instrument, Transaction, Side
from app.services.tax_profile import TaxProfileData, TaxProfileService
from app.calc.tax import TaxConfig, TaxBracket
from decimal import Decimal


def test_tax_profile_is_unique_per_user_jurisdiction_and_year(session):
    user = User()
    session.add(user)
    session.flush()
    session.add(TaxProfile(user_id=user.id, jurisdiction="TR", tax_year=2025, currency="TRY", source_url="gib", source_version="2026-02", assumptions_json="[]", disclaimer="estimate"))
    session.flush()
    session.add(TaxProfile(user_id=user.id, jurisdiction="TR", tax_year=2025, currency="TRY", source_url="gib", source_version="2026-02", assumptions_json="[]", disclaimer="estimate"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_profile_isolated_to_user_and_turkey_try_metadata(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One"), Portfolio(name="Two")]))
    other = User(workspace=Workspace(portfolios=[Portfolio(name="Other")]))
    session.add_all([user, other])
    session.flush()
    service = TaxProfileService(session)
    profile = service.save(user.id, TaxProfileData("TR", 2025, "TRY", "https://gib.gov.tr", "2026-02", ["fixed"], "estimate"))
    assert profile.currency == "TRY"
    assert service.get(user.id, "TR", 2025).id == profile.id
    assert service.get(other.id, "TR", 2025) is None
    assert len(service.portfolios_for_user(session, user.id)) == 2


def test_user_estimate_combines_portfolios_before_progressive_brackets(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One"), Portfolio(name="Two")]))
    session.add(user)
    session.flush()
    service = TaxProfileService(session)
    service.save(user.id, TaxProfileData("TR", 2025, "TRY", "gib", "2026-02", [], "estimate"))
    config = TaxConfig(brackets=(TaxBracket(Decimal("100"), Decimal("0.10")), TaxBracket(None, Decimal("0.20"))))
    estimate = service.estimate_for_user(user.id, {user.workspace.portfolios[0].id: (Decimal("80"), Decimal("0")), user.workspace.portfolios[1].id: (Decimal("80"), Decimal("0"))}, config)
    assert estimate.tax_try == Decimal("22")


def test_api_estimate_uses_requested_year_and_all_owned_portfolios(session):
    from app.api.routes import get_tax_estimate
    from app.api.request_authority import RequestAuthority
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One"), Portfolio(name="Two")]))
    session.add(user)
    session.flush()
    service = TaxProfileService(session)
    service.save(user.id, TaxProfileData("TR", 2025, "TRY", "gib", "2026-02", ["combined"], "estimate"))
    instrument = Instrument(ticker="TAX", exchange="X", yf_symbol="TAX.X", currency="TRY", name="Tax")
    session.add(instrument)
    session.flush()
    for portfolio in user.workspace.portfolios:
        session.add_all([
            Transaction(portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date=datetime(2025, 1, 2), side=Side.BUY, quantity=Decimal("1"), price_native=Decimal("80"), fees_native=Decimal("0"), fx_rate_to_try=Decimal("1"), fx_rate_date=datetime(2025, 1, 2).date(), fx_provider="synthetic"),
            Transaction(portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date=datetime(2025, 2, 2), side=Side.SELL, quantity=Decimal("1"), price_native=Decimal("160"), fees_native=Decimal("0"), fx_rate_to_try=Decimal("1"), fx_rate_date=datetime(2025, 2, 2).date(), fx_provider="synthetic"),
        ])
    session.flush()
    response = get_tax_estimate(session, RequestAuthority(mode="user", user_id=user.id, workspace_id=user.workspace.id), 2025)
    assert response.tax_year == 2025
    assert response.source_version == "2026-02"
    assert response.disclaimer == "estimate"
    assert response.tax_try > Decimal("0")


def test_user_estimate_uses_stored_foreign_fee_fx_provenance(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One"), Portfolio(name="Two")]))
    session.add(user); session.flush()
    service = TaxProfileService(session)
    service.save(user.id, TaxProfileData("TR", 2025, "TRY", "gib", "2026-02", [], "estimate"))
    instrument = Instrument(ticker="FEE", exchange="X", yf_symbol="FEE.X", currency="USD", name="Fee")
    session.add(instrument); session.flush()
    p = user.workspace.portfolios[0]
    session.add(Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2025, 1, 2), side=Side.BUY, quantity=1, price_native=10, fees_native=3, fee_currency="EUR", fee_fx_rate_to_try=33, fee_fx_rate_date=datetime(2025, 1, 2).date(), fee_fx_provider="stored", fx_rate_to_try=30, fx_rate_date=datetime(2025, 1, 2).date(), fx_provider="instrument"))
    session.flush()
    config = TaxConfig(brackets=(TaxBracket(None, Decimal("1")),))
    estimate = service.estimate_for_user(user.id, None, config, 2025)
    assert estimate.gross_gain_try == Decimal("0")


def test_user_estimate_uses_fifo_cost_for_partial_sale(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One"), Portfolio(name="Two")]))
    session.add(user); session.flush()
    service = TaxProfileService(session)
    service.save(user.id, TaxProfileData("TR", 2025, "TRY", "gib", "2026-02", [], "estimate"))
    instrument = Instrument(ticker="FIFO", exchange="X", yf_symbol="FIFO.X", currency="TRY", name="Fifo")
    session.add(instrument); session.flush()
    p = user.workspace.portfolios[0]
    session.add_all([
        Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2025, 1, 2), side=Side.BUY, quantity=2, price_native=100, fees_native=0, fx_rate_to_try=1, fx_rate_date=datetime(2025, 1, 2).date(), fx_provider="synthetic"),
        Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2025, 2, 2), side=Side.SELL, quantity=1, price_native=150, fees_native=0, fx_rate_to_try=1, fx_rate_date=datetime(2025, 2, 2).date(), fx_provider="synthetic"),
    ])
    session.flush()
    config = TaxConfig(brackets=(TaxBracket(None, Decimal("1")),))
    estimate = service.estimate_for_user(user.id, None, config, 2025)
    assert estimate.gross_gain_try == Decimal("50")


def test_requested_year_sale_replays_prior_buy_and_foreign_fee_fx(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One")]))
    session.add(user); session.flush()
    service = TaxProfileService(session)
    service.save(user.id, TaxProfileData("TR", 2025, "TRY", "gib", "2026-02", [], "estimate"))
    instrument = Instrument(ticker="CROSS", exchange="X", yf_symbol="CROSS.X", currency="USD", name="Cross")
    session.add(instrument); session.flush(); p = user.workspace.portfolios[0]
    session.add_all([
        Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2024, 12, 1), side=Side.BUY, quantity=1, price_native=10, fees_native=3, fee_currency="EUR", fee_fx_rate_to_try=33, fee_fx_rate_date=datetime(2024, 12, 1).date(), fee_fx_provider="fee", fx_rate_to_try=30, fx_rate_date=datetime(2024, 12, 1).date(), fx_provider="instrument"),
        Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2025, 2, 1), side=Side.SELL, quantity=1, price_native=20, fees_native=1, fee_currency="EUR", fee_fx_rate_to_try=36, fee_fx_rate_date=datetime(2025, 2, 1).date(), fee_fx_provider="fee", fx_rate_to_try=40, fx_rate_date=datetime(2025, 2, 1).date(), fx_provider="instrument"),
    ]); session.flush()
    estimate = service.estimate_for_user(user.id, None, TaxConfig(brackets=(TaxBracket(None, Decimal("1")),)), 2025)
    assert estimate.gross_gain_try == Decimal("365")


def test_multiple_instruments_accumulate_within_one_portfolio(session):
    user = User(workspace=Workspace(portfolios=[Portfolio(name="One")]))
    session.add(user); session.flush(); service = TaxProfileService(session)
    service.save(user.id, TaxProfileData("TR", 2025, "TRY", "gib", "2026-02", [], "estimate"))
    p = user.workspace.portfolios[0]
    instruments = [Instrument(ticker=t, exchange="X", yf_symbol=f"{t}.X", currency="TRY", name=t) for t in ("A", "B")]
    session.add_all(instruments); session.flush()
    for instrument in instruments:
        session.add(Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2025, 1, 1), side=Side.BUY, quantity=1, price_native=10, fees_native=0, fx_rate_to_try=1, fx_rate_date=datetime(2025, 1, 1).date(), fx_provider="synthetic"))
        session.add(Transaction(portfolio_id=p.id, instrument_id=instrument.id, trade_date=datetime(2025, 2, 1), side=Side.SELL, quantity=1, price_native=20, fees_native=0, fx_rate_to_try=1, fx_rate_date=datetime(2025, 2, 1).date(), fx_provider="synthetic"))
    session.flush()
    estimate = service.estimate_for_user(user.id, None, TaxConfig(brackets=(TaxBracket(None, Decimal("1")),)), 2025)
    assert estimate.gross_gain_try == Decimal("20")

from datetime import date, datetime, timezone
from decimal import Decimal
import inspect
import pytest
from sqlalchemy import select
from app.api.request_authority import RequestAuthority
from app.models import Instrument, Portfolio, Transaction, User, Workspace, Side
from app.services import portfolio_merge
from app.api import routes
from app.api.request_authority import RequestAuthorityError
from app.schemas import PortfolioMergeRequest


def _authority(workspace_id, user_id=1):
    return RequestAuthority(mode="user", user_id=user_id, workspace_id=workspace_id)


def test_portfolio_merge_synthetic_rules(session, monkeypatch):
    user = User(); session.add(user); session.flush()
    target_ws = Workspace(user_id=user.id); source_ws = Workspace(user_id=None)
    session.add_all([target_ws, source_ws]); session.flush()
    source = Portfolio(workspace_id=source_ws.id, name="Guest")
    target = Portfolio(workspace_id=target_ws.id, name="Target", base_currency="USD")
    session.add_all([source, target]); session.flush()
    monkeypatch.setattr(portfolio_merge.guest_access, "require", lambda *a, **k: type("G", (), {"workspace_id": source_ws.id})())
    instrument = Instrument(ticker="ACME", exchange="X", yf_symbol="ACME", currency="USD", name="Acme")
    session.add(instrument); session.flush()
    def add(portfolio, fees="1", fx="30"):
        row = Transaction(portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date=date(2026, 1, 1), side=Side.BUY, quantity=Decimal("2"), price_native=Decimal("10"), fees_native=Decimal(fees), fx_rate_to_try=Decimal(fx), fx_rate_date=date(2026,1,1), fx_provider="manual")
        session.add(row); session.flush(); return row
    source_row = add(source)
    original_updated_at = source_row.updated_at
    add(target, fees="2")
    extra = Transaction(portfolio_id=source.id, instrument_id=instrument.id, trade_date=date(2026,2,1), side=Side.SELL, quantity=Decimal("1"), price_native=Decimal("11"), fees_native=Decimal("0"), fx_rate_to_try=Decimal("30"), fx_rate_date=date(2026,2,1), fx_provider="manual")
    session.add(extra); session.flush()
    original_extra_updated_at = extra.updated_at
    plan = portfolio_merge.preview(session, authority=_authority(target_ws.id, user.id), guest_secret="x", source_portfolio_id=source.id, target_portfolio_id=target.id)
    assert len(plan.candidates) == 1 and plan.candidates[0].differences[0].field == "fees_native"
    assert [r.id for r in plan.movable_source_rows] == [extra.id]
    result = portfolio_merge.confirm(session, authority=_authority(target_ws.id, user.id), guest_secret="x", source_portfolio_id=source.id, target_portfolio_id=target.id, revision_token=plan.revision_token, decisions=[{"source_transaction_id": source_row.id, "action": "skip"}])
    assert result.skipped_count == 1 and result.moved_count == 1
    assert session.scalar(select(Transaction.portfolio_id).where(Transaction.id == source_row.id)) == source.id
    assert session.scalar(select(Transaction.portfolio_id).where(Transaction.id == extra.id)) == target.id
    assert session.scalar(select(Transaction.updated_at).where(Transaction.id == extra.id)) == original_extra_updated_at.replace(tzinfo=None)
    assert source_row.updated_at.replace(tzinfo=None) == original_updated_at.replace(tzinfo=None)


def test_portfolio_merge_rejects_stale_revision(session, monkeypatch):
    user = User(); session.add(user); session.flush(); target_ws = Workspace(user_id=user.id); source_ws = Workspace(); session.add_all([target_ws, source_ws]); session.flush()
    source = Portfolio(workspace_id=source_ws.id, name="Guest"); target = Portfolio(workspace_id=target_ws.id, name="Target"); session.add_all([source,target]); session.flush()
    monkeypatch.setattr(portfolio_merge.guest_access, "require", lambda *a, **k: type("G", (), {"workspace_id": source_ws.id})())
    instrument = Instrument(ticker="X", exchange="X", yf_symbol="X", currency="USD", name="X"); session.add(instrument); session.flush()
    row = Transaction(portfolio_id=source.id, instrument_id=instrument.id, trade_date=date(2026,1,1), side=Side.BUY, quantity=Decimal("1"), price_native=Decimal("1"), fees_native=Decimal("0"), fx_rate_to_try=Decimal("30"), fx_rate_date=date(2026,1,1), fx_provider="x"); session.add(row); session.flush()
    plan = portfolio_merge.preview(session, authority=_authority(target_ws.id,user.id), guest_secret="x", source_portfolio_id=source.id, target_portfolio_id=target.id)
    row.note = "changed"; session.flush()
    with pytest.raises(portfolio_merge.PortfolioMergeError):
        portfolio_merge.confirm(session, authority=_authority(target_ws.id,user.id), guest_secret="x", source_portfolio_id=source.id, target_portfolio_id=target.id, revision_token=plan.revision_token, decisions=[])


def test_merge_route_requires_explicit_guest_cookie(session):
    from starlette.requests import Request

    request = Request({"type": "http", "method": "POST", "path": "/api/portfolio/merge/preview", "headers": [], "query_string": b""})
    with pytest.raises(RequestAuthorityError):
        routes.portfolio_merge_preview(
            PortfolioMergeRequest(source_portfolio_id=1, target_portfolio_id=2),
            request,
            session,
            _authority(1, 1),
        )


def test_confirm_locks_transaction_rows_before_recheck():
    assert "lock_rows=True" in inspect.getsource(portfolio_merge.confirm)
    assert "with_for_update" in inspect.getsource(portfolio_merge._load_rows)

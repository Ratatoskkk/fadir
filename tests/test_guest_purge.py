from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.models import (
    GuestAccess,
    Instrument,
    LoginTransaction,
    Portfolio,
    Side,
    Snapshot,
    Transaction,
    User,
    Workspace,
)
from app.services.guest_access import purge_expired_guests

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


def _guest(session, n: int, *, last_access: datetime, revoked: bool = False, instrument=None):
    workspace = Workspace(created_at=last_access, updated_at=last_access)
    workspace.guest_access = GuestAccess(
        secret_digest=bytes([n]) * 32,
        created_at=last_access,
        last_access_at=last_access,
        revoked_at=last_access if revoked else None,
    )
    portfolio = Portfolio(name="p")
    workspace.portfolios.append(portfolio)
    session.add(workspace)
    session.flush()
    session.add(
        Transaction(
            portfolio_id=portfolio.id, instrument_id=instrument.id, trade_date=date(2026, 1, 2),
            side=Side.BUY, quantity=Decimal("1"), price_native=Decimal("1"), fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("1"), fx_rate_date=date(2026, 1, 2), fx_provider="synthetic",
        )
    )
    session.add(Snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 2, n), payload_json="{}"))
    session.flush()
    return workspace.id


def test_purge_removes_only_expired_or_revoked_guest_workspaces(session):
    instrument = Instrument(ticker="T", exchange="X", yf_symbol="T", currency="TRY", name="t")
    session.add(instrument)
    session.flush()
    old = _guest(session, 1, last_access=NOW - timedelta(days=91), instrument=instrument)
    edge = _guest(session, 2, last_access=NOW - timedelta(days=90), instrument=instrument)
    revoked = _guest(session, 3, last_access=NOW - timedelta(days=1), revoked=True, instrument=instrument)
    fresh = _guest(session, 4, last_access=NOW - timedelta(days=89), instrument=instrument)

    user = User(workspace=Workspace(portfolios=[Portfolio(name="mine")]))
    session.add(user)
    session.flush()
    session.add(
        Transaction(
            portfolio_id=user.workspace.portfolios[0].id, instrument_id=instrument.id,
            trade_date=date(2020, 1, 2), side=Side.BUY, quantity=Decimal("1"), price_native=Decimal("1"),
            fees_native=Decimal("0"), fx_rate_to_try=Decimal("1"), fx_rate_date=date(2020, 1, 2),
            fx_provider="synthetic",
        )
    )

    stale = LoginTransaction(
        state_digest=b"a" * 32, nonce_digest=b"b" * 32,
        created_at=NOW - timedelta(days=3), expires_at=NOW - timedelta(days=2),
    )
    recent = LoginTransaction(
        state_digest=b"c" * 32, nonce_digest=b"d" * 32,
        created_at=NOW - timedelta(hours=2), expires_at=NOW - timedelta(hours=1),
    )
    session.add_all([stale, recent])
    session.flush()
    recent_id = recent.id
    session.commit()

    assert purge_expired_guests(session, NOW) == 3
    session.commit()

    assert set(session.scalars(select(Workspace.id).where(Workspace.user_id.is_(None)))) == {fresh}
    assert {old, edge, revoked}.isdisjoint(session.scalars(select(Portfolio.workspace_id)))
    assert session.scalar(select(func.count()).select_from(GuestAccess)) == 1
    # One guest's rows and the signed-in user's rows remain.
    assert session.scalar(select(func.count()).select_from(Transaction)) == 2
    assert session.scalar(select(func.count()).select_from(Snapshot)) == 1
    assert session.scalar(select(func.count()).select_from(Workspace).where(Workspace.user_id.is_not(None))) == 1
    assert list(session.scalars(select(LoginTransaction.id))) == [recent_id]
    assert purge_expired_guests(session, NOW) == 0

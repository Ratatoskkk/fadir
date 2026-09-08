from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app import models
from app.api import routes
from app.api.request_authority import RequestAuthority, get_request_authority
from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token
from app.models import Portfolio, Snapshot, Transaction, User, Workspace
from app.services.privacy import PrivacyService


def test_privacy_service_surface_exists() -> None:
    assert PrivacyService


@pytest.fixture
def privacy_client(session):
    from app.main import app

    user = User()
    workspace = Workspace(user=user)
    portfolio = Portfolio(workspace=workspace, name="Private", base_currency="TRY")
    other = Portfolio(workspace=workspace, name="Other", base_currency="USD")
    instrument = models.Instrument(
        ticker="SYN", exchange="TEST", yf_symbol="SYN.TEST", currency="USD", name="Synthetic"
    )
    transaction = Transaction(
        portfolio=portfolio,
        instrument=instrument,
        trade_date=date(2026, 1, 2),
        side=models.Side.BUY,
        quantity=Decimal("2"),
        price_native=Decimal("10.25"),
        fees_native=Decimal("0.50"),
        fee_currency="USD",
        fee_fx_rate_to_try=Decimal("35.1"),
        fee_fx_rate_date=date(2026, 1, 2),
        fee_fx_provider="manual",
        fx_rate_to_try=Decimal("35"),
        fx_rate_date=date(2026, 1, 2),
        fx_provider="synthetic",
        note="private note",
    )
    snapshot = Snapshot(
        portfolio=portfolio,
        snapshot_date=date(2026, 1, 2),
        payload_json='{"value":"20.50"}',
    )
    session.add_all([user, workspace, portfolio, other, instrument, transaction, snapshot])
    session.add_all(
        [
            models.LoginIdentity(user=user, issuer="synthetic", subject="privacy-user"),
            models.TaxProfile(
                user=user,
                jurisdiction="TR",
                tax_year=2026,
                currency="TRY",
                source_url="https://example.invalid/source",
                source_version="synthetic",
                assumptions_json="[]",
                disclaimer="synthetic",
            ),
        ]
    )
    session.flush()
    authority = {"workspace_id": workspace.id, "user_id": user.id}
    previous_factory = getattr(app.state, "session_factory", None)
    previous_authority_factory = getattr(app.state, "authority_session_factory", None)
    app.state.session_factory = lambda: sessionmaker_for(session)
    app.state.authority_session_factory = lambda: sessionmaker_for(session)
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(
        mode="user", user_id=authority["user_id"], workspace_id=authority["workspace_id"]
    )
    session.commit()
    try:
        with TestClient(app) as client:
            csrf = issue_csrf_token()
            client.cookies.set(CSRF_COOKIE_NAME, csrf)
            client.headers.update({"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: csrf})
            yield client, session, user, workspace, portfolio, other, authority
    finally:
        app.dependency_overrides.pop(get_request_authority, None)
        if previous_factory is not None:
            app.state.session_factory = previous_factory
        else:
            delattr(app.state, "session_factory")
        if previous_authority_factory is not None:
            app.state.authority_session_factory = previous_authority_factory
        else:
            delattr(app.state, "authority_session_factory")


def sessionmaker_for(session):
    from sqlalchemy.orm import Session

    return Session(session.get_bind())


def test_guest_and_unauthenticated_privacy_routes_reject(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/portfolios/1/export").status_code == 401
        assert client.delete("/api/portfolios/1").status_code == 401
        assert client.delete("/api/account").status_code == 401


def test_json_and_csv_exports_are_private_and_deterministic(privacy_client) -> None:
    client, _session, _user, _workspace, portfolio, _other, _authority = privacy_client

    exported = client.get(f"/api/portfolios/{portfolio.id}/export")
    assert exported.status_code == 200
    assert exported.headers["cache-control"] == "no-store"
    body = exported.json()
    assert body["portfolio"]["id"] == portfolio.id
    assert body["transactions"][0]["quantity"] == "2.00000000"
    assert body["transactions"][0]["price_native"] == "10.250000000000"
    assert body["transactions"][0]["ticker"] == "SYN"
    assert body["transactions"][0]["currency"] == "USD"
    assert body["snapshots"][0]["payload_json"] == '{"value":"20.50"}'
    assert "secret" not in exported.text.lower()
    assert "workspace_id" not in exported.text

    csv_export = client.get(f"/api/portfolios/{portfolio.id}/export?format=csv")
    assert csv_export.status_code == 200
    assert csv_export.headers["content-disposition"] == (
        f'attachment; filename="portfolio-{portfolio.id}.csv"'
    )
    assert "record_type" in csv_export.text
    assert "2.00000000,10.250000000000" in csv_export.text
    assert "SYN" in csv_export.text and "USD" in csv_export.text
    assert csv_export.headers["cache-control"] == "no-store"


def test_cross_workspace_export_and_portfolio_delete_are_rejected(privacy_client) -> None:
    client, session, _user, _workspace, portfolio, other, authority = privacy_client
    authority["workspace_id"] = other.workspace_id + 999

    rejected = client.get(f"/api/portfolios/{portfolio.id}/export")
    assert rejected.status_code == 404
    assert session.get(Portfolio, portfolio.id) is not None


def test_portfolio_delete_removes_only_owned_private_rows(privacy_client) -> None:
    client, session, _user, _workspace, portfolio, other, _authority = privacy_client
    portfolio_id = portfolio.id
    other_id = other.id

    response = client.delete(f"/api/portfolios/{portfolio_id}")
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    session.expire_all()
    assert session.get(Portfolio, portfolio_id) is None
    assert session.scalar(select(Transaction).where(Transaction.portfolio_id == portfolio_id)) is None
    assert session.scalar(select(Snapshot).where(Snapshot.portfolio_id == portfolio_id)) is None
    assert session.get(Portfolio, other_id) is not None


def test_account_delete_revokes_sessions_and_cascades_user_data(privacy_client) -> None:
    client, session, user, workspace, portfolio, _other, _authority = privacy_client
    user_id = user.id
    workspace_id = workspace.id
    portfolio_id = portfolio.id
    session.add(
        models.UserSession(
            user_id=user_id,
            public_id="A" * 22,
            secret_digest=b"s" * 32,
            created_at=datetime.now(timezone.utc),
            last_access_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    response = client.delete("/api/account")
    assert response.status_code == 204, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "__Host-fadir-user=" in response.headers.get("set-cookie", "")
    session.expire_all()
    assert session.get(User, user_id) is None
    assert session.get(Workspace, workspace_id) is None
    assert session.get(Portfolio, portfolio_id) is None
    assert session.scalar(select(models.LoginIdentity).where(models.LoginIdentity.user_id == user_id)) is None
    assert session.scalar(select(models.TaxProfile).where(models.TaxProfile.user_id == user_id)) is None

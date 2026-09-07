from fastapi.testclient import TestClient
from decimal import Decimal
from datetime import date

import pytest

from app.models import Instrument, Portfolio, Side, Transaction, Workspace
from app.api.request_authority import RequestAuthority, get_request_authority
from app.api.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, issue_csrf_token


@pytest.fixture
def private_client(session, monkeypatch):
    from app.main import app

    first = Workspace(portfolios=[Portfolio(name="First")])
    second = Workspace()
    instrument = Instrument(
        ticker="SYN",
        exchange="TEST",
        yf_symbol="SYN.TEST",
        currency="USD",
        name="Synthetic",
    )
    session.add_all([first, second, instrument])
    session.flush()
    session.add(
        Transaction(
            portfolio_id=first.portfolios[0].id,
            instrument_id=instrument.id,
            trade_date=date(2026, 1, 1),
            side=Side.BUY,
            quantity=Decimal("1"),
            price_native=Decimal("10"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("35"),
            fx_rate_date=date(2026, 1, 1),
            fx_provider="synthetic",
        )
    )
    session.commit()

    authority = {"workspace_id": first.id}
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(
        mode="guest", user_id=None, workspace_id=authority["workspace_id"]
    )
    try:
        with TestClient(app) as client:
            token = issue_csrf_token()
            client.cookies.set(CSRF_COOKIE_NAME, token)
            client.headers.update(
                {"Origin": "https://ratatosk.dev", CSRF_HEADER_NAME: token}
            )
            yield client, session, first, second, instrument, authority
    finally:
        app.dependency_overrides.pop(get_request_authority, None)


def test_private_transactions_require_request_authority(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/transactions")

    assert response.status_code == 401


def test_malformed_unauthenticated_create_rejects_authority_before_validation(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/api/transactions", json={})

    assert response.status_code == 401


def test_private_transactions_are_workspace_scoped_and_default_first(private_client) -> None:
    client, session, first, second, _instrument, authority = private_client

    default = client.get("/api/transactions")
    assert default.status_code == 200
    assert len(default.json()) == 1

    cross = client.get(
        "/api/transactions", params={"portfolio_id": second.id}
    )
    assert cross.status_code == 404
    assert cross.json()["detail"] == "request rejected"
    assert client.get(
        "/api/transactions", params={"portfolio_id": first.portfolios[0].id}
    ).status_code == 200


def test_empty_read_does_not_create_and_first_save_creates_default(private_client) -> None:
    client, session, _first, second, _instrument, authority = private_client
    authority["workspace_id"] = second.id

    assert client.get("/api/transactions").json() == []
    assert session.query(Portfolio).filter_by(workspace_id=second.id).count() == 0

    response = client.post(
        "/api/transactions",
        json={
            "ticker": "SYN",
            "trade_date": "2026-02-01",
            "side": "BUY",
            "quantity": "1",
            "price_native": "10",
            "fx_rate_override": "35",
        },
    )
    assert response.status_code == 201, response.text
    portfolio = session.query(Portfolio).filter_by(workspace_id=second.id).one()
    assert portfolio.name == "Ana Portföy"
    assert response.json()["id"]


def test_write_rejection_is_rolled_back_and_not_cached(private_client, monkeypatch) -> None:
    client, session, _first, _second, _instrument, _authority = private_client
    response = client.post(
        "/api/transactions",
        headers={"Origin": "https://evil.example"},
        json={
            "ticker": "SYN",
            "trade_date": "2026-02-01",
            "quantity": "1",
            "price_native": "10",
            "fx_rate_override": "35",
        },
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_cookie_authority_cors_allows_only_configured_origins(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.options(
            "/api/transactions",
            headers={
                "Origin": "https://ratatosk.dev",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ratatosk.dev"
    assert response.headers["access-control-allow-credentials"] == "true"

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.api import routes
from app.api.request_authority import RequestAuthority, get_request_authority
from app.models import Portfolio, Workspace
from app.schemas import PortfolioOptionOut


def test_portfolio_option_schema_is_safe() -> None:
    option = PortfolioOptionOut(id=3, name="Ana Portföy", base_currency="TRY")
    assert option.model_dump() == {
        "id": 3,
        "name": "Ana Portföy",
        "base_currency": "TRY",
    }


@pytest.fixture
def portfolio_client(session):
    from app.main import app

    first = Workspace(
        portfolios=[
            Portfolio(name="Later", base_currency="USD"),
            Portfolio(name="Earlier", base_currency="TRY"),
        ]
    )
    empty = Workspace()
    other = Workspace(portfolios=[Portfolio(name="Other", base_currency="EUR")])
    session.add_all([first, empty, other])
    session.flush()
    session.commit()
    authority = {"workspace_id": first.id}
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(
        mode="guest", user_id=None, workspace_id=authority["workspace_id"]
    )
    try:
        with TestClient(app) as client:
            yield client, session, first, empty, other, authority
    finally:
        app.dependency_overrides.pop(get_request_authority, None)


def test_portfolio_list_requires_private_authority(tmp_db) -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/portfolios")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_portfolio_list_is_scoped_ordered_and_non_mutating(portfolio_client) -> None:
    client, session, first, empty, other, authority = portfolio_client

    response = client.get("/api/portfolios")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == [
        {"id": first.portfolios[0].id, "name": "Later", "base_currency": "USD"},
        {"id": first.portfolios[1].id, "name": "Earlier", "base_currency": "TRY"},
    ]
    assert all("workspace_id" not in row for row in response.json())
    assert "user_id" not in response.text

    authority["workspace_id"] = empty.id
    before = session.query(Portfolio).count()
    assert client.get("/api/portfolios").json() == []
    assert session.query(Portfolio).count() == before

    authority["workspace_id"] = other.id
    assert client.get("/api/portfolios").json() == [
        {"id": other.portfolios[0].id, "name": "Other", "base_currency": "EUR"}
    ]

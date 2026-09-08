from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models
from app.api import routes
from app.api.request_authority import RequestAuthority, get_request_authority
from app.schemas import PortfolioMergeOptionOut, PortfolioMergeOptionsOut


def test_merge_options_route_returns_safe_source_and_target_choices(monkeypatch):
    from app.db import make_engine

    engine = make_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.session_factory = lambda: Session(engine)
    app.state.configured_origin = "https://ratatosk.dev"
    app.dependency_overrides[get_request_authority] = lambda: RequestAuthority(
        mode="user", user_id=7, workspace_id=2
    )
    monkeypatch.setattr(
        routes.portfolio_merge_service,
        "options",
        lambda *args, **kwargs: PortfolioMergeOptionsOut(
            source=[PortfolioMergeOptionOut(id=11, name="Guest", base_currency="USD")],
            target=[PortfolioMergeOptionOut(id=22, name="Main", base_currency="TRY")],
        ),
    )
    app.include_router(routes.private_router)
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/portfolio/merge/options",
                cookies={routes.GUEST_COOKIE_NAME: "g" * 43},
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "source": [{"id": 11, "name": "Guest", "base_currency": "USD"}],
            "target": [{"id": 22, "name": "Main", "base_currency": "TRY"}],
        }
        assert "secret" not in response.text.lower()
    finally:
        engine.dispose()

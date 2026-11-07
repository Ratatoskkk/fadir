from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.testclient import TestClient
import pytest

from app.api.request_authority import PASS_COOKIE_NAME, RequestAuthority, get_request_authority
from app.models import GuestAccess, Portfolio, PortfolioPass, Workspace
from app.services import portfolio_codes

ORIGIN = "https://ratatosk.dev"


@pytest.fixture(autouse=True)
def _reset_code_limits():
    portfolio_codes.reset_limits()
    yield
    portfolio_codes.reset_limits()


CSRF = "c" * 43


@pytest.fixture
def owner_workspace(session):
    portfolio = Portfolio(name="Ana Portföy", base_currency="TRY")
    workspace = Workspace(portfolios=[portfolio])
    session.add(workspace)
    session.commit()
    return workspace


@pytest.fixture
def client(owner_workspace):
    """The owner's browser is a Guest; any browser holding a pass resolves for real."""
    from app.main import app

    def authority(request: Request) -> RequestAuthority:
        if PASS_COOKIE_NAME in request.cookies:
            return get_request_authority(request)
        return RequestAuthority(mode="guest", user_id=None, workspace_id=owner_workspace.id)

    app.dependency_overrides[get_request_authority] = authority
    try:
        with TestClient(app, base_url=ORIGIN) as c:
            c.cookies.set("__Host-fadir-csrf", CSRF)
            yield c
    finally:
        app.dependency_overrides.pop(get_request_authority, None)


def _browser():
    from app.main import app

    return TestClient(app, base_url=ORIGIN)


def _csrf(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get("__Host-fadir-csrf")}


def _open(client: TestClient, code: str):
    return client.post("/api/access/code", headers={"Origin": ORIGIN}, json={"code": code})


def _guest_with_portfolio(client: TestClient) -> dict:
    started = client.post("/api/portfolios/start", headers=_csrf(client))
    assert started.status_code == 200
    return started.json()


def test_new_portfolios_get_unique_four_digit_codes(session) -> None:
    portfolios = [Portfolio(name=f"P{i}", base_currency="TRY") for i in range(40)]
    session.add(Workspace(portfolios=portfolios))
    session.flush()
    codes = [p.code for p in portfolios]
    assert len(set(codes)) == 40
    assert all(len(code) == 4 and code.isdigit() for code in codes)


def test_allocation_moves_to_longer_codes_when_a_length_runs_out(session, monkeypatch) -> None:
    monkeypatch.setattr(portfolio_codes, "CODE_SPACES", ((4, 3), (5, 4), (6, 10**6)))
    portfolios = [Portfolio(name=f"P{i}", base_currency="TRY") for i in range(8)]
    session.add(Workspace(portfolios=portfolios))
    session.flush()
    assert sorted(len(p.code) for p in portfolios) == [4, 4, 4, 5, 5, 5, 5, 6]
    assert len({p.code for p in portfolios}) == 8
    assert portfolio_codes.lengths_in_use(session) == [4, 5, 6]


def test_normalize_accepts_only_four_to_six_digits() -> None:
    assert portfolio_codes.normalize(" 0420 ") == "0420"
    assert portfolio_codes.normalize("123456") == "123456"
    for bad in ("123", "1234567", "12a4", "", None, 1234):
        assert portfolio_codes.normalize(bad) is None


def test_access_reports_none_for_a_fresh_browser(tmp_db) -> None:
    with _browser() as fresh:
        response = fresh.get("/api/access")
    assert response.status_code == 200
    assert response.json() == {"mode": "none", "code_lengths": [4]}
    assert "set-cookie" not in response.headers


def test_code_opens_only_that_portfolio_on_another_browser(client) -> None:
    owner = _guest_with_portfolio(client)
    with _browser() as other:
        assert other.get("/api/access").json()["mode"] == "none"
        opened = _open(other, owner["code"])
        assert opened.status_code == 200
        assert opened.json()["mode"] == "code"
        assert other.cookies.get(PASS_COOKIE_NAME)
        assert other.get("/api/access").json()["mode"] == "code"

        assert other.get("/api/portfolios").json() == [owner]
        assert other.get("/api/portfolio").status_code == 200
        assert other.get(f"/api/portfolio?portfolio_id={owner['id'] + 99}").status_code == 404

        # A pass cannot manage codes, create Portfolios, or reach User-only data.
        assert other.post(f"/api/portfolios/{owner['id']}/code", headers=_csrf(other)).status_code == 403
        assert other.post("/api/portfolios/start", headers=_csrf(other)).status_code == 403
        assert other.get("/api/user/sessions").status_code == 401

        assert other.delete("/api/access/code", headers=_csrf(other)).status_code == 204
        assert other.get("/api/access").json()["mode"] == "none"


def test_pass_is_stored_only_as_a_digest(client, session) -> None:
    owner = _guest_with_portfolio(client)
    with _browser() as other:
        _open(other, owner["code"])
        secret = other.cookies.get(PASS_COOKIE_NAME)
    row = session.query(PortfolioPass).one()
    assert len(row.secret_digest) == 32
    assert secret.encode() not in row.secret_digest


def test_wrong_codes_are_throttled(client) -> None:
    owner = _guest_with_portfolio(client)
    wrong = f"{(int(owner['code']) + 1) % 10000:04d}"
    with _browser() as other:
        for _ in range(portfolio_codes.CLIENT_FAILURE_LIMIT):
            assert _open(other, wrong).status_code == 404
        assert _open(other, owner["code"]).status_code == 429


def test_code_redeem_requires_same_origin(client) -> None:
    owner = _guest_with_portfolio(client)
    response = client.post(
        "/api/access/code", headers={"Origin": "https://evil.example"}, json={"code": owner["code"]}
    )
    assert response.status_code == 403


def test_regenerating_a_code_closes_every_pass(client) -> None:
    owner = _guest_with_portfolio(client)
    with _browser() as other:
        _open(other, owner["code"])
        assert other.get("/api/portfolio").status_code == 200

        renewed = client.post(f"/api/portfolios/{owner['id']}/code", headers=_csrf(client))
        assert renewed.status_code == 200
        new_code = renewed.json()["code"]
        assert new_code != owner["code"]

        assert other.get("/api/portfolio").status_code == 401
        # The dead pass is cleared, so the browser can ask for a code again.
        assert other.get("/api/access").json()["mode"] == "none"
        assert _open(other, owner["code"]).status_code == 404
        assert _open(other, new_code).status_code == 200


def test_pass_keeps_its_guest_workspace_alive(client, session, owner_workspace) -> None:
    owner = _guest_with_portfolio(client)
    stale = datetime.now(timezone.utc) - timedelta(days=60)
    guest = GuestAccess(
        workspace_id=owner_workspace.id, secret_digest=b"d" * 32, created_at=stale, last_access_at=stale
    )
    session.add(guest)
    session.commit()

    now = datetime.now(timezone.utc)
    issued = portfolio_codes.redeem(session, owner["code"], "test", now=now)
    portfolio_codes.authenticate(session, issued.secret, now=now)
    session.commit()
    session.refresh(guest)
    last = guest.last_access_at
    last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    assert last > stale + timedelta(days=59)


def test_deleting_a_portfolio_removes_its_passes(session) -> None:
    portfolio = Portfolio(name="P", base_currency="TRY")
    session.add(Workspace(portfolios=[portfolio]))
    session.flush()
    portfolio_codes.redeem(session, portfolio.code, "test", now=datetime.now(timezone.utc))
    session.commit()
    session.delete(portfolio)
    session.commit()
    assert session.query(PortfolioPass).count() == 0

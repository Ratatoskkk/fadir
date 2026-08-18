"""API contract tests (SPEC §7, Epics 5 and 6).

Fully offline: price and FX caches are seeded directly, and anything that would reach
Yahoo is monkeypatched.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models import FxCache, Instrument, PriceCache, Side, Transaction

TODAY = date.today()

# `_seed` caches prices and FX for TODAY-14 .. TODAY, so every window below is expressed
# relative to TODAY. Fixed calendar dates rot: a hard-coded July window sat inside the
# seeded range when it was written and silently fell outside it as the clock moved on,
# leaving the assertions comparing zero against zero.
WINDOW = {
    "from": (TODAY - timedelta(days=7)).isoformat(),
    "to": (TODAY - timedelta(days=1)).isoformat(),
}
LONG_WINDOW = {
    "from": (TODAY - timedelta(days=14)).isoformat(),
    "to": TODAY.isoformat(),
}


@pytest.fixture
def client(session, monkeypatch):
    """A TestClient wired to the per-test SQLite DB with caches pre-seeded."""
    from app.main import app

    _seed(session)
    session.commit()

    # Nothing in these tests may touch the network.
    from app.providers import yf_client

    monkeypatch.setattr(yf_client, "fetch_close_series", lambda *a, **k: {})
    monkeypatch.setattr(yf_client, "fetch_close_series_batch", lambda syms, *a, **k: {s: {} for s in syms})
    monkeypatch.setattr(yf_client, "fetch_splits", lambda *a, **k: [])

    with TestClient(app) as c:
        yield c


def _seed(session) -> None:
    instruments = [
        Instrument(ticker="AAPL", exchange="NASDAQ", yf_symbol="AAPL", currency="USD", name="Apple Inc"),
        Instrument(ticker="ERIC", exchange="STO", yf_symbol="ERIC-B.ST", currency="SEK", name="Telefonaktiebolaget LM Ericsson"),
    ]
    session.add_all(instruments)
    session.flush()

    rates = {"USD": Decimal("47.50"), "SEK": Decimal("4.99")}
    for currency, rate in rates.items():
        for back in range(0, 15):
            session.add(
                FxCache(
                    base=currency,
                    quote="TRY",
                    rate_date=TODAY - timedelta(days=back),
                    rate=rate,
                    provider="yfinance" if currency == "USD" else "yfinance:SEKUSD=X*USDTRY=X",
                )
            )

    closes = {"AAPL": Decimal("190.41"), "ERIC": Decimal("30.24")}
    for instrument in instruments:
        for back in range(0, 15):
            session.add(
                PriceCache(
                    instrument_id=instrument.id,
                    price_date=TODAY - timedelta(days=back),
                    close_native=closes[instrument.ticker],
                    is_adjusted=False,
                )
            )

    session.add(
        Transaction(
            instrument_id=instruments[0].id,
            trade_date=date(2026, 5, 11),
            side=Side.BUY,
            quantity=Decimal("12"),
            price_native=Decimal("180.00"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("40.00"),
            fx_rate_date=date(2026, 5, 11),
            fx_provider="yfinance",
        )
    )
    session.add(
        Transaction(
            instrument_id=instruments[1].id,
            trade_date=date(2026, 3, 29),
            side=Side.BUY,
            quantity=Decimal("800"),
            price_native=Decimal("20.00"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("4.20"),
            fx_rate_date=date(2026, 3, 27),  # Sunday trade, Friday rate
            fx_provider="yfinance:SEKUSD=X*USDTRY=X",
        )
    )
    session.flush()


# -- static file serving -------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/..%2F..%2Fconfig.yaml",
        "/..%2F..%2Ffadir.db",
        "/assets%2F..%2F..%2F..%2Fconfig.yaml",
    ],
)
def test_spa_route_refuses_to_serve_files_outside_the_bundle(client, path):
    """The SPA catch-all takes an arbitrary client-supplied path.

    `fadir.db` and `config.yaml` (which can hold a TCMB API key) sit one directory above
    `frontend/dist`. Percent-encoded separators survive the browser and are decoded by
    the router, so `..` really does arrive in the handler. Binding to loopback is no
    defence — any page the browser has open can issue these requests. Anything outside
    the bundle must fall through to the SPA shell.
    """
    response = client.get(path)
    body = response.content

    # Either outcome is safe: the SPA shell from the catch-all, or a refusal from the
    # /assets mount, which guards itself. What must never happen is the file.
    assert response.status_code in (200, 404)
    assert b"tcmb_api_key" not in body
    assert b"SQLite format" not in body
    if response.status_code == 200:
        assert b"<!doctype html" in body[:64].lower()


# -- portfolio ---------------------------------------------------------------------


def test_get_portfolio_shape_and_identity(client):
    body = client.get("/api/portfolio").json()

    assert body["base_currency"] == "TRY"
    assert len(body["positions"]) == 2

    for position in body["positions"]:
        a = position["attribution"]
        pnl = Decimal(position["pnl_try"])
        assert abs(Decimal(a["price_effect_try"]) + Decimal(a["fx_effect_try"]) - pnl) < Decimal("0.01")
        assert abs(
            Decimal(a["local_return"]) * Decimal(a["fx_return"]) - Decimal(a["total_return"])
        ) < Decimal("1e-9")

    totals = body["totals"]
    assert abs(
        Decimal(totals["price_effect_try"])
        + Decimal(totals["fx_effect_try"])
        - Decimal(totals["pnl_try"])
    ) < Decimal("0.01")


def test_money_serialised_as_strings_not_floats(client):
    """A float here would undo the Decimal discipline at the last step."""
    body = client.get("/api/portfolio").json()
    assert isinstance(body["totals"]["pnl_try"], str)
    assert isinstance(body["positions"][0]["cost_native"], str)
    assert isinstance(body["liquidation"]["net_proceeds_try"], str)


def test_portfolio_exposes_the_after_tax_estimate(client):
    body = client.get("/api/portfolio").json()
    tax = body["tax"]

    assert tax["applicable"] is True
    assert isinstance(tax["tax_try"], str)  # money stays a string on the wire

    gain = Decimal(body["liquidation"]["net_pnl_try"])
    assert Decimal(tax["gross_gain_try"]) == gain
    # Net after tax = proceeds - tax, and never exceeds the pre-tax proceeds.
    assert Decimal(tax["net_after_tax_try"]) == Decimal(
        body["liquidation"]["net_proceeds_try"]
    ) - Decimal(tax["tax_try"])
    assert Decimal(tax["net_after_tax_try"]) <= Decimal(
        body["liquidation"]["net_proceeds_try"]
    )


def test_tax_estimate_always_ships_its_caveats(client):
    """The number must never appear without the assumptions that produced it."""
    tax = client.get("/api/portfolio").json()["tax"]
    assert len(tax["assumptions"]) >= 3
    assert tax["disclaimer"]
    assert "YMM" in tax["disclaimer"] or "SMMM" in tax["disclaimer"]


def test_next_market_open_present_only_when_everything_is_shut(client):
    """Drives the frontend's decision to sleep rather than poll."""
    body = client.get("/api/portfolio").json()
    any_open = any(p["session"] == "open" for p in body["positions"])

    if any_open:
        assert body["next_market_open"] is None
    else:
        assert body["next_market_open"] is not None
        from datetime import datetime, timezone

        when = datetime.fromisoformat(body["next_market_open"])
        assert when > datetime.now(timezone.utc)


def test_liquidation_card_is_labelled_an_estimate(client):
    """US-3.2: labelled as excluding tax and FX spread."""
    liq = client.get("/api/portfolio").json()["liquidation"]
    assert liq["excludes_tax"] is True
    assert "estimate" in liq["note"].lower()
    assert "tax" in liq["note"].lower()
    assert Decimal(liq["net_proceeds_try"]) > 0


def test_triangulated_fx_provenance_is_exposed(client):
    """docs/FINDINGS.md F-2: triangulation must be visible, never silent."""
    positions = {p["ticker"]: p for p in client.get("/api/portfolio").json()["positions"]}
    assert positions["ERIC"]["fx_triangulated"] is True
    assert "*" in positions["ERIC"]["fx_provider"]
    assert positions["AAPL"]["fx_triangulated"] is False


def test_closed_market_positions_are_flagged_not_presented_as_live(client):
    """SPEC §8: never imply a live price outside the session."""
    for position in client.get("/api/portfolio").json()["positions"]:
        assert position["session"] in {"open", "closed"}
        assert "price_date" in position
        if position["session"] == "closed":
            assert position["stale"] is True


# -- history -----------------------------------------------------------------------


def test_history_three_series_decompose(client):
    body = client.get("/api/portfolio/history", params=WINDOW).json()
    assert body["freq"] == "D"
    assert len(body["points"]) == 7

    for point in body["points"]:
        value = Decimal(point["value_try"])
        const = Decimal(point["value_constant_fx_try"])
        cost = Decimal(point["cost_basis_try"])
        assert Decimal(point["fx_effect_try"]) == value - const
        assert Decimal(point["price_effect_try"]) == const - cost
        assert Decimal(point["pnl_try"]) == value - cost


def test_history_can_be_narrowed_to_one_ticker(client):
    """Same builder, same decomposition — just fewer positions folded in."""
    params = WINDOW
    whole = client.get("/api/portfolio/history", params=params).json()
    just_aapl = client.get(
        "/api/portfolio/history", params={**params, "ticker": "AAPL"}
    ).json()

    assert just_aapl["tickers"] == ["AAPL"]
    assert whole["tickers"] == []
    assert len(just_aapl["points"]) == len(whole["points"])

    # The filtered series is a strict subset of the portfolio's value...
    for one, all_ in zip(just_aapl["points"], whole["points"]):
        assert Decimal(one["value_try"]) < Decimal(all_["value_try"])
        # ...and still satisfies the §6 identities on its own.
        value, const, cost = (
            Decimal(one["value_try"]),
            Decimal(one["value_constant_fx_try"]),
            Decimal(one["cost_basis_try"]),
        )
        assert Decimal(one["fx_effect_try"]) == value - const
        assert Decimal(one["price_effect_try"]) == const - cost


def test_filtered_history_series_sum_to_the_portfolio_series(client):
    """Two single-ticker charts must add up to the combined one, or the filter lies."""
    params = WINDOW
    whole = client.get("/api/portfolio/history", params=params).json()["points"]
    parts = [
        client.get("/api/portfolio/history", params={**params, "ticker": t}).json()["points"]
        for t in ("AAPL", "ERIC")
    ]

    for index, combined in enumerate(whole):
        summed = sum(Decimal(p[index]["value_try"]) for p in parts)
        assert abs(summed - Decimal(combined["value_try"])) < Decimal("0.01")


def test_history_rejects_an_unknown_ticker_rather_than_ignoring_it(client):
    """Silently returning everything would look like a filter that disagrees with the table."""
    response = client.get("/api/portfolio/history", params={"ticker": "NOPE"})
    assert response.status_code == 404
    assert "NOPE" in response.json()["detail"]


def test_history_accepts_several_tickers(client):
    body = client.get(
        "/api/portfolio/history",
        params=[*WINDOW.items(), ("ticker", "AAPL"), ("ticker", "ERIC")],
    ).json()
    assert body["tickers"] == ["AAPL", "ERIC"]


# -- daily change --------------------------------------------------------------------


def test_positions_and_totals_carry_a_daily_change(client):
    body = client.get("/api/portfolio").json()

    for position in body["positions"]:
        daily = position["daily"]
        assert daily["available"] is True
        assert daily["reference_date"] is not None
        # The §6 identity again, on the day's move.
        assert abs(
            Decimal(daily["price_effect_try"])
            + Decimal(daily["fx_effect_try"])
            - Decimal(daily["pnl_try"])
        ) < Decimal("0.01")

    total = body["totals"]["daily"]
    assert total["available"] is True
    assert abs(
        Decimal(total["price_effect_try"])
        + Decimal(total["fx_effect_try"])
        - Decimal(total["pnl_try"])
    ) < Decimal("0.01")
    # The portfolio figure is the sum of the position figures.
    assert abs(
        sum(Decimal(p["daily"]["pnl_try"]) for p in body["positions"])
        - Decimal(total["pnl_try"])
    ) < Decimal("0.01")


def test_daily_change_is_unavailable_when_only_one_session_exists(client, session):
    """Reported as absent, never as a zero move."""
    from app.models import PriceCache

    aapl = next(i for i in session.query(Instrument) if i.ticker == "AAPL")
    keep = TODAY
    for row in session.query(PriceCache).filter(PriceCache.instrument_id == aapl.id):
        if row.price_date != keep:
            session.delete(row)
    session.commit()

    body = client.get("/api/portfolio").json()
    aapl_row = next(p for p in body["positions"] if p["ticker"] == "AAPL")

    assert aapl_row["daily"]["available"] is False
    assert aapl_row["daily"]["reference_date"] is None
    # The portfolio figure still reports, on the positions that do have history.
    assert body["totals"]["daily"]["available"] is True


def test_history_weekly_frequency(client):
    daily = client.get("/api/portfolio/history", params=LONG_WINDOW).json()
    weekly = client.get(
        "/api/portfolio/history", params={**LONG_WINDOW, "freq": "W"}
    ).json()
    assert len(weekly["points"]) < len(daily["points"])


def test_history_rejects_inverted_range(client):
    r = client.get(
        "/api/portfolio/history", params={"from": WINDOW["to"], "to": WINDOW["from"]}
    )
    assert r.status_code == 422


# -- transactions ------------------------------------------------------------------


def test_list_transactions_derives_try_total(client):
    rows = client.get("/api/transactions").json()
    assert len(rows) == 2
    aapl = next(r for r in rows if r["ticker"] == "AAPL")
    assert Decimal(aapl["total_native"]) == Decimal("2160.00")
    assert Decimal(aapl["total_try"]) == Decimal("2160.00") * Decimal("40.00")


def test_weekend_transaction_flags_carried_forward_fx(client):
    rows = client.get("/api/transactions").json()
    eric = next(r for r in rows if r["ticker"] == "ERIC")
    assert eric["fx_carried_forward"] is True
    assert eric["fx_rate_date"] < eric["trade_date"]


def test_create_transaction_autofetches_fx(client):
    """US-6.1: FX rate auto-fetched for the chosen date."""
    r = client.post(
        "/api/transactions",
        json={
            "ticker": "AAPL",
            "trade_date": TODAY.isoformat(),
            "side": "BUY",
            "quantity": "5",
            "price_native": "180.00",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["fx_rate_to_try"]) == Decimal("47.50")
    assert body["fx_provider"] == "yfinance"


def test_create_transaction_with_fx_override_marks_manual(client):
    """SPEC §7: an override sets fx_provider='manual' so the UI can flag it."""
    r = client.post(
        "/api/transactions",
        json={
            "ticker": "AAPL",
            "trade_date": TODAY.isoformat(),
            "quantity": "5",
            "price_native": "180.00",
            "fx_rate_override": "48.1234",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["fx_provider"] == "manual"
    assert Decimal(body["fx_rate_to_try"]) == Decimal("48.1234")


def test_create_transaction_unknown_ticker_404(client):
    r = client.post(
        "/api/transactions",
        json={"ticker": "ZZZZ", "trade_date": TODAY.isoformat(), "quantity": "1", "price_native": "1"},
    )
    assert r.status_code == 404


def test_create_transaction_rejects_non_positive_quantity(client):
    r = client.post(
        "/api/transactions",
        json={"ticker": "AAPL", "trade_date": TODAY.isoformat(), "quantity": "0", "price_native": "1"},
    )
    assert r.status_code == 422


def test_patch_transaction_updates_and_refetches_fx(client):
    txn_id = client.get("/api/transactions").json()[0]["id"]
    r = client.patch(f"/api/transactions/{txn_id}", json={"quantity": "20", "refetch_fx": True})
    assert r.status_code == 200
    assert Decimal(r.json()["quantity"]) == Decimal("20")


def test_patch_override_switches_provider_to_manual(client):
    txn_id = client.get("/api/transactions").json()[0]["id"]
    r = client.patch(f"/api/transactions/{txn_id}", json={"fx_rate_override": "50.0"})
    assert r.json()["fx_provider"] == "manual"


def test_delete_transaction_recomputes_portfolio(client):
    """US-6.2: deleting a transaction recomputes FIFO lots and totals."""
    before = Decimal(client.get("/api/portfolio").json()["totals"]["cost_try"])

    rows = client.get("/api/transactions").json()
    aapl_id = next(r["id"] for r in rows if r["ticker"] == "AAPL")
    assert client.delete(f"/api/transactions/{aapl_id}").status_code == 204

    after = Decimal(client.get("/api/portfolio").json()["totals"]["cost_try"])
    assert after < before
    assert len(client.get("/api/transactions").json()) == 1


def test_oversized_sell_degrades_one_row_instead_of_the_whole_dashboard(client, session):
    """A SELL exceeding the lots on file must not 500 the portfolio endpoint.

    Nothing stops such a row being recorded — the FIFO matcher only meets it later, when
    the view is built. If that exception escapes, the dashboard stops rendering, and the
    only screen that can delete the bad row is the screen that will not load. Degrade the
    position and keep the rest, exactly as a dead symbol is handled (SPEC §8).
    """
    aapl = next(i for i in session.query(Instrument) if i.ticker == "AAPL")
    session.add(
        Transaction(
            instrument_id=aapl.id,
            trade_date=TODAY,
            side=Side.SELL,
            quantity=Decimal("9999"),  # only 12 were ever bought
            price_native=Decimal("200.00"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("47.50"),
            fx_rate_date=TODAY,
            fx_provider="yfinance",
        )
    )
    session.commit()

    response = client.get("/api/portfolio")
    assert response.status_code == 200

    body = response.json()
    rows = {p["ticker"]: p for p in body["positions"]}

    assert rows["AAPL"]["ok"] is False
    assert "lot" in rows["AAPL"]["error"].lower()
    assert any("AAPL" in w for w in body["warnings"])

    # The healthy position is untouched and still carries its full value.
    assert rows["ERIC"]["ok"] is True
    assert Decimal(rows["ERIC"]["market_value_try"]) > 0
    # Totals exclude the broken row rather than counting it as a wipeout.
    assert Decimal(body["totals"]["market_value_try"]) == Decimal(
        rows["ERIC"]["market_value_try"]
    )


def test_delete_missing_transaction_404(client):
    assert client.delete("/api/transactions/99999").status_code == 404


def test_record_a_sell_produces_split_realized_pnl(client):
    """US-6.3: realized PnL appears, split into price and FX components."""
    r = client.post(
        "/api/transactions",
        json={
            "ticker": "AAPL",
            "trade_date": TODAY.isoformat(),
            "side": "SELL",
            "quantity": "12",
            "price_native": "200.00",
            "fx_rate_override": "47.50",
        },
    )
    assert r.status_code == 201

    position = next(
        p for p in client.get("/api/portfolio").json()["positions"] if p["ticker"] == "AAPL"
    )
    realized = position["realized"]
    assert Decimal(realized["quantity"]) == Decimal("12")

    # 12 @ 180.00 -> 12 @ 200.00, entry rate 40.00, exit rate 47.50.
    assert Decimal(realized["pnl_native"]) == Decimal("240.00")
    assert Decimal(realized["price_effect_try"]) == Decimal("240.00") * Decimal("40.00")
    assert Decimal(realized["fx_effect_try"]) == Decimal("2400.00") * Decimal("7.50")
    assert (
        Decimal(realized["price_effect_try"]) + Decimal(realized["fx_effect_try"])
        == Decimal(realized["pnl_try"])
    )
    assert Decimal(position["quantity"]) == 0


# -- instruments -------------------------------------------------------------------


def test_list_instruments(client):
    rows = client.get("/api/instruments").json()
    assert {r["ticker"] for r in rows} == {"AAPL", "ERIC"}


def test_create_instrument_validates_symbol_against_yfinance(client, monkeypatch):
    """SPEC §7: 'validates symbol against yfinance before insert'."""
    from app.api import routes

    monkeypatch.setattr(routes.yf_client, "fetch_last_close", lambda *a, **k: None)
    r = client.post(
        "/api/instruments",
        json={"ticker": "FAKE", "exchange": "NYSE", "yf_symbol": "FAKE", "currency": "USD", "name": "Fake"},
    )
    assert r.status_code == 422
    assert "no price data" in r.json()["detail"]


def test_create_instrument_rejects_currency_mismatch(client, monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes.yf_client, "fetch_last_close", lambda *a, **k: (Decimal("10"), TODAY))
    monkeypatch.setattr(routes.yf_client, "fetch_currency", lambda *a, **k: "EUR")
    r = client.post(
        "/api/instruments",
        json={"ticker": "XX", "exchange": "ETR", "yf_symbol": "XX.DE", "currency": "USD", "name": "X"},
    )
    assert r.status_code == 422
    assert "EUR" in r.json()["detail"]


def test_create_instrument_succeeds_when_verified(client, monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes.yf_client, "fetch_last_close", lambda *a, **k: (Decimal("10"), TODAY))
    monkeypatch.setattr(routes.yf_client, "fetch_currency", lambda *a, **k: "USD")
    r = client.post(
        "/api/instruments",
        json={"ticker": "IBM", "exchange": "NYSE", "yf_symbol": "IBM", "currency": "USD", "name": "IBM"},
    )
    assert r.status_code == 201
    assert r.json()["ticker"] == "IBM"


def test_create_duplicate_instrument_409(client, monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes.yf_client, "fetch_last_close", lambda *a, **k: (Decimal("10"), TODAY))
    r = client.post(
        "/api/instruments",
        json={"ticker": "AAPL", "exchange": "NASDAQ", "yf_symbol": "AAPL", "currency": "USD", "name": "dup"},
    )
    assert r.status_code == 409


# -- operations --------------------------------------------------------------------


def test_health_reports_providers_and_cache_age(client):
    body = client.get("/api/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert len(body["providers"]) == 2

    triangulated = [p for p in body["providers"] if p["detail"]["triangulated"]]
    assert len(triangulated) == 1  # SEK
    for provider in body["providers"]:
        assert provider["detail"]["cache_age_seconds"] is not None
        assert provider["detail"]["last_rate_date"] is not None

    assert {i["ticker"] for i in body["instruments"]} == {"AAPL", "ERIC"}
    # Read from the settings rather than a literal: the point is that /health reports
    # the TTL actually in force, not that the TTL happens to be any given number.
    # Pinning the number here just breaks the test every time the cadence is tuned.
    from app.config import get_settings

    assert body["cache"]["fx_current_ttl_seconds"] == get_settings().cache.fx_current_ttl_seconds
    assert body["settings"]["base_currency"] == "TRY"
    assert (
        body["settings"]["default_refresh_seconds"]
        == get_settings().refresh.default_interval_seconds
    )


def test_refresh_endpoint_reports_per_instrument(client):
    """US-5.2 / US-5.3: refresh returns per-symbol outcomes, not a single verdict."""
    body = client.post("/api/refresh").json()
    assert set(body["per_instrument"]) == {"AAPL", "ERIC"}
    for status in body["per_instrument"].values():
        assert "session" in status
        assert "last_traded" in status


def test_one_failing_symbol_degrades_one_row_only(client, session):
    """US-5.3: a symbol with no price data must not take down the page."""
    broken = Instrument(
        ticker="2330", exchange="TPE", yf_symbol="2330.TW", currency="TWD", name="Taiwan Semiconductor Manufacturing"
    )
    session.add(broken)
    session.flush()
    session.add(
        Transaction(
            instrument_id=broken.id,
            trade_date=date(2026, 5, 4),
            side=Side.BUY,
            quantity=Decimal("39"),
            price_native=Decimal("1000.00"),
            fees_native=Decimal("0"),
            fx_rate_to_try=Decimal("1.47"),
            fx_rate_date=date(2026, 5, 4),
            fx_provider="yfinance:TWDUSD=X*USDTRY=X",
        )
    )
    session.commit()

    body = client.get("/api/portfolio").json()
    assert len(body["positions"]) == 3

    broken_row = next(p for p in body["positions"] if p["ticker"] == "2330")
    assert broken_row["ok"] is False
    assert broken_row["error"]

    # The other two rows are intact and the totals exclude the broken one.
    healthy = [p for p in body["positions"] if p["ticker"] != "2330"]
    assert all(p["ok"] for p in healthy)
    assert Decimal(body["totals"]["market_value_try"]) == sum(
        Decimal(p["market_value_try"]) for p in healthy
    )
    assert any("2330" in w for w in body["warnings"])

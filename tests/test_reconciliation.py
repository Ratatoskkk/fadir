"""Reconciliation golden-file test (SPEC §12) — "this is the regression net".

Drives the real engine over a frozen fixture and compares every figure against
`reconciliation_golden.json`, whose values were computed independently by
`scripts/make_golden.py` (which does not import `app.calc`). A divergence means either the
engine changed behaviour or the independent arithmetic disagrees — both worth failing on.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.calc import (
    MarketQuote,
    Side,
    TxnInput,
    build_lot_book,
    liquidation,
    summarise_portfolio,
)
from app.calc.attribution import position_metrics

FIXTURES = Path(__file__).parent / "fixtures"
INPUT = json.loads((FIXTURES / "reconciliation_input.json").read_text(encoding="utf-8"))
GOLDEN = json.loads((FIXTURES / "reconciliation_golden.json").read_text(encoding="utf-8"))

CENTS = Decimal("0.01")
RATIO = Decimal("0.000000001")


def _build():
    instruments = INPUT["instruments"]
    current_fx = {k: Decimal(v) for k, v in INPUT["current_fx"].items()}
    prices = {k: Decimal(v) for k, v in INPUT["current_prices"].items()}
    price_dates = {k: date.fromisoformat(v) for k, v in INPUT["price_dates"].items()}

    by_ticker: dict[str, list[TxnInput]] = {}
    for row in INPUT["transactions"]:
        ticker = row["ticker"]
        by_ticker.setdefault(ticker, []).append(
            TxnInput(
                id=row["id"],
                ticker=ticker,
                currency=instruments[ticker]["currency"],
                trade_date=date.fromisoformat(row["trade_date"]),
                side=Side(row["side"]),
                quantity=Decimal(row["quantity"]),
                price_native=Decimal(row["price_native"]),
                fees_native=Decimal(row["fees_native"]),
                fx_rate_to_try=Decimal(row["fx_rate_to_try"]),
                fx_rate_date=date.fromisoformat(row["fx_rate_date"]),
                fx_provider="fixture",
            )
        )

    metrics = {}
    for ticker, txns in by_ticker.items():
        currency = instruments[ticker]["currency"]
        book = build_lot_book(ticker, currency, txns)
        quote = MarketQuote(
            ticker=ticker,
            currency=currency,
            price_native=prices[ticker],
            price_date=price_dates[ticker],
            fx_rate_to_try=current_fx[currency],
            fx_rate_date=date.fromisoformat(INPUT["as_of"]),
            fx_provider="fixture",
        )
        metrics[ticker] = position_metrics(book, quote)
    return metrics


ENGINE = _build()
GOLDEN_POSITIONS = {p["ticker"]: p for p in GOLDEN["positions"]}


def test_golden_covers_every_position():
    assert set(ENGINE) == set(GOLDEN_POSITIONS)
    assert len(ENGINE) == 6


def test_fixture_holds_all_thirteen_seed_transactions():
    assert len(INPUT["transactions"]) == 13


@pytest.mark.parametrize("ticker", sorted(GOLDEN_POSITIONS))
def test_position_matches_golden(ticker):
    actual = ENGINE[ticker]
    expected = GOLDEN_POSITIONS[ticker]

    assert actual.currency == expected["currency"]
    assert actual.lot_count == expected["lot_count"]
    assert actual.quantity.quantize(CENTS) == Decimal(expected["quantity"])

    for attr in (
        "cost_native",
        "cost_try",
        "market_value_native",
        "market_value_try",
        "pnl_native",
        "pnl_try",
    ):
        assert getattr(actual, attr).quantize(CENTS) == Decimal(expected[attr]), attr


@pytest.mark.parametrize("ticker", sorted(GOLDEN_POSITIONS))
def test_attribution_matches_golden(ticker):
    a = ENGINE[ticker].attribution
    expected = GOLDEN_POSITIONS[ticker]

    assert a.weighted_avg_cost_fx_rate.quantize(Decimal("0.00000001")) == Decimal(
        expected["weighted_avg_cost_fx_rate"]
    )
    assert a.local_return.quantize(RATIO) == Decimal(expected["local_return"])
    assert a.fx_return.quantize(RATIO) == Decimal(expected["fx_return"])
    assert a.total_return.quantize(RATIO) == Decimal(expected["total_return"])
    assert a.price_effect_try.quantize(CENTS) == Decimal(expected["price_effect_try"])
    assert a.fx_effect_try.quantize(CENTS) == Decimal(expected["fx_effect_try"])


@pytest.mark.parametrize("ticker", sorted(GOLDEN_POSITIONS))
def test_identities_hold_for_every_position(ticker):
    """US-3.1 restated against the frozen fixture."""
    m = ENGINE[ticker]
    a = m.attribution
    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENTS
    assert abs(a.local_return * a.fx_return - a.total_return) < Decimal("1e-9")
    assert abs(a.total_return - m.market_value_try / m.cost_try) < Decimal("1e-9")


def test_totals_match_golden():
    totals = summarise_portfolio(list(ENGINE.values()))
    expected = GOLDEN["totals"]

    assert totals.cost_try.quantize(CENTS) == Decimal(expected["cost_try"])
    assert totals.market_value_try.quantize(CENTS) == Decimal(expected["market_value_try"])
    assert totals.pnl_try.quantize(CENTS) == Decimal(expected["pnl_try"])
    assert totals.price_effect_try.quantize(CENTS) == Decimal(expected["price_effect_try"])
    assert totals.fx_effect_try.quantize(CENTS) == Decimal(expected["fx_effect_try"])
    assert totals.total_return.quantize(RATIO) == Decimal(expected["total_return"])


def test_liquidation_matches_golden():
    totals = summarise_portfolio(list(ENGINE.values()))
    liq = liquidation(totals, Decimal("0"))
    expected = GOLDEN["liquidation"]

    assert liq.gross_proceeds_try.quantize(CENTS) == Decimal(expected["gross_proceeds_try"])
    assert liq.net_proceeds_try.quantize(CENTS) == Decimal(expected["net_proceeds_try"])
    assert liq.total_invested_try.quantize(CENTS) == Decimal(expected["total_invested_try"])
    assert liq.net_pnl_try.quantize(CENTS) == Decimal(expected["net_pnl_try"])


def test_the_fixture_exhibits_divergent_local_and_fx_returns():
    """The fixture must actually exercise the feature it exists to protect.

    A golden file where every position moves the same way would pass while the
    decomposition was broken. Here 2330 and SAP are down locally but up on FX.
    """
    down_locally_up_on_fx = [
        t
        for t, p in GOLDEN_POSITIONS.items()
        if Decimal(p["local_return"]) < 1 < Decimal(p["fx_return"])
    ]
    assert set(down_locally_up_on_fx) == {"2330", "IBM", "SAP"}

    # And at least one position where FX rescues a local loss into a smaller TRY loss.
    sap = GOLDEN_POSITIONS["SAP"]
    assert Decimal(sap["price_effect_try"]) < 0
    assert Decimal(sap["fx_effect_try"]) > 0


def test_golden_file_is_in_sync_with_its_generator():
    """Fails if the fixture changed but the golden was not regenerated."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[1] / "scripts" / "make_golden.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

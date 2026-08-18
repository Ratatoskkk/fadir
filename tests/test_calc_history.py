"""Historical series (SPEC §6, Epic 4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.calc import Side, build_history
from app.calc.history import PositionHistoryInput
from tests.conftest import txn

CENT = Decimal("0.01")


def _eric_positions():
    return [
        PositionHistoryInput(
            ticker="ERIC",
            currency="SEK",
            transactions=[
                txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "800", "20.00", "4.20"),
                txn(2, "ERIC", "SEK", "2026-04-15", Side.BUY, "800", "30.00", "4.35"),
            ],
        )
    ]


def test_only_lots_held_on_that_date_are_valued():
    """US-4.1: on 2026-04-10 only the 2026-03-29 lot is valued."""
    closes = {"ERIC": {date(2026, 4, 10): Decimal("15.00"), date(2026, 4, 20): Decimal("25.00")}}
    fx = {"SEK": {date(2026, 4, 10): Decimal("4.30"), date(2026, 4, 20): Decimal("4.40")}}

    points = build_history(
        _eric_positions(), closes, fx, date(2026, 4, 10), date(2026, 4, 20)
    )
    by_date = {p.point_date: p for p in points}

    early = by_date[date(2026, 4, 10)]
    # 800 shares only.
    assert early.value_try == Decimal("800") * Decimal("15.00") * Decimal("4.30")
    assert early.cost_basis_try == Decimal("16000.00") * Decimal("4.20")

    later = by_date[date(2026, 4, 20)]
    # Both lots now: 1,600 shares.
    assert later.value_try == Decimal("1600") * Decimal("25.00") * Decimal("4.40")


def test_prior_close_carried_forward_and_flagged():
    """US-4.1: on a non-trading day the prior close is carried forward and flagged."""
    closes = {"ERIC": {date(2026, 4, 10): Decimal("15.00")}}  # Friday only
    fx = {"SEK": {date(2026, 4, 10): Decimal("4.30")}}

    points = build_history(
        _eric_positions(), closes, fx, date(2026, 4, 10), date(2026, 4, 12)
    )
    by_date = {p.point_date: p for p in points}

    assert not by_date[date(2026, 4, 10)].price_carried_forward
    saturday = by_date[date(2026, 4, 11)]
    assert saturday.price_carried_forward
    assert saturday.fx_carried_forward
    # Value is unchanged because Friday's close and rate were reused, not interpolated.
    assert saturday.value_try == by_date[date(2026, 4, 10)].value_try


def test_carry_forward_stops_after_lookback_window():
    """Beyond the lookback the position is reported missing, never guessed."""
    closes = {"ERIC": {date(2026, 4, 10): Decimal("15.00")}}
    fx = {"SEK": {date(2026, 4, 10): Decimal("4.30")}}

    points = build_history(
        _eric_positions(),
        closes,
        fx,
        date(2026, 4, 10),
        date(2026, 4, 25),
        max_lookback_days=7,
    )
    by_date = {p.point_date: p for p in points}

    assert by_date[date(2026, 4, 17)].missing == ()
    far = by_date[date(2026, 4, 20)]
    assert far.missing == ("ERIC",)
    assert far.value_try == Decimal("0")


def test_three_series_decompose_exactly():
    """value_try - value_constant_fx == FX contribution; constant_fx - cost == price."""
    closes = {"ERIC": {date(2026, 5, 1): Decimal("30.00")}}
    fx = {"SEK": {date(2026, 5, 1): Decimal("5.00")}}

    point = build_history(
        _eric_positions(), closes, fx, date(2026, 5, 1), date(2026, 5, 1)
    )[0]

    assert point.price_effect_try + point.fx_effect_try == point.pnl_try
    assert point.value_try - point.value_constant_fx_try == point.fx_effect_try
    assert point.value_constant_fx_try - point.cost_basis_try == point.price_effect_try


def test_fx_gap_is_zero_when_rate_equals_cost_rate():
    """With FX flat at the cost rate, series one and two must coincide."""
    positions = [
        PositionHistoryInput(
            ticker="AAPL",
            currency="USD",
            transactions=[txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "12", "180.00", "40.00")],
        )
    ]
    closes = {"AAPL": {date(2026, 6, 1): Decimal("190.00")}}
    fx = {"USD": {date(2026, 6, 1): Decimal("40.00")}}

    point = build_history(positions, closes, fx, date(2026, 6, 1), date(2026, 6, 1))[0]
    assert point.value_try == point.value_constant_fx_try
    assert point.fx_effect_try == Decimal("0")


def test_series_starts_flat_before_inception():
    positions = _eric_positions()
    closes = {"ERIC": {date(2026, 3, 20): Decimal("10.00")}}
    fx = {"SEK": {date(2026, 3, 20): Decimal("4.20")}}

    points = build_history(positions, closes, fx, date(2026, 3, 20), date(2026, 3, 28))
    assert all(p.value_try == Decimal("0") for p in points)
    assert all(p.cost_basis_try == Decimal("0") for p in points)


def test_weekly_resample_takes_last_point_of_each_week():
    closes = {"ERIC": {date(2026, 4, 10) + __import__("datetime").timedelta(days=i): Decimal(15 + i) for i in range(14)}}
    fx = {"SEK": {date(2026, 4, 10) + __import__("datetime").timedelta(days=i): Decimal("4.30") for i in range(14)}}

    daily = build_history(_eric_positions(), closes, fx, date(2026, 4, 10), date(2026, 4, 23))
    weekly = build_history(
        _eric_positions(), closes, fx, date(2026, 4, 10), date(2026, 4, 23), freq="W"
    )

    assert len(daily) == 14
    assert len(weekly) < len(daily)
    # The final weekly point is the final daily point.
    assert weekly[-1].point_date == daily[-1].point_date
    assert weekly[-1].value_try == daily[-1].value_try


def test_multi_currency_history_aggregates():
    positions = [
        PositionHistoryInput(
            "ERIC",
            "SEK",
            [txn(1, "ERIC", "SEK", "2026-05-01", Side.BUY, "100", "20.00", "4.50")],
        ),
        PositionHistoryInput(
            "AAPL",
            "USD",
            [txn(2, "AAPL", "USD", "2026-05-01", Side.BUY, "10", "150.00", "40.00")],
        ),
    ]
    closes = {
        "ERIC": {date(2026, 6, 1): Decimal("25.00")},
        "AAPL": {date(2026, 6, 1): Decimal("180.00")},
    }
    fx = {
        "SEK": {date(2026, 6, 1): Decimal("5.00")},
        "USD": {date(2026, 6, 1): Decimal("45.00")},
    }

    point = build_history(positions, closes, fx, date(2026, 6, 1), date(2026, 6, 1))[0]
    expected = Decimal("100") * Decimal("25") * Decimal("5") + Decimal("10") * Decimal("180") * Decimal("45")
    assert point.value_try == expected
    assert point.price_effect_try + point.fx_effect_try == point.pnl_try


def test_sold_position_leaves_the_series():
    positions = [
        PositionHistoryInput(
            "IBM",
            "USD",
            [
                txn(1, "IBM", "USD", "2026-04-19", Side.BUY, "10", "100.00", "40.00"),
                txn(2, "IBM", "USD", "2026-05-10", Side.SELL, "10", "120.00", "42.00"),
            ],
        )
    ]
    closes = {"IBM": {d: Decimal("130.00") for d in [date(2026, 5, 9), date(2026, 5, 11)]}}
    fx = {"USD": {d: Decimal("43.00") for d in [date(2026, 5, 9), date(2026, 5, 11)]}}

    points = {
        p.point_date: p
        for p in build_history(positions, closes, fx, date(2026, 5, 9), date(2026, 5, 11))
    }
    assert points[date(2026, 5, 9)].value_try > 0
    # After the sale the position contributes nothing to open value or cost.
    assert points[date(2026, 5, 11)].value_try == Decimal("0")
    assert points[date(2026, 5, 11)].cost_basis_try == Decimal("0")

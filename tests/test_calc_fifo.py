"""FIFO lot matching (SPEC §6, §12 fixtures)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.calc import Side, build_lot_book
from app.calc.fifo import InsufficientLots
from tests.conftest import txn


def test_single_lot():
    book = build_lot_book(
        "ERIC", "SEK", [txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "800", "20.00", "4.50")]
    )
    assert book.quantity == Decimal("800")
    assert book.cost_native == Decimal("16000.00")
    assert book.cost_try == Decimal("72000.000")
    assert book.weighted_avg_cost_fx_rate == Decimal("4.50")
    assert book.disposals == []


def test_multi_lot_weighted_avg_fx_is_cost_weighted_not_qty_weighted():
    """SPEC §6: 'Weighted average cost FX rate is weighted by native cost, not quantity.'

    The two weightings give different answers here, so this genuinely discriminates.
    """
    book = build_lot_book(
        "ERIC",
        "SEK",
        [
            # 100 shares @ 10 = 1,000 native at rate 4.0
            txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "100", "10.00", "4.00"),
            # 100 shares @ 40 = 4,000 native at rate 5.0
            txn(2, "ERIC", "SEK", "2026-04-15", Side.BUY, "100", "40.00", "5.00"),
        ],
    )
    assert book.cost_native == Decimal("5000.00")
    # Quantity-weighted would be (4+5)/2 = 4.5. Cost-weighted is the correct 4.8.
    assert book.weighted_avg_cost_fx_rate == Decimal("4.8")
    assert book.cost_try == Decimal("24000.00")


def test_average_purchase_price_uses_all_purchase_quantities_prices_and_fees():
    book = build_lot_book(
        "IBM",
        "USD",
        [
            txn(1, "IBM", "USD", "2026-03-01", Side.BUY, "2", "100.00", "40.00", fees="10.00"),
            txn(2, "IBM", "USD", "2026-04-01", Side.BUY, "3", "200.00", "41.00", fees="15.00"),
        ],
    )

    # (2 x 100 + 10 + 3 x 200 + 15) / (2 + 3) = 165.
    assert book.average_purchase_price_native == Decimal("165.00")


def test_sales_do_not_change_the_lifetime_average_purchase_price():
    purchases = [
        txn(1, "IBM", "USD", "2026-03-01", Side.BUY, "2", "100.00", "40.00", fees="10.00"),
        txn(2, "IBM", "USD", "2026-04-01", Side.BUY, "3", "200.00", "41.00", fees="15.00"),
    ]
    partial = build_lot_book(
        "IBM",
        "USD",
        purchases
        + [txn(3, "IBM", "USD", "2026-05-01", Side.SELL, "2", "250.00", "42.00", fees="99.00")],
    )
    closed = build_lot_book(
        "IBM",
        "USD",
        purchases
        + [txn(3, "IBM", "USD", "2026-05-01", Side.SELL, "5", "250.00", "42.00", fees="99.00")],
    )

    assert partial.quantity == Decimal("3")
    assert partial.average_purchase_price_native == Decimal("165.00")
    assert closed.quantity == Decimal("0")
    assert closed.average_purchase_price_native == Decimal("165.00")


def test_average_purchase_price_is_absent_without_a_purchase():
    book = build_lot_book("IBM", "USD", [])
    assert book.average_purchase_price_native is None


def test_fifo_consumes_oldest_lot_first():
    book = build_lot_book(
        "ERIC",
        "SEK",
        [
            txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "100", "10.00", "4.00"),
            txn(2, "ERIC", "SEK", "2026-04-15", Side.BUY, "100", "20.00", "5.00"),
            txn(3, "ERIC", "SEK", "2026-05-20", Side.SELL, "100", "30.00", "6.00"),
        ],
    )
    assert len(book.disposals) == 1
    disposal = book.disposals[0]
    # The oldest lot (id 1, the 10.00 one) is the one consumed.
    assert disposal.lot_txn_id == 1
    assert disposal.cost_native == Decimal("1000.00")
    assert disposal.lot_fx_rate == Decimal("4.00")
    # Remaining open position is the second lot only.
    assert book.quantity == Decimal("100")
    assert book.cost_native == Decimal("2000.00")


def test_partial_sell_spans_two_lots():
    book = build_lot_book(
        "ERIC",
        "SEK",
        [
            txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "100", "10.00", "4.00"),
            txn(2, "ERIC", "SEK", "2026-04-15", Side.BUY, "100", "20.00", "5.00"),
            txn(3, "ERIC", "SEK", "2026-05-20", Side.SELL, "150", "30.00", "6.00"),
        ],
    )
    assert len(book.disposals) == 2
    assert book.disposals[0].quantity == Decimal("100")
    assert book.disposals[0].lot_txn_id == 1
    assert book.disposals[1].quantity == Decimal("50")
    assert book.disposals[1].lot_txn_id == 2
    assert book.quantity == Decimal("50")
    # Only half of lot 2 remains: 50 x 20.
    assert book.cost_native == Decimal("1000.00")


def test_realized_pnl_separates_price_and_fx():
    """A disposal's price and FX effects must sum to its TRY PnL."""
    book = build_lot_book(
        "AAPL",
        "USD",
        [
            txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00"),
            txn(2, "AAPL", "USD", "2026-07-01", Side.SELL, "10", "150.00", "45.00"),
        ],
    )
    d = book.disposals[0]
    assert d.cost_native == Decimal("1000.00")
    assert d.proceeds_native == Decimal("1500.00")
    assert d.pnl_native == Decimal("500.00")
    assert d.cost_try == Decimal("40000.00")
    assert d.proceeds_try == Decimal("67500.00")
    assert d.pnl_try == Decimal("27500.00")
    # 500 native gain valued at the entry rate.
    assert d.price_effect_try == Decimal("20000.00")
    # 1,500 native exposed to a 5.00 TRY/USD move.
    assert d.fx_effect_try == Decimal("7500.00")
    assert d.price_effect_try + d.fx_effect_try == d.pnl_try
    assert book.quantity == Decimal("0")


def test_fees_are_allocated_pro_rata_on_partial_consumption():
    book = build_lot_book(
        "IBM",
        "USD",
        [
            txn(1, "IBM", "USD", "2026-04-19", Side.BUY, "100", "10.00", "40.00", fees="50.00"),
            txn(2, "IBM", "USD", "2026-06-01", Side.SELL, "40", "12.00", "40.00"),
        ],
    )
    # 40 of 100 shares carry 40% of the 50.00 entry fee.
    assert book.disposals[0].cost_native == Decimal("420.00")
    # The remaining 60 keep the other 60%.
    assert book.cost_native == Decimal("630.00")


def test_zero_quantity_position_reports_no_basis():
    """Fully closed positions have no cost to divide by; nothing should blow up."""
    book = build_lot_book(
        "IBM",
        "USD",
        [
            txn(1, "IBM", "USD", "2026-04-19", Side.BUY, "10", "100.00", "40.00"),
            txn(2, "IBM", "USD", "2026-06-01", Side.SELL, "10", "110.00", "41.00"),
        ],
    )
    assert book.quantity == Decimal("0")
    assert book.cost_native == Decimal("0")
    assert book.weighted_avg_cost_fx_rate is None


def test_empty_transaction_list():
    book = build_lot_book("ERIC", "SEK", [])
    assert book.quantity == Decimal("0")
    assert book.cost_try == Decimal("0")
    assert book.weighted_avg_cost_fx_rate is None


def test_as_of_excludes_later_lots():
    """US-4.1: on 2026-04-10 only the 2026-03-29 lot exists."""
    transactions = [
        txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "800", "20.00", "4.50"),
        txn(2, "ERIC", "SEK", "2026-04-15", Side.BUY, "800", "30.00", "4.60"),
    ]
    early = build_lot_book("ERIC", "SEK", transactions, as_of=__import__("datetime").date(2026, 4, 10))
    assert early.quantity == Decimal("800")
    assert early.cost_native == Decimal("16000.00")

    later = build_lot_book("ERIC", "SEK", transactions, as_of=__import__("datetime").date(2026, 4, 20))
    assert later.quantity == Decimal("1600")


def test_same_day_buy_then_sell_matches():
    """BUY is ordered before SELL on a shared date, so a same-day round trip works."""
    book = build_lot_book(
        "KO",
        "USD",
        [
            txn(2, "KO", "USD", "2026-05-11", Side.SELL, "5", "95.00", "40.00"),
            txn(1, "KO", "USD", "2026-05-11", Side.BUY, "5", "90.00", "40.00"),
        ],
    )
    assert len(book.disposals) == 1
    assert book.quantity == Decimal("0")


def test_running_totals_never_drift_from_a_full_recomputation():
    """The open-position totals are maintained incrementally for speed.

    That is only safe if they track a full recomputation to a precision far finer than
    money. They cannot always match bit for bit: allocating an indivisible fee across
    shares requires a division, so a lot with 11 lira of fees over 3 shares carries a
    repeating decimal, and subtracting partial takes rounds differently from summing the
    remainder fresh. Observed drift is around the 49th significant digit — roughly
    1e-43 relative, or about 1e-38 of a kuruş.

    The tolerance below is many orders of magnitude tighter than any figure that could
    ever reach a user, while still admitting the unavoidable rounding. The exact-zero
    case is pinned separately in the next test.
    """
    import random

    random.seed(20260801)

    for trial in range(200):
        transactions = []
        txn_id = 0
        held = Decimal("0")
        day = 1

        for _ in range(random.randint(1, 12)):
            txn_id += 1
            day += random.randint(1, 5)
            trade_date = f"2026-01-{day:02d}" if day <= 28 else f"2026-02-{day - 28:02d}"

            # Bias towards buys so there is usually inventory to sell.
            if held > 0 and random.random() < 0.35:
                qty = (held * Decimal(random.randint(1, 100)) / Decimal(100)).quantize(
                    Decimal("0.001")
                )
                if qty <= 0:
                    continue
                transactions.append(
                    txn(
                        txn_id, "X", "USD", trade_date, Side.SELL,
                        str(qty), str(random.randint(50, 300)),
                        str(random.randint(20, 60)),
                        fees=str(random.choice([0, 3, 7, 11])),
                    )
                )
                held -= qty
            else:
                qty = Decimal(random.randint(1, 300))
                transactions.append(
                    txn(
                        txn_id, "X", "USD", trade_date, Side.BUY,
                        str(qty), str(random.randint(50, 300)),
                        str(random.randint(20, 60)),
                        # 7 and 11 divide badly into most share counts.
                        fees=str(random.choice([0, 7, 11, 50])),
                    )
                )
                held += qty

        book = build_lot_book("X", "USD", transactions)
        expected_qty, expected_native, expected_try = book._recompute_totals()

        def close_enough(actual: Decimal, expected: Decimal) -> bool:
            tolerance = max(Decimal("1e-25"), abs(expected) * Decimal("1e-38"))
            return abs(actual - expected) <= tolerance

        # Quantity involves no division, so it must be exact.
        assert book.quantity == expected_qty, f"trial {trial}: quantity drifted"
        assert close_enough(book.cost_native, expected_native), (
            f"trial {trial}: cost_native drifted "
            f"{book.cost_native} vs {expected_native}"
        )
        assert close_enough(book.cost_try, expected_try), (
            f"trial {trial}: cost_try drifted {book.cost_try} vs {expected_try}"
        )
        # And the drift must never be visible at money scale.
        assert abs(book.cost_try - expected_try) < Decimal("0.000001")


def test_totals_are_exactly_zero_after_selling_everything():
    """A fully closed position must land on exact zero, not a residual dust amount."""
    book = build_lot_book(
        "X",
        "USD",
        [
            txn(1, "X", "USD", "2026-01-05", Side.BUY, "3", "100.00", "40.00", fees="7"),
            txn(2, "X", "USD", "2026-01-06", Side.BUY, "7", "133.33", "41.00", fees="11"),
            txn(3, "X", "USD", "2026-02-01", Side.SELL, "4", "150.00", "42.00"),
            txn(4, "X", "USD", "2026-02-02", Side.SELL, "6", "160.00", "43.00"),
        ],
    )
    assert book.quantity == Decimal("0")
    assert book.cost_native == Decimal("0")
    assert book.cost_try == Decimal("0")
    assert book.weighted_avg_cost_fx_rate is None


def test_oversell_raises():
    with pytest.raises(InsufficientLots):
        build_lot_book(
            "ERIC",
            "SEK",
            [
                txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "10", "10.00", "4.00"),
                txn(2, "ERIC", "SEK", "2026-04-01", Side.SELL, "20", "12.00", "4.00"),
            ],
        )

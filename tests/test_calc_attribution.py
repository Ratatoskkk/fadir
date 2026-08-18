"""Return attribution (SPEC §6, US-3.1, US-3.2).

The two identities the spec demands:

    price_effect_try + fx_effect_try == pnl_try          (within 0.01)
    local_return x fx_return         == total_return     (within 1e-9)

Both hold exactly here, so the tolerances are headroom rather than necessity.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.calc import Side, attribute, build_lot_book, liquidation, summarise_portfolio
from app.calc.attribution import position_metrics
from tests.conftest import quote, txn

CENT = Decimal("0.01")
TIGHT = Decimal("1e-9")


def _book_and_quote(txns, ticker, currency, price, fx):
    book = build_lot_book(ticker, currency, txns)
    return book, quote(ticker, currency, price, fx)


def test_attribution_identity_simple():
    book, q = _book_and_quote(
        [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "12", "180.00", "38.00")],
        "AAPL",
        "USD",
        "190.41",
        "47.507801",
    )
    m = position_metrics(book, q)
    a = m.attribution

    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENT
    assert abs(a.local_return * a.fx_return - a.total_return) < TIGHT
    # total_return must also equal mv_try / cost_try.
    assert abs(a.total_return - m.market_value_try / m.cost_try) < TIGHT


def test_attribution_identity_multi_lot():
    book, q = _book_and_quote(
        [
            txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "800", "20.00", "4.20"),
            txn(2, "ERIC", "SEK", "2026-04-15", Side.BUY, "800", "30.00", "4.35"),
            txn(3, "ERIC", "SEK", "2026-05-07", Side.BUY, "440", "50.00", "4.70"),
        ],
        "ERIC",
        "SEK",
        "30.24",
        "4.99593",
    )
    m = position_metrics(book, q)
    a = m.attribution
    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENT
    assert abs(a.local_return * a.fx_return - a.total_return) < TIGHT


def test_negative_price_effect_positive_fx_effect():
    """Down in local currency, up in TRY — the case that motivates the whole design."""
    book, q = _book_and_quote(
        [txn(1, "ERIC", "SEK", "2026-03-29", Side.BUY, "100", "50.00", "4.00")],
        "ERIC",
        "SEK",
        "40.00",  # -20% in SEK
        "6.00",  # +50% FX
    )
    m = position_metrics(book, q)
    a = m.attribution

    assert a.local_return == Decimal("0.8")
    assert a.fx_return == Decimal("1.5")
    assert a.total_return == Decimal("1.2")  # up 20% in TRY despite the SEK loss
    assert m.pnl_native < 0
    assert m.pnl_try > 0
    assert a.price_effect_try < 0
    assert a.fx_effect_try > 0
    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENT


def test_try_strengthening_negative_fx_effect():
    """SPEC §12: 'FX effect negative while price effect positive — must be explicitly
    tested, not assumed.'

    The lira strengthens against USD (rate falls 40 -> 34) while the stock rises.
    """
    book, q = _book_and_quote(
        [txn(1, "IBM", "USD", "2026-04-19", Side.BUY, "100", "100.00", "40.00")],
        "IBM",
        "USD",
        "120.00",  # +20% in USD
        "34.00",  # TRY strengthens 15%
    )
    m = position_metrics(book, q)
    a = m.attribution

    assert a.local_return == Decimal("1.2")
    assert a.fx_return == Decimal("0.85")
    assert a.total_return == Decimal("1.02")

    assert m.pnl_native > 0
    assert a.price_effect_try > 0  # +2,000 USD valued at the 40.00 entry rate
    assert a.fx_effect_try < 0  # 12,000 USD exposed to a -6.00 move
    assert a.price_effect_try == Decimal("80000.00")
    assert a.fx_effect_try == Decimal("-72000.00")
    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENT
    # Net still positive, but only just — exactly the nuance a blended figure hides.
    assert m.pnl_try == Decimal("8000.00")


def test_both_effects_negative():
    book, q = _book_and_quote(
        [txn(1, "SAP", "EUR", "2026-04-29", Side.BUY, "38", "25.00", "50.00")],
        "SAP",
        "EUR",
        "14.20",
        "45.00",
    )
    m = position_metrics(book, q)
    a = m.attribution
    assert a.price_effect_try < 0
    assert a.fx_effect_try < 0
    assert m.pnl_try < 0
    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENT


def test_weekend_trade_date_carries_fx_forward():
    """A Sunday purchase uses Friday's rate, and says so."""
    t = txn(
        1,
        "ERIC",
        "SEK",
        "2026-03-29",  # Sunday
        Side.BUY,
        "800",
        "20.00",
        "4.50",
        fx_rate_date="2026-03-27",  # Friday
    )
    assert t.fx_carried_forward
    book = build_lot_book("ERIC", "SEK", [t])
    # The carried rate is the one that prices the lot — no interpolation.
    assert book.open_lots[0].fx_rate_to_try == Decimal("4.50")
    assert book.open_lots[0].fx_rate_date.isoformat() == "2026-03-27"


def test_fx_carried_forward_flag_comes_from_the_resolver_not_a_date_comparison():
    """FX and equity calendars differ legitimately, so the flag cannot be inferred.

    A Friday close with a Saturday FX quote is normal, not a carry-forward. Only the
    resolver knows whether the rate it returned was published on the date requested.
    """
    book = build_lot_book(
        "AAPL", "USD", [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00")]
    )

    # Dates differ, but nothing was carried forward.
    normal = position_metrics(
        book,
        quote("AAPL", "USD", "150.00", "45.00", price_date="2026-07-31", fx_rate_date="2026-08-01"),
    )
    assert normal.fx_carried_forward is False

    genuinely_carried = position_metrics(
        book,
        quote(
            "AAPL",
            "USD",
            "150.00",
            "45.00",
            price_date="2026-07-31",
            fx_rate_date="2026-07-24",
            fx_carried_forward=True,
        ),
    )
    assert genuinely_carried.fx_carried_forward is True


def test_closed_position_has_no_return():
    """No basis to divide by: report nothing rather than a misleading 0%."""
    book = build_lot_book(
        "IBM",
        "USD",
        [
            txn(1, "IBM", "USD", "2026-04-19", Side.BUY, "10", "100.00", "40.00"),
            txn(2, "IBM", "USD", "2026-06-01", Side.SELL, "10", "110.00", "41.00"),
        ],
    )
    a = attribute(book, quote("IBM", "USD", "120.00", "42.00"))
    assert a.local_return is None
    assert a.fx_return is None
    assert a.total_return is None
    assert a.price_effect_try == Decimal("0")
    assert a.fx_effect_try == Decimal("0")


def test_portfolio_totals_sum_the_identity():
    positions = []
    for t, ccy, price, fx in [
        ("AAPL", "USD", "190.41", "47.5"),
        ("ERIC", "SEK", "30.24", "4.99"),
        ("SAP", "EUR", "14.20", "54.77"),
    ]:
        book = build_lot_book(
            t, ccy, [txn(1, t, ccy, "2026-05-01", Side.BUY, "10", "100.00", "40.00")]
        )
        positions.append(position_metrics(book, quote(t, ccy, price, fx)))

    totals = summarise_portfolio(positions)
    assert abs(totals.price_effect_try + totals.fx_effect_try - totals.pnl_try) < CENT
    assert abs(totals.total_return - totals.market_value_try / totals.cost_try) < TIGHT


def test_failed_position_excluded_from_totals():
    """US-5.3: an unpriced row must not count as zero market value."""
    good_book = build_lot_book(
        "AAPL", "USD", [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00")]
    )
    bad_book = build_lot_book(
        "2330", "TWD", [txn(2, "2330", "TWD", "2026-05-04", Side.BUY, "39", "1000.00", "1.47")]
    )
    good = position_metrics(good_book, quote("AAPL", "USD", "150.00", "45.00"))
    bad = position_metrics(
        bad_book,
        quote("2330", "TWD", "0", "1.47", ok=False, error="no price data"),
    )

    totals = summarise_portfolio([good, bad])
    # Only the priced position contributes.
    assert totals.cost_try == good.cost_try
    assert totals.market_value_try == good.market_value_try


def test_liquidation_default_zero_haircut():
    book = build_lot_book(
        "AAPL", "USD", [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00")]
    )
    totals = summarise_portfolio([position_metrics(book, quote("AAPL", "USD", "150.00", "45.00"))])
    liq = liquidation(totals)

    assert liq.gross_proceeds_try == Decimal("67500.00")
    assert liq.haircut_try == Decimal("0")
    assert liq.net_proceeds_try == Decimal("67500.00")
    assert liq.total_invested_try == Decimal("40000.00")
    assert liq.net_pnl_try == Decimal("27500.00")
    assert liq.excludes_tax


def test_liquidation_with_haircut():
    book = build_lot_book(
        "AAPL", "USD", [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, "10", "100.00", "40.00")]
    )
    totals = summarise_portfolio([position_metrics(book, quote("AAPL", "USD", "150.00", "45.00"))])
    liq = liquidation(totals, Decimal("0.005"))

    assert liq.haircut_try == Decimal("337.500")
    assert liq.net_proceeds_try == Decimal("67162.500")
    assert liq.net_pnl_try == Decimal("27162.500")


@pytest.mark.parametrize(
    "price,fx",
    [
        ("190.41", "47.507801"),
        ("0.01", "0.0001"),
        ("99999.99", "1234.5678"),
        ("20.00", "4.995930"),
    ],
)
def test_identity_holds_across_magnitudes(price, fx):
    """No float creeping in at any scale."""
    book = build_lot_book(
        "X", "USD", [txn(1, "X", "USD", "2026-05-01", Side.BUY, "7", "123.45", "38.7654321")]
    )
    m = position_metrics(book, quote("X", "USD", price, fx))
    a = m.attribution
    assert abs(a.price_effect_try + a.fx_effect_try - m.pnl_try) < CENT
    assert abs(a.local_return * a.fx_return - a.total_return) < TIGHT


# -- daily change ---------------------------------------------------------------------


def _daily_book(quantity="10", cost="100.00", cost_fx="30.00"):
    return build_lot_book(
        "AAPL",
        "USD",
        [txn(1, "AAPL", "USD", "2026-05-11", Side.BUY, quantity, cost, cost_fx)],
    )


def test_daily_change_decomposes_exactly_like_the_lifetime_attribution():
    """price_effect + fx_effect == pnl_try, same identity, same exactness."""
    book = _daily_book()
    m = position_metrics(
        book,
        quote(
            "AAPL",
            "USD",
            "110.00",
            "40.00",
            prev_price="100.00",
            prev_fx="38.00",
            prev_price_date="2026-07-31",
        ),
    )
    d = m.daily

    assert d.available is True
    assert d.reference_date.isoformat() == "2026-07-31"

    # 10 x 110 x 40 = 44,000 against 10 x 100 x 38 = 38,000
    assert d.pnl_try == Decimal("6000.00")
    # price: 10 x (110-100) x 38 = 3,800   fx: 10 x 110 x (40-38) = 2,200
    assert d.price_effect_try == Decimal("3800.00")
    assert d.fx_effect_try == Decimal("2200.00")
    assert d.price_effect_try + d.fx_effect_try == d.pnl_try
    assert d.pnl_native == Decimal("100.00")  # 10 x (110 - 100), no FX in it


def test_daily_change_isolates_a_pure_currency_move():
    """§12 in miniature: flat in USD, up in TRY, and the split says so."""
    book = _daily_book()
    m = position_metrics(
        book,
        quote("AAPL", "USD", "100.00", "40.00", prev_price="100.00", prev_fx="38.00"),
    )
    d = m.daily

    assert d.pnl_native == Decimal("0")
    assert d.price_effect_try == Decimal("0")
    assert d.fx_effect_try == Decimal("2000.00")
    assert d.pnl_try == Decimal("2000.00")


def test_daily_change_can_be_negative_on_price_while_positive_on_fx():
    book = _daily_book()
    d = position_metrics(
        book,
        quote("AAPL", "USD", "90.00", "45.00", prev_price="100.00", prev_fx="38.00"),
    ).daily

    assert d.price_effect_try < 0
    assert d.fx_effect_try > 0
    assert d.price_effect_try + d.fx_effect_try == d.pnl_try


def test_no_previous_session_reports_unavailable_not_zero():
    """"No data" and "did not move" are different claims and must not be conflated."""
    d = position_metrics(_daily_book(), quote("AAPL", "USD", "110.00", "40.00")).daily

    assert d.available is False
    assert d.reference_date is None
    assert d.return_ratio is None


def test_daily_change_is_unavailable_for_an_unpriced_position():
    d = position_metrics(
        _daily_book(),
        quote("AAPL", "USD", "0", "0", ok=False, prev_price="100.00", prev_fx="38.00"),
    ).daily
    assert d.available is False


def test_portfolio_daily_skips_positions_with_no_previous_session():
    """A position with no history contributes nothing, rather than a zero that dilutes."""
    with_history = position_metrics(
        _daily_book(),
        quote(
            "AAPL", "USD", "110.00", "40.00",
            prev_price="100.00", prev_fx="38.00", prev_price_date="2026-07-31",
        ),
    )
    without = position_metrics(
        build_lot_book(
            "IBM", "USD", [txn(2, "IBM", "USD", "2026-05-11", Side.BUY, "5", "50.00", "30.00")]
        ),
        quote("IBM", "USD", "60.00", "40.00"),
    )

    totals = summarise_portfolio([with_history, without])
    d = totals.daily

    assert d.available is True
    assert d.pnl_try == Decimal("6000.00")  # IBM adds nothing
    assert d.price_effect_try + d.fx_effect_try == d.pnl_try
    # 44,000 / 38,000 — the ratio is against the moving position only.
    assert abs(d.return_ratio - Decimal("44000") / Decimal("38000")) < TIGHT


def test_portfolio_daily_reference_date_is_the_earliest_session_represented():
    """Exchanges close at different times and a dropped NaN close (F-4) widens the gap.

    Labelling the aggregate with the *latest* date would claim a shorter window than the
    figure actually covers.
    """
    a = position_metrics(
        _daily_book(),
        quote(
            "AAPL", "USD", "110.00", "40.00",
            prev_price="100.00", prev_fx="38.00", prev_price_date="2026-07-31",
        ),
    )
    b = position_metrics(
        build_lot_book(
            "ERIC", "SEK", [txn(2, "ERIC", "SEK", "2026-03-29", Side.BUY, "100", "11.00", "4.00")]
        ),
        quote(
            "ERIC", "SEK", "30.00", "5.00",
            prev_price="29.00", prev_fx="4.90", prev_price_date="2026-07-30",
        ),
    )

    totals = summarise_portfolio([a, b])
    assert totals.daily.reference_date.isoformat() == "2026-07-30"

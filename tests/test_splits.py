"""Split handling (SPEC §5, US-2.2).

Both halves of the rule are proven here against synthetic splits, because whether a live
instrument happens to have split in the right window is an accident of the calendar and
not something a test may depend on (docs/FINDINGS.md F-3).

A split **after** a purchase must adjust that lot. A split **before** every purchase must
not: a trade executed after the ex-date already sits on the post-split basis, so adjusting
it again would overstate the position by the split ratio. That is the exact corruption §5
exists to prevent, and it is the case that shows up in real data far more often.

The machinery under test is entirely generic, as §5 requires — assume every instrument may
split, and special-case none of them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.config import get_settings
from app.models import ActionKind, CorporateAction, Instrument, Side, Transaction
from app.providers.price_service import PriceService


@pytest.fixture
def instrument(session):
    inst = Instrument(
        ticker="KO",
        exchange="NYSE",
        yf_symbol="KO",
        currency="USD",
        name="Coca-Cola Co",
        active=True,
    )
    session.add(inst)
    session.flush()
    return inst


def _add_txn(session, instrument, trade_date: str, qty: str, price: str) -> Transaction:
    t = Transaction(
        instrument_id=instrument.id,
        trade_date=date.fromisoformat(trade_date),
        side=Side.BUY,
        quantity=Decimal(qty),
        price_native=Decimal(price),
        fees_native=Decimal("0"),
        fx_rate_to_try=Decimal("40.00"),
        fx_rate_date=date.fromisoformat(trade_date),
        fx_provider="yfinance",
    )
    session.add(t)
    session.flush()
    return t


def _add_split(session, instrument, action_date: str, ratio: str) -> CorporateAction:
    action = CorporateAction(
        instrument_id=instrument.id,
        action_date=date.fromisoformat(action_date),
        kind=ActionKind.SPLIT,
        ratio=Decimal(ratio),
        applied_to_transactions=False,
    )
    session.add(action)
    session.flush()
    return action


def test_cost_basis_native_is_invariant_across_a_split(session, instrument):
    """US-2.2: cost_native unchanged and quantity x price_native invariant."""
    t1 = _add_txn(session, instrument, "2026-05-11", "12", "90.00")
    t2 = _add_txn(session, instrument, "2026-05-20", "8", "96.00")
    before = t1.quantity * t1.price_native + t2.quantity * t2.price_native

    _add_split(session, instrument, "2026-06-15", "5")
    session.refresh(instrument)

    service = PriceService(session, get_settings())
    adjusted = service.apply_pending_splits(instrument)

    assert adjusted == 2
    session.refresh(t1)
    session.refresh(t2)

    assert t1.quantity == Decimal("60")
    assert t1.price_native == Decimal("18.00")
    assert t2.quantity == Decimal("40")
    assert t2.price_native == Decimal("19.20")

    after = t1.quantity * t1.price_native + t2.quantity * t2.price_native
    assert after == before


def test_applying_the_same_split_twice_is_a_no_op(session, instrument):
    """US-2.2: 'Given adjustment runs twice, then the second run is a no-op.'"""
    t1 = _add_txn(session, instrument, "2026-05-11", "12", "90.00")
    _add_split(session, instrument, "2026-06-15", "5")
    session.refresh(instrument)

    service = PriceService(session, get_settings())
    assert service.apply_pending_splits(instrument) == 1

    session.refresh(t1)
    qty_after_first = t1.quantity
    price_after_first = t1.price_native

    # Second run must change nothing.
    assert service.apply_pending_splits(instrument) == 0
    session.refresh(t1)
    assert t1.quantity == qty_after_first
    assert t1.price_native == price_after_first


def test_split_before_purchase_is_not_applied(session, instrument):
    """The common real-data shape (docs/FINDINGS.md F-3): the split predates every trade.

    A trade executed after the ex-date is already on the post-split basis, so touching it
    would corrupt the position — here, 30 shares at 90.00 would become 150 at 18.00
    against a live price near 100.
    """
    t1 = _add_txn(session, instrument, "2025-05-12", "20", "90.00")
    t2 = _add_txn(session, instrument, "2025-05-20", "10", "96.00")
    _add_split(session, instrument, "2024-12-18", "5")  # ex-date before both trades
    session.refresh(instrument)

    service = PriceService(session, get_settings())
    adjusted = service.apply_pending_splits(instrument)

    assert adjusted == 0
    session.refresh(t1)
    session.refresh(t2)
    assert t1.quantity == Decimal("20")
    assert t1.price_native == Decimal("90.00")
    assert t2.quantity == Decimal("10")
    assert t2.price_native == Decimal("96.00")

    # The action is still marked applied, so it is never reconsidered.
    action = session.query(CorporateAction).one()
    assert action.applied_to_transactions is True


def test_split_applies_only_to_transactions_before_the_ex_date(session, instrument):
    early = _add_txn(session, instrument, "2026-05-11", "12", "90.00")
    late = _add_txn(session, instrument, "2026-07-01", "10", "20.00")
    _add_split(session, instrument, "2026-06-15", "5")
    session.refresh(instrument)

    PriceService(session, get_settings()).apply_pending_splits(instrument)
    session.refresh(early)
    session.refresh(late)

    assert early.quantity == Decimal("60")
    assert late.quantity == Decimal("10")  # untouched
    assert late.price_native == Decimal("20.00")


def test_two_sequential_splits_compound_correctly(session, instrument):
    """A 2-for-1 then a 3-for-1, applied oldest first.

    100.00 / 2 / 3 is a non-terminating decimal, so the basis cannot be preserved to the
    last bit in any finite representation. What must hold — and does — is invariance at
    money scale: the residual here is ~2e-11 on a 1,000 basis.
    """
    t1 = _add_txn(session, instrument, "2026-04-01", "10", "100.00")
    before = t1.quantity * t1.price_native

    _add_split(session, instrument, "2026-05-01", "2")
    _add_split(session, instrument, "2026-06-01", "3")
    session.refresh(instrument)

    PriceService(session, get_settings()).apply_pending_splits(instrument)
    session.refresh(t1)

    assert t1.quantity == Decimal("60")
    assert abs(t1.price_native * t1.quantity - before) < Decimal("0.01")


def test_clean_ratio_splits_are_bit_exact(session, instrument):
    """Ratios that terminate in decimal must preserve the basis exactly, not approximately."""
    for ratio, qty, price in [("2", "10", "100.00"), ("5", "12", "90.00"), ("4", "7", "25.25")]:
        inst = Instrument(
            ticker=f"T{ratio}",
            exchange="NYSE",
            yf_symbol=f"T{ratio}",
            currency="USD",
            name=f"Test {ratio}",
        )
        session.add(inst)
        session.flush()

        t = _add_txn(session, inst, "2026-04-01", qty, price)
        before = t.quantity * t.price_native
        _add_split(session, inst, "2026-05-01", ratio)
        session.refresh(inst)

        PriceService(session, get_settings()).apply_pending_splits(inst)
        session.refresh(t)
        assert t.quantity * t.price_native == before, f"ratio {ratio} drifted"


def test_reverse_split_preserves_basis(session, instrument):
    """A 1-for-10 reverse split arrives as ratio 0.1."""
    t1 = _add_txn(session, instrument, "2026-04-01", "1000", "2.00")
    before = t1.quantity * t1.price_native

    _add_split(session, instrument, "2026-05-01", "0.1")
    session.refresh(instrument)

    PriceService(session, get_settings()).apply_pending_splits(instrument)
    session.refresh(t1)

    assert t1.quantity == Decimal("100")
    assert t1.price_native == Decimal("20.00")
    assert t1.quantity * t1.price_native == before


def test_duplicate_split_rows_are_rejected_by_the_constraint(session, instrument):
    """The uniqueness guard from SPEC §5.4."""
    from sqlalchemy.exc import IntegrityError

    _add_split(session, instrument, "2026-06-15", "5")
    with pytest.raises(IntegrityError):
        _add_split(session, instrument, "2026-06-15", "5")
    session.rollback()


def test_sync_splits_is_idempotent(session, instrument, monkeypatch):
    """Re-syncing the same Yahoo response must not duplicate corporate actions."""
    from app.providers import price_service as ps
    from app.providers.base import SplitEvent

    monkeypatch.setattr(
        ps.yf_client,
        "fetch_splits",
        lambda symbol: [SplitEvent(action_date=date(2025, 12, 18), ratio=Decimal("5"))],
    )

    service = PriceService(session, get_settings())
    assert service.sync_splits(instrument) == 1
    assert service.sync_splits(instrument) == 0
    assert session.query(CorporateAction).count() == 1

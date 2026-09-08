from datetime import date
from decimal import Decimal

from app.calc.fifo import build_lot_book
from app.calc.types import Side, TxnInput
from app.schemas import TransactionOut


def test_foreign_fee_is_preserved_and_converted_for_fifo_cost():
    txn = TxnInput(
        id=1,
        ticker="ABC",
        currency="USD",
        trade_date=date(2026, 1, 2),
        side=Side.BUY,
        quantity=Decimal("2"),
        price_native=Decimal("10"),
        fees_native=Decimal("3"),
        fx_rate_to_try=Decimal("30"),
        fx_rate_date=date(2026, 1, 2),
        fx_provider="manual",
        fee_currency="EUR",
        fee_fx_rate_to_try=Decimal("33"),
        fee_fx_rate_date=date(2026, 1, 2),
        fee_fx_provider="manual",
    )

    book = build_lot_book("ABC", "USD", [txn])

    assert txn.fee_currency == "EUR"
    assert book.cost_native == Decimal("23.30")


def test_legacy_fee_defaults_to_instrument_currency():
    txn = TxnInput(
        id=1, ticker="ABC", currency="USD", trade_date=date(2026, 1, 2),
        side=Side.BUY, quantity=Decimal("1"), price_native=Decimal("10"),
        fees_native=Decimal("2"), fx_rate_to_try=Decimal("30"),
        fx_rate_date=date(2026, 1, 2), fx_provider="manual",
    )
    assert txn.fee_native_equivalent == Decimal("2")


def test_fee_metadata_uses_string_money_serialization():
    payload = TransactionOut(
        id=1, instrument_id=2, ticker="ABC", currency="USD",
        trade_date=date(2026, 1, 2), side="BUY", quantity=Decimal("1"),
        price_native=Decimal("10"), fees_native=Decimal("3"),
        fee_currency="EUR", fee_fx_rate_to_try=Decimal("33"),
        fee_fx_rate_date=date(2026, 1, 2), fee_fx_provider="manual",
        total_native=Decimal("10"), fx_rate_to_try=Decimal("30"),
        fx_rate_date=date(2026, 1, 2), fx_provider="manual",
        fx_carried_forward=False, total_try=Decimal("399"), note=None,
    )
    assert payload.model_dump(mode="json")["fee_fx_rate_to_try"] == "33"

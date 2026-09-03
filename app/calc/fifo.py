"""FIFO lot matching (SPEC §6, "Cost basis").

Each SELL consumes the oldest open lots. Every disposal carries the *original lot's* FX
rate alongside the sale's FX rate, which is what makes realized FX gain separable from
realized price gain — the same decomposition the unrealized attribution uses, so the two
are directly comparable.

Fees are allocated pro-rata across a lot's shares, so a partial consumption takes a
proportional share of the entry cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext

from app.calc.types import CALC_PRECISION, ZERO, Side, TxnInput


class InsufficientLots(ValueError):
    """A SELL tried to consume more shares than were open."""


@dataclass
class Lot:
    """An open (or partially consumed) purchase lot."""

    txn_id: int
    trade_date: date
    quantity_original: Decimal
    quantity_open: Decimal
    price_native: Decimal
    fees_native: Decimal
    fx_rate_to_try: Decimal
    fx_rate_date: date
    fx_provider: str

    @property
    def fee_per_unit(self) -> Decimal:
        if self.quantity_original == ZERO:
            return ZERO
        return self.fees_native / self.quantity_original

    def cost_native_for(self, quantity: Decimal) -> Decimal:
        """Entry cost of `quantity` shares from this lot, fees included."""
        return quantity * self.price_native + quantity * self.fee_per_unit

    @property
    def cost_native_open(self) -> Decimal:
        return self.cost_native_for(self.quantity_open)

    @property
    def cost_try_open(self) -> Decimal:
        """Derived at read time from native cost x the lot's own rate (SPEC §0)."""
        return self.cost_native_open * self.fx_rate_to_try


@dataclass(frozen=True)
class Disposal:
    """One SELL consuming one lot."""

    sell_txn_id: int
    sell_date: date
    lot_txn_id: int
    lot_date: date
    quantity: Decimal

    cost_native: Decimal
    proceeds_native: Decimal
    lot_fx_rate: Decimal
    sell_fx_rate: Decimal

    @property
    def pnl_native(self) -> Decimal:
        return self.proceeds_native - self.cost_native

    @property
    def cost_try(self) -> Decimal:
        return self.cost_native * self.lot_fx_rate

    @property
    def proceeds_try(self) -> Decimal:
        return self.proceeds_native * self.sell_fx_rate

    @property
    def pnl_try(self) -> Decimal:
        return self.proceeds_try - self.cost_try

    @property
    def price_effect_try(self) -> Decimal:
        """Gain attributable to the local price move, valued at the entry rate."""
        return (self.proceeds_native - self.cost_native) * self.lot_fx_rate

    @property
    def fx_effect_try(self) -> Decimal:
        """Gain attributable to the currency move over the holding period."""
        return self.proceeds_native * (self.sell_fx_rate - self.lot_fx_rate)


@dataclass(frozen=True)
class RealizedPnl:
    quantity: Decimal
    cost_native: Decimal
    proceeds_native: Decimal
    pnl_native: Decimal
    cost_try: Decimal
    proceeds_try: Decimal
    pnl_try: Decimal
    price_effect_try: Decimal
    fx_effect_try: Decimal


@dataclass
class LotBook:
    """Result of replaying a ticker's transactions in trade-date order.

    Open-position totals are maintained incrementally as transactions are applied
    rather than re-summed on every read. The history builder reads them once per
    position per day, so re-summing turned a cheap lookup into O(open lots) of Decimal
    work per access — the dominant cost of building a long series.

    `_recompute_totals` re-derives the same figures the slow way and is used by the
    tests to prove the running totals never drift from a full recomputation.
    """

    ticker: str
    currency: str
    open_lots: list[Lot] = field(default_factory=list)
    disposals: list[Disposal] = field(default_factory=list)

    _quantity: Decimal = ZERO
    _cost_native: Decimal = ZERO
    _cost_try: Decimal = ZERO
    _purchase_quantity: Decimal = ZERO
    _purchase_cost_native: Decimal = ZERO

    # -- open position -------------------------------------------------------------

    @property
    def quantity(self) -> Decimal:
        return self._quantity

    @property
    def cost_native(self) -> Decimal:
        return self._cost_native

    @property
    def cost_try(self) -> Decimal:
        return self._cost_try

    @property
    def average_purchase_price_native(self) -> Decimal | None:
        """Lifetime purchase cost per share, with purchase fees included."""
        if self._purchase_quantity == ZERO:
            return None
        with localcontext() as ctx:
            ctx.prec = CALC_PRECISION
            return self._purchase_cost_native / self._purchase_quantity

    def _recompute_totals(self) -> tuple[Decimal, Decimal, Decimal]:
        """Re-derive the totals by summing every lot. Reference implementation."""
        with localcontext() as ctx:
            ctx.prec = CALC_PRECISION
            return (
                sum((lot.quantity_open for lot in self.open_lots), ZERO),
                sum((lot.cost_native_open for lot in self.open_lots), ZERO),
                sum((lot.cost_try_open for lot in self.open_lots), ZERO),
            )

    @property
    def weighted_avg_cost_fx_rate(self) -> Decimal | None:
        """Weighted by native cost, not by quantity (SPEC §6).

        Equals `cost_try / cost_native` by construction, which is what makes
        `local_return x fx_return == total_return` an exact identity rather than an
        approximation.
        """
        native = self.cost_native
        if native == ZERO:
            return None
        return self.cost_try / native

    # -- incremental construction ---------------------------------------------------

    def apply(self, txn: TxnInput) -> None:
        """Fold one transaction into the book, mutating it in place.

        Lets a caller walk forward through time applying each transaction exactly once,
        instead of replaying the whole history to answer "what was held on day N?".
        `build_history` relies on this: rebuilding per day made the series
        O(days x positions x transactions), which grows badly with a long history.

        Transactions must arrive in `_sort_key` order, which `build_lot_book` and
        `build_history` both guarantee.
        """
        with localcontext() as ctx:
            ctx.prec = CALC_PRECISION

            if txn.side is Side.BUY:
                lot = Lot(
                    txn_id=txn.id,
                    trade_date=txn.trade_date,
                    quantity_original=txn.quantity,
                    quantity_open=txn.quantity,
                    price_native=txn.price_native,
                    fees_native=txn.fees_native,
                    fx_rate_to_try=txn.fx_rate_to_try,
                    fx_rate_date=txn.fx_rate_date,
                    fx_provider=txn.fx_provider,
                )
                self.open_lots.append(lot)
                cost = lot.cost_native_open
                self._quantity += lot.quantity_open
                self._cost_native += cost
                self._cost_try += cost * lot.fx_rate_to_try
                self._purchase_quantity += lot.quantity_original
                self._purchase_cost_native += cost
            else:
                _consume(self, txn)

    def prune(self) -> None:
        """Drop fully consumed lots. Purely cosmetic — they sum to zero either way."""
        self.open_lots = [lot for lot in self.open_lots if lot.quantity_open > ZERO]

    @property
    def realized(self) -> RealizedPnl:
        return RealizedPnl(
            quantity=sum((d.quantity for d in self.disposals), ZERO),
            cost_native=sum((d.cost_native for d in self.disposals), ZERO),
            proceeds_native=sum((d.proceeds_native for d in self.disposals), ZERO),
            pnl_native=sum((d.pnl_native for d in self.disposals), ZERO),
            cost_try=sum((d.cost_try for d in self.disposals), ZERO),
            proceeds_try=sum((d.proceeds_try for d in self.disposals), ZERO),
            pnl_try=sum((d.pnl_try for d in self.disposals), ZERO),
            price_effect_try=sum((d.price_effect_try for d in self.disposals), ZERO),
            fx_effect_try=sum((d.fx_effect_try for d in self.disposals), ZERO),
        )


def _sort_key(txn: TxnInput) -> tuple[date, int, int]:
    """Trade date first; BUY before SELL on the same date; then id for determinism.

    Ordering BUYs first on a shared date means a same-day round trip matches against the
    lot it obviously belongs to instead of failing for want of inventory.
    """
    return (txn.trade_date, 0 if txn.side is Side.BUY else 1, txn.id)


def build_lot_book(
    ticker: str,
    currency: str,
    transactions: list[TxnInput],
    *,
    as_of: date | None = None,
) -> LotBook:
    """Replay transactions in FIFO order.

    `as_of` restricts the replay to transactions on or before that date, which is what
    the historical series uses to value only the lots actually held on a given day
    (SPEC §6, US-4.1).
    """
    book = LotBook(ticker=ticker, currency=currency)

    relevant = [t for t in transactions if as_of is None or t.trade_date <= as_of]
    for txn in sorted(relevant, key=_sort_key):
        book.apply(txn)

    # Fully consumed lots are dropped only after the whole replay, so FIFO order holds.
    book.prune()
    return book


def _consume(book: LotBook, sell: TxnInput) -> None:
    remaining = sell.quantity
    if remaining <= ZERO:
        return

    # The running total is exactly this sum, maintained as lots are applied and drawn
    # down, so a SELL costs the lots it actually consumes rather than a full rescan.
    available = book.quantity
    if remaining > available:
        raise InsufficientLots(
            f"{book.ticker}: SELL of {remaining} on {sell.trade_date} exceeds "
            f"{available} open shares"
        )

    # Sale fees are allocated across the shares sold, mirroring entry-fee treatment.
    sell_fee_per_unit = (
        sell.fees_native / sell.quantity if sell.quantity != ZERO else ZERO
    )

    for lot in book.open_lots:
        if remaining <= ZERO:
            break
        if lot.quantity_open <= ZERO:
            continue

        take = min(lot.quantity_open, remaining)
        proceeds = take * sell.price_native - take * sell_fee_per_unit
        taken_cost = lot.cost_native_for(take)

        # Keep the running totals in step with the lot being drawn down.
        book._quantity -= take
        book._cost_native -= taken_cost
        book._cost_try -= taken_cost * lot.fx_rate_to_try

        book.disposals.append(
            Disposal(
                sell_txn_id=sell.id,
                sell_date=sell.trade_date,
                lot_txn_id=lot.txn_id,
                lot_date=lot.trade_date,
                quantity=take,
                cost_native=taken_cost,
                proceeds_native=proceeds,
                lot_fx_rate=lot.fx_rate_to_try,
                sell_fx_rate=sell.fx_rate_to_try,
            )
        )

        lot.quantity_open -= take
        remaining -= take

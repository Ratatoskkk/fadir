"""Input types for the calc engine (SPEC §6).

These are deliberately plain dataclasses rather than ORM objects: the calc module must be
constructible from fixtures with no DB present.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


ZERO = Decimal("0")
ONE = Decimal("1")

#: Working precision for every money calculation. Wide enough that Decimal division
#: never loses a figure that matters at TRY scale. Pinned here rather than inherited
#: from the caller's context so a lot book built in a test and one built inside the
#: attribution engine produce bit-identical totals.
CALC_PRECISION = 50


@dataclass(frozen=True)
class TxnInput:
    """A transaction as the calc engine sees it.

    Native-currency amounts plus a separately sourced FX rate — never a pre-converted
    TRY cost (SPEC §0).
    """

    id: int
    ticker: str
    currency: str
    trade_date: date
    side: Side
    quantity: Decimal
    price_native: Decimal
    fees_native: Decimal
    fx_rate_to_try: Decimal
    fx_rate_date: date
    fx_provider: str
    fee_currency: str | None = None
    fee_fx_rate_to_try: Decimal | None = None
    fee_fx_rate_date: date | None = None
    fee_fx_provider: str | None = None

    @property
    def gross_native(self) -> Decimal:
        return self.quantity * self.price_native

    @property
    def fx_carried_forward(self) -> bool:
        return self.fx_rate_date != self.trade_date

    @property
    def fee_native_equivalent(self) -> Decimal:
        if not self.fees_native:
            return ZERO
        if self.fee_currency is None or self.fee_currency == self.currency:
            return self.fees_native
        if self.fee_fx_rate_to_try is None:
            raise ValueError("foreign fee requires fee FX rate")
        return self.fees_native * self.fee_fx_rate_to_try / self.fx_rate_to_try


@dataclass(frozen=True)
class MarketQuote:
    """Current market state for one instrument."""

    ticker: str
    currency: str
    price_native: Decimal
    price_date: date
    fx_rate_to_try: Decimal
    fx_rate_date: date
    fx_provider: str
    #: False when the price could not be fetched; the position still renders, flagged.
    ok: bool = True
    session: str = "closed"
    stale: bool = False
    error: str | None = None
    #: True when no rate was published on the date requested and an earlier one was
    #: carried forward. Set from the resolver's own `FxQuote.carried_forward` — it is not
    #: inferable by comparing `fx_rate_date` with `price_date`, since FX and equity
    #: calendars differ legitimately (FX quotes on a Saturday, the exchange does not).
    fx_carried_forward: bool = False

    # -- the previous session, for the daily change ------------------------------------
    #
    # The close before `price_date` and the FX rate published on *that* date. Both are
    # needed because a day's move in TRY is a price move and a currency move, and this
    # app refuses to blend the two anywhere else either. All three are None when there is
    # no earlier session on file, in which case no daily figure is reported at all —
    # showing zero would be a claim that the position did not move.
    prev_price_native: Decimal | None = None
    prev_price_date: date | None = None
    prev_fx_rate_to_try: Decimal | None = None

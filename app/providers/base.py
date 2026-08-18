"""Provider interfaces and shared types (SPEC §3).

The `FxProvider` Protocol is exactly as specified: providers return *published* rates
only. They do not carry rates forward across weekends and holidays — that policy lives
one layer up in `app.providers.fx_service.FxService`, which walks backwards up to
`max_lookback_days` and returns an `FxQuote` recording the `rate_date` actually used
(SPEC §3, "Store the actual rate_date used alongside the rate").

Keeping carry-forward out of the providers means a provider can never disguise a stale
rate as a fresh one, and the resolver has a single, testable place where the policy is
enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """Base class for all provider failures."""


class UnsupportedCurrencyPair(ProviderError):
    """The provider does not publish this pair at all.

    Raised by `TcmbFxProvider` for TWD (SPEC §3). This is deliberately *not* recoverable
    by falling back to another route inside the provider — silent fallback would produce
    a series with mixed provenance. The config layer resolves it by assigning a different
    provider to that currency.
    """


class RateUnavailable(ProviderError):
    """The pair is supported but no rate could be found in the permitted window."""


class PriceUnavailable(ProviderError):
    """No usable price for this instrument."""


@dataclass(frozen=True)
class FxQuote:
    """A resolved FX rate together with its full provenance."""

    base: str
    quote: str
    rate: Decimal
    #: The date the rate was actually published. May precede the requested date.
    rate_date: date
    #: The date that was asked for.
    requested_date: date
    #: 'yfinance', 'tcmb', 'manual', or an explicit triangulation route label.
    provider: str

    @property
    def carried_forward(self) -> bool:
        return self.rate_date != self.requested_date

    @property
    def days_carried(self) -> int:
        return (self.requested_date - self.rate_date).days


@dataclass(frozen=True)
class PricePoint:
    """A daily close in native currency."""

    price_date: date
    close_native: Decimal


@dataclass(frozen=True)
class SplitEvent:
    action_date: date
    #: Shares received per share held. A 5-for-1 split is Decimal("5").
    ratio: Decimal


@runtime_checkable
class FxProvider(Protocol):
    """SPEC §3 interface."""

    #: Stable identifier persisted as provenance.
    name: str

    def rate(self, base: str, quote: str, on: date) -> Decimal: ...

    def series(self, base: str, quote: str, start: date, end: date) -> dict[date, Decimal]: ...


@runtime_checkable
class PriceProvider(Protocol):
    def daily_closes(
        self, yf_symbol: str, start: date, end: date
    ) -> dict[date, Decimal]: ...

    def splits(self, yf_symbol: str) -> list[SplitEvent]: ...

"""yfinance FX provider (SPEC §3, docs/FINDINGS.md F-2).

Yahoo publishes a direct `<CCY>TRY=X` pair for USD and EUR only. SEK and TWD have no TRY
pair in either direction, so they are routed through USD:

    SEK/TRY = SEKUSD=X x USDTRY=X
    TWD/TRY = TWDUSD=X x USDTRY=X

SPEC §3 forbids *silent* triangulation because it "would produce a series with mixed
provenance". This implementation triangulates only where Yahoo leaves no alternative, and
never silently: every rate carries a provenance label naming the exact route
(`yfinance:SEKUSD=X*USDTRY=X`), which is persisted in `fx_cache.provider` and
`transaction.fx_provider`, surfaced by `/api/health`, and displayed in the UI. Provenance
is therefore always explicit and always auditable.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from app.providers.base import FxProvider, RateUnavailable, UnsupportedCurrencyPair
from app.providers.yf_client import RATE_QUANTUM, fetch_close_series
from app.registry import FX_DIRECT, FX_SYMBOL, FX_VIA_USD

log = logging.getLogger(__name__)

USD_TRY = FX_SYMBOL["USD"]


class YFinanceFxProvider(FxProvider):
    name = "yfinance"

    def __init__(self) -> None:
        self._supported = set(FX_DIRECT) | set(FX_VIA_USD)
        #: Legs already fetched by *this* provider instance, keyed by (symbol, window).
        #: USDTRY is the second leg of both triangulations, so refreshing USD, SEK and
        #: TWD downloaded it three times over the same window. Providers are built per
        #: `FxService`, i.e. per request, so this deduplicates within one refresh and
        #: never serves a rate across requests.
        self._legs: dict[tuple[str, date, date], dict[date, Decimal]] = {}

    def _leg(self, symbol: str, start: date, end: date) -> dict[date, Decimal]:
        key = (symbol, start, end)
        if key not in self._legs:
            self._legs[key] = fetch_close_series(symbol, start, end, quantum=RATE_QUANTUM)
        return self._legs[key]

    # -- provenance ----------------------------------------------------------------

    def provenance(self, base: str) -> str:
        """The label recorded for rates from this provider for `base`."""
        base = base.upper()
        if base in FX_VIA_USD:
            return f"{self.name}:{FX_VIA_USD[base]}*{USD_TRY}"
        return self.name

    def is_triangulated(self, base: str) -> bool:
        return base.upper() in FX_VIA_USD

    # -- FxProvider ----------------------------------------------------------------

    def rate(self, base: str, quote: str, on: date) -> Decimal:
        series = self.series(base, quote, on, on)
        if on not in series:
            raise RateUnavailable(f"no published {base}/{quote} rate on {on}")
        return series[on]

    def series(self, base: str, quote: str, start: date, end: date) -> dict[date, Decimal]:
        base, quote = base.upper(), quote.upper()

        if base == quote:
            return {}
        if quote != "TRY":
            raise UnsupportedCurrencyPair(
                f"{self.name} is configured for <CCY>/TRY only, got {base}/{quote}"
            )
        if base not in self._supported:
            raise UnsupportedCurrencyPair(f"{self.name} has no route for {base}/TRY")

        if base in FX_DIRECT:
            return self._leg(FX_SYMBOL[base], start, end)

        # Triangulate via USD. Both legs are fetched over the same window and combined
        # only on dates where *both* published — never interpolated to fill a gap in one
        # leg, since that would invent a rate. The resolver's carry-forward rule handles
        # the resulting holes exactly as it handles any other unpublished date.
        leg_symbol = FX_VIA_USD[base]
        leg = self._leg(leg_symbol, start, end)
        usd = self._leg(USD_TRY, start, end)

        # The product of two quantized legs, re-quantized so the stored rate does not
        # carry spurious trailing precision from the multiplication.
        common = leg.keys() & usd.keys()
        if not common and (leg or usd):
            log.warning(
                "no overlapping dates between %s and %s for %s/TRY over %s..%s",
                leg_symbol,
                USD_TRY,
                base,
                start,
                end,
            )
        return {
            d: (leg[d] * usd[d]).quantize(RATE_QUANTUM, rounding=ROUND_HALF_EVEN)
            for d in sorted(common)
        }

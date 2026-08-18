"""TCMB EVDS FX provider (SPEC §3).

Official Turkish Central Bank rates, appropriate when figures are used for tax purposes.
Requires a free API key from evds2.tcmb.gov.tr, supplied via `config.yaml` or the
`FADIR_TCMB_API_KEY` environment variable.

**The TWD limitation is load-bearing.** TCMB's published basket does not include TWD.
This provider raises `UnsupportedCurrencyPair` for TWD and never falls back, never
triangulates through USD, and never substitutes a nearby currency — a triangulated rate
would be a yfinance-derived number wearing a central-bank label, and the whole reason to
choose TCMB is single-source official provenance. The config layer resolves this by
routing TWD to a different provider (see `config.yaml`).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from app.providers.base import (
    FxProvider,
    ProviderError,
    RateUnavailable,
    UnsupportedCurrencyPair,
)

log = logging.getLogger(__name__)

EVDS_BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"

#: EVDS series codes for the forex-selling rate against TRY.
#: TWD is deliberately absent — TCMB does not publish it.
SERIES_CODE: dict[str, str] = {
    "USD": "TP.DK.USD.S.YTL",
    "EUR": "TP.DK.EUR.S.YTL",
    "SEK": "TP.DK.SEK.S.YTL",
    "GBP": "TP.DK.GBP.S.YTL",
    "CHF": "TP.DK.CHF.S.YTL",
    "JPY": "TP.DK.JPY.S.YTL",
}

#: Currencies TCMB is known not to publish. Listed explicitly so the error message can
#: say *why* rather than just "unknown currency".
NOT_IN_TCMB_BASKET: frozenset[str] = frozenset({"TWD"})

#: TCMB quotes JPY per 100 units.
PER_100 = frozenset({"JPY"})


class TcmbFxProvider(FxProvider):
    name = "tcmb"

    def __init__(self, api_key: str | None, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def provenance(self, base: str) -> str:
        return self.name

    def is_triangulated(self, base: str) -> bool:
        return False

    def _check_supported(self, base: str, quote: str) -> str:
        base, quote = base.upper(), quote.upper()
        if quote != "TRY":
            raise UnsupportedCurrencyPair(
                f"tcmb publishes rates against TRY only, got {base}/{quote}"
            )
        if base in NOT_IN_TCMB_BASKET:
            raise UnsupportedCurrencyPair(
                f"TCMB does not publish {base}. Route {base} to another provider in "
                f"config.yaml (fx.overrides). Triangulating through USD is refused here "
                f"deliberately: it would give a yfinance-derived rate a central-bank label."
            )
        if base not in SERIES_CODE:
            raise UnsupportedCurrencyPair(f"no TCMB series code known for {base}/TRY")
        return base

    def rate(self, base: str, quote: str, on: date) -> Decimal:
        series = self.series(base, quote, on, on)
        if on not in series:
            raise RateUnavailable(f"TCMB published no {base}/{quote} rate on {on}")
        return series[on]

    def series(self, base: str, quote: str, start: date, end: date) -> dict[date, Decimal]:
        base = self._check_supported(base, quote)

        if not self._api_key:
            raise ProviderError(
                "TCMB API key missing. Set fx.tcmb_api_key in config.yaml or the "
                "FADIR_TCMB_API_KEY environment variable."
            )

        code = SERIES_CODE[base]
        params = {
            "series": code,
            "startDate": start.strftime("%d-%m-%Y"),
            "endDate": end.strftime("%d-%m-%Y"),
            "type": "json",
            "key": self._api_key,
        }

        try:
            response = httpx.get(EVDS_BASE_URL, params=params, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"TCMB request failed for {base}/TRY: {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"TCMB returned non-JSON for {base}/TRY: {exc}") from exc

        items = payload.get("items") or []
        key = code.replace(".", "_")
        divisor = Decimal("100") if base in PER_100 else Decimal("1")

        out: dict[date, Decimal] = {}
        for item in items:
            raw_date = item.get("Tarih")
            raw_value = item.get(key)
            if not raw_date or raw_value in (None, "", "null"):
                continue  # TCMB emits null on non-business days; carry-forward handles it
            try:
                day, month, year = raw_date.split("-")
                parsed = date(int(year), int(month), int(day))
                out[parsed] = Decimal(str(raw_value)) / divisor
            except (ValueError, InvalidOperation) as exc:
                log.warning("skipping unparseable TCMB row %r: %s", item, exc)
                continue

        return out

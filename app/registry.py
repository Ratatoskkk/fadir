"""Instrument seed set and FX routing tables (SPEC §2, §3).

Two separate things live here, and they answer to different owners.

`REGISTRY` is **yours**. It ships empty, because the app has no idea what you hold. It is
the seed set only: entries here are created as instruments the first time you bootstrap,
and after that the database is the source of truth. You never have to touch this file —
adding a holding through the dashboard, or letting `scripts/bootstrap.py` read your
transaction CSV, does the same job. Fill it in only if you want a fixed starting set that
`scripts/verify_symbols.py` can check before you import anything.

The FX tables below are **not** yours. They record which currency pairs Yahoo actually
publishes, which is a fact about the provider rather than a preference.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegistryEntry:
    ticker: str
    exchange: str
    yf_symbol: str
    currency: str
    name: str
    # Ordered fallbacks tried by verify_symbols.py when the primary symbol is dead.
    fallbacks: tuple[str, ...] = ()


#: Empty by default. To pin a starting set, add entries in this shape:
#:
#:     REGISTRY = (
#:         RegistryEntry("AAPL", "NASDAQ", "AAPL", "USD", "Apple Inc"),
#:         RegistryEntry("SAP", "ETR", "SAP.DE", "EUR", "SAP SE"),
#:     )
#:
#: `yf_symbol` is what Yahoo Finance calls the instrument — check it resolves with
#: `make verify` before you rely on it. See `examples/seed_transactions.example.csv`.
REGISTRY: tuple[RegistryEntry, ...] = ()

BY_TICKER: dict[str, RegistryEntry] = {e.ticker: e for e in REGISTRY}

BASE_CURRENCY = "TRY"

#: Every non-TRY currency the app can price. Extend it when you add a holding in a
#: currency not listed, and give the new currency a route below.
CURRENCIES: tuple[str, ...] = ("USD", "SEK", "EUR", "TWD")

#: Direct yfinance FX pair symbols to TRY (SPEC §3).
#:
#: docs/FINDINGS.md F-2: only USD and EUR actually have a `<CCY>TRY=X` pair on Yahoo. SEK
#: and TWD have no TRY pair in either direction and must be routed via USD — see
#: `app/providers/fx_yfinance.py`, which labels the triangulation explicitly rather than
#: performing it silently.
FX_SYMBOL = {c: f"{c}TRY=X" for c in CURRENCIES}

#: Currencies with a working direct TRY pair on Yahoo.
FX_DIRECT: tuple[str, ...] = ("USD", "EUR")

#: Currencies that must be triangulated through USD, and the leg used to do it.
FX_VIA_USD: dict[str, str] = {"SEK": "SEKUSD=X", "TWD": "TWDUSD=X"}

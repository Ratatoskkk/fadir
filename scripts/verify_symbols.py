"""SPEC §2 / US-2.1 — verify every yfinance symbol resolves before anything else is built.

Checks the instruments you actually hold: the registry seed set, plus everything already
in the database. The registry ships empty, so on a fresh install this checks the FX legs
alone, and after you add holdings it checks those too.

Fetches a short window of history for each symbol and each FX pair, prints the reported
currency and last close, and fails the run on:

  * a symbol that returns no data (after trying its declared fallbacks), or
  * a symbol whose reported currency disagrees with the one recorded for it.

Failures are reported, never silently substituted. If a fallback symbol works, the
script says so loudly and exits non-zero so a person decides whether to amend the
record.

Usage:  python scripts/verify_symbols.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yfinance as yf  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.models import Instrument  # noqa: E402
from app.registry import (  # noqa: E402
    BASE_CURRENCY,
    CURRENCIES,
    FX_DIRECT,
    FX_SYMBOL,
    FX_VIA_USD,
    REGISTRY,
    RegistryEntry,
)

PERIOD = "5d"


def _probe(symbol: str) -> tuple[str | None, float | None, str | None, str | None]:
    """Return (currency, last_close, last_date, error)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=PERIOD, auto_adjust=False)
    except Exception as exc:  # noqa: BLE001 - diagnostic script, report anything
        return None, None, None, f"{type(exc).__name__}: {exc}"

    if hist is None or hist.empty:
        return None, None, None, "no history rows returned"

    # docs/FINDINGS.md F-4: Yahoo intermittently returns the newest European session with a
    # valid Open/High/Low/Volume but a NaN Close. Take the last *valid* close.
    closes = hist["Close"].dropna()
    if closes.empty:
        return None, None, None, f"all {len(hist)} rows have a NaN close"
    last_close = float(closes.iloc[-1])
    last_date = str(closes.index[-1].date())

    currency = None
    try:
        currency = ticker.fast_info.get("currency")
    except Exception:  # noqa: BLE001
        currency = None
    if not currency:
        try:
            currency = ticker.info.get("currency")
        except Exception:  # noqa: BLE001
            currency = None

    return (
        currency.upper() if currency else None,
        last_close,
        last_date,
        None,
    )


def _entries() -> tuple[RegistryEntry, ...]:
    """The registry seed set, plus every instrument already in the database.

    The registry ships empty and instruments normally arrive through the dashboard or a
    CSV, so reading only the registry would check nothing on a real install.
    """
    entries = {e.ticker: e for e in REGISTRY}

    settings = get_settings()
    if not settings.db_path.exists():
        return tuple(entries.values())

    try:
        with session_scope() as session:
            for row in session.execute(select(Instrument)).scalars():
                entries.setdefault(
                    row.ticker,
                    RegistryEntry(
                        ticker=row.ticker,
                        exchange=row.exchange,
                        yf_symbol=row.yf_symbol,
                        currency=row.currency,
                        name=row.name or row.ticker,
                    ),
                )
    except Exception as exc:  # noqa: BLE001 - a diagnostic must not die on a bad DB
        print(f"could not read instruments from {settings.db_path}: {exc}\n")

    return tuple(entries.values())


def verify_instruments() -> list[str]:
    problems: list[str] = []
    entries = _entries()

    if not entries:
        print("No instruments yet — the registry is empty and the database holds none.")
        print("Add holdings in the dashboard, or run:")
        print("  python scripts/bootstrap.py --seed examples/seed_transactions.example.csv")
        print("Checking FX routes only.\n")
        return problems

    print(f"{'ticker':<8} {'symbol':<12} {'ccy':<5} {'last close':>14}  {'as of':<12} status")
    print("-" * 76)

    for entry in entries:
        candidates = (entry.yf_symbol, *entry.fallbacks)
        resolved = False

        for idx, symbol in enumerate(candidates):
            currency, close, last_date, error = _probe(symbol)

            if error is not None:
                if idx == len(candidates) - 1:
                    problems.append(f"{entry.ticker}: all symbols failed ({symbol}: {error})")
                    print(
                        f"{entry.ticker:<8} {symbol:<12} {'-':<5} {'-':>14}  {'-':<12} FAIL {error}"
                    )
                continue

            status = "ok"
            if currency is None:
                status = "WARN currency not reported by Yahoo"
            elif currency != entry.currency:
                status = f"FAIL currency {currency} != registry {entry.currency}"
                problems.append(
                    f"{entry.ticker} ({symbol}): currency {currency}, registry says {entry.currency}"
                )
            if idx > 0:
                status = f"FALLBACK used instead of {entry.yf_symbol} - {status}"
                problems.append(
                    f"{entry.ticker}: primary {entry.yf_symbol} failed; "
                    f"fallback {symbol} works. Update the registry deliberately."
                )

            print(
                f"{entry.ticker:<8} {symbol:<12} {currency or '?':<5} "
                f"{close:>14,.4f}  {last_date:<12} {status}"
            )
            resolved = True
            break

        if not resolved and not any(p.startswith(entry.ticker) for p in problems):
            problems.append(f"{entry.ticker}: unresolved")

    return problems


def verify_fx() -> list[str]:
    """Verify every leg the FX provider actually uses (docs/FINDINGS.md F-2).

    USD and EUR resolve directly; SEK and TWD have no TRY pair on Yahoo in either
    direction and are routed through USD. Each leg is probed on its own so a broken
    triangulation leg is reported as such rather than as a vague pair failure.
    """
    problems: list[str] = []
    print()
    print(f"{'pair':<10} {'route':<26} {'rate':>14}  {'as of':<12} status")
    print("-" * 82)

    usd_try, usd_try_date = None, None

    for currency in CURRENCIES:
        pair = f"{currency}/{BASE_CURRENCY}"

        if currency in FX_DIRECT:
            symbol = FX_SYMBOL[currency]
            _, rate, last_date, error = _probe(symbol)
            if error is not None:
                problems.append(f"{pair} ({symbol}): {error}")
                print(f"{pair:<10} {symbol:<26} {'-':>14}  {'-':<12} FAIL {error}")
                continue
            if currency == "USD":
                usd_try, usd_try_date = rate, last_date
            print(f"{pair:<10} {symbol:<26} {rate:>14,.6f}  {last_date:<12} direct")
            continue

        leg = FX_VIA_USD[currency]
        _, leg_rate, leg_date, error = _probe(leg)
        route = f"{leg} x {FX_SYMBOL['USD']}"
        if error is not None:
            problems.append(f"{pair} (leg {leg}): {error}")
            print(f"{pair:<10} {route:<26} {'-':>14}  {'-':<12} FAIL {error}")
            continue
        if usd_try is None:
            problems.append(f"{pair}: cannot triangulate, USDTRY=X leg unavailable")
            print(f"{pair:<10} {route:<26} {'-':>14}  {'-':<12} FAIL no USDTRY leg")
            continue

        rate = leg_rate * usd_try
        as_of = min(leg_date, usd_try_date or leg_date)
        print(f"{pair:<10} {route:<26} {rate:>14,.6f}  {as_of:<12} triangulated via USD")

    return problems


def main() -> int:
    print("Verifying instrument symbols against yfinance...\n")
    problems = verify_instruments()
    problems += verify_fx()

    print()
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("All symbols resolved and every currency matches what is recorded for it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

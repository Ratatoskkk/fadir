"""Thin, defensive wrapper around yfinance (SPEC §5, §8).

Everything that touches Yahoo goes through here, so the awkward parts are handled once:

* `auto_adjust=False` always. yfinance's default back-adjusts prices, silently rewriting
  history across a split (SPEC §5). Splits are handled explicitly instead.
* `end` is exclusive in yfinance; callers pass an inclusive date and this module adds the
  day.
* NaN closes are dropped, not propagated (docs/FINDINGS.md F-4). Yahoo intermittently returns
  the newest European session with a valid Open/High/Low/Volume but a NaN Close; a NaN
  reaching the calc engine would poison every downstream figure.
* Floats become `Decimal` via `str()`, never `Decimal(float)`, so no binary artefact ever
  enters a money path (SPEC §4).
* Exponential backoff on transient failure, and batched `yf.download` for multi-symbol
  refreshes (SPEC §8 rate limiting).
"""

from __future__ import annotations

import logging
import math
import random
import time
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal

import pandas as pd
import yfinance as yf

from app.providers.base import SplitEvent

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 0.6


#: Yahoo serves prices at float32 precision, so a 14.20 close arrives as 14.19999981 and
#: 190.41 as 190.41000366. Carrying that noise into a NUMERIC column would show up in the
#: UI and in every derived figure. Quantizing at the ingestion boundary — the only place
#: floats exist at all — keeps the noise out of the money paths entirely. Four places is
#: far finer than any tick size these instruments trade at.
PRICE_QUANTUM = Decimal("0.0001")
#: FX needs more headroom: a triangulated rate is a product of two quoted legs.
RATE_QUANTUM = Decimal("0.00000001")


def _to_decimal(value: object, quantum: Decimal | None = None) -> Decimal | None:
    """Convert a pandas/numpy scalar to Decimal, rejecting NaN and non-finite values."""
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    dec = Decimal(str(f))
    return dec.quantize(quantum, rounding=ROUND_HALF_EVEN) if quantum is not None else dec


def _with_backoff(fn, what: str):  # type: ignore[no-untyped-def]
    """Retry `fn` with exponential backoff and jitter. Returns None on final failure."""
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - any Yahoo failure is retryable here
            last = exc
            if attempt == MAX_ATTEMPTS - 1:
                break
            delay = BASE_BACKOFF_SECONDS * (2**attempt) + random.uniform(0, 0.25)
            log.warning(
                "%s failed (attempt %d/%d): %s - retrying in %.2fs",
                what,
                attempt + 1,
                MAX_ATTEMPTS,
                exc,
                delay,
            )
            time.sleep(delay)
    log.error("%s failed after %d attempts: %s", what, MAX_ATTEMPTS, last)
    return None


def _closes_from_frame(
    frame: pd.DataFrame | None, quantum: Decimal = PRICE_QUANTUM
) -> dict[date, Decimal]:
    if frame is None or frame.empty or "Close" not in frame:
        return {}
    out: dict[date, Decimal] = {}
    for idx, value in frame["Close"].items():
        dec = _to_decimal(value, quantum)
        if dec is None:
            continue  # docs/FINDINGS.md F-4
        out[idx.date() if hasattr(idx, "date") else idx] = dec
    return out


def fetch_close_series(
    symbol: str, start: date, end: date, *, quantum: Decimal = PRICE_QUANTUM
) -> dict[date, Decimal]:
    """Daily unadjusted closes for one symbol, inclusive of `end`. Empty dict on failure."""

    def _do() -> pd.DataFrame:
        return yf.Ticker(symbol).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=False,
            raise_errors=True,
        )

    frame = _with_backoff(_do, f"history({symbol})")
    closes = _closes_from_frame(frame, quantum)
    if not closes:
        log.warning("no usable closes for %s over %s..%s", symbol, start, end)
    return closes


def fetch_close_series_batch(
    symbols: list[str], start: date, end: date
) -> dict[str, dict[date, Decimal]]:
    """Batch all symbols into a single `yf.download` call (SPEC §8 rate limiting).

    A symbol that errors or returns nothing yields an empty dict for that symbol rather
    than failing the batch — "never fail the whole dashboard because one symbol errored".
    """
    if not symbols:
        return {}

    unique = sorted(set(symbols))

    def _do() -> pd.DataFrame:
        return yf.download(
            tickers=unique,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            progress=False,
            threads=True,
        )

    frame = _with_backoff(_do, f"download({len(unique)} symbols)")
    results: dict[str, dict[date, Decimal]] = {s: {} for s in unique}

    if frame is None or frame.empty:
        log.warning("batch download returned nothing; falling back to per-symbol fetches")
        for symbol in unique:
            results[symbol] = fetch_close_series(symbol, start, end)
        return results

    for symbol in unique:
        try:
            if isinstance(frame.columns, pd.MultiIndex):
                if symbol not in frame.columns.get_level_values(0):
                    sub = None
                else:
                    sub = frame[symbol]
            else:
                sub = frame  # single symbol - yfinance flattens the columns
            results[symbol] = _closes_from_frame(sub)
        except Exception as exc:  # noqa: BLE001 - isolate per symbol
            log.error("failed extracting %s from batch: %s", symbol, exc)
            results[symbol] = {}

        if not results[symbol]:
            # One retry alone, in case the batch dropped it.
            results[symbol] = fetch_close_series(symbol, start, end)

    return results


def fetch_last_close(symbol: str, lookback_days: int = 10) -> tuple[Decimal, date] | None:
    """Most recent valid close and the session it belongs to."""
    today = date.today()
    closes = fetch_close_series(symbol, today - timedelta(days=lookback_days), today)
    if not closes:
        return None
    last_date = max(closes)
    return closes[last_date], last_date


#: Yahoo's intraday retention: 5-minute bars go back about 60 days but only ~5 days are
#: reliably populated; hourly covers roughly two years. Asking for more than the window
#: allows returns an empty frame, so the caller must respect these.
INTRADAY_INTERVALS: dict[str, str] = {"5m": "5d", "15m": "1mo", "1h": "1mo"}


def fetch_intraday_closes(
    symbol: str, interval: str = "5m", period: str | None = None
) -> dict[datetime, Decimal]:
    """Intraday closes for one symbol, keyed by timezone-aware UTC timestamps.

    Normalising to UTC here is what makes the four exchanges combinable: a Taipei bar and
    a New York bar only line up on a common clock. Empty dict on failure, so one dead
    symbol degrades one row rather than the chart (SPEC §8).
    """
    if interval not in INTRADAY_INTERVALS:
        raise ValueError(f"unsupported intraday interval {interval!r}")
    period = period or INTRADAY_INTERVALS[interval]

    def _do() -> pd.DataFrame:
        return yf.Ticker(symbol).history(
            period=period,
            interval=interval,
            auto_adjust=False,
            actions=False,
            raise_errors=True,
        )

    frame = _with_backoff(_do, f"intraday({symbol},{interval})")
    if frame is None or frame.empty or "Close" not in frame:
        log.warning("no intraday data for %s at %s", symbol, interval)
        return {}

    out: dict[datetime, Decimal] = {}
    for idx, value in frame["Close"].items():
        dec = _to_decimal(value, PRICE_QUANTUM)
        if dec is None:
            continue  # docs/FINDINGS.md F-4 applies intraday too
        stamp = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        out[stamp.astimezone(timezone.utc)] = dec
    return out


def fetch_splits(symbol: str) -> list[SplitEvent]:
    """All split events Yahoo knows about for `symbol` (SPEC §5 step 1)."""

    def _do() -> pd.Series:
        return yf.Ticker(symbol).splits

    series = _with_backoff(_do, f"splits({symbol})")
    if series is None or len(series) == 0:
        return []

    events: list[SplitEvent] = []
    for idx, value in series.items():
        ratio = _to_decimal(value)
        if ratio is None or ratio <= 0 or ratio == 1:
            continue
        events.append(
            SplitEvent(
                action_date=idx.date() if hasattr(idx, "date") else idx,
                ratio=ratio,
            )
        )
    return sorted(events, key=lambda e: e.action_date)


def fetch_currency(symbol: str) -> str | None:
    """Reported trading currency, or None if Yahoo does not say."""

    def _do() -> str | None:
        ticker = yf.Ticker(symbol)
        try:
            currency = ticker.fast_info.get("currency")
        except Exception:  # noqa: BLE001
            currency = None
        if not currency:
            currency = ticker.info.get("currency")
        return currency

    currency = _with_backoff(_do, f"currency({symbol})")
    return currency.upper() if currency else None

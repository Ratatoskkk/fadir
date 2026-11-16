"""What a Ticker view symbol is: the company's sector, industry and business, from Yahoo.

Display-only, like the chart: nothing is persisted. A profile changes rarely, so a small
in-process cache keeps each symbol to one Yahoo round trip a day; after a failure Yahoo is
not asked again for a while and the last good profile stands in.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse

import yfinance as yf

log = logging.getLogger(__name__)

TTL_SECONDS = 24 * 3600
#: Yahoo answers some failures with an empty profile, so "no profile" is kept for less.
EMPTY_TTL_SECONDS = 3600
FAILURE_BACKOFF_SECONDS = 300
MAX_ENTRIES = 256
#: Yahoo's summaries run to a few paragraphs; anything longer is cut at a sentence.
MAX_SUMMARY = 2400


@dataclass(frozen=True)
class Profile:
    symbol: str
    name: str | None
    #: Yahoo's own word for the kind of instrument: Equity, ETF, Index, Futures, ...
    kind: str | None
    sector: str | None
    industry: str | None
    #: Funds have a category and a fund family instead of a sector and an industry.
    category: str | None
    fund_family: str | None
    summary: str | None
    website: str | None
    city: str | None
    country: str | None
    employees: int | None
    market_cap: float | None
    currency: str | None


class ProfileUnavailable(LookupError):
    """Yahoo has no profile for the symbol."""


class ProfileFailed(RuntimeError):
    """Yahoo failed and there is no earlier profile to stand in; worth retrying later."""


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value or None


def _summary(value: object) -> str | None:
    text = _text(value)
    if text is None or len(text) <= MAX_SUMMARY:
        return text
    cut = text.rfind(". ", 0, MAX_SUMMARY)
    return text[: cut + 1] if cut > 0 else text[:MAX_SUMMARY].rstrip() + "…"


def _website(value: object) -> str | None:
    """Only a plain http(s) address becomes a link."""
    text = _text(value)
    if text is None:
        return None
    parsed = urlparse(text)
    return text if parsed.scheme in ("http", "https") and parsed.netloc else None


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _positive_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value > 0 else None


def _currency(info: dict) -> str | None:
    """The market cap's currency: the quote's (Yahoo states market cap in it)."""
    code = _text(info.get("currency"))
    return code.upper() if code else None


def from_info(symbol: str, info: dict) -> Profile | None:
    """A Profile from yfinance's `Ticker.info`; None when Yahoo knows nothing about it."""
    profile = Profile(
        symbol=symbol,
        name=_text(info.get("longName")) or _text(info.get("shortName")),
        kind=_text(info.get("typeDisp")),
        sector=_text(info.get("sectorDisp")) or _text(info.get("sector")),
        industry=_text(info.get("industryDisp")) or _text(info.get("industry")),
        category=_text(info.get("category")),
        fund_family=_text(info.get("fundFamily")),
        summary=_summary(info.get("longBusinessSummary") or info.get("description")),
        website=_website(info.get("website")),
        city=_text(info.get("city")),
        country=_text(info.get("country")),
        employees=_positive_int(info.get("fullTimeEmployees")),
        market_cap=_positive_float(info.get("marketCap")),
        currency=_currency(info),
    )
    return profile if profile.name or profile.kind else None


class _Failed(Exception):
    """Yahoo could not be reached or answered with an error; worth asking again later."""


def _fetch(symbol: str) -> Profile | None:
    """The profile, or None when Yahoo has none. Raises _Failed when Yahoo failed."""
    try:
        info = yf.Ticker(symbol).info
    except Exception as exc:  # noqa: BLE001 - any Yahoo failure is retried after the back-off
        log.warning("profile(%s) failed: %s", symbol, exc)
        raise _Failed from exc
    return from_info(symbol, info) if isinstance(info, dict) else None


_cache: OrderedDict[str, tuple[float, Profile | None]] = OrderedDict()
_failed: dict[str, float] = {}
_lock = threading.Lock()
_key_locks: dict[str, threading.Lock] = {}


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _failed.clear()
        _key_locks.clear()


def profile(symbol: str) -> Profile:
    """The symbol's profile, fetched at most once a day and once at a time per symbol."""
    def cached() -> tuple[bool, Profile | None, bool]:
        """(fresh, value, known): a fresh hit, or a stale value that may stand in."""
        hit = _cache.get(symbol)
        if hit is None:
            return False, None, False
        _cache.move_to_end(symbol)
        ttl = TTL_SECONDS if hit[1] is not None else EMPTY_TTL_SECONDS
        return time.monotonic() - hit[0] < ttl, hit[1], True

    with _lock:
        fresh, value, known = cached()
        key_lock = _key_locks.setdefault(symbol, threading.Lock())
    if fresh:
        return _found(symbol, value)
    with key_lock:
        with _lock:
            fresh, value, known = cached()
            failed_at = _failed.get(symbol)
        if fresh:
            return _found(symbol, value)
        if failed_at is not None and time.monotonic() - failed_at < FAILURE_BACKOFF_SECONDS:
            if known:
                return _found(symbol, value)
            raise ProfileFailed(f"profile for {symbol} unavailable")
        try:
            result = _fetch(symbol)
        except _Failed:
            with _lock:
                _failed[symbol] = time.monotonic()
            if known:
                return _found(symbol, value)  # a failed refresh keeps the last answer
            raise ProfileFailed(f"profile for {symbol} unavailable") from None
        with _lock:
            _failed.pop(symbol, None)
            # "Yahoo has no profile" is an answer too, cached like one.
            _cache[symbol] = (time.monotonic(), result)
            _cache.move_to_end(symbol)
            while len(_cache) > MAX_ENTRIES:
                old, _ = _cache.popitem(last=False)
                if old in _key_locks and not _key_locks[old].locked():
                    del _key_locks[old]
        return _found(symbol, result)


def _found(symbol: str, value: Profile | None) -> Profile:
    if value is None:
        raise ProfileUnavailable(f"no profile for {symbol}")
    return value

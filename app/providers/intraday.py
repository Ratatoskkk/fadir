"""Intraday price and FX fetching for the 1-day view.

Deliberately **not** persisted to SQLite, unlike daily closes. Intraday bars are only
retained by Yahoo for a few days, they are superseded constantly while a session runs,
and the whole point of the 1G view is freshness — a settled daily close is immutable and
worth keeping forever, a five-minute bar from Tuesday is not. So this is a small,
explicitly bounded in-process cache with a short TTL.

"Bounded" is load-bearing: the cache holds at most one entry per (symbol, interval) and
each entry is replaced wholesale on refetch, so it cannot grow with uptime. Worst case is
roughly ten symbols x a few hundred bars.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from app.providers import yf_client
from app.registry import FX_DIRECT, FX_SYMBOL, FX_VIA_USD

log = logging.getLogger(__name__)

#: Intraday bars are stale quickly; this roughly matches the 5-minute bar cadence.
DEFAULT_TTL_SECONDS = 120

USD_TRY = FX_SYMBOL["USD"]


@dataclass
class _Entry:
    fetched_at: float
    series: dict[datetime, Decimal]


class IntradayService:
    """Fetches and briefly caches intraday series for symbols and FX pairs.

    The instance is shared across requests so the cache is actually reused, which makes
    every mutable field on it shared too. Fetch errors are therefore *not* kept here:
    each caller passes its own `errors` list, so a warning belongs to the request that
    provoked it instead of accumulating for the lifetime of the process and being
    replayed to every later caller.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl = ttl_seconds
        self._cache: dict[tuple[str, str], _Entry] = {}

    # -- cache -----------------------------------------------------------------------

    def _get(
        self,
        symbol: str,
        interval: str,
        *,
        force: bool = False,
        errors: list[str] | None = None,
    ) -> dict[datetime, Decimal]:
        key = (symbol, interval)
        entry = self._cache.get(key)
        now = time.monotonic()

        if entry is not None and not force and (now - entry.fetched_at) < self.ttl:
            return entry.series

        try:
            series = yf_client.fetch_intraday_closes(symbol, interval)
        except Exception as exc:  # noqa: BLE001 - one symbol must not break the chart
            log.error("intraday fetch failed for %s: %s", symbol, exc)
            if errors is not None:
                errors.append(f"{symbol}: {exc}")
            # Serve the stale copy if we have one; a slightly old curve beats no curve.
            return entry.series if entry is not None else {}

        if not series and entry is not None:
            return entry.series

        # Replacing the entry wholesale is what keeps the cache bounded.
        self._cache[key] = _Entry(fetched_at=now, series=series)
        return series

    def clear(self) -> None:
        self._cache.clear()

    # -- public --------------------------------------------------------------------

    def prices(
        self,
        symbols: list[str],
        interval: str = "5m",
        *,
        force: bool = False,
        errors: list[str] | None = None,
    ) -> dict[str, dict[datetime, Decimal]]:
        return {
            s: self._get(s, interval, force=force, errors=errors)
            for s in sorted(set(symbols))
        }

    def fx(
        self,
        currencies: list[str],
        interval: str = "5m",
        *,
        force: bool = False,
        errors: list[str] | None = None,
    ) -> dict[str, dict[datetime, Decimal]]:
        """Intraday <CCY>/TRY series, triangulating through USD where required.

        Same routing and the same explicit provenance rule as the daily provider
        (docs/FINDINGS.md F-2): SEK and TWD have no direct TRY pair on Yahoo at any
        granularity, so they are combined from their USD leg and USDTRY. Bars are matched
        on exact UTC timestamps and a bar present in only one leg is dropped rather than
        paired with a guess.
        """
        wanted = sorted(set(c.upper() for c in currencies))
        out: dict[str, dict[datetime, Decimal]] = {}

        needs_usd = any(c in FX_VIA_USD for c in wanted)
        usd_series = (
            self._get(USD_TRY, interval, force=force, errors=errors) if needs_usd else {}
        )

        for currency in wanted:
            if currency == "TRY":
                continue
            if currency in FX_DIRECT:
                out[currency] = self._get(
                    FX_SYMBOL[currency], interval, force=force, errors=errors
                )
                continue

            leg_symbol = FX_VIA_USD.get(currency)
            if leg_symbol is None:
                log.warning("no intraday FX route for %s", currency)
                out[currency] = {}
                continue

            leg = self._get(leg_symbol, interval, force=force, errors=errors)
            common = leg.keys() & usd_series.keys()
            out[currency] = {
                stamp: (leg[stamp] * usd_series[stamp]).quantize(yf_client.RATE_QUANTUM)
                for stamp in sorted(common)
            }

        return out


def session_days(series_by_key: dict[str, dict[datetime, Decimal]]) -> list[date]:
    """Every UTC day with intraday data, newest first.

    Yahoo serves roughly five days of 5-minute bars in one request, so the earlier
    sessions are already in hand — paging back through them costs nothing beyond
    choosing a different day to frame.
    """
    days = {s.astimezone(timezone.utc).date() for series in series_by_key.values() for s in series}
    return sorted(days, reverse=True)


def latest_session_bounds(
    series_by_key: dict[str, dict[datetime, Decimal]], offset: int = 0
) -> tuple[datetime, datetime] | None:
    """Start and end of a single session's data.

    `offset` counts back from the most recent: 0 is the last day the portfolio actually
    traded (so a Saturday shows Friday rather than an empty grid), 1 the day before it,
    and so on. Returns None once the offset runs past the retained window.
    """
    days = session_days(series_by_key)
    if not days or offset < 0 or offset >= len(days):
        return None

    day = days[offset]
    stamps = [
        s
        for series in series_by_key.values()
        for s in series
        if s.astimezone(timezone.utc).date() == day
    ]
    return min(stamps), max(stamps)

"""FX resolution: per-currency provider routing, caching, and carry-forward (SPEC §3, §8).

This is the single place where the weekend/holiday policy lives:

    Use the most recent *prior* published rate, look back up to `max_lookback_days`
    calendar days, then fail loudly. Never interpolate forward, never average.

The `rate_date` actually used is returned on every quote, so the UI can show when a rate
was carried forward. Four of the thirteen seed transactions fall on weekends and all four
surface this.

Caching follows SPEC §8: historical rates are immutable and cached permanently; the
current rate carries a short TTL.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import FxCache, utcnow
from app.providers.base import FxProvider, FxQuote, ProviderError, RateUnavailable
from app.providers.fx_tcmb import TcmbFxProvider
from app.providers.fx_yfinance import YFinanceFxProvider
from app.registry import BASE_CURRENCY

log = logging.getLogger(__name__)

MANUAL_PROVIDER = "manual"


def build_providers(settings: Settings) -> dict[str, FxProvider]:
    return {
        "yfinance": YFinanceFxProvider(),
        "tcmb": TcmbFxProvider(settings.fx.tcmb_api_key),
    }


class FxService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        providers: dict[str, FxProvider] | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.providers = providers if providers is not None else build_providers(settings)
        #: Per-provider health, surfaced by /api/health.
        self.status: dict[str, dict[str, object]] = {}
        #: Resolved current rates, per currency. A view resolves a rate per *position*,
        #: so three USD holdings asked the same question three times; the service is
        #: built per request, so this cannot serve a rate across requests.
        self._current: dict[str, FxQuote] = {}

    # -- routing -------------------------------------------------------------------

    def provider_for(self, currency: str) -> FxProvider:
        name = self.settings.fx.provider_for(currency)
        provider = self.providers.get(name)
        if provider is None:
            raise ProviderError(
                f"fx provider {name!r} configured for {currency} is not registered"
            )
        return provider

    def provenance_for(self, currency: str) -> str:
        provider = self.provider_for(currency)
        getter = getattr(provider, "provenance", None)
        return getter(currency) if callable(getter) else provider.name

    # -- cache ---------------------------------------------------------------------

    def _cached_on_or_before(
        self, currency: str, on: date, lookback_days: int
    ) -> FxCache | None:
        earliest = on - timedelta(days=lookback_days)
        stmt = (
            select(FxCache)
            .where(
                FxCache.base == currency,
                FxCache.quote == BASE_CURRENCY,
                FxCache.rate_date <= on,
                FxCache.rate_date >= earliest,
            )
            .order_by(FxCache.rate_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def _store(
        self,
        currency: str,
        rates: dict[date, Decimal],
        provider_label: str,
        *,
        window_end: date | None = None,
    ) -> int:
        """Upsert published rates. Historical rows are immutable once written.

        `window_end` is the last date the caller actually asked the provider about. When
        that reaches today, the newest row is re-stamped even if its rate is unchanged —
        see the comment below.
        """
        if not rates:
            return 0

        # Fetched as ORM rows rather than bare dates: the two rows that may need
        # updating are already in this result, so no follow-up query is needed.
        existing_stmt = select(FxCache).where(
            FxCache.base == currency,
            FxCache.quote == BASE_CURRENCY,
            FxCache.provider == provider_label,
            FxCache.rate_date.in_(list(rates)),
        )
        existing = {row.rate_date: row for row in self.session.execute(existing_stmt).scalars()}

        today = date.today()
        newest = max(rates)
        # `fetched_at` on the newest row is what `current()` measures its TTL against, so
        # it has to mean "when we last asked", not "when this rate first appeared". Every
        # weekend and every holiday the newest publication predates today; without this
        # re-stamp that row looks permanently expired and `current()` refetches on every
        # call — and since a page load resolves a rate per position, one view of the
        # dashboard became one Yahoo round trip per position. Only stamped when the fetch
        # actually covered today, so warming an old window cannot pass a stale rate off
        # as freshly checked.
        checked_now = window_end is not None and window_end >= today

        written = 0
        for rate_date, rate in rates.items():
            row = existing.get(rate_date)
            if row is not None:
                # Today's row is still moving, so refresh it; settled days are immutable.
                if rate_date == today:
                    row.rate = rate
                    row.fetched_at = utcnow()
                elif rate_date == newest and checked_now:
                    row.fetched_at = utcnow()
                continue
            self.session.add(
                FxCache(
                    base=currency,
                    quote=BASE_CURRENCY,
                    rate_date=rate_date,
                    rate=rate,
                    provider=provider_label,
                )
            )
            written += 1
        self.session.flush()
        return written

    # -- fetching ------------------------------------------------------------------

    def warm(self, currency: str, start: date, end: date) -> int:
        """Fetch and cache the published series for a window. Returns rows written."""
        currency = currency.upper()
        if currency == BASE_CURRENCY:
            return 0

        provider = self.provider_for(currency)
        label = self.provenance_for(currency)
        # Widen backwards so a trade on the window's first day still has a prior rate
        # to carry forward from.
        fetch_start = start - timedelta(days=self.settings.fx.max_lookback_days + 5)

        try:
            rates = provider.series(currency, BASE_CURRENCY, fetch_start, end)
        except ProviderError as exc:
            self.status[label] = {
                "ok": False,
                "error": str(exc),
                "last_attempt": utcnow().isoformat(),
            }
            log.error("fx fetch failed for %s/%s: %s", currency, BASE_CURRENCY, exc)
            raise

        written = self._store(currency, rates, label, window_end=end)
        self.status[label] = {
            "ok": bool(rates),
            "last_success": utcnow().isoformat() if rates else None,
            "points": len(rates),
            "triangulated": bool(getattr(provider, "is_triangulated", lambda _c: False)(currency)),
        }
        return written

    # -- public API ----------------------------------------------------------------

    def quote(self, currency: str, on: date, *, allow_fetch: bool = True) -> FxQuote:
        """Resolve `currency`/TRY on `on`, carrying forward at most `max_lookback_days`."""
        currency = currency.upper()
        lookback = self.settings.fx.max_lookback_days

        if currency == BASE_CURRENCY:
            return FxQuote(
                base=BASE_CURRENCY,
                quote=BASE_CURRENCY,
                rate=Decimal("1"),
                rate_date=on,
                requested_date=on,
                provider="identity",
            )

        row = self._cached_on_or_before(currency, on, lookback)
        if row is None and allow_fetch:
            self.warm(currency, on - timedelta(days=lookback), on)
            row = self._cached_on_or_before(currency, on, lookback)

        if row is None:
            raise RateUnavailable(
                f"no published {currency}/{BASE_CURRENCY} rate on {on} or in the "
                f"{lookback} calendar days before it. Refusing to interpolate or average."
            )

        return FxQuote(
            base=currency,
            quote=BASE_CURRENCY,
            rate=row.rate,
            rate_date=row.rate_date,
            requested_date=on,
            provider=row.provider,
        )

    def current(self, currency: str, *, force: bool = False) -> FxQuote:
        """Latest rate, honouring the current-FX TTL (SPEC §8)."""
        currency = currency.upper()
        today = date.today()

        if currency == BASE_CURRENCY:
            return self.quote(currency, today, allow_fetch=False)

        if not force:
            cached = self._current.get(currency)
            if cached is not None:
                return cached

        row = self._cached_on_or_before(currency, today, self.settings.fx.max_lookback_days)
        stale = True
        if row is not None:
            age = (utcnow().replace(tzinfo=None) - row.fetched_at).total_seconds()
            stale = age > self.settings.cache.fx_current_ttl_seconds

        if force or stale:
            try:
                self.warm(currency, today - timedelta(days=10), today)
            except ProviderError:
                if row is None:
                    raise
                log.warning("using stale cached %s/TRY; refresh failed", currency)

        resolved = self.quote(currency, today, allow_fetch=False)
        self._current[currency] = resolved
        return resolved

    def published_series(
        self, currency: str, start: date, end: date, *, allow_fetch: bool = False
    ) -> dict[date, Decimal]:
        """Published rates in [start, end], in a single query.

        No carry-forward: these are the rates that actually exist. The history builder
        applies the carry-forward policy itself, so handing it dense pre-filled data
        would only make it re-derive what was already known.
        """
        currency = currency.upper()
        if currency == BASE_CURRENCY:
            return {}
        if allow_fetch:
            self.warm(currency, start, end)

        stmt = select(FxCache.rate_date, FxCache.rate).where(
            FxCache.base == currency,
            FxCache.quote == BASE_CURRENCY,
            FxCache.rate_date >= start,
            FxCache.rate_date <= end,
        )
        return {rate_date: rate for rate_date, rate in self.session.execute(stmt)}

    def series(
        self, currency: str, start: date, end: date, *, allow_fetch: bool = True
    ) -> dict[date, FxQuote]:
        """A quote for every calendar day in [start, end], carry-forward applied.

        Used where every calendar day needs a rate but only business days have
        published ones. The published rates are read in one query and the carry-forward
        walk happens in memory — resolving day by day issued a query per day, which for
        a multi-year window meant thousands of round trips to answer one question.
        """
        currency = currency.upper()
        if allow_fetch and currency != BASE_CURRENCY:
            self.warm(currency, start, end)

        if currency == BASE_CURRENCY:
            out: dict[date, FxQuote] = {}
            day = start
            while day <= end:
                out[day] = FxQuote(
                    base=BASE_CURRENCY,
                    quote=BASE_CURRENCY,
                    rate=Decimal("1"),
                    rate_date=day,
                    requested_date=day,
                    provider="identity",
                )
                day += timedelta(days=1)
            return out

        lookback = self.settings.fx.max_lookback_days
        published = self.published_series(
            currency, start - timedelta(days=lookback), end
        )
        providers = self._provider_labels(currency, start - timedelta(days=lookback), end)

        out = {}
        day = start
        # Prime from the most recent publication before the window.
        last_date: date | None = max((d for d in published if d < start), default=None)

        while day <= end:
            if day in published:
                last_date = day
            if last_date is not None and (day - last_date).days <= lookback:
                out[day] = FxQuote(
                    base=currency,
                    quote=BASE_CURRENCY,
                    rate=published[last_date],
                    rate_date=last_date,
                    requested_date=day,
                    provider=providers.get(last_date, self.provenance_for(currency)),
                )
            else:
                log.warning("no %s/TRY rate available for %s within lookback", currency, day)
            day += timedelta(days=1)
        return out

    def _provider_labels(
        self, currency: str, start: date, end: date
    ) -> dict[date, str]:
        stmt = select(FxCache.rate_date, FxCache.provider).where(
            FxCache.base == currency,
            FxCache.quote == BASE_CURRENCY,
            FxCache.rate_date >= start,
            FxCache.rate_date <= end,
        )
        return {rate_date: provider for rate_date, provider in self.session.execute(stmt)}

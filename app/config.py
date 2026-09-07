"""Configuration loading (SPEC §3 fx routing, §6 haircut, §8 cache TTLs)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from app.calc.tax import DEFAULT_BRACKETS, TaxBracket, TaxConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DEFAULT_DB_PATH = PROJECT_ROOT / "fadir.db"


@dataclass(frozen=True)
class FxConfig:
    default_provider: str = "yfinance"
    #: currency -> provider name. Absent currencies use `default_provider`.
    overrides: dict[str, str] = field(default_factory=dict)
    max_lookback_days: int = 7
    tcmb_api_key: str | None = None

    def provider_for(self, currency: str) -> str:
        return self.overrides.get(currency.upper(), self.default_provider)


@dataclass(frozen=True)
class LiquidationConfig:
    haircut_pct: Decimal = Decimal("0")


@dataclass(frozen=True)
class CacheConfig:
    intraday_quote_ttl_seconds: int = 60
    #: An hour. Share prices are what need to be current; the lira does not move enough
    #: inside one to matter, and a steady rate keeps each cycle to one equity fetch.
    fx_current_ttl_seconds: int = 3600


@dataclass(frozen=True)
class RefreshConfig:
    #: See config.yaml for why 10s is the fast end of what is safe against Yahoo.
    default_interval_seconds: int = 10
    closed_market_interval_seconds: int = 3600


@dataclass(frozen=True)
class HistoryConfig:
    #: Portfolio inception — the first date the daily series covers (SPEC §6). Leave it
    #: unset and the app uses the earliest transaction you hold, which is what a fresh
    #: install wants. Set it only to start the chart later than your first trade.
    start_date: date | None = None


@dataclass(frozen=True)
class GoogleConfig:
    web_client_id: str | None = None
    verification_timeout_seconds: float = 5.0


@dataclass(frozen=True)
class Settings:
    fx: FxConfig = field(default_factory=FxConfig)
    liquidation: LiquidationConfig = field(default_factory=LiquidationConfig)
    tax: TaxConfig = field(default_factory=TaxConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    refresh: RefreshConfig = field(default_factory=RefreshConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    db_path: Path = DEFAULT_DB_PATH
    database_url: str | None = None

    @property
    def database_target(self) -> str | Path:
        return self.database_url if self.database_url is not None else self.db_path

    def __repr__(self) -> str:
        database_url = "<configured>" if self.database_url is not None else None
        return (
            "Settings("
            f"fx={self.fx!r}, liquidation={self.liquidation!r}, tax={self.tax!r}, "
            f"cache={self.cache!r}, refresh={self.refresh!r}, history={self.history!r}, "
            f"google={self.google!r}, "
            f"db_path={self.db_path!r}, database_url={database_url!r})"
        )


def _load_tax(raw: dict[str, Any]) -> TaxConfig:
    """Build the tax config, falling back to the statutory defaults in app.calc.tax."""
    indexing = raw.get("inflation_indexing") or {}

    brackets: tuple[TaxBracket, ...] = DEFAULT_BRACKETS
    configured = raw.get("brackets")
    if configured:
        parsed: list[TaxBracket] = []
        for entry in configured:
            upto = entry.get("upto")
            parsed.append(
                TaxBracket(
                    upper=None if upto in (None, "", "null") else Decimal(str(upto)),
                    rate=Decimal(str(entry.get("rate", "0"))),
                )
            )
        # An open-ended top bracket is required, else a large gain would fall through
        # the tariff untaxed.
        if parsed and parsed[-1].upper is not None:
            parsed.append(TaxBracket(None, parsed[-1].rate))
        if parsed:
            brackets = tuple(parsed)

    return TaxConfig(
        enabled=bool(raw.get("enabled", True)),
        brackets=brackets,
        other_income_try=Decimal(str(raw.get("other_income_try", "0"))),
        exemption_try=Decimal(str(raw.get("exemption_try", "0"))),
        indexing_enabled=bool(indexing.get("enabled", False)),
        indexing_rate=Decimal(str(indexing.get("rate", "0"))),
        indexing_threshold=Decimal(str(indexing.get("threshold", "0.10"))),
    )


def _as_date(value: Any) -> date | None:
    """Parse a config date. Absent, blank or `null` all mean "derive it"."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return None


def load_settings(path: Path | None = None) -> Settings:
    """Load settings from YAML, with env-var overrides for secrets and DB location."""
    path = path or DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    fx_raw = raw.get("fx") or {}
    liq_raw = raw.get("liquidation") or {}
    tax_raw = raw.get("tax") or {}
    cache_raw = raw.get("cache") or {}
    refresh_raw = raw.get("refresh") or {}
    hist_raw = raw.get("history") or {}
    google_raw = raw.get("google") or {}

    overrides = {k.upper(): str(v).lower() for k, v in (fx_raw.get("overrides") or {}).items()}

    fx = FxConfig(
        default_provider=str(fx_raw.get("default_provider", "yfinance")).lower(),
        overrides=overrides,
        max_lookback_days=int(fx_raw.get("max_lookback_days", 7)),
        tcmb_api_key=os.environ.get("FADIR_TCMB_API_KEY") or fx_raw.get("tcmb_api_key"),
    )

    db_path = (
        Path(os.environ["FADIR_DB_PATH"])
        if os.environ.get("FADIR_DB_PATH")
        else DEFAULT_DB_PATH
    )
    database_url = os.environ["FADIR_DATABASE_URL"] if "FADIR_DATABASE_URL" in os.environ else None

    google_client_id = (
        os.environ.get("FADIR_GOOGLE_WEB_CLIENT_ID")
        or os.environ.get("FADIR_GOOGLE_CLIENT_ID")
        or google_raw.get("web_client_id")
    )
    timeout_value = (
        os.environ.get("FADIR_GOOGLE_VERIFICATION_TIMEOUT_SECONDS")
        or google_raw.get("verification_timeout_seconds", 5.0)
    )
    google_timeout = float(timeout_value)
    if not 0.1 <= google_timeout <= 30.0:
        raise ValueError("Google identity verification timeout is outside its allowed range")

    return Settings(
        fx=fx,
        liquidation=LiquidationConfig(
            haircut_pct=Decimal(str(liq_raw.get("haircut_pct", "0"))),
        ),
        tax=_load_tax(tax_raw),
        cache=CacheConfig(
            intraday_quote_ttl_seconds=int(cache_raw.get("intraday_quote_ttl_seconds", 60)),
            fx_current_ttl_seconds=int(cache_raw.get("fx_current_ttl_seconds", 3600)),
        ),
        refresh=RefreshConfig(
            default_interval_seconds=int(refresh_raw.get("default_interval_seconds", 10)),
            closed_market_interval_seconds=int(
                refresh_raw.get("closed_market_interval_seconds", 3600)
            ),
        ),
        history=HistoryConfig(
            start_date=_as_date(hist_raw.get("start_date")),
        ),
        google=GoogleConfig(
            web_client_id=str(google_client_id).strip() if google_client_id else None,
            verification_timeout_seconds=google_timeout,
        ),
        db_path=db_path,
        database_url=database_url,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()

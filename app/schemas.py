"""Pydantic request/response models (SPEC §7).

Money crosses the wire as a JSON **string**, not a float. A float would reintroduce at
the serialisation boundary exactly the imprecision the engine works to avoid, and the
frontend formats from strings anyway.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

#: Serialise Decimal as a plain string to preserve exactness across the wire.
Money = Annotated[Decimal, PlainSerializer(lambda v: str(v), return_type=str)]
OptMoney = Annotated[Decimal | None, PlainSerializer(lambda v: None if v is None else str(v), return_type=str | None)]


class AttributionOut(BaseModel):
    local_return: OptMoney = None
    fx_return: OptMoney = None
    total_return: OptMoney = None
    price_effect_try: Money
    fx_effect_try: Money
    weighted_avg_cost_fx_rate: OptMoney = None
    current_fx_rate: Money


class DailyOut(BaseModel):
    """The move since the previous session, split into price and FX like everything else.

    `available` is false when there is no earlier session on file. The UI must render
    nothing in that case — a zero would assert the position did not move, which is a
    different and unsupported claim.
    """

    available: bool
    reference_date: date | None = None
    pnl_try: Money
    price_effect_try: Money
    fx_effect_try: Money
    pnl_native: Money
    return_ratio: OptMoney = None


class RealizedOut(BaseModel):
    quantity: Money
    pnl_native: Money
    pnl_try: Money
    price_effect_try: Money
    fx_effect_try: Money


class PositionOut(BaseModel):
    ticker: str
    name: str
    exchange: str
    currency: str
    quantity: Money

    average_purchase_price_native: OptMoney = None
    cost_native: Money
    cost_try: Money
    market_value_native: Money
    market_value_try: Money
    pnl_native: Money
    pnl_try: Money

    attribution: AttributionOut
    realized: RealizedOut
    daily: DailyOut

    price_native: Money
    price_date: date
    fx_rate_to_try: Money
    fx_rate_date: date
    fx_provider: str
    #: True when the FX rate came from an explicit USD triangulation (docs/FINDINGS.md F-2).
    fx_triangulated: bool = False
    fx_carried_forward: bool = False

    lot_count: int
    ok: bool
    session: Literal["open", "closed"]
    stale: bool
    error: str | None = None


class TotalsOut(BaseModel):
    cost_try: Money
    market_value_try: Money
    pnl_try: Money
    price_effect_try: Money
    fx_effect_try: Money
    total_return: OptMoney = None
    realized_pnl_try: Money
    realized_price_effect_try: Money
    realized_fx_effect_try: Money
    daily: DailyOut


class LiquidationOut(BaseModel):
    gross_proceeds_try: Money
    haircut_pct: Money
    haircut_try: Money
    net_proceeds_try: Money
    total_invested_try: Money
    net_pnl_try: Money
    net_return: OptMoney = None
    excludes_tax: bool = True
    note: str = (
        "Estimate. Assumes every position is sold at the current market price and fully "
        "converted to TRY today. Excludes tax; FX spread and commission only to the "
        "extent of the configured haircut."
    )


class TaxOut(BaseModel):
    """Approximate Turkish capital gains tax. An estimate, not tax advice."""

    applicable: bool
    gross_gain_try: Money
    taxable_gain_try: Money
    tax_try: Money
    net_after_tax_try: Money
    effective_rate: Money
    marginal_rate: Money
    indexing_applied: bool
    indexing_rate: Money
    #: How the taxable base splits. The FX gain is *inside* the base — Turkish law
    #: measures the gain in lira at acquisition- and disposal-date rates — so these
    #: exist to make that visible, not to add a separate charge.
    price_portion_try: Money
    fx_portion_try: Money
    tax_on_price_try: Money
    tax_on_fx_try: Money
    assumptions: list[str] = Field(default_factory=list)
    disclaimer: str
    tax_year: int | None = None
    jurisdiction: str | None = None
    source_url: str | None = None
    source_version: str | None = None


class TaxProfileIn(BaseModel):
    tax_year: int = Field(ge=2000)
    source_url: str
    source_version: str
    assumptions: list[str] = Field(default_factory=list)
    disclaimer: str


class TaxProfileOut(BaseModel):
    id: int
    jurisdiction: str
    tax_year: int
    currency: str
    source_url: str
    source_version: str
    assumptions: list[str]
    disclaimer: str


class PortfolioOut(BaseModel):
    as_of: datetime
    base_currency: str = "TRY"
    positions: list[PositionOut]
    totals: TotalsOut
    liquidation: LiquidationOut
    tax: TaxOut
    warnings: list[str] = Field(default_factory=list)
    #: Set only when every exchange is shut. The frontend sleeps until this moment
    #: rather than polling for prices that cannot change.
    next_market_open: datetime | None = None


class PortfolioOptionOut(BaseModel):
    id: int
    name: str
    base_currency: str


class PortfolioExportTransactionOut(BaseModel):
    id: int
    portfolio_id: int
    instrument_id: int
    ticker: str
    exchange: str
    yf_symbol: str
    currency: str
    instrument_name: str
    instrument_active: bool
    trade_date: str
    side: Literal["BUY", "SELL"]
    quantity: str
    price_native: str
    fees_native: str
    fee_currency: str | None
    fee_fx_rate_to_try: str
    fee_fx_rate_date: str
    fee_fx_provider: str | None
    fx_rate_to_try: str
    fx_rate_date: str
    fx_provider: str
    note: str | None
    created_at: str
    updated_at: str


class PortfolioExportSnapshotOut(BaseModel):
    snapshot_date: str
    payload_json: str
    created_at: str


class PortfolioExportOut(BaseModel):
    portfolio: dict[str, int | str]
    transactions: list[PortfolioExportTransactionOut]
    snapshots: list[PortfolioExportSnapshotOut]


class HistoryPointOut(BaseModel):
    date: date
    value_try: Money
    value_constant_fx_try: Money
    cost_basis_try: Money
    value_after_tax_try: Money
    pnl_try: Money
    pnl_after_tax_try: Money
    tax_try: Money
    price_effect_try: Money
    fx_effect_try: Money
    price_carried_forward: bool = False
    fx_carried_forward: bool = False
    missing: list[str] = Field(default_factory=list)


class HistoryOut(BaseModel):
    start: date
    end: date
    freq: str
    points: list[HistoryPointOut]
    #: Tickers the series was restricted to; empty means the whole portfolio.
    tickers: list[str] = Field(default_factory=list)


class IntradayPointOut(BaseModel):
    at: datetime
    value_try: Money
    value_constant_fx_try: Money
    cost_basis_try: Money
    value_after_tax_try: Money
    pnl_try: Money
    pnl_after_tax_try: Money
    tax_try: Money
    price_effect_try: Money
    fx_effect_try: Money
    carried_forward: bool = False
    missing: list[str] = Field(default_factory=list)


class IntradayOut(BaseModel):
    interval: str
    session_date: date | None = None
    points: list[IntradayPointOut]
    warnings: list[str] = Field(default_factory=list)
    #: Tickers the series was restricted to; empty means the whole portfolio.
    tickers: list[str] = Field(default_factory=list)
    #: Sessions back from the most recent one: 0 is today (or the last day that traded).
    offset: int = 0
    #: How many sessions Yahoo's retained window actually holds, so the UI knows when
    #: it has reached the end and can stop offering to page further back.
    sessions_available: int = 0


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_id: int
    ticker: str
    currency: str
    trade_date: date
    side: Literal["BUY", "SELL"]
    quantity: Money
    price_native: Money
    fees_native: Money
    fee_currency: str | None = None
    fee_fx_rate_to_try: OptMoney = None
    fee_fx_rate_date: date | None = None
    fee_fx_provider: str | None = None
    total_native: Money
    fx_rate_to_try: Money
    fx_rate_date: date
    fx_provider: str
    fx_carried_forward: bool
    #: Derived at read time, never stored (SPEC §0).
    total_try: Money
    note: str | None = None


class TransactionCreate(BaseModel):
    ticker: str
    trade_date: date
    side: Literal["BUY", "SELL"] = "BUY"
    quantity: Decimal = Field(gt=0)
    price_native: Decimal = Field(ge=0)
    fees_native: Decimal = Field(default=Decimal("0"), ge=0)
    fee_currency: str | None = Field(default=None, min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    fee_fx_rate_override: Decimal | None = Field(default=None, gt=0)
    #: When the broker's executed rate is known and differs from the published reference
    #: rate. Setting this forces `fx_provider = 'manual'` so the UI can flag it (SPEC §7).
    fx_rate_override: Decimal | None = Field(default=None, gt=0)
    note: str | None = None


class TransactionPatch(BaseModel):
    trade_date: date | None = None
    side: Literal["BUY", "SELL"] | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    price_native: Decimal | None = Field(default=None, ge=0)
    fees_native: Decimal | None = Field(default=None, ge=0)
    fee_currency: str | None = Field(default=None, min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    fee_fx_rate_override: Decimal | None = Field(default=None, gt=0)
    fx_rate_override: Decimal | None = Field(default=None, gt=0)
    #: Re-fetch the published rate, discarding a previous manual override.
    refetch_fx: bool = False
    note: str | None = None


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    exchange: str
    yf_symbol: str
    currency: str
    name: str
    active: bool


class InstrumentCreate(BaseModel):
    ticker: str
    exchange: str
    yf_symbol: str
    currency: str
    name: str


class ProviderHealth(BaseModel):
    name: str
    ok: bool
    detail: dict[str, Any] = Field(default_factory=dict)


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    now: datetime
    providers: list[ProviderHealth]
    instruments: list[dict[str, Any]]
    cache: dict[str, Any]
    settings: dict[str, Any]


class RefreshOut(BaseModel):
    ok: bool
    price_rows_written: int
    splits_found: int
    splits_applied: int
    errors: list[str] = Field(default_factory=list)
    per_instrument: dict[str, Any] = Field(default_factory=dict)


class GuestBootstrapGuestOut(BaseModel):
    active: bool
    last_access_at: datetime
    expires_at: datetime
    notice_due: bool = False


class GuestBootstrapOut(BaseModel):
    mode: Literal["guest"] = "guest"
    created: bool
    guest: GuestBootstrapGuestOut
    user: None = None
    portfolios: list[Any] = Field(default_factory=list)
    migration_required: bool = False


class GoogleLoginStartOut(BaseModel):
    client_id: str
    nonce: str
    expires_at: datetime


class GoogleLoginVerifyIn(BaseModel):
    credential: str
    nonce: str


class GoogleLoginVerifyOut(BaseModel):
    expires_at: datetime
    choice_needed: bool = True


class GoogleLoginTransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["claim", "transfer", "merge"]
    rename: str | None = Field(default=None, max_length=128)


class GoogleLoginTransitionOut(BaseModel):
    action: Literal["claim", "transfer", "merge"]


class PortfolioMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_portfolio_id: int = Field(gt=0)
    target_portfolio_id: int = Field(gt=0)


class PortfolioMergeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_transaction_id: int = Field(gt=0)
    action: Literal["keep", "skip"]


class PortfolioMergeConfirmIn(PortfolioMergeRequest):
    revision_token: str = Field(min_length=32, max_length=128)
    decisions: list[PortfolioMergeDecision]


class PortfolioMergeTransactionOut(BaseModel):
    id: int
    instrument_id: int
    currency: str
    trade_date: date
    side: Literal["BUY", "SELL"]
    quantity: Money
    price_native: Money
    fees_native: Money
    fx_rate_to_try: Money
    fx_rate_date: date
    fx_provider: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class PortfolioMergeDifference(BaseModel):
    field: Literal["fees_native", "fx_rate_to_try", "fx_rate_date", "fx_provider"]
    source: str | None
    target: str | None


class PortfolioMergeCandidateOut(BaseModel):
    source: PortfolioMergeTransactionOut
    target: PortfolioMergeTransactionOut
    source_count: int
    target_count: int
    differences: list[PortfolioMergeDifference]


class PortfolioMergePreviewOut(BaseModel):
    source_portfolio_id: int
    target_portfolio_id: int
    source_base_currency: str
    target_base_currency: str
    candidates: list[PortfolioMergeCandidateOut]
    movable_source_rows: list[PortfolioMergeTransactionOut]
    revision_token: str


class PortfolioMergeConfirmOut(BaseModel):
    moved_count: int
    skipped_count: int


class PortfolioMergeOptionOut(BaseModel):
    id: int
    name: str
    base_currency: str


class PortfolioMergeOptionsOut(BaseModel):
    source: list[PortfolioMergeOptionOut]
    target: list[PortfolioMergeOptionOut]

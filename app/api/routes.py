"""API routes (SPEC §7)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.attribution import DailyChange, PositionMetrics
from app.config import Settings, get_settings
from app.api.csrf import (
    CSRF_COOKIE_NAME,
    CsrfError,
    CookiePolicy,
    issue_csrf_token,
    set_csrf_cookie,
    validate_request_csrf,
)
from app.api.request_authority import (
    GUEST_COOKIE_MAX_AGE,
    GUEST_COOKIE_NAME,
    RequestAuthority,
    RequestAuthorityError,
    delete_guest_cookie,
    get_request_authority,
    set_guest_cookie,
)
from app.api.request_transaction import RequestTransactionRoute, request_session
from app.db import get_session
from app.models import FxCache, GuestAccess, Instrument, Portfolio, Side, Transaction
from app.providers import market_hours, yf_client
from app.providers.base import ProviderError, RateUnavailable
from app.providers.fx_service import MANUAL_PROVIDER, FxService
from app.providers.price_service import PriceService
from app.schemas import (
    AttributionOut,
    DailyOut,
    GuestBootstrapOut,
    HealthOut,
    HistoryOut,
    HistoryPointOut,
    InstrumentCreate,
    InstrumentOut,
    IntradayOut,
    IntradayPointOut,
    LiquidationOut,
    PortfolioOut,
    PositionOut,
    ProviderHealth,
    RealizedOut,
    RefreshOut,
    TaxOut,
    TotalsOut,
    TransactionCreate,
    TransactionOut,
    TransactionPatch,
)
from app.services.portfolio import PortfolioService
from app.services.portfolio_scope import PortfolioScope, PortfolioScopeNotFound
from app.services import guest_access

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
private_router = APIRouter(prefix="/api", route_class=RequestTransactionRoute)

SessionDep = Annotated[Session, Depends(get_session)]
RequestSessionDep = Annotated[Session, Depends(request_session)]
AuthorityDep = Annotated[RequestAuthority, Depends(get_request_authority)]


def _write_guard(request: Request, authority: AuthorityDep) -> None:
    validate_request_csrf(request)


def _settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(_settings)]


def _service(session: Session, settings: Settings) -> PortfolioService:
    return PortfolioService(session, settings)


# -- serialisation helpers ---------------------------------------------------------


def _known_tickers(session: Session, requested: list[str] | None) -> list[str] | None:
    """Validate a `ticker` filter against the instruments on file.

    An unknown ticker is rejected rather than quietly ignored: silently returning the
    whole portfolio for `?ticker=TYPO` would look like a working filter that disagrees
    with the positions table.
    """
    if not requested:
        return None

    wanted = {t.strip().upper() for t in requested if t.strip()}
    if not wanted:
        return None

    known = {t.upper() for t in session.execute(select(Instrument.ticker)).scalars()}
    unknown = sorted(wanted - known)
    if unknown:
        raise HTTPException(404, f"unknown ticker(s): {', '.join(unknown)}")
    return sorted(wanted)


def _daily_out(daily: DailyChange) -> DailyOut:
    return DailyOut(
        available=daily.available,
        reference_date=daily.reference_date,
        pnl_try=daily.pnl_try,
        price_effect_try=daily.price_effect_try,
        fx_effect_try=daily.fx_effect_try,
        pnl_native=daily.pnl_native,
        return_ratio=daily.return_ratio,
    )


def _position_out(metrics: PositionMetrics, instrument: Instrument | None) -> PositionOut:
    a = metrics.attribution
    return PositionOut(
        ticker=metrics.ticker,
        name=instrument.name if instrument else metrics.ticker,
        exchange=instrument.exchange if instrument else "",
        currency=metrics.currency,
        quantity=metrics.quantity,
        average_purchase_price_native=metrics.average_purchase_price_native,
        cost_native=metrics.cost_native,
        cost_try=metrics.cost_try,
        market_value_native=metrics.market_value_native,
        market_value_try=metrics.market_value_try,
        pnl_native=metrics.pnl_native,
        pnl_try=metrics.pnl_try,
        attribution=AttributionOut(
            local_return=a.local_return,
            fx_return=a.fx_return,
            total_return=a.total_return,
            price_effect_try=a.price_effect_try,
            fx_effect_try=a.fx_effect_try,
            weighted_avg_cost_fx_rate=a.weighted_avg_cost_fx_rate,
            current_fx_rate=a.current_fx_rate,
        ),
        realized=RealizedOut(
            quantity=metrics.realized.quantity,
            pnl_native=metrics.realized.pnl_native,
            pnl_try=metrics.realized.pnl_try,
            price_effect_try=metrics.realized.price_effect_try,
            fx_effect_try=metrics.realized.fx_effect_try,
        ),
        daily=_daily_out(metrics.daily),
        price_native=metrics.price_native,
        price_date=metrics.price_date,
        fx_rate_to_try=metrics.fx_rate_to_try,
        fx_rate_date=metrics.fx_rate_date,
        fx_provider=metrics.fx_provider,
        fx_triangulated="*" in metrics.fx_provider,
        fx_carried_forward=metrics.fx_carried_forward,
        lot_count=metrics.lot_count,
        ok=metrics.ok,
        session=metrics.session,  # type: ignore[arg-type]
        stale=metrics.stale,
        error=metrics.error,
    )


def _transaction_out(txn: Transaction) -> TransactionOut:
    total_native = txn.quantity * txn.price_native
    return TransactionOut(
        id=txn.id,
        instrument_id=txn.instrument_id,
        ticker=txn.instrument.ticker,
        currency=txn.instrument.currency,
        trade_date=txn.trade_date,
        side=txn.side.value,  # type: ignore[arg-type]
        quantity=txn.quantity,
        price_native=txn.price_native,
        fees_native=txn.fees_native,
        total_native=total_native,
        fx_rate_to_try=txn.fx_rate_to_try,
        fx_rate_date=txn.fx_rate_date,
        fx_provider=txn.fx_provider,
        fx_carried_forward=txn.fx_carried_forward,
        # Always derived, never stored (SPEC §0).
        total_try=(total_native + txn.fees_native) * txn.fx_rate_to_try,
        note=txn.note,
    )


def _empty_portfolio_out() -> PortfolioOut:
    zero = Decimal("0")
    daily = DailyOut(
        available=False,
        reference_date=None,
        pnl_try=zero,
        price_effect_try=zero,
        fx_effect_try=zero,
        pnl_native=zero,
        return_ratio=None,
    )
    return PortfolioOut(
        as_of=datetime.now(timezone.utc),
        positions=[],
        totals=TotalsOut(
            cost_try=zero,
            market_value_try=zero,
            pnl_try=zero,
            price_effect_try=zero,
            fx_effect_try=zero,
            total_return=None,
            realized_pnl_try=zero,
            realized_price_effect_try=zero,
            realized_fx_effect_try=zero,
            daily=daily,
        ),
        liquidation=LiquidationOut(
            gross_proceeds_try=zero,
            haircut_pct=zero,
            haircut_try=zero,
            net_proceeds_try=zero,
            total_invested_try=zero,
            net_pnl_try=zero,
            net_return=None,
        ),
        tax=TaxOut(
            applicable=False,
            gross_gain_try=zero,
            taxable_gain_try=zero,
            tax_try=zero,
            net_after_tax_try=zero,
            effective_rate=zero,
            marginal_rate=zero,
            indexing_applied=False,
            indexing_rate=zero,
            price_portion_try=zero,
            fx_portion_try=zero,
            tax_on_price_try=zero,
            tax_on_fx_try=zero,
            assumptions=[],
            disclaimer="No Portfolio selected.",
        ),
        warnings=[],
        next_market_open=None,
    )


def _bootstrap_origin_guard(request: Request) -> None:
    configured = getattr(request.app.state, "configured_origin", None)
    if type(configured) is not str or not configured:
        raise CsrfError()
    expected = configured.rstrip("/")
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        parsed = urlsplit(referer) if referer else None
        origin = (
            f"{parsed.scheme}://{parsed.netloc}"
            if parsed and parsed.scheme in {"http", "https"} and parsed.netloc
            else None
        )
    if origin != expected:
        raise CsrfError()


def _guest_bootstrap_context(session: Session, row: GuestAccess) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    last_access = row.last_access_at
    if last_access.tzinfo is None:
        last_access = last_access.replace(tzinfo=timezone.utc)
    expires_at = last_access + timedelta(days=90)
    has_saved_portfolio = session.execute(
        select(Portfolio.id).where(Portfolio.workspace_id == row.workspace_id).limit(1)
    ).first() is not None
    return {
        "active": row.revoked_at is None and now < expires_at,
        "last_access_at": last_access,
        "expires_at": expires_at,
        "notice_due": has_saved_portfolio,
    }


@private_router.post("/guest/bootstrap", response_model=GuestBootstrapOut)
def bootstrap_guest(
    request: Request,
    response: Response,
    session: RequestSessionDep,
) -> GuestBootstrapOut | Response:
    """Issue or revalidate one Guest Workspace without exposing its authority."""
    _bootstrap_origin_guard(request)
    token = request.cookies.get(GUEST_COOKIE_NAME)
    created = token is None
    if created:
        issued = guest_access.issue(
            session, clock=lambda: datetime.now(timezone.utc)
        )
        workspace_id = issued.workspace_id
    else:
        try:
            authority = guest_access.require(
                session, token, clock=lambda: datetime.now(timezone.utc)
            )
        except Exception:
            delete_guest_cookie(response)
            response.status_code = 401
            response.body = b'{"detail":"request rejected"}'
            response.media_type = "application/json"
            return response
        workspace_id = authority.workspace_id

    row = session.get(GuestAccess, workspace_id)
    if row is None:
        raise RequestAuthorityError()
    if created:
        set_guest_cookie(response, issued.secret.get_secret_value())
    if CSRF_COOKIE_NAME not in request.cookies:
        set_csrf_cookie(
            response,
            issue_csrf_token(),
            policy=CookiePolicy(max_age=GUEST_COOKIE_MAX_AGE),
        )
    if created:
        response.status_code = 201
    return GuestBootstrapOut(
        created=created, guest=_guest_bootstrap_context(session, row)
    )


def _scope(
    session: Session,
    authority: RequestAuthority,
    portfolio_id: int | None,
    *,
    for_write: bool = False,
) -> PortfolioScope | None:
    try:
        if for_write:
            return PortfolioScope.select_for_write(
                session,
                workspace_id=authority.workspace_id,
                portfolio_id=portfolio_id,
            )
        return PortfolioScope.select(
            session,
            workspace_id=authority.workspace_id,
            portfolio_id=portfolio_id,
        )
    except PortfolioScopeNotFound as exc:
        raise HTTPException(404, "Portfolio not found") from exc


# -- portfolio ---------------------------------------------------------------------


@private_router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio(
    session: RequestSessionDep,
    authority: AuthorityDep,
    settings: SettingsDep,
    portfolio_id: int | None = Query(default=None),
) -> PortfolioOut:
    scope = _scope(session, authority, portfolio_id)
    if scope is None:
        return _empty_portfolio_out()
    service = _service(session, settings)
    service = service.scoped(scope)
    view = service.build_view()

    return PortfolioOut(
        as_of=view.as_of,
        # The view already loaded these; re-querying them here was a third pass over
        # the same table for data that is sitting in hand.
        positions=[_position_out(p, view.instruments.get(p.ticker)) for p in view.positions],
        totals=TotalsOut(
            cost_try=view.totals.cost_try,
            market_value_try=view.totals.market_value_try,
            pnl_try=view.totals.pnl_try,
            price_effect_try=view.totals.price_effect_try,
            fx_effect_try=view.totals.fx_effect_try,
            total_return=view.totals.total_return,
            realized_pnl_try=view.totals.realized_pnl_try,
            realized_price_effect_try=view.totals.realized_price_effect_try,
            realized_fx_effect_try=view.totals.realized_fx_effect_try,
            daily=_daily_out(view.totals.daily),
        ),
        liquidation=LiquidationOut(
            gross_proceeds_try=view.liquidation.gross_proceeds_try,
            haircut_pct=view.liquidation.haircut_pct,
            haircut_try=view.liquidation.haircut_try,
            net_proceeds_try=view.liquidation.net_proceeds_try,
            total_invested_try=view.liquidation.total_invested_try,
            net_pnl_try=view.liquidation.net_pnl_try,
            net_return=view.liquidation.net_return,
        ),
        tax=TaxOut(
            applicable=view.tax.applicable,
            gross_gain_try=view.tax.gross_gain_try,
            taxable_gain_try=view.tax.taxable_gain_try,
            tax_try=view.tax.tax_try,
            net_after_tax_try=view.tax.net_after_tax_try,
            effective_rate=view.tax.effective_rate,
            marginal_rate=view.tax.marginal_rate,
            indexing_applied=view.tax.indexing_applied,
            indexing_rate=view.tax.indexing_rate,
            price_portion_try=view.tax.price_portion_try,
            fx_portion_try=view.tax.fx_portion_try,
            tax_on_price_try=view.tax.tax_on_price_try,
            tax_on_fx_try=view.tax.tax_on_fx_try,
            assumptions=view.tax.assumptions,
            disclaimer=view.tax.disclaimer,
        ),
        warnings=view.warnings,
        next_market_open=view.next_market_open,
    )


@private_router.get("/portfolio/history", response_model=HistoryOut)
def get_history(
    session: RequestSessionDep,
    authority: AuthorityDep,
    settings: SettingsDep,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    freq: str = Query(default="D", pattern="^[DWMdwm]$"),
    ticker: list[str] | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
) -> HistoryOut:
    scope = _scope(session, authority, portfolio_id)
    if scope is None:
        start = from_ or date.today()
        end = to or start
        if start > end:
            raise HTTPException(422, "`from` must not be after `to`")
        return HistoryOut(
            start=start, end=end, freq=freq.upper(), tickers=[], points=[]
        )
    service = _service(session, settings).scoped(scope)
    start = from_ or service.inception()
    end = to or date.today()
    if start > end:
        raise HTTPException(422, "`from` must not be after `to`")

    tickers = _known_tickers(session, ticker)
    points = service.build_history(start, end, freq.upper(), tickers=tickers)
    return HistoryOut(
        start=start,
        end=end,
        freq=freq.upper(),
        tickers=tickers or [],
        points=[
            HistoryPointOut(
                date=p.point_date,
                value_try=p.value_try,
                value_constant_fx_try=p.value_constant_fx_try,
                cost_basis_try=p.cost_basis_try,
                value_after_tax_try=p.value_after_tax_try,
                pnl_try=p.pnl_try,
                pnl_after_tax_try=p.pnl_after_tax_try,
                tax_try=p.tax_try,
                price_effect_try=p.price_effect_try,
                fx_effect_try=p.fx_effect_try,
                price_carried_forward=p.price_carried_forward,
                fx_carried_forward=p.fx_carried_forward,
                missing=list(p.missing),
            )
            for p in points
        ],
    )


@private_router.get("/portfolio/intraday", response_model=IntradayOut)
def get_intraday(
    session: RequestSessionDep,
    authority: AuthorityDep,
    settings: SettingsDep,
    interval: str = Query(default="5m", pattern="^(5m|15m|1h)$"),
    force: bool = Query(default=False),
    ticker: list[str] | None = Query(default=None),
    offset: int = Query(default=0, ge=0, le=30),
    portfolio_id: int | None = Query(default=None),
) -> IntradayOut:
    """The 1G view (SPEC §9 range selector, extended).

    Intraday bars are not persisted — see `app/providers/intraday.py` for why. `force`
    bypasses the short in-process TTL so the manual refresh button gets fresh bars.
    `ticker` narrows the series to a subset, as on the daily history.
    """
    scope = _scope(session, authority, portfolio_id)
    if scope is None:
        return IntradayOut(interval=interval, tickers=[], offset=offset, points=[])
    service = _service(session, settings).scoped(scope)
    tickers = _known_tickers(session, ticker)
    points, warnings, sessions_available = service.build_intraday(
        interval, force=force, tickers=tickers, session_offset=offset
    )

    return IntradayOut(
        interval=interval,
        session_date=points[0].at.date() if points else None,
        tickers=tickers or [],
        offset=offset,
        sessions_available=sessions_available,
        points=[
            IntradayPointOut(
                at=p.at,
                value_try=p.value_try,
                value_constant_fx_try=p.value_constant_fx_try,
                cost_basis_try=p.cost_basis_try,
                value_after_tax_try=p.value_after_tax_try,
                pnl_try=p.pnl_try,
                pnl_after_tax_try=p.value_after_tax_try - p.cost_basis_try,
                tax_try=p.value_try - p.value_after_tax_try,
                price_effect_try=p.price_effect_try,
                fx_effect_try=p.fx_effect_try,
                carried_forward=p.carried_forward,
                missing=list(p.missing),
            )
            for p in points
        ],
        warnings=warnings,
    )


# -- transactions ------------------------------------------------------------------


def _load_transactions(session: Session, scope: PortfolioScope) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.instrument))
        .where(Transaction.portfolio_id == scope.portfolio.id)
        .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
    )
    return list(session.execute(stmt).scalars())


@private_router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    session: RequestSessionDep,
    authority: AuthorityDep,
    portfolio_id: int | None = Query(default=None),
) -> list[TransactionOut]:
    scope = _scope(session, authority, portfolio_id)
    if scope is None:
        return []
    return [_transaction_out(t) for t in _load_transactions(session, scope)]


def _resolve_fx(
    fx: FxService, currency: str, trade_date: date, override: Decimal | None
) -> tuple[Decimal, date, str]:
    """Published rate for the trade date, or the caller's executed rate.

    An override is the broker's actual executed rate, so it is recorded against the trade
    date itself with `fx_provider='manual'` — the UI flags it (SPEC §7).
    """
    if override is not None:
        return override, trade_date, MANUAL_PROVIDER
    try:
        quote = fx.quote(currency, trade_date)
    except (RateUnavailable, ProviderError) as exc:
        raise HTTPException(
            502,
            f"could not resolve {currency}/TRY for {trade_date}: {exc}. "
            f"Supply fx_rate_override to record the executed rate instead.",
        ) from exc
    return quote.rate, quote.rate_date, quote.provider


@private_router.post(
    "/transactions",
    response_model=TransactionOut,
    status_code=201,
    dependencies=[Depends(_write_guard)],
)
def create_transaction(
    payload: TransactionCreate,
    session: RequestSessionDep,
    authority: AuthorityDep,
    settings: SettingsDep,
    portfolio_id: int | None = Query(default=None),
) -> TransactionOut:
    instrument = session.execute(
        select(Instrument).where(Instrument.ticker == payload.ticker)
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(404, f"unknown ticker {payload.ticker!r}")

    fx = FxService(session, settings)
    rate, rate_date, provider = _resolve_fx(
        fx, instrument.currency, payload.trade_date, payload.fx_rate_override
    )

    txn = Transaction(
        instrument_id=instrument.id,
        trade_date=payload.trade_date,
        side=Side(payload.side),
        quantity=payload.quantity,
        price_native=payload.price_native,
        fees_native=payload.fees_native,
        fx_rate_to_try=rate,
        fx_rate_date=rate_date,
        fx_provider=provider,
        note=payload.note,
    )
    scope = _scope(session, authority, portfolio_id, for_write=True)
    assert scope is not None
    scope.add(txn)
    session.flush()
    session.refresh(txn)
    return _transaction_out(txn)


@private_router.patch(
    "/transactions/{txn_id}",
    response_model=TransactionOut,
    dependencies=[Depends(_write_guard)],
)
def update_transaction(
    txn_id: int,
    payload: TransactionPatch,
    session: RequestSessionDep,
    authority: AuthorityDep,
    settings: SettingsDep,
    portfolio_id: int | None = Query(default=None),
) -> TransactionOut:
    scope = _scope(session, authority, portfolio_id)
    if scope is None:
        raise HTTPException(404, f"transaction {txn_id} not found")
    txn = scope.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(404, f"transaction {txn_id} not found")

    for field in ("trade_date", "quantity", "price_native", "fees_native", "note"):
        value = getattr(payload, field)
        if value is not None:
            setattr(txn, field, value)
    if payload.side is not None:
        txn.side = Side(payload.side)

    fx = FxService(session, settings)
    if payload.fx_rate_override is not None:
        txn.fx_rate_to_try = payload.fx_rate_override
        txn.fx_rate_date = txn.trade_date
        txn.fx_provider = MANUAL_PROVIDER
    elif payload.refetch_fx or payload.trade_date is not None:
        # The trade date moved, so the previously recorded rate belongs to the wrong day.
        rate, rate_date, provider = _resolve_fx(fx, txn.instrument.currency, txn.trade_date, None)
        txn.fx_rate_to_try = rate
        txn.fx_rate_date = rate_date
        txn.fx_provider = provider

    session.flush()
    session.refresh(txn)
    return _transaction_out(txn)


@private_router.delete(
    "/transactions/{txn_id}",
    status_code=204,
    dependencies=[Depends(_write_guard)],
)
def delete_transaction(
    txn_id: int,
    session: RequestSessionDep,
    authority: AuthorityDep,
    portfolio_id: int | None = Query(default=None),
) -> None:
    scope = _scope(session, authority, portfolio_id)
    if scope is None:
        raise HTTPException(404, f"transaction {txn_id} not found")
    txn = scope.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(404, f"transaction {txn_id} not found")
    session.delete(txn)
    session.flush()


# -- instruments -------------------------------------------------------------------


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(session: SessionDep) -> list[InstrumentOut]:
    stmt = select(Instrument).order_by(Instrument.ticker)
    return [InstrumentOut.model_validate(i) for i in session.execute(stmt).scalars()]


@router.post("/instruments", response_model=InstrumentOut, status_code=201)
def create_instrument(payload: InstrumentCreate, session: SessionDep) -> InstrumentOut:
    """Validates the symbol against yfinance before insert (SPEC §7)."""
    existing = session.execute(
        select(Instrument).where(
            (Instrument.ticker == payload.ticker) | (Instrument.yf_symbol == payload.yf_symbol)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, f"{payload.ticker} / {payload.yf_symbol} already exists")

    probe = yf_client.fetch_last_close(payload.yf_symbol)
    if probe is None:
        raise HTTPException(
            422,
            f"yfinance returned no price data for {payload.yf_symbol!r}; "
            f"refusing to add an unverifiable symbol",
        )

    reported = yf_client.fetch_currency(payload.yf_symbol)
    if reported and reported != payload.currency.upper():
        raise HTTPException(
            422,
            f"{payload.yf_symbol} trades in {reported}, not {payload.currency.upper()}",
        )

    instrument = Instrument(
        ticker=payload.ticker,
        exchange=payload.exchange,
        yf_symbol=payload.yf_symbol,
        currency=payload.currency.upper(),
        name=payload.name,
        active=True,
    )
    session.add(instrument)
    session.commit()
    session.refresh(instrument)
    return InstrumentOut.model_validate(instrument)


# -- operations --------------------------------------------------------------------


@private_router.post(
    "/refresh",
    response_model=RefreshOut,
    dependencies=[Depends(_write_guard)],
)
def refresh(
    session: RequestSessionDep,
    settings: SettingsDep,
    _authority: AuthorityDep,
) -> RefreshOut:
    """Force cache invalidation and refetch (SPEC §7, US-5.2)."""
    service = _service(session, settings)
    report = service.refresh_shared(force=True)
    return RefreshOut(
        ok=not report.errors,
        price_rows_written=report.price_rows_written,
        splits_found=report.splits_found,
        splits_applied=report.splits_applied,
        errors=report.errors,
        per_instrument={
            ticker: {
                "ok": s.ok,
                "last_close": str(s.last_close) if s.last_close is not None else None,
                "last_traded": s.last_traded.isoformat() if s.last_traded else None,
                "session": s.session,
                "stale": s.stale,
                "error": s.error,
            }
            for ticker, s in report.per_instrument.items()
        },
    )


@router.get("/health", response_model=HealthOut)
def health(session: SessionDep, settings: SettingsDep) -> HealthOut:
    """Per-provider status, last successful fetch, and cache age (SPEC §7)."""
    now = datetime.now(timezone.utc)
    prices = PriceService(session, settings)
    fx = FxService(session, settings)

    instrument_status: list[dict[str, object]] = []
    degraded = False

    for instrument in session.execute(select(Instrument)).scalars():
        latest = prices.last_cached_close(instrument.id)
        is_open = market_hours.is_open(instrument.exchange, now)
        ok = latest is not None
        degraded = degraded or not ok
        instrument_status.append(
            {
                "ticker": instrument.ticker,
                "yf_symbol": instrument.yf_symbol,
                "currency": instrument.currency,
                "exchange": instrument.exchange,
                "market_open": is_open,
                "last_close": str(latest[0]) if latest else None,
                "last_traded": latest[1].isoformat() if latest else None,
                "ok": ok,
            }
        )

    providers: list[ProviderHealth] = []
    seen: set[str] = set()
    for currency in sorted({i["currency"] for i in instrument_status}):  # type: ignore[misc]
        label = fx.provenance_for(str(currency))
        if label in seen:
            continue
        seen.add(label)

        row = session.execute(
            select(FxCache)
            .where(FxCache.provider == label)
            .order_by(FxCache.rate_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        ok = row is not None
        degraded = degraded or not ok
        providers.append(
            ProviderHealth(
                name=label,
                ok=ok,
                detail={
                    "currency": currency,
                    "configured_provider": settings.fx.provider_for(str(currency)),
                    "triangulated": "*" in label,
                    "last_rate_date": row.rate_date.isoformat() if row else None,
                    "last_fetched_at": row.fetched_at.isoformat() if row else None,
                    "cache_age_seconds": (
                        int((now.replace(tzinfo=None) - row.fetched_at).total_seconds())
                        if row
                        else None
                    ),
                    "last_rate": str(row.rate) if row else None,
                },
            )
        )

    return HealthOut(
        status="degraded" if degraded else "ok",
        now=now,
        providers=providers,
        instruments=instrument_status,
        cache={
            "intraday_quote_ttl_seconds": settings.cache.intraday_quote_ttl_seconds,
            "fx_current_ttl_seconds": settings.cache.fx_current_ttl_seconds,
            "daily_close_policy": "permanent (settled closes are immutable)",
            "fx_historical_policy": "permanent",
        },
        settings={
            "base_currency": "TRY",
            "default_refresh_seconds": settings.refresh.default_interval_seconds,
            "closed_market_refresh_seconds": settings.refresh.closed_market_interval_seconds,
            "liquidation_haircut_pct": str(settings.liquidation.haircut_pct),
            "fx_max_lookback_days": settings.fx.max_lookback_days,
            "history_start": _service(session, settings).inception().isoformat(),
        },
    )

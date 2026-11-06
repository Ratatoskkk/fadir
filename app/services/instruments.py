"""Finding instruments by search and adding them from a Yahoo symbol alone.

The User types a name or ticker; known instruments come first, then Yahoo matches.
Picking a Yahoo match is enough to trade it: the service verifies the symbol has prices
and reads its currency, so nobody types an exchange, currency, or display name.
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Instrument
from app.providers import yf_client

#: Yahoo exchange codes mapped onto the codes `market_hours` knows. Others are kept as
#: Yahoo reports them; an unknown exchange is simply treated as closed.
YAHOO_EXCHANGES = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NAS": "NASDAQ",
    "NYQ": "NYSE",
    "ASE": "NYSE",
    "PCX": "NYSE",
    "TAI": "TPE",
    "GER": "ETR",
}


#: Characters a Yahoo symbol may use; the schemas enforce the same pattern.
SYMBOL_PATTERN = re.compile(r"[A-Za-z0-9^][A-Za-z0-9.=^-]{0,31}")

#: Shared instruments one workspace may create per rolling window.
CREATION_LIMIT = 20
CREATION_WINDOW_SECONDS = 24 * 3600


class InstrumentRejected(ValueError):
    """The symbol cannot be added (no prices, no currency, or unknown to Yahoo)."""


class InstrumentBudgetExceeded(InstrumentRejected):
    """The workspace created too many new instruments in the last 24 hours."""


_created: dict[int | None, deque[float]] = defaultdict(deque)
_created_lock = threading.Lock()


def reset_creation_budget() -> None:
    with _created_lock:
        _created.clear()


def _budget_left(workspace_id: int | None, now: float) -> bool:
    with _created_lock:
        stamps = _created[workspace_id]
        while stamps and stamps[0] <= now - CREATION_WINDOW_SECONDS:
            stamps.popleft()
        return len(stamps) < CREATION_LIMIT


def _spend_budget(workspace_id: int | None, now: float) -> None:
    with _created_lock:
        _created[workspace_id].append(now)


@dataclass(frozen=True)
class SearchResult:
    yf_symbol: str
    ticker: str
    name: str
    exchange: str
    currency: str | None
    known: bool


def _exchange(yahoo_code: str) -> str:
    code = yahoo_code.upper()
    return YAHOO_EXCHANGES.get(code, code)[:16]


def search(session: Session, query: str, limit: int = 8) -> list[SearchResult]:
    text = query.strip()
    if not text:
        return []
    pattern = f"%{text.upper()}%"
    known = list(
        session.scalars(
            select(Instrument)
            .where(
                or_(
                    func.upper(Instrument.ticker).like(pattern),
                    func.upper(Instrument.yf_symbol).like(pattern),
                    func.upper(Instrument.name).like(pattern),
                )
            )
            .order_by(Instrument.ticker)
            .limit(limit)
        )
    )
    results = [
        SearchResult(i.yf_symbol, i.ticker, i.name, i.exchange, i.currency, True) for i in known
    ]
    seen = {i.yf_symbol.upper() for i in known}
    for match in yf_client.search_symbols(text, limit):
        symbol = match["symbol"].upper()
        if not SYMBOL_PATTERN.fullmatch(symbol):
            continue
        if symbol in seen or len(results) >= limit:
            continue
        seen.add(symbol)
        results.append(
            SearchResult(
                symbol,
                symbol,
                match["name"][:128],
                _exchange(match["exchange"]),
                None,
                False,
            )
        )
    return results


def ensure_instrument(
    session: Session, yf_symbol: str, workspace_id: int | None = None
) -> Instrument:
    """The instrument for `yf_symbol`, adding it after checking Yahoo has prices for it.

    A new instrument takes the full symbol as its ticker, so nobody can claim a short
    ticker in the shared table. Each workspace may add `CREATION_LIMIT` new instruments
    per rolling day; finding an existing one is free.
    """
    symbol = yf_symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise InstrumentRejected("invalid symbol")
    existing = session.scalar(select(Instrument).where(func.upper(Instrument.yf_symbol) == symbol))
    if existing is not None:
        return existing
    if session.scalar(select(Instrument.id).where(Instrument.ticker == symbol)) is not None:
        raise InstrumentRejected(f"ticker {symbol} is taken")
    if not _budget_left(workspace_id, time.monotonic()):
        raise InstrumentBudgetExceeded("too many new instruments")

    if yf_client.fetch_last_close(symbol) is None:
        raise InstrumentRejected(f"no price data for {symbol}")
    currency = yf_client.fetch_currency(symbol)
    if not currency or len(currency) != 3:
        raise InstrumentRejected(f"no trading currency for {symbol}")
    meta = next((m for m in yf_client.search_symbols(symbol, 20) if m["symbol"].upper() == symbol), None)

    instrument = Instrument(
        ticker=symbol,
        exchange=_exchange(meta["exchange"]) if meta else "",
        yf_symbol=symbol,
        currency=currency,
        name=(meta["name"] if meta else symbol)[:128],
        active=True,
    )
    session.add(instrument)
    session.flush()
    _spend_budget(workspace_id, time.monotonic())
    return instrument

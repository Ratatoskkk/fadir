"""Finding instruments by search and adding them from a Yahoo symbol alone.

The User types a name or ticker; known instruments come first, then Yahoo matches.
Picking a Yahoo match is enough to trade it: the service verifies the symbol has prices
and reads its currency, so nobody types an exchange, currency, or display name.
"""

from __future__ import annotations

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


class InstrumentRejected(ValueError):
    """The symbol cannot be added (no prices, no currency, or unknown to Yahoo)."""


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


def _suggested_ticker(session: Session, yf_symbol: str) -> str:
    """The symbol without its market suffix, unless another instrument already uses it."""
    base = yf_symbol.split(".", 1)[0].upper()
    taken = session.scalar(select(Instrument.id).where(Instrument.ticker == base))
    return yf_symbol.upper() if taken else base


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
        if symbol in seen or len(results) >= limit:
            continue
        seen.add(symbol)
        results.append(
            SearchResult(
                symbol,
                _suggested_ticker(session, symbol),
                match["name"][:128],
                _exchange(match["exchange"]),
                None,
                False,
            )
        )
    return results


def ensure_instrument(session: Session, yf_symbol: str) -> Instrument:
    """The instrument for `yf_symbol`, adding it after checking Yahoo has prices for it."""
    symbol = yf_symbol.strip().upper()
    if not symbol or len(symbol) > 32:
        raise InstrumentRejected("invalid symbol")
    existing = session.scalar(select(Instrument).where(func.upper(Instrument.yf_symbol) == symbol))
    if existing is not None:
        return existing

    if yf_client.fetch_last_close(symbol) is None:
        raise InstrumentRejected(f"no price data for {symbol}")
    currency = yf_client.fetch_currency(symbol)
    if not currency or len(currency) != 3:
        raise InstrumentRejected(f"no trading currency for {symbol}")
    meta = next((m for m in yf_client.search_symbols(symbol, 20) if m["symbol"].upper() == symbol), None)

    instrument = Instrument(
        ticker=_suggested_ticker(session, symbol),
        exchange=_exchange(meta["exchange"]) if meta else "",
        yf_symbol=symbol,
        currency=currency,
        name=(meta["name"] if meta else symbol)[:128],
        active=True,
    )
    session.add(instrument)
    session.flush()
    return instrument

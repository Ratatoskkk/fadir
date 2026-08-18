"""Instrument bootstrap and seed CSV import (SPEC §10, Epic 1).

US-1.1 — every imported transaction stores `price_native` in its native currency plus a
separately fetched `fx_rate_to_try` with its own `fx_rate_date` and `fx_provider`. No
TRY-denominated total is ever stored.

US-1.2 — totals are recomputed from `quantity x price_native` and never trusted from
input. If the source carries a stated total that disagrees, the recomputed figure wins and
the discrepancy is logged (see docs/FINDINGS.md F-6: the supplied CSV has no total column, so
the check is a no-op against it, but the rule is implemented and tested).
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Instrument, Side, Transaction
from app.providers.fx_service import FxService
from app.registry import REGISTRY

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Your own transactions. Git ignores `data/`, so what you put here stays local. The file
#: is optional: with no CSV the app simply starts empty and you add holdings in the UI.
DEFAULT_SEED_CSV = PROJECT_ROOT / "data" / "seed_transactions.csv"

#: A worked example against real, public symbols. Copy it to DEFAULT_SEED_CSV to try the
#: dashboard with data, or read it to see the column shape.
EXAMPLE_SEED_CSV = PROJECT_ROOT / "examples" / "seed_transactions.example.csv"

#: Column names that, if present, hold a pre-computed total we must not trust.
TOTAL_COLUMNS = ("total_native", "total", "amount", "gross")

#: Tolerance below which a stated/recomputed difference is just formatting noise.
TOTAL_TOLERANCE = Decimal("0.005")


@dataclass
class ImportReport:
    instruments_created: int = 0
    transactions_created: int = 0
    skipped_existing: int = 0
    discrepancies: list[str] = field(default_factory=list)
    fx_carried_forward: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def instrument_from_row(row: dict[str, str]) -> Instrument | None:
    """Build an Instrument from a CSV row, or None if the row does not describe one.

    The registry ships empty, so the CSV is the ordinary way an instrument first appears.
    Every column needed is already there for the transaction itself, bar the display name,
    which falls back to the ticker.
    """
    ticker = (row.get("ticker") or "").strip()
    exchange = (row.get("exchange") or "").strip()
    yf_symbol = (row.get("yf_symbol") or "").strip()
    currency = (row.get("currency") or "").strip().upper()
    if not (ticker and exchange and yf_symbol and currency):
        return None
    return Instrument(
        ticker=ticker,
        exchange=exchange,
        yf_symbol=yf_symbol,
        currency=currency,
        name=(row.get("name") or "").strip() or ticker,
        active=True,
    )


def ensure_instruments(session: Session) -> int:
    """Create any registry instrument not yet in the DB. Returns how many were created."""
    existing = set(session.execute(select(Instrument.ticker)).scalars())
    created = 0
    for entry in REGISTRY:
        if entry.ticker in existing:
            continue
        session.add(
            Instrument(
                ticker=entry.ticker,
                exchange=entry.exchange,
                yf_symbol=entry.yf_symbol,
                currency=entry.currency,
                name=entry.name,
                active=True,
            )
        )
        created += 1
    session.flush()
    return created


def _parse_decimal(raw: str | None, field_name: str, row_no: int) -> Decimal:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"row {row_no}: missing {field_name}")
    try:
        return Decimal(str(raw).strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"row {row_no}: cannot parse {field_name}={raw!r}") from exc


def _stated_total(row: dict[str, str]) -> Decimal | None:
    for column in TOTAL_COLUMNS:
        if column in row and str(row[column]).strip():
            try:
                return Decimal(str(row[column]).strip().replace(",", ""))
            except InvalidOperation:
                return None
    return None


def import_seed_csv(
    session: Session,
    settings: Settings,
    csv_path: Path | None = None,
    *,
    fx_service: FxService | None = None,
) -> ImportReport:
    """Import the seed CSV, fetching an FX rate for every trade date.

    Idempotent on `(instrument, trade_date, side, quantity, price_native)`: re-running
    against the same file adds nothing.
    """
    csv_path = csv_path or DEFAULT_SEED_CSV
    report = ImportReport()

    report.instruments_created = ensure_instruments(session)

    # A fresh install has no CSV. That is the blank slate working as intended, not a
    # failure — the schema is ready and the user adds holdings in the dashboard.
    if not csv_path.exists():
        log.info("no seed CSV at %s; starting empty", csv_path)
        session.flush()
        return report

    instruments = {
        i.ticker: i for i in session.execute(select(Instrument)).scalars()
    }

    fx = fx_service or FxService(session, settings)

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    # Warm the FX cache once per currency across the full date span, rather than issuing
    # a request per row.
    trade_dates = [date.fromisoformat(r["trade_date"].strip()) for r in rows if r.get("trade_date")]
    if trade_dates:
        currencies = {r["currency"].strip().upper() for r in rows if r.get("currency")}
        for currency in sorted(currencies):
            try:
                fx.warm(currency, min(trade_dates), max(trade_dates))
            except Exception as exc:  # noqa: BLE001 - report, continue with other currencies
                log.error("could not warm FX for %s: %s", currency, exc)
                report.errors.append(f"FX warm failed for {currency}: {exc}")

    for row_no, row in enumerate(rows, start=2):  # header is line 1
        try:
            ticker = row["ticker"].strip()
            instrument = instruments.get(ticker)
            if instrument is None:
                instrument = instrument_from_row(row)
                if instrument is None:
                    report.errors.append(
                        f"row {row_no}: unknown ticker {ticker!r} and the row does not "
                        f"carry exchange, yf_symbol and currency to create it"
                    )
                    continue
                session.add(instrument)
                session.flush()
                instruments[ticker] = instrument
                report.instruments_created += 1

            trade_date = date.fromisoformat(row["trade_date"].strip())
            side = Side(row["side"].strip().upper())
            quantity = _parse_decimal(row.get("quantity"), "quantity", row_no)
            price = _parse_decimal(row.get("price_native"), "price_native", row_no)

            # US-1.2: recompute, never trust.
            computed_total = quantity * price
            stated = _stated_total(row)
            if stated is not None and abs(stated - computed_total) > TOTAL_TOLERANCE:
                message = (
                    f"row {row_no} ({ticker} {trade_date}): stated total {stated} "
                    f"disagrees with {quantity} x {price} = {computed_total}; "
                    f"using {computed_total}"
                )
                log.warning(message)
                report.discrepancies.append(message)

            currency = row.get("currency", instrument.currency).strip().upper()
            if currency != instrument.currency:
                report.errors.append(
                    f"row {row_no}: currency {currency} disagrees with registry "
                    f"{instrument.currency} for {ticker}"
                )
                continue

            duplicate = session.execute(
                select(Transaction).where(
                    Transaction.instrument_id == instrument.id,
                    Transaction.trade_date == trade_date,
                    Transaction.side == side,
                    Transaction.quantity == quantity,
                    Transaction.price_native == price,
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                report.skipped_existing += 1
                continue

            quote = fx.quote(currency, trade_date)
            if quote.carried_forward:
                note = (
                    f"{ticker} {trade_date} ({trade_date.strftime('%a')}): no rate published, "
                    f"carried forward {quote.days_carried}d from {quote.rate_date}"
                )
                log.info(note)
                report.fx_carried_forward.append(note)

            session.add(
                Transaction(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    side=side,
                    quantity=quantity,
                    price_native=price,
                    fees_native=_parse_decimal(row.get("fees_native") or "0", "fees_native", row_no),
                    fx_rate_to_try=quote.rate,
                    fx_rate_date=quote.rate_date,
                    fx_provider=quote.provider,
                    note=(row.get("note") or None),
                )
            )
            report.transactions_created += 1

        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the import
            log.error("row %d failed: %s", row_no, exc)
            report.errors.append(f"row {row_no}: {exc}")

    session.flush()
    return report

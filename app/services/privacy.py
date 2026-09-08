"""Private Portfolio export and deletion operations."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
import json
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models import Portfolio, Snapshot, Transaction, User, UserSession, Workspace
from app.schemas import (
    PortfolioExportOut,
    PortfolioExportSnapshotOut,
    PortfolioExportTransactionOut,
)


class PrivacyError(RuntimeError):
    """A private export or deletion request cannot be fulfilled."""


class PrivacyNotFound(PrivacyError):
    """The requested resource is not owned by the current User."""


@dataclass(frozen=True)
class ExportDocument:
    body: bytes
    media_type: str
    filename: str


_CSV_COLUMNS = (
    "record_type",
    "id",
    "portfolio_id",
    "name",
    "base_currency",
    "created_at",
    "updated_at",
    "instrument_id",
    "ticker",
    "exchange",
    "yf_symbol",
    "currency",
    "instrument_name",
    "instrument_active",
    "trade_date",
    "side",
    "quantity",
    "price_native",
    "fees_native",
    "fee_currency",
    "fee_fx_rate_to_try",
    "fee_fx_rate_date",
    "fee_fx_provider",
    "fx_rate_to_try",
    "fx_rate_date",
    "fx_provider",
    "note",
    "snapshot_date",
    "payload_json",
)


def _text(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return "" if value is None else str(value)


def _owned_portfolio(
    session: Session, *, user_id: int, workspace_id: int, portfolio_id: int
) -> Portfolio:
    portfolio = session.scalar(
        select(Portfolio)
        .join(Workspace)
        .where(
            Portfolio.id == portfolio_id,
            Portfolio.workspace_id == workspace_id,
            Workspace.user_id == user_id,
        )
    )
    if portfolio is None:
        raise PrivacyNotFound()
    return portfolio


def _export_data(session: Session, portfolio: Portfolio) -> PortfolioExportOut:
    transactions = session.scalars(
        select(Transaction)
        .options(selectinload(Transaction.instrument))
        .where(Transaction.portfolio_id == portfolio.id)
        .order_by(Transaction.id)
    ).all()
    snapshots = session.scalars(
        select(Snapshot)
        .where(Snapshot.portfolio_id == portfolio.id)
        .order_by(Snapshot.snapshot_date)
    ).all()
    return PortfolioExportOut(
        portfolio={
            "id": portfolio.id,
            "name": portfolio.name,
            "base_currency": portfolio.base_currency,
            "created_at": _text(portfolio.created_at),
            "updated_at": _text(portfolio.updated_at),
        },
        transactions=[
            PortfolioExportTransactionOut(
                id=row.id,
                portfolio_id=row.portfolio_id,
                instrument_id=row.instrument_id,
                ticker=row.instrument.ticker,
                exchange=row.instrument.exchange,
                yf_symbol=row.instrument.yf_symbol,
                currency=row.instrument.currency,
                instrument_name=row.instrument.name,
                instrument_active=row.instrument.active,
                trade_date=_text(row.trade_date),
                side=row.side.value,
                quantity=_text(row.quantity),
                price_native=_text(row.price_native),
                fees_native=_text(row.fees_native),
                fee_currency=row.fee_currency,
                fee_fx_rate_to_try=_text(row.fee_fx_rate_to_try),
                fee_fx_rate_date=_text(row.fee_fx_rate_date),
                fee_fx_provider=row.fee_fx_provider,
                fx_rate_to_try=_text(row.fx_rate_to_try),
                fx_rate_date=_text(row.fx_rate_date),
                fx_provider=row.fx_provider,
                note=row.note,
                created_at=_text(row.created_at),
                updated_at=_text(row.updated_at),
            )
            for row in transactions
        ],
        snapshots=[
            PortfolioExportSnapshotOut(
                snapshot_date=_text(row.snapshot_date),
                payload_json=row.payload_json,
                created_at=_text(row.created_at),
            )
            for row in snapshots
        ],
    )


def _csv_row(record_type: str, **values: object) -> list[str]:
    row = {column: "" for column in _CSV_COLUMNS}
    row["record_type"] = record_type
    row.update({key: _text(value) for key, value in values.items()})
    return [row[column] for column in _CSV_COLUMNS]


class PrivacyService:
    def export(
        self,
        session: Session,
        *,
        user_id: int,
        workspace_id: int,
        portfolio_id: int,
        format: Literal["json", "csv"] = "json",
    ) -> ExportDocument:
        portfolio = _owned_portfolio(
            session,
            user_id=user_id,
            workspace_id=workspace_id,
            portfolio_id=portfolio_id,
        )
        data = _export_data(session, portfolio)
        if format == "json":
            body = json.dumps(
                data.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            return ExportDocument(
                body=body,
                media_type="application/json",
                filename=f"portfolio-{portfolio.id}.json",
            )

        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(_CSV_COLUMNS)
        writer.writerow(
            _csv_row(
                "portfolio",
                id=data.portfolio["id"],
                name=data.portfolio["name"],
                base_currency=data.portfolio["base_currency"],
                created_at=data.portfolio["created_at"],
                updated_at=data.portfolio["updated_at"],
            )
        )
        for row in data.transactions:
            writer.writerow(_csv_row("transaction", **row.model_dump()))
        for row in data.snapshots:
            writer.writerow(_csv_row("snapshot", **row.model_dump()))
        return ExportDocument(
            body=output.getvalue().encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            filename=f"portfolio-{portfolio.id}.csv",
        )

    def delete_portfolio(
        self,
        session: Session,
        *,
        user_id: int,
        workspace_id: int,
        portfolio_id: int,
    ) -> None:
        portfolio = _owned_portfolio(
            session,
            user_id=user_id,
            workspace_id=workspace_id,
            portfolio_id=portfolio_id,
        )
        session.delete(portfolio)
        session.flush()

    def delete_account(self, session: Session, *, user_id: int, workspace_id: int) -> None:
        user = session.scalar(
            select(User)
            .join(Workspace)
            .where(User.id == user_id, Workspace.id == workspace_id)
            .with_for_update()
        )
        if user is None:
            raise PrivacyNotFound()
        now = datetime.now(timezone.utc)
        session.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        session.delete(user)
        session.flush()

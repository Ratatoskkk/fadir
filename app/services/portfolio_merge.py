"""Guest-to-user Portfolio merge planning and execution."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.request_authority import RequestAuthority
from app.models import Instrument, Portfolio, Transaction, Workspace
from app.schemas import (
    PortfolioMergeCandidateOut,
    PortfolioMergeConfirmOut,
    PortfolioMergeDecision,
    PortfolioMergeDifference,
    PortfolioMergePreviewOut,
    PortfolioMergeTransactionOut,
)
from app.services import guest_access


class PortfolioMergeError(RuntimeError):
    """A merge request failed validation or became stale."""


_DIFFERENCE_FIELDS = ("fees_native", "fx_rate_to_try", "fx_rate_date", "fx_provider")


@dataclass(frozen=True)
class _Row:
    transaction: Transaction
    currency: str

    @property
    def key(self) -> tuple[Any, ...]:
        txn = self.transaction
        return (
            txn.instrument_id,
            self.currency,
            txn.trade_date,
            txn.side.value,
            txn.quantity,
            txn.price_native,
        )


def _wire(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _row_out(row: _Row) -> PortfolioMergeTransactionOut:
    txn = row.transaction
    return PortfolioMergeTransactionOut(
        id=txn.id,
        instrument_id=txn.instrument_id,
        currency=row.currency,
        trade_date=txn.trade_date,
        side=txn.side.value,
        quantity=txn.quantity,
        price_native=txn.price_native,
        fees_native=txn.fees_native,
        fx_rate_to_try=txn.fx_rate_to_try,
        fx_rate_date=txn.fx_rate_date,
        fx_provider=txn.fx_provider,
        note=txn.note,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )


def _row_dict(row: _Row) -> dict[str, Any]:
    txn = row.transaction
    return {
        "id": txn.id,
        "instrument_id": txn.instrument_id,
        "currency": row.currency,
        "trade_date": _wire(txn.trade_date),
        "side": txn.side.value,
        "quantity": _wire(txn.quantity),
        "price_native": _wire(txn.price_native),
        "fees_native": _wire(txn.fees_native),
        "fx_rate_to_try": _wire(txn.fx_rate_to_try),
        "fx_rate_date": _wire(txn.fx_rate_date),
        "fx_provider": txn.fx_provider,
        "note": txn.note,
        "created_at": _wire(txn.created_at),
        "updated_at": _wire(txn.updated_at),
    }


def _token(source: Portfolio, target: Portfolio, source_rows: list[_Row], target_rows: list[_Row]) -> str:
    payload = {
        "source": {"id": source.id, "workspace_id": source.workspace_id, "base_currency": source.base_currency, "updated_at": _wire(source.updated_at)},
        "target": {"id": target.id, "workspace_id": target.workspace_id, "base_currency": target.base_currency, "updated_at": _wire(target.updated_at)},
        "source_rows": [_row_dict(row) for row in source_rows],
        "target_rows": [_row_dict(row) for row in target_rows],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _load_rows(session: Session, portfolio_id: int, *, lock_rows: bool = False) -> list[_Row]:
    statement = (
        select(Transaction, Instrument.currency)
        .join(Instrument, Instrument.id == Transaction.instrument_id)
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.id)
    )
    if lock_rows:
        statement = statement.with_for_update()
    rows = session.execute(statement).all()
    return [_Row(transaction=txn, currency=currency) for txn, currency in rows]


def _locked_portfolios(
    session: Session,
    source_portfolio_id: int,
    target_portfolio_id: int,
    source_workspace_id: int,
    target_workspace_id: int,
    user_id: int,
) -> tuple[Portfolio, Portfolio]:
    if source_portfolio_id == target_portfolio_id:
        raise PortfolioMergeError()
    workspaces = session.execute(
        select(Workspace)
        .where(Workspace.id.in_([source_workspace_id, target_workspace_id]))
        .order_by(Workspace.id)
        .with_for_update()
    ).scalars().all()
    workspace_by_id = {workspace.id: workspace for workspace in workspaces}
    source_workspace = workspace_by_id.get(source_workspace_id)
    target_workspace = workspace_by_id.get(target_workspace_id)
    if (
        source_workspace is None
        or target_workspace is None
        or source_workspace.user_id is not None
        or target_workspace.user_id != user_id
    ):
        raise PortfolioMergeError()
    rows = session.execute(
        select(Portfolio)
        .where(Portfolio.id.in_([source_portfolio_id, target_portfolio_id]))
        .order_by(Portfolio.id)
        .with_for_update()
    ).scalars().all()
    by_id = {portfolio.id: portfolio for portfolio in rows}
    source = by_id.get(source_portfolio_id)
    target = by_id.get(target_portfolio_id)
    if source is None or target is None:
        raise PortfolioMergeError()
    if source.workspace_id != source_workspace_id or target.workspace_id != target_workspace_id:
        raise PortfolioMergeError()
    return source, target


def _pair(source_rows: Iterable[_Row], target_rows: Iterable[_Row]):
    source_groups: dict[tuple[Any, ...], list[_Row]] = {}
    target_groups: dict[tuple[Any, ...], list[_Row]] = {}
    for row in source_rows:
        source_groups.setdefault(row.key, []).append(row)
    for row in target_rows:
        target_groups.setdefault(row.key, []).append(row)
    candidates: list[tuple[_Row, _Row, int, int]] = []
    movable: list[_Row] = []
    for key, group in source_groups.items():
        target_group = target_groups.get(key, [])
        paired = min(len(group), len(target_group))
        candidates.extend((group[i], target_group[i], len(group), len(target_group)) for i in range(paired))
        movable.extend(group[paired:])
    return candidates, movable


def _differences(source: _Row, target: _Row) -> list[PortfolioMergeDifference]:
    differences = []
    for field in _DIFFERENCE_FIELDS:
        left = getattr(source.transaction, field)
        right = getattr(target.transaction, field)
        if left != right:
            differences.append(PortfolioMergeDifference(field=field, source=_wire(left), target=_wire(right)))
    return differences


def _plan(
    source: Portfolio,
    target: Portfolio,
    source_rows: list[_Row],
    target_rows: list[_Row],
) -> PortfolioMergePreviewOut:
    candidates, movable = _pair(source_rows, target_rows)
    return PortfolioMergePreviewOut(
        source_portfolio_id=source.id,
        target_portfolio_id=target.id,
        source_base_currency=source.base_currency,
        target_base_currency=target.base_currency,
        candidates=[
            PortfolioMergeCandidateOut(
                source=_row_out(left),
                target=_row_out(right),
                source_count=source_count,
                target_count=target_count,
                differences=_differences(left, right),
            )
            for left, right, source_count, target_count in candidates
        ],
        movable_source_rows=[_row_out(row) for row in movable],
        revision_token=_token(source, target, source_rows, target_rows),
    )


def _prepare(
    session: Session,
    *,
    authority: RequestAuthority,
    guest_secret: str,
    source_portfolio_id: int,
    target_portfolio_id: int,
    lock_rows: bool = False,
) -> tuple[Portfolio, Portfolio, list[_Row], list[_Row], PortfolioMergePreviewOut]:
    if not authority.is_user or authority.user_id is None:
        raise PortfolioMergeError()
    try:
        guest = guest_access.require(session, guest_secret, clock=lambda: datetime.now(timezone.utc))
    except Exception:
        raise PortfolioMergeError() from None
    source, target = _locked_portfolios(
        session,
        source_portfolio_id,
        target_portfolio_id,
        guest.workspace_id,
        authority.workspace_id,
        authority.user_id,
    )
    ordered = sorted((source, target), key=lambda portfolio: portfolio.id)
    loaded = {
        portfolio.id: _load_rows(session, portfolio.id, lock_rows=lock_rows)
        for portfolio in ordered
    }
    source_rows = loaded[source.id]
    target_rows = loaded[target.id]
    return source, target, source_rows, target_rows, _plan(source, target, source_rows, target_rows)


def preview(
    session: Session,
    *,
    authority: RequestAuthority,
    guest_secret: str,
    source_portfolio_id: int,
    target_portfolio_id: int,
) -> PortfolioMergePreviewOut:
    return _prepare(
        session,
        authority=authority,
        guest_secret=guest_secret,
        source_portfolio_id=source_portfolio_id,
        target_portfolio_id=target_portfolio_id,
    )[-1]


def confirm(
    session: Session,
    *,
    authority: RequestAuthority,
    guest_secret: str,
    source_portfolio_id: int,
    target_portfolio_id: int,
    revision_token: str,
    decisions: list[PortfolioMergeDecision],
) -> PortfolioMergeConfirmOut:
    decisions = [
        decision
        if isinstance(decision, PortfolioMergeDecision)
        else PortfolioMergeDecision.model_validate(decision)
        for decision in decisions
    ]
    source, target, source_rows, target_rows, plan = _prepare(
        session,
        authority=authority,
        guest_secret=guest_secret,
        source_portfolio_id=source_portfolio_id,
        target_portfolio_id=target_portfolio_id,
        lock_rows=True,
    )
    if revision_token != plan.revision_token:
        raise PortfolioMergeError()
    expected = {candidate.source.id for candidate in plan.candidates}
    provided = [decision.source_transaction_id for decision in decisions]
    if len(provided) != len(set(provided)) or set(provided) != expected:
        raise PortfolioMergeError()
    actions = {decision.source_transaction_id: decision.action for decision in decisions}
    candidates, movable = _pair(source_rows, target_rows)
    moved = 0
    skipped = 0

    def move(row: _Row) -> None:
        original_updated_at = row.transaction.updated_at
        session.execute(
            update(Transaction)
            .where(Transaction.id == row.transaction.id, Transaction.portfolio_id == source.id)
            .values(portfolio_id=target.id, updated_at=original_updated_at)
        )

    for row in movable:
        move(row)
        moved += 1
    for left, _right, _source_count, _target_count in candidates:
        if actions[left.transaction.id] == "keep":
            move(left)
            moved += 1
        else:
            skipped += 1
    session.flush()
    session.expire_all()
    return PortfolioMergeConfirmOut(moved_count=moved, skipped_count=skipped)

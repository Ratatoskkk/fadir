"""Portfolio-scoped access to private database rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models import Portfolio, Snapshot, Transaction, Workspace


class PortfolioScopeNotFound(LookupError):
    """The Workspace and Portfolio pair does not identify a Portfolio."""


class PortfolioScopeViolation(ValueError):
    """A caller tried to bypass the Portfolio scope."""


class PortfolioScope:
    """Validate one Portfolio and contain its private row access."""

    def __init__(self, session: Session, portfolio: Portfolio) -> None:
        self._session = session
        self.portfolio = portfolio

    @classmethod
    def require(
        cls,
        session: Session,
        *,
        workspace_id: int,
        portfolio_id: int,
    ) -> PortfolioScope:
        portfolio = session.scalar(
            select(Portfolio).where(
                Portfolio.id == portfolio_id,
                Portfolio.workspace_id == workspace_id,
            )
        )
        if portfolio is None:
            raise PortfolioScopeNotFound("Portfolio not found")
        return cls(session, portfolio)

    @classmethod
    def select(
        cls,
        session: Session,
        *,
        workspace_id: int,
        portfolio_id: int | None = None,
    ) -> PortfolioScope | None:
        """Select an explicitly requested Portfolio or the first Workspace Portfolio."""
        if portfolio_id is not None:
            return cls.require(
                session,
                workspace_id=workspace_id,
                portfolio_id=portfolio_id,
            )
        portfolio = session.scalar(
            select(Portfolio)
            .where(Portfolio.workspace_id == workspace_id)
            .order_by(Portfolio.id)
            .limit(1)
        )
        return cls(session, portfolio) if portfolio is not None else None

    @classmethod
    def select_for_write(
        cls,
        session: Session,
        *,
        workspace_id: int,
        portfolio_id: int | None = None,
        base_currency: str = "TRY",
    ) -> PortfolioScope:
        """Select a Portfolio, creating the first-save default in the caller transaction."""
        existing = cls.select(
            session,
            workspace_id=workspace_id,
            portfolio_id=portfolio_id,
        )
        if existing is not None:
            return existing

        workspace = session.scalar(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .with_for_update()
        )
        if workspace is None:
            raise PortfolioScopeNotFound("Workspace not found")

        existing = cls.select(session, workspace_id=workspace_id)
        if existing is not None:
            return existing

        portfolio = Portfolio(
            workspace_id=workspace.id,
            name="Ana Portföy",
            base_currency=base_currency,
        )
        session.add(portfolio)
        session.flush()
        return cls(session, portfolio)

    @staticmethod
    def _model_spec(model: type[Any]) -> tuple[Any, tuple[Any, ...]]:
        if model is Transaction:
            return Transaction.id, (
                Transaction.trade_date.desc(),
                Transaction.id.desc(),
            )
        if model is Snapshot:
            return Snapshot.snapshot_date, (Snapshot.snapshot_date.desc(),)
        raise PortfolioScopeViolation("Unsupported Portfolio model")

    def all(self, model: type[Any]) -> list[Any]:
        _, ordering = self._model_spec(model)
        statement = (
            select(model)
            .where(model.portfolio_id == self.portfolio.id)
            .order_by(*ordering)
        )
        return list(self._session.scalars(statement))

    def get(self, model: type[Any], key: object) -> Any | None:
        key_column, _ = self._model_spec(model)
        statement = select(model).where(
            key_column == key,
            model.portfolio_id == self.portfolio.id,
        )
        return self._session.scalar(statement)

    def add(self, row: Any) -> Any:
        self._model_spec(type(row))
        state = inspect(row)
        if state.persistent or state.detached or state.deleted:
            raise PortfolioScopeViolation("Portfolio row must be new")
        if state.session is not None and state.session is not self._session:
            raise PortfolioScopeViolation("Portfolio row belongs to another Session")

        portfolio_id = row.portfolio_id
        if portfolio_id is not None and portfolio_id != self.portfolio.id:
            raise PortfolioScopeViolation("Portfolio row names another Portfolio")

        related_portfolio = row.portfolio
        if related_portfolio is not None and related_portfolio is not self.portfolio:
            if related_portfolio.id != self.portfolio.id:
                raise PortfolioScopeViolation("Portfolio row names another Portfolio")

        row.portfolio_id = self.portfolio.id
        row.portfolio = self.portfolio
        self._session.add(row)
        return row

    def delete(self, model: type[Any], key: object) -> bool:
        row = self.get(model, key)
        if row is None:
            return False
        self._session.delete(row)
        return True

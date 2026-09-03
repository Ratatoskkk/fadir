from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app import models
from app.db import make_engine


def _scope_types():
    try:
        module = importlib.import_module("app.services.portfolio_scope")
    except ModuleNotFoundError:
        pytest.fail("Portfolio scope module is absent")
    return (
        module.PortfolioScope,
        module.PortfolioScopeNotFound,
        module.PortfolioScopeViolation,
    )


def _transaction(
    instrument_id: int,
    *,
    trade_date: date,
    portfolio_id: int | None = None,
) -> models.Transaction:
    return models.Transaction(
        instrument_id=instrument_id,
        portfolio_id=portfolio_id,
        trade_date=trade_date,
        side=models.Side.BUY,
        quantity=Decimal("1"),
        price_native=Decimal("10"),
        fees_native=Decimal("0"),
        fx_rate_to_try=Decimal("35"),
        fx_rate_date=trade_date,
        fx_provider="synthetic",
    )


@pytest.fixture
def scoped_database(tmp_path):
    engine = make_engine(tmp_path / "portfolio-scope.db")
    models.Base.metadata.create_all(engine)

    with Session(engine) as session:
        first_workspace = models.Workspace(
            portfolios=[models.Portfolio(name="First")]
        )
        second_workspace = models.Workspace(
            portfolios=[models.Portfolio(name="Second")]
        )
        instrument = models.Instrument(
            ticker="SYN",
            exchange="TEST",
            yf_symbol="SYN.TEST",
            currency="USD",
            name="Synthetic Instrument",
        )
        session.add_all([first_workspace, second_workspace, instrument])
        session.flush()

        first_portfolio = first_workspace.portfolios[0]
        second_portfolio = second_workspace.portfolios[0]
        transactions = [
            _transaction(
                instrument.id,
                trade_date=date(2026, 1, 2),
                portfolio_id=first_portfolio.id,
            ),
            _transaction(
                instrument.id,
                trade_date=date(2026, 1, 3),
                portfolio_id=first_portfolio.id,
            ),
            _transaction(
                instrument.id,
                trade_date=date(2026, 1, 3),
                portfolio_id=first_portfolio.id,
            ),
            _transaction(
                instrument.id,
                trade_date=date(2026, 1, 4),
                portfolio_id=second_portfolio.id,
            ),
            _transaction(instrument.id, trade_date=date(2026, 1, 5)),
        ]
        snapshots = [
            models.Snapshot(
                snapshot_date=date(2026, 1, 2),
                payload_json='{"scope":"first-old"}',
                portfolio_id=first_portfolio.id,
            ),
            models.Snapshot(
                snapshot_date=date(2026, 1, 3),
                payload_json='{"scope":"first-new"}',
                portfolio_id=first_portfolio.id,
            ),
            models.Snapshot(
                snapshot_date=date(2026, 1, 4),
                payload_json='{"scope":"second"}',
                portfolio_id=second_portfolio.id,
            ),
            models.Snapshot(
                snapshot_date=date(2026, 1, 5),
                payload_json='{"scope":"unowned"}',
            ),
        ]
        session.add_all([*transactions, *snapshots])
        session.commit()

        data = SimpleNamespace(
            first_workspace_id=first_workspace.id,
            second_workspace_id=second_workspace.id,
            first_portfolio_id=first_portfolio.id,
            second_portfolio_id=second_portfolio.id,
            instrument_id=instrument.id,
            first_transaction_ids=(
                transactions[0].id,
                transactions[1].id,
                transactions[2].id,
            ),
            second_transaction_id=transactions[3].id,
            unowned_transaction_id=transactions[4].id,
            first_snapshot_dates=(snapshots[0].snapshot_date, snapshots[1].snapshot_date),
            second_snapshot_date=snapshots[2].snapshot_date,
            unowned_snapshot_date=snapshots[3].snapshot_date,
        )

    yield engine, data
    engine.dispose()


def test_require_validates_workspace_and_portfolio_together(scoped_database) -> None:
    PortfolioScope, PortfolioScopeNotFound, _ = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        first = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )
        second = PortfolioScope.require(
            session,
            workspace_id=data.second_workspace_id,
            portfolio_id=data.second_portfolio_id,
        )
        assert first.portfolio.id == data.first_portfolio_id
        assert second.portfolio.id == data.second_portfolio_id

        with pytest.raises(PortfolioScopeNotFound) as cross_workspace:
            PortfolioScope.require(
                session,
                workspace_id=data.second_workspace_id,
                portfolio_id=data.first_portfolio_id,
            )
        with pytest.raises(PortfolioScopeNotFound) as missing:
            PortfolioScope.require(
                session,
                workspace_id=data.first_workspace_id,
                portfolio_id=999_999,
            )

        assert type(cross_workspace.value) is type(missing.value)
        assert str(cross_workspace.value) == "Portfolio not found"
        assert str(missing.value) == "Portfolio not found"


def test_all_returns_only_owned_rows_in_required_order(scoped_database) -> None:
    PortfolioScope, _, _ = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        scope = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )

        transactions = scope.all(models.Transaction)
        snapshots = scope.all(models.Snapshot)

        assert [row.id for row in transactions] == list(
            reversed(data.first_transaction_ids)
        )
        assert [row.snapshot_date for row in snapshots] == list(
            reversed(data.first_snapshot_dates)
        )


def test_get_and_delete_fail_closed_across_portfolios(scoped_database) -> None:
    PortfolioScope, _, _ = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        scope = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )

        assert scope.get(models.Transaction, data.first_transaction_ids[0]) is not None
        assert scope.get(models.Transaction, data.second_transaction_id) is None
        assert scope.get(models.Snapshot, data.second_snapshot_date) is None
        assert not scope.delete(models.Transaction, data.second_transaction_id)
        assert not scope.delete(models.Snapshot, data.second_snapshot_date)
        assert session.get(models.Transaction, data.second_transaction_id) is not None
        assert session.get(models.Snapshot, data.second_snapshot_date) is not None


def test_add_assigns_scope_and_rejects_invalid_rows(scoped_database) -> None:
    PortfolioScope, _, PortfolioScopeViolation = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        scope = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )
        transaction = _transaction(
            data.instrument_id, trade_date=date(2026, 2, 1)
        )
        snapshot = models.Snapshot(
            snapshot_date=date(2026, 2, 1), payload_json="{}"
        )

        scope.add(transaction)
        scope.add(snapshot)
        assert transaction.portfolio_id == data.first_portfolio_id
        assert snapshot.portfolio_id == data.first_portfolio_id
        assert transaction in session.new
        assert snapshot in session.new

        cross_owned = _transaction(
            data.instrument_id,
            trade_date=date(2026, 2, 2),
            portfolio_id=data.second_portfolio_id,
        )
        with pytest.raises(PortfolioScopeViolation):
            scope.add(cross_owned)

        persistent = session.get(models.Transaction, data.first_transaction_ids[0])
        with pytest.raises(PortfolioScopeViolation):
            scope.add(persistent)


def test_unsupported_shared_models_fail_closed(scoped_database) -> None:
    PortfolioScope, _, PortfolioScopeViolation = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        scope = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )
        for model in (
            models.Instrument,
            models.PriceCache,
            models.FxCache,
            models.CorporateAction,
            models.Workspace,
        ):
            with pytest.raises(PortfolioScopeViolation):
                scope.all(model)

        with pytest.raises(PortfolioScopeViolation):
            scope.add(models.Instrument())


def test_unowned_rows_are_not_visible(scoped_database) -> None:
    PortfolioScope, _, _ = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        scope = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )

        assert scope.get(models.Transaction, data.unowned_transaction_id) is None
        assert scope.get(models.Snapshot, data.unowned_snapshot_date) is None
        assert all(row.portfolio_id is not None for row in scope.all(models.Transaction))
        assert all(row.portfolio_id is not None for row in scope.all(models.Snapshot))


def test_module_does_not_commit_and_caller_rollback_reverses_changes(
    scoped_database,
) -> None:
    PortfolioScope, _, _ = _scope_types()
    engine, data = scoped_database
    with Session(engine) as session:
        scope = PortfolioScope.require(
            session,
            workspace_id=data.first_workspace_id,
            portfolio_id=data.first_portfolio_id,
        )
        added = _transaction(data.instrument_id, trade_date=date(2026, 3, 1))
        with patch.object(session, "commit", wraps=session.commit) as commit:
            scope.add(added)
            session.flush()
            added_id = added.id
            assert scope.delete(models.Transaction, data.first_transaction_ids[0])
            commit.assert_not_called()
        session.rollback()

    with Session(engine) as session:
        assert session.get(models.Transaction, added_id) is None
        assert session.get(models.Transaction, data.first_transaction_ids[0]) is not None

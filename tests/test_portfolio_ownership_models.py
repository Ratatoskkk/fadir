from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import make_engine


@pytest.fixture
def engine(tmp_path):
    database_engine = make_engine(tmp_path / "portfolio-ownership.db")
    models.Base.metadata.create_all(database_engine)
    yield database_engine
    database_engine.dispose()


def _ownership_models():
    missing = [
        f"{model.__name__}.portfolio_id"
        for model in (models.Transaction, models.Snapshot)
        if "portfolio_id" not in model.__table__.columns
    ]
    assert not missing, f"Portfolio ownership keys are absent: {', '.join(missing)}"
    return models.Portfolio, models.Transaction, models.Snapshot


def _transaction(instrument, **values):
    return models.Transaction(
        instrument=instrument,
        trade_date=date(2026, 1, 2),
        side=models.Side.BUY,
        quantity=Decimal("1"),
        price_native=Decimal("10"),
        fees_native=Decimal("0"),
        fx_rate_to_try=Decimal("35"),
        fx_rate_date=date(2026, 1, 2),
        fx_provider="synthetic",
        **values,
    )


def _instrument() -> models.Instrument:
    return models.Instrument(
        ticker="SYN",
        exchange="TEST",
        yf_symbol="SYN.TEST",
        currency="USD",
        name="Synthetic Instrument",
    )


def test_portfolio_ownership_model_contract() -> None:
    Portfolio, Transaction, Snapshot = _ownership_models()

    for model, constraint_name in (
        (Transaction, "fk_transaction_portfolio_id_portfolio"),
        (Snapshot, "fk_snapshot_portfolio_id_portfolio"),
    ):
        column = model.__table__.c.portfolio_id
        foreign_key = next(iter(column.foreign_keys))
        assert column.nullable
        assert foreign_key.target_fullname == "portfolio.id"
        assert foreign_key.ondelete == "CASCADE"
        assert foreign_key.constraint.name == constraint_name

    transaction_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in Transaction.__table__.indexes
    }
    assert transaction_indexes["ix_transaction_instrument_date"] == (
        "instrument_id",
        "trade_date",
    )
    assert transaction_indexes["ix_transaction_portfolio_instrument_date"] == (
        "portfolio_id",
        "instrument_id",
        "trade_date",
    )

    snapshot_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in Snapshot.__table__.indexes
    }
    assert snapshot_indexes["ix_snapshot_portfolio_date"] == (
        "portfolio_id",
        "snapshot_date",
    )
    assert tuple(Snapshot.__table__.primary_key.columns.keys()) == ("snapshot_date",)
    assert "delete-orphan" not in Portfolio.transactions.property.cascade


def test_portfolio_queries_return_only_associated_rows(engine) -> None:
    Portfolio, Transaction, Snapshot = _ownership_models()
    with Session(engine) as session:
        workspace = models.Workspace(
            portfolios=[Portfolio(name="First"), Portfolio(name="Second")]
        )
        first, second = workspace.portfolios
        instrument = _instrument()
        first_transaction = _transaction(instrument, portfolio=first)
        second_transaction = _transaction(instrument, portfolio=second)
        first_snapshot = Snapshot(
            snapshot_date=date(2026, 1, 2), payload_json="{}", portfolio=first
        )
        second_snapshot = Snapshot(
            snapshot_date=date(2026, 1, 3), payload_json="{}", portfolio=second
        )
        session.add_all(
            [
                workspace,
                instrument,
                first_transaction,
                second_transaction,
                first_snapshot,
                second_snapshot,
            ]
        )
        session.commit()

        first_transactions = session.scalars(
            select(Transaction).where(Transaction.portfolio_id == first.id)
        ).all()
        first_snapshots = session.scalars(
            select(Snapshot).where(Snapshot.portfolio_id == first.id)
        ).all()

        assert first_transactions == [first_transaction]
        assert first_snapshots == [first_snapshot]
        assert first.transactions == [first_transaction]
        assert first.snapshots == [first_snapshot]


def test_missing_portfolio_foreign_keys_fail(engine) -> None:
    _, _, Snapshot = _ownership_models()
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.commit()

        session.add(_transaction(instrument, portfolio_id=999))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Snapshot(
                snapshot_date=date(2026, 1, 2),
                payload_json="{}",
                portfolio_id=999,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_portfolio_delete_removes_associated_private_rows(engine) -> None:
    Portfolio, Transaction, Snapshot = _ownership_models()
    with Session(engine) as session:
        portfolio = Portfolio(name="Owned")
        workspace = models.Workspace(portfolios=[portfolio])
        instrument = _instrument()
        transaction = _transaction(instrument, portfolio=portfolio)
        snapshot = Snapshot(
            snapshot_date=date(2026, 1, 2), payload_json="{}", portfolio=portfolio
        )
        session.add_all([workspace, instrument, transaction, snapshot])
        session.commit()
        transaction_id = transaction.id
        snapshot_date = snapshot.snapshot_date

        session.delete(portfolio)
        session.commit()

    with Session(engine) as session:
        assert session.get(Transaction, transaction_id) is None
        assert session.get(Snapshot, snapshot_date) is None


def test_null_portfolio_ownership_remains_valid(engine) -> None:
    _, _, Snapshot = _ownership_models()
    with Session(engine) as session:
        instrument = _instrument()
        transaction = _transaction(instrument)
        snapshot = Snapshot(snapshot_date=date(2026, 1, 2), payload_json="{}")
        session.add_all([instrument, transaction, snapshot])
        session.commit()

        assert transaction.portfolio_id is None
        assert snapshot.portfolio_id is None


def test_shared_models_have_no_portfolio_key() -> None:
    for model in (
        models.Instrument,
        models.PriceCache,
        models.FxCache,
        models.CorporateAction,
    ):
        assert "portfolio_id" not in model.__table__.columns

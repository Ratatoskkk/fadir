"""Add transitional Portfolio ownership keys.

Revision ID: 0003_portfolio_ownership_keys
Revises: 0002_user_workspace_portfolio_roots
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_portfolio_ownership_keys"
down_revision: str | None = "0002_user_workspace_portfolio_roots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.add_column(sa.Column("portfolio_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_transaction_portfolio_id_portfolio",
            "portfolio",
            ["portfolio_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_transaction_portfolio_instrument_date",
            ["portfolio_id", "instrument_id", "trade_date"],
            unique=False,
        )

    with op.batch_alter_table("snapshot") as batch_op:
        batch_op.add_column(sa.Column("portfolio_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_snapshot_portfolio_id_portfolio",
            "portfolio",
            ["portfolio_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_snapshot_portfolio_date",
            ["portfolio_id", "snapshot_date"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("snapshot") as batch_op:
        batch_op.drop_index("ix_snapshot_portfolio_date")
        batch_op.drop_constraint(
            "fk_snapshot_portfolio_id_portfolio", type_="foreignkey"
        )
        batch_op.drop_column("portfolio_id")

    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_index("ix_transaction_portfolio_instrument_date")
        batch_op.drop_constraint(
            "fk_transaction_portfolio_id_portfolio", type_="foreignkey"
        )
        batch_op.drop_column("portfolio_id")

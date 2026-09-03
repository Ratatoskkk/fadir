"""Create the current schema baseline.

Revision ID: 0001_current_schema_baseline
Revises:
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_current_schema_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("yf_symbol", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker"),
        sa.UniqueConstraint("yf_symbol"),
    )
    op.create_table(
        "fx_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base", sa.String(length=3), nullable=False),
        sa.Column("quote", sa.String(length=3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=24, scale=10), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base", "quote", "rate_date", "provider", name="uq_fx_cache_key"
        ),
    )
    op.create_index(
        "ix_fx_cache_lookup",
        "fx_cache",
        ["base", "quote", "rate_date"],
        unique=False,
    )
    op.create_table(
        "snapshot",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_date"),
    )
    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column(
            "side",
            sa.Enum("BUY", "SELL", name="side", native_enum=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column(
            "price_native", sa.Numeric(precision=28, scale=12), nullable=False
        ),
        sa.Column("fees_native", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column(
            "fx_rate_to_try", sa.Numeric(precision=24, scale=10), nullable=False
        ),
        sa.Column("fx_rate_date", sa.Date(), nullable=False),
        sa.Column("fx_provider", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "fx_rate_to_try > 0", name="ck_transaction_fx_positive"
        ),
        sa.CheckConstraint(
            "price_native >= 0", name="ck_transaction_price_nonneg"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_transaction_qty_positive"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instrument.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_instrument_date",
        "transaction",
        ["instrument_id", "trade_date"],
        unique=False,
    )
    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close_native", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("is_adjusted", sa.Boolean(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instrument.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "price_date",
            name="uq_price_cache_instrument_date",
        ),
    )
    op.create_table(
        "corporate_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("action_date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("SPLIT", "DIVIDEND", name="actionkind", native_enum=False),
            nullable=False,
        ),
        sa.Column("ratio", sa.Numeric(precision=24, scale=10), nullable=False),
        sa.Column("applied_to_transactions", sa.Boolean(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instrument.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "action_date",
            "kind",
            name="uq_corporate_action_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("corporate_action")
    op.drop_table("price_cache")
    op.drop_index("ix_transaction_instrument_date", table_name="transaction")
    op.drop_table("transaction")
    op.drop_table("snapshot")
    op.drop_index("ix_fx_cache_lookup", table_name="fx_cache")
    op.drop_table("fx_cache")
    op.drop_table("instrument")

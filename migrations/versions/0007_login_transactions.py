"""Add one-use browser-bound login transactions.

Revision ID: 0007_login_transactions
Revises: 0006_login_identities
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_login_transactions"
down_revision: str | None = "0006_login_identities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_transaction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("nonce_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(state_digest) = 32",
            name="ck_login_transaction_state_digest_length",
        ),
        sa.CheckConstraint(
            "length(nonce_digest) = 32",
            name="ck_login_transaction_nonce_digest_length",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_login_transaction_expiry_after_creation",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "state_digest", name="uq_login_transaction_state_digest"
        ),
    )
    op.create_index(
        "ix_login_transaction_expires_at",
        "login_transaction",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_login_transaction_expires_at", table_name="login_transaction")
    op.drop_table("login_transaction")

"""Add verified identity state to login transactions.

Revision ID: 0008_login_transaction_verification
Revises: 0007_login_transactions
"""

from typing import Sequence

from alembic import op
from alembic import context
import sqlalchemy as sa


revision: str = "0008_login_transaction_verification"
down_revision: str | None = "0007_login_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column(
            "login_transaction",
            sa.Column("verified_issuer", sa.String(length=255), nullable=True),
        )
        op.add_column(
            "login_transaction",
            sa.Column("verified_subject", sa.String(length=255), nullable=True),
        )
        op.add_column(
            "login_transaction",
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_check_constraint(
            "ck_login_transaction_verified_issuer_nonempty",
            "login_transaction",
            "verified_issuer IS NULL OR length(verified_issuer) > 0",
        )
        op.create_check_constraint(
            "ck_login_transaction_verified_subject_nonempty",
            "login_transaction",
            "verified_subject IS NULL OR length(verified_subject) > 0",
        )
        return
    if op.get_bind().dialect.name != "sqlite":
        op.add_column(
            "login_transaction",
            sa.Column("verified_issuer", sa.String(length=255), nullable=True),
        )
        op.add_column(
            "login_transaction",
            sa.Column("verified_subject", sa.String(length=255), nullable=True),
        )
        op.add_column(
            "login_transaction",
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_check_constraint(
            "ck_login_transaction_verified_issuer_nonempty",
            "login_transaction",
            "verified_issuer IS NULL OR length(verified_issuer) > 0",
        )
        op.create_check_constraint(
            "ck_login_transaction_verified_subject_nonempty",
            "login_transaction",
            "verified_subject IS NULL OR length(verified_subject) > 0",
        )
        return
    with op.batch_alter_table("login_transaction", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("verified_issuer", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("verified_subject", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_login_transaction_verified_issuer_nonempty",
            "verified_issuer IS NULL OR length(verified_issuer) > 0",
        )
        batch_op.create_check_constraint(
            "ck_login_transaction_verified_subject_nonempty",
            "verified_subject IS NULL OR length(verified_subject) > 0",
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(
            "ck_login_transaction_verified_subject_nonempty",
            "login_transaction",
            type_="check",
        )
        op.drop_constraint(
            "ck_login_transaction_verified_issuer_nonempty",
            "login_transaction",
            type_="check",
        )
        op.drop_column("login_transaction", "verified_at")
        op.drop_column("login_transaction", "verified_subject")
        op.drop_column("login_transaction", "verified_issuer")
        return
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "ck_login_transaction_verified_subject_nonempty",
            "login_transaction",
            type_="check",
        )
        op.drop_constraint(
            "ck_login_transaction_verified_issuer_nonempty",
            "login_transaction",
            type_="check",
        )
        op.drop_column("login_transaction", "verified_at")
        op.drop_column("login_transaction", "verified_subject")
        op.drop_column("login_transaction", "verified_issuer")
        return
    with op.batch_alter_table("login_transaction", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_login_transaction_verified_subject_nonempty", type_="check"
        )
        batch_op.drop_constraint(
            "ck_login_transaction_verified_issuer_nonempty", type_="check"
        )
        batch_op.drop_column("verified_at")
        batch_op.drop_column("verified_subject")
        batch_op.drop_column("verified_issuer")

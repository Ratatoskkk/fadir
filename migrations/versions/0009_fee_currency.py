"""Add fee currency and fee FX provenance."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_fee_currency"
down_revision: str | None = "0008_login_transaction_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transaction", sa.Column("fee_currency", sa.String(length=3), nullable=True))
    op.add_column("transaction", sa.Column("fee_fx_rate_to_try", sa.Numeric(precision=24, scale=10), nullable=True))
    op.add_column("transaction", sa.Column("fee_fx_rate_date", sa.Date(), nullable=True))
    op.add_column("transaction", sa.Column("fee_fx_provider", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("transaction", "fee_fx_provider")
    op.drop_column("transaction", "fee_fx_rate_date")
    op.drop_column("transaction", "fee_fx_rate_to_try")
    op.drop_column("transaction", "fee_currency")

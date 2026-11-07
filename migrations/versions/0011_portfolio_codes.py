"""Add Portfolio Codes and the device passes they issue."""

import secrets
from typing import Sequence

from alembic import context, op
import sqlalchemy as sa

revision: str = "0011_portfolio_codes"
down_revision: str | None = "0010_tax_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill() -> None:
    if context.is_offline_mode():
        # Offline SQL cannot draw random codes per row; ids are unique, so they serve.
        op.execute("UPDATE portfolio SET code = lpad(CAST(id AS TEXT), 4, '0')")
        return
    connection = op.get_bind()
    portfolio = sa.table("portfolio", sa.column("id", sa.Integer), sa.column("code", sa.String))
    ids = [row.id for row in connection.execute(sa.select(portfolio.c.id).order_by(portfolio.c.id))]
    used: set[str] = set()
    for portfolio_id in ids:
        for digits in (4, 5, 6):
            size = 10**digits
            if sum(1 for code in used if len(code) == digits) >= size:
                continue
            while True:
                code = f"{secrets.randbelow(size):0{digits}d}"
                if code not in used:
                    break
            break
        used.add(code)
        connection.execute(
            sa.update(portfolio).where(portfolio.c.id == portfolio_id).values(code=code)
        )


def upgrade() -> None:
    op.add_column("portfolio", sa.Column("code", sa.String(length=6), nullable=True))
    _backfill()
    with op.batch_alter_table("portfolio") as batch:
        batch.alter_column("code", existing_type=sa.String(length=6), nullable=False)
        batch.create_unique_constraint("uq_portfolio_code", ["code"])
        batch.create_check_constraint("ck_portfolio_code_length", "length(code) BETWEEN 4 AND 6")

    op.create_table(
        "portfolio_pass",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("secret_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_access_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(secret_digest) = 32", name="ck_portfolio_pass_digest_length"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_digest", name="uq_portfolio_pass_secret_digest"),
    )
    op.create_index("ix_portfolio_pass_portfolio", "portfolio_pass", ["portfolio_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_pass_portfolio", table_name="portfolio_pass")
    op.drop_table("portfolio_pass")
    with op.batch_alter_table("portfolio") as batch:
        batch.drop_constraint("ck_portfolio_code_length", type_="check")
        batch.drop_constraint("uq_portfolio_code", type_="unique")
        batch.drop_column("code")

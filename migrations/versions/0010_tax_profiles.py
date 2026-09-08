"""Add user-owned tax profiles."""
from typing import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "0010_tax_profiles"
down_revision: str | None = "0009_fee_currency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "tax_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jurisdiction", sa.String(length=2), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("source_version", sa.String(length=128), nullable=False),
        sa.Column("assumptions_json", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("tax_year >= 2000", name="ck_tax_profile_year_valid"),
        sa.CheckConstraint("length(jurisdiction) = 2", name="ck_tax_profile_jurisdiction_length"),
        sa.CheckConstraint("length(currency) = 3", name="ck_tax_profile_currency_length"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "jurisdiction", "tax_year", name="uq_tax_profile_user_jurisdiction_year"),
    )

def downgrade() -> None:
    op.drop_table("tax_profile")

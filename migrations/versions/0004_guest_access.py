"""Add the internal Guest access record."""

from alembic import op
import sqlalchemy as sa


revision = "0004_guest_access"
down_revision = "0003_portfolio_ownership_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guest_access",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("secret_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_access_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("secret_digest", name="uq_guest_access_secret_digest"),
        sa.CheckConstraint("length(secret_digest) = 32", name="ck_guest_access_digest_length"),
    )


def downgrade():
    op.drop_table("guest_access")

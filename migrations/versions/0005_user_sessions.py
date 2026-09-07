"""Add internal User Session persistence.

Revision ID: 0005_user_sessions
Revises: 0004_guest_access
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_user_sessions"
down_revision: str | None = "0004_guest_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=22), nullable=False),
        sa.Column("secret_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_access_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(public_id) = 22", name="ck_user_session_public_id_length"
        ),
        sa.CheckConstraint(
            "length(secret_digest) = 32", name="ck_user_session_digest_length"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_user_session_public_id"),
        sa.UniqueConstraint("secret_digest", name="uq_user_session_secret_digest"),
    )
    op.create_index(
        "ix_user_session_user_active",
        "user_session",
        ["user_id", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_session_user_active", table_name="user_session")
    op.drop_table("user_session")

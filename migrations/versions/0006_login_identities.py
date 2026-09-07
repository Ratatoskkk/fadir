"""Add durable provider identities for Users.

Revision ID: 0006_login_identities
Revises: 0005_user_sessions
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_login_identities"
down_revision: str | None = "0005_user_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_identity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(issuer) > 0", name="ck_login_identity_issuer_nonempty"
        ),
        sa.CheckConstraint(
            "length(subject) > 0", name="ck_login_identity_subject_nonempty"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issuer", "subject", name="uq_login_identity_issuer_subject"
        ),
    )
    op.create_index("ix_login_identity_user", "login_identity", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_identity_user", table_name="login_identity")
    op.drop_table("login_identity")

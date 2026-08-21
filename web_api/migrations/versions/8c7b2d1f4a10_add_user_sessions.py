"""add server-side user sessions

Revision ID: 8c7b2d1f4a10
Revises: 5d2a9a282ea1
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c7b2d1f4a10"
down_revision: str | None = "5d2a9a282ea1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "UserSessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_hash", sa.String(length=64), nullable=False),
        sa.Column("prev_refresh_hash", sa.String(length=64), nullable=True),
        sa.Column("last_refresh_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=200), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["Users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_hash"),
    )
    op.create_index("ix_UserSessions_id", "UserSessions", ["id"])
    op.create_index("ix_UserSessions_user_id", "UserSessions", ["user_id"])
    op.create_index("ix_UserSessions_refresh_hash", "UserSessions", ["refresh_hash"])
    op.create_index("ix_UserSessions_prev_refresh_hash", "UserSessions", ["prev_refresh_hash"])
    op.create_index("ix_UserSessions_expires_at", "UserSessions", ["expires_at"])
    op.create_index("ix_UserSessions_revoked_at", "UserSessions", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_UserSessions_revoked_at", table_name="UserSessions")
    op.drop_index("ix_UserSessions_expires_at", table_name="UserSessions")
    op.drop_index("ix_UserSessions_prev_refresh_hash", table_name="UserSessions")
    op.drop_index("ix_UserSessions_refresh_hash", table_name="UserSessions")
    op.drop_index("ix_UserSessions_user_id", table_name="UserSessions")
    op.drop_index("ix_UserSessions_id", table_name="UserSessions")
    op.drop_table("UserSessions")

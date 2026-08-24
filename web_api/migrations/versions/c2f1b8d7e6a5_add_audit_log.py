"""add general audit log

Revision ID: c2f1b8d7e6a5
Revises: 8c7b2d1f4a10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import mssql

revision: str = "c2f1b8d7e6a5"
down_revision: str | None = "8c7b2d1f4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "AuditLog" in sa_inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "AuditLog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime().with_variant(mssql.DATETIME2(precision=7), "mssql"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=True),
        sa.Column("actor_slack_id", sa.String(length=20), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.Text().with_variant(mssql.TEXT(), "mssql"), nullable=True),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["Users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_AuditLog_id", "AuditLog", ["id"])
    op.create_index("ix_AuditLog_created_at", "AuditLog", ["created_at"])
    op.create_index("ix_AuditLog_actor_user_id", "AuditLog", ["actor_user_id"])
    op.create_index("ix_AuditLog_action", "AuditLog", ["action"])
    op.create_index("ix_AuditLog_target_id", "AuditLog", ["target_id"])
    op.create_index("ix_AuditLog_trace_id", "AuditLog", ["trace_id"])


def downgrade() -> None:
    if "AuditLog" not in sa_inspect(op.get_bind()).get_table_names():
        return

    op.drop_index("ix_AuditLog_trace_id", table_name="AuditLog")
    op.drop_index("ix_AuditLog_target_id", table_name="AuditLog")
    op.drop_index("ix_AuditLog_action", table_name="AuditLog")
    op.drop_index("ix_AuditLog_actor_user_id", table_name="AuditLog")
    op.drop_index("ix_AuditLog_created_at", table_name="AuditLog")
    op.drop_index("ix_AuditLog_id", table_name="AuditLog")
    op.drop_table("AuditLog")

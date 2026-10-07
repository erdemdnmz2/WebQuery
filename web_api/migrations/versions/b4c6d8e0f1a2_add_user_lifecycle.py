"""add user lifecycle columns

Revision ID: b4c6d8e0f1a2
Revises: a3f5c81b9d24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import mssql

revision: str = "b4c6d8e0f1a2"
down_revision: str | None = "a3f5c81b9d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_DATETIME = sa.DateTime().with_variant(mssql.DATETIME2(precision=7), "mssql")


def _user_columns() -> set[str]:
    return {column["name"] for column in sa_inspect(op.get_bind()).get_columns("Users")}


def upgrade() -> None:
    columns = _user_columns()

    if "is_active" not in columns:
        op.add_column(
            "Users",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    if "disabled_at" not in columns:
        op.add_column("Users", sa.Column("disabled_at", _APP_DATETIME, nullable=True))

    if "disabled_by" not in columns:
        op.add_column(
            "Users", sa.Column("disabled_by", sa.String(length=50), nullable=True)
        )

    if "created_at" not in columns:
        op.add_column(
            "Users",
            sa.Column(
                "created_at",
                _APP_DATETIME,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    if "last_login_at" not in columns:
        op.add_column(
            "Users", sa.Column("last_login_at", _APP_DATETIME, nullable=True)
        )

    indexes = {index["name"] for index in sa_inspect(op.get_bind()).get_indexes("Users")}
    if "ix_Users_is_active" not in indexes:
        op.create_index("ix_Users_is_active", "Users", ["is_active"])


def downgrade() -> None:
    columns = _user_columns()
    indexes = {index["name"] for index in sa_inspect(op.get_bind()).get_indexes("Users")}

    if "ix_Users_is_active" in indexes:
        op.drop_index("ix_Users_is_active", table_name="Users")
    for column in ("last_login_at", "created_at", "disabled_by", "disabled_at", "is_active"):
        if column in columns:
            op.drop_column("Users", column)

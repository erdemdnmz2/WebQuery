"""add persistent platform owner boundary

Revision ID: c8a4e6f2b9d1
Revises: e4b1c7a09d52
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "c8a4e6f2b9d1"
down_revision: str | None = "e4b1c7a09d52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "is_platform_owner"
_INDEX = "ix_Users_is_platform_owner"


def _columns() -> set[str]:
    return {column["name"] for column in sa_inspect(op.get_bind()).get_columns("Users")}


def _indexes() -> set[str]:
    return {index["name"] for index in sa_inspect(op.get_bind()).get_indexes("Users")}


def upgrade() -> None:
    if _COLUMN not in _columns():
        op.add_column(
            "Users",
            sa.Column(
                _COLUMN,
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if _INDEX not in _indexes():
        op.create_index(_INDEX, "Users", [_COLUMN], unique=False)


def downgrade() -> None:
    if _INDEX in _indexes():
        op.drop_index(_INDEX, table_name="Users")
    if _COLUMN in _columns():
        op.drop_column("Users", _COLUMN)

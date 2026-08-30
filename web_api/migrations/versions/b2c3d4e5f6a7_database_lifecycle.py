"""add target database retirement columns

Registration lifecycle (P1-10, OQ-2026-016): a retired target database is
deactivated rather than deleted. `ActionLogging.database_id`, `MaskingRules` and
`UserDatabaseAssociation` all reference this row, and `QueryData` matches it by
(servername, database_name), so a hard delete would orphan exactly the audit
trail the record exists to preserve.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "Databases"
_INDEX = "ix_Databases_is_active"


def _columns() -> set[str]:
    return {column["name"] for column in sa_inspect(op.get_bind()).get_columns(_TABLE)}


def _indexes() -> set[str]:
    return {index["name"] for index in sa_inspect(op.get_bind()).get_indexes(_TABLE)}


def upgrade() -> None:
    existing = _columns()
    if "is_active" not in existing:
        # Every already-registered database is active; the server default keeps
        # existing rows queryable through the migration.
        op.add_column(
            _TABLE,
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
        )
    if "retired_at" not in existing:
        op.add_column(_TABLE, sa.Column("retired_at", sa.DateTime(), nullable=True))
    if "retired_by" not in existing:
        op.add_column(_TABLE, sa.Column("retired_by", sa.String(length=50), nullable=True))
    if _INDEX not in _indexes():
        op.create_index(_INDEX, _TABLE, ["is_active"], unique=False)


def downgrade() -> None:
    if _INDEX in _indexes():
        op.drop_index(_INDEX, table_name=_TABLE)
    existing = _columns()
    for column in ("retired_by", "retired_at", "is_active"):
        if column in existing:
            op.drop_column(_TABLE, column)

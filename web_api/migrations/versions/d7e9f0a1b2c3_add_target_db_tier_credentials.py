"""add target database tier credentials

Revision ID: d7e9f0a1b2c3
Revises: b4c6d8e0f1a2
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "d7e9f0a1b2c3"
down_revision: str | None = "b4c6d8e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREDENTIAL_COLUMNS = (
    ("username_ro", sa.String(length=100)),
    ("password_ro", sa.Text()),
    ("username_rw", sa.String(length=100)),
    ("password_rw", sa.Text()),
    ("username_ddl", sa.String(length=100)),
    ("password_ddl", sa.Text()),
)


def _columns() -> set[str]:
    return {column["name"] for column in sa_inspect(op.get_bind()).get_columns("Databases")}


def upgrade() -> None:
    existing = _columns()
    for name, column_type in _CREDENTIAL_COLUMNS:
        if name not in existing:
            op.add_column("Databases", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    existing = _columns()
    for name, _column_type in reversed(_CREDENTIAL_COLUMNS):
        if name in existing:
            op.drop_column("Databases", name)

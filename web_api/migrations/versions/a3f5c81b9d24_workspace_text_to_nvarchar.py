"""widen workspace name and description to NVARCHAR

Revision ID: a3f5c81b9d24
Revises: f6d4a7b9c2e1

The baseline created Workspaces.name and Workspaces.description as VARCHAR,
which on MSSQL is bound to the server codepage: "Veritabanı envanteri" comes
back as "Veritabani envanteri". The model declares these columns as
AppNVarChar, so a database built from the baseline alone disagrees with the
ORM and still loses Turkish letters. See SPEC-0012 BR-05.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "a3f5c81b9d24"
down_revision: str | None = "f6d4a7b9c2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors AppNVarChar in app_database/models.py.
_NVARCHAR_MAX = sa.String().with_variant(mssql.NVARCHAR(length=None), "mssql")


def _is_mssql() -> bool:
    """Only MSSQL distinguishes VARCHAR from NVARCHAR here.

    SQLite and PostgreSQL already store Unicode in their VARCHAR columns, so
    there is nothing to convert and no reason to rewrite the table.
    """
    return op.get_bind().dialect.name == "mssql"


def upgrade() -> None:
    if not _is_mssql():
        return

    op.alter_column(
        "Workspaces",
        "name",
        existing_type=sa.String(length=100),
        type_=_NVARCHAR_MAX,
        existing_nullable=False,
    )
    op.alter_column(
        "Workspaces",
        "description",
        existing_type=sa.String(length=255),
        type_=_NVARCHAR_MAX,
        existing_nullable=True,
    )


def downgrade() -> None:
    if not _is_mssql():
        return

    # Narrowing back to VARCHAR is lossy for any row that used the wider type.
    op.alter_column(
        "Workspaces",
        "description",
        existing_type=_NVARCHAR_MAX,
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "Workspaces",
        "name",
        existing_type=_NVARCHAR_MAX,
        type_=sa.String(length=100),
        existing_nullable=False,
    )

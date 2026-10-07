"""add query decision metadata

Revision ID: f6d4a7b9c2e1
Revises: c2f1b8d7e6a5
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import mssql

revision: str = "f6d4a7b9c2e1"
down_revision: str | None = "c2f1b8d7e6a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _query_data_columns() -> set[str]:
    return {
        column["name"]
        for column in sa_inspect(op.get_bind()).get_columns("QueryData")
    }


def upgrade() -> None:
    columns = _query_data_columns()
    if "decision_reason" not in columns:
        op.add_column(
            "QueryData", sa.Column("decision_reason", sa.String(length=500), nullable=True)
        )
    if "decided_by" not in columns:
        op.add_column(
            "QueryData", sa.Column("decided_by", sa.String(length=50), nullable=True)
        )
    if "decided_at" not in columns:
        op.add_column(
            "QueryData",
            sa.Column(
                "decided_at",
                sa.DateTime().with_variant(mssql.DATETIME2(precision=7), "mssql"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    columns = _query_data_columns()
    for column in ("decided_at", "decided_by", "decision_reason"):
        if column in columns:
            op.drop_column("QueryData", column)

"""audit remediation: drop dead token blacklist, constrain masking rules

Two changes from the 2026-08-29 audit:

* `BlacklistedTokens` is dropped (OQ-2026-014). `sessions.mint_access` never
  issued a `jti`, so the table was never written and its lookup never fired;
  ADR-0008's server-side `UserSessions` rows are the revocation record. Leaving
  a table that advertises a security control nobody runs is worse than either
  wiring it up or removing it.

* `MaskingRules` gains a unique constraint on (database_id, table_name,
  column_name). The save path already refuses duplicates in the request body,
  but nothing stopped two concurrent saves, or a direct write, from leaving two
  rows for one column (P2-20i).

Revision ID: a1b2c3d4e5f6
Revises: c8a4e6f2b9d1
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "c8a4e6f2b9d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BLACKLIST_TABLE = "BlacklistedTokens"
_MASKING_TABLE = "MaskingRules"
_MASKING_UNIQUE = "uq_MaskingRules_database_table_column"


def _tables() -> set[str]:
    return set(sa_inspect(op.get_bind()).get_table_names())


def _constraints(table: str) -> set[str]:
    inspector = sa_inspect(op.get_bind())
    if table not in set(inspector.get_table_names()):
        return set()
    return {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table)
        if constraint.get("name")
    }


def _deduplicate_masking_rules() -> None:
    """Keep one row per (database_id, table_name, column_name).

    A pre-existing duplicate would make the constraint creation fail, taking
    startup down on an install that was working. The newest row wins, matching
    what the save path would have produced.
    """
    op.execute(
        sa.text(
            """
            DELETE FROM "MaskingRules"
            WHERE id NOT IN (
                SELECT keep_id FROM (
                    SELECT MAX(id) AS keep_id
                    FROM "MaskingRules"
                    GROUP BY database_id, table_name, column_name
                ) AS survivors
            )
            """
        )
    )


def upgrade() -> None:
    if _BLACKLIST_TABLE in _tables():
        op.drop_table(_BLACKLIST_TABLE)

    if _MASKING_TABLE in _tables() and _MASKING_UNIQUE not in _constraints(_MASKING_TABLE):
        _deduplicate_masking_rules()
        # batch_alter_table so this also runs under SQLite, which cannot ALTER a
        # constraint in place and needs the copy-and-move strategy. On SQL
        # Server it compiles to a plain ADD CONSTRAINT.
        with op.batch_alter_table(_MASKING_TABLE) as batch:
            batch.create_unique_constraint(
                _MASKING_UNIQUE, ["database_id", "table_name", "column_name"]
            )


def downgrade() -> None:
    if _MASKING_UNIQUE in _constraints(_MASKING_TABLE):
        with op.batch_alter_table(_MASKING_TABLE) as batch:
            batch.drop_constraint(_MASKING_UNIQUE, type_="unique")

    if _BLACKLIST_TABLE not in _tables():
        op.create_table(
            _BLACKLIST_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("jti", sa.String(length=100), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_BlacklistedTokens_id"), _BLACKLIST_TABLE, ["id"], unique=False
        )
        op.create_index(
            op.f("ix_BlacklistedTokens_jti"), _BLACKLIST_TABLE, ["jti"], unique=True
        )

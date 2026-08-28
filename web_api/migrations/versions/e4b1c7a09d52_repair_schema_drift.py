"""repair schema drift left by pre-Alembic create_all installs

The baseline revision returns early when every table already exists, so an
install bootstrapped with Base.metadata.create_all() never received the indexes
and constraints the baseline declares, and no later revision adds them. This
revision creates whatever is missing, and is a no-op on a database that was
built by migrations from the start.

Revision ID: e4b1c7a09d52
Revises: d7e9f0a1b2c3
Create Date: 2026-08-28
"""
import uuid as uuid_module
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import mssql

from common.schema_contract import REQUIRED_INDEXES, REQUIRED_UNIQUE, unique_column_sets

revision: str = "e4b1c7a09d52"
down_revision: str | None = "d7e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID_TYPE = sa.String(length=36).with_variant(mssql.UNIQUEIDENTIFIER(), "mssql")

# NOT NULL columns a create_all() install may have created as nullable, with the
# value to backfill before the constraint can be applied. Only columns whose
# correct value is unambiguous appear here: `uuid` is per-row identity that
# nothing can yet reference, and `approval_status` has a model default that
# describes exactly what an un-flagged historical log row was. Any other NOT
# NULL gap is left for the startup guard to report, because inventing a value
# for it would be guessing at what the row meant.
_NOT_NULL_REPAIRS: tuple[tuple[str, str, object, str | None], ...] = (
    ("Databases", "uuid", _UUID_TYPE, None),  # None: generate one per row
    (
        "ActionLogging",
        "approval_status",
        sa.Enum(
            "AUTO_APPROVED", "PENDING", "APPROVED", "REJECTED", name="approvalstatus"
        ),
        "AUTO_APPROVED",
    ),
)


def _reflect(bind, name: str) -> sa.Table:
    return sa.Table(name, sa.MetaData(), autoload_with=bind)


def _dependent_indexes(bind, table_name: str, column_name: str) -> list[dict]:
    """Indexes that MSSQL will refuse to let us alter the column underneath.

    `ALTER COLUMN` fails with error 5074 while any index covers the column, so
    they are dropped and recreated around the change. A unique index is not
    dropped: on MSSQL it may be the physical form of a unique constraint, which
    `DROP INDEX` cannot remove, and silently skipping the alter would leave the
    guarantee missing while the migration reported success.
    """
    dependent = []
    for index in sa_inspect(bind).get_indexes(table_name):
        if column_name not in index["column_names"]:
            continue
        if index.get("unique"):
            raise RuntimeError(
                f"'{table_name}.{column_name}' üzerinde unique index "
                f"'{index['name']}' var; NOT NULL değişikliği elle yapılmalı."
            )
        dependent.append(index)
    return dependent


def _repair_not_null(bind, table_name: str, column_name: str, column_type, fill) -> None:
    """Backfill a nullable column and then apply its NOT NULL constraint."""
    table = _reflect(bind, table_name)
    column = table.c[column_name]

    if fill is None:
        # Per-row values: a shared uuid would be worse than a NULL one.
        rows = bind.execute(
            sa.select(table.c.id).where(column.is_(None))
        ).fetchall()
        for (row_id,) in rows:
            bind.execute(
                table.update()
                .where(table.c.id == row_id)
                .values(**{column_name: str(uuid_module.uuid4())})
            )
    else:
        bind.execute(
            table.update().where(column.is_(None)).values(**{column_name: fill})
        )

    dependent = _dependent_indexes(bind, table_name, column_name)
    for index in dependent:
        op.drop_index(index["name"], table_name=table_name)

    op.alter_column(
        table_name, column_name, existing_type=column_type, nullable=False
    )

    for index in dependent:
        op.create_index(
            index["name"],
            table_name,
            [name for name in index["column_names"] if name],
            unique=False,
        )


def _duplicate_group_count(bind, table_name: str, columns: tuple[str, ...]) -> int:
    """How many column-value groups appear more than once."""
    table = _reflect(bind, table_name)
    grouped = [table.c[name] for name in columns]
    duplicates = (
        sa.select(*grouped).group_by(*grouped).having(sa.func.count() > 1).subquery()
    )
    return bind.execute(
        sa.select(sa.func.count()).select_from(duplicates)
    ).scalar_one()


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa_inspect(bind).get_table_names())

    # 1. NOT NULL guarantees, before anything indexes or constrains the column.
    for table_name, column_name, column_type, fill in _NOT_NULL_REPAIRS:
        if table_name not in tables:
            continue
        column = next(
            (
                candidate
                for candidate in sa_inspect(bind).get_columns(table_name)
                if candidate["name"] == column_name
            ),
            None,
        )
        if column is not None and column.get("nullable", True):
            _repair_not_null(bind, table_name, column_name, column_type, fill)

    # 2. Uniqueness guarantees. A duplicate row makes the constraint
    #    uncreatable; skipping it silently would leave the database without the
    #    guarantee while reporting success, so this fails loudly instead.
    for spec in REQUIRED_UNIQUE:
        if spec.table not in tables or spec.name is None:
            continue
        if frozenset(spec.columns) in unique_column_sets(sa_inspect(bind), spec.table):
            continue

        duplicates = _duplicate_group_count(bind, spec.table, spec.columns)
        if duplicates:
            raise RuntimeError(
                f"'{spec.table}' tablosunda ({', '.join(spec.columns)}) için "
                f"{duplicates} yinelenen grup var. '{spec.name}' kısıtı "
                "oluşturulamaz; önce yinelenen kayıtları temizleyin."
            )
        op.create_unique_constraint(spec.name, spec.table, list(spec.columns))

    # 3. Indexes.
    for spec in REQUIRED_INDEXES:
        if spec.table not in tables:
            continue
        existing = {index["name"] for index in sa_inspect(bind).get_indexes(spec.table)}
        if spec.name not in existing:
            op.create_index(
                spec.name, spec.table, list(spec.columns), unique=spec.unique
            )


def downgrade() -> None:
    """Deliberately empty.

    This revision only creates objects that every other revision already
    assumes exist. Dropping them would recreate the drift it repairs, and it
    cannot tell an object it created apart from one the baseline created.
    """

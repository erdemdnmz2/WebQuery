"""The indexes, uniqueness and nullability the application database must carry.

Alembic's baseline revision returns early when every table already exists,
because a pre-Alembic install bootstrapped its tables with
``Base.metadata.create_all()``. That guard keeps the baseline from failing on
such an install, but it also means the install never receives the indexes and
constraints the baseline would have created, and no later revision adds them.
The result is a database that runs while silently missing `uq_server_database`
— the only real guarantee against registering the same target twice — and the
indexes the Slack approval lookup and the per-query uuid lookup depend on.

This module is the single list of what must be present:

- ``e4b1c7a09d52_repair_schema_drift`` creates whatever is missing.
- ``common.schema_guard`` refuses to start the application if anything still is.
- ``tests/unit/test_schema_contract.py`` asserts this list matches
  ``Base.metadata``, so the contract cannot drift away from the models.

Migrations must not import model classes, which is why this is plain data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexSpec:
    """One index, identified by name because that is how migrations create it."""

    name: str
    table: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True)
class UniqueSpec:
    """One uniqueness guarantee, identified by its column set.

    Some unique constraints are declared without a name and the database
    generates one (``UQ__Users__AB6E6164B8487291``). Matching on columns rather
    than on the name is therefore the only check that works everywhere.
    """

    table: str
    columns: tuple[str, ...]
    name: str | None = None


REQUIRED_INDEXES: tuple[IndexSpec, ...] = (
    IndexSpec("ix_ActionLogging_approval_status", "ActionLogging", ("approval_status",)),
    IndexSpec("ix_ActionLogging_database_id", "ActionLogging", ("database_id",)),
    IndexSpec("ix_ActionLogging_id", "ActionLogging", ("id",)),
    IndexSpec("ix_ActionLogging_machine_name", "ActionLogging", ("machine_name",)),
    IndexSpec("ix_ActionLogging_trace_id", "ActionLogging", ("trace_id",)),
    IndexSpec("ix_ActionLogging_user_id", "ActionLogging", ("user_id",)),
    IndexSpec("ix_ActionLogging_username", "ActionLogging", ("username",)),
    IndexSpec("ix_AuditLog_action", "AuditLog", ("action",)),
    IndexSpec("ix_AuditLog_actor_user_id", "AuditLog", ("actor_user_id",)),
    IndexSpec("ix_AuditLog_created_at", "AuditLog", ("created_at",)),
    IndexSpec("ix_AuditLog_id", "AuditLog", ("id",)),
    IndexSpec("ix_AuditLog_target_id", "AuditLog", ("target_id",)),
    IndexSpec("ix_AuditLog_trace_id", "AuditLog", ("trace_id",)),
    IndexSpec("ix_BlacklistedTokens_id", "BlacklistedTokens", ("id",)),
    IndexSpec("ix_BlacklistedTokens_jti", "BlacklistedTokens", ("jti",), unique=True),
    IndexSpec("ix_Databases_id", "Databases", ("id",)),
    IndexSpec("ix_Databases_uuid", "Databases", ("uuid",)),
    IndexSpec("ix_LoginLogging_id", "LoginLogging", ("id",)),
    IndexSpec("ix_MaskingRules_id", "MaskingRules", ("id",)),
    IndexSpec("ix_QueryData_id", "QueryData", ("id",)),
    IndexSpec("ix_QueryData_uuid", "QueryData", ("uuid",)),
    IndexSpec("ix_UserSessions_expires_at", "UserSessions", ("expires_at",)),
    IndexSpec("ix_UserSessions_id", "UserSessions", ("id",)),
    IndexSpec("ix_UserSessions_prev_refresh_hash", "UserSessions", ("prev_refresh_hash",)),
    IndexSpec("ix_UserSessions_refresh_hash", "UserSessions", ("refresh_hash",), unique=True),
    IndexSpec("ix_UserSessions_revoked_at", "UserSessions", ("revoked_at",)),
    IndexSpec("ix_UserSessions_user_id", "UserSessions", ("user_id",)),
    IndexSpec("ix_Users_id", "Users", ("id",)),
    IndexSpec("ix_Users_is_active", "Users", ("is_active",)),
    IndexSpec("ix_Users_username", "Users", ("username",), unique=True),
    IndexSpec("ix_Workspaces_id", "Workspaces", ("id",)),
)

REQUIRED_UNIQUE: tuple[UniqueSpec, ...] = (
    UniqueSpec("Databases", ("servername", "database_name"), name="uq_server_database"),
    UniqueSpec("Users", ("email",)),
    UniqueSpec("Workspaces", ("query_id",)),
)

REQUIRED_NOT_NULL: tuple[tuple[str, str], ...] = (
    ("ActionLogging", "approval_status"),
    ("ActionLogging", "machine_name"),
    ("ActionLogging", "query"),
    ("ActionLogging", "query_date"),
    ("ActionLogging", "user_id"),
    ("ActionLogging", "username"),
    ("AuditLog", "action"),
    ("AuditLog", "created_at"),
    ("BlacklistedTokens", "expires_at"),
    ("BlacklistedTokens", "jti"),
    ("Databases", "database_name"),
    ("Databases", "servername"),
    ("Databases", "technology"),
    ("Databases", "uuid"),
    ("LoginLogging", "client_ip"),
    ("LoginLogging", "login_date"),
    ("LoginLogging", "user_id"),
    ("MaskingRules", "column_name"),
    ("MaskingRules", "database_id"),
    ("MaskingRules", "table_name"),
    ("QueryData", "query"),
    ("QueryData", "status"),
    ("QueryData", "user_id"),
    ("QueryData", "uuid"),
    ("UserDatabaseAssociation", "is_admin"),
    ("UserDatabaseAssociation", "role"),
    ("UserSessions", "created_at"),
    ("UserSessions", "expires_at"),
    ("UserSessions", "refresh_hash"),
    ("UserSessions", "user_id"),
    ("Users", "created_at"),
    ("Users", "is_active"),
    ("Workspaces", "name"),
    ("Workspaces", "query_id"),
    ("Workspaces", "user_id"),
)


def unique_column_sets(inspector, table: str) -> set[frozenset[str]]:
    """Every uniqueness guarantee on a table, however the backend reports it.

    Backends disagree on where a uniqueness guarantee shows up. SQLite reports
    it through ``get_unique_constraints``; the MSSQL dialect does not implement
    that method at all and instead surfaces the constraint's backing index
    through ``get_indexes`` with ``unique=True`` (``UQ__Users__AB6E6164...``).
    Reading both and comparing column sets rather than names is what makes the
    check work on either.
    """
    found: set[frozenset[str]] = set()
    try:
        for constraint in inspector.get_unique_constraints(table):
            found.add(frozenset(constraint["column_names"]))
    except NotImplementedError:
        # MSSQL. Its unique constraints arrive through get_indexes below.
        pass
    for index in inspector.get_indexes(table):
        if index.get("unique"):
            found.add(frozenset(name for name in index["column_names"] if name))
    return found


def missing_objects(inspector) -> list[str]:
    """Return a human-readable line per schema guarantee that is absent.

    Takes a synchronous SQLAlchemy ``Inspector`` so the same function serves the
    migration (``sa.inspect(op.get_bind())``) and the startup guard
    (``connection.run_sync(...)``). An empty list means the database carries
    every guarantee in this module.
    """
    missing: list[str] = []
    tables = set(inspector.get_table_names())

    required_tables = (
        {spec.table for spec in REQUIRED_INDEXES}
        | {spec.table for spec in REQUIRED_UNIQUE}
        | {table for table, _ in REQUIRED_NOT_NULL}
    )
    for table in sorted(required_tables - tables):
        missing.append(f"tablo eksik: {table}")

    for spec in REQUIRED_INDEXES:
        if spec.table not in tables:
            continue
        names = {index["name"] for index in inspector.get_indexes(spec.table)}
        if spec.name not in names:
            columns = ", ".join(spec.columns)
            missing.append(f"index eksik: {spec.name} ({spec.table}.{columns})")

    for spec in REQUIRED_UNIQUE:
        if spec.table not in tables:
            continue
        if frozenset(spec.columns) not in unique_column_sets(inspector, spec.table):
            columns = ", ".join(spec.columns)
            label = spec.name or "adsız"
            missing.append(f"unique kısıtı eksik: {label} ({spec.table}: {columns})")

    for table, column in REQUIRED_NOT_NULL:
        if table not in tables:
            continue
        for info in inspector.get_columns(table):
            if info["name"] == column and info.get("nullable", True):
                missing.append(f"NOT NULL değil: {table}.{column}")
                break

    return missing

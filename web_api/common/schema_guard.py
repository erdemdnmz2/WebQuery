"""Startup validation for the application database schema.

``config_guard`` checks the environment before anything connects; this checks
the schema after the connection succeeds and after ``entrypoint.sh`` has run
``alembic upgrade head``. Both fail closed, for the same reason: a WebQuery
that starts with a silently incomplete schema keeps working until the missing
guarantee is the one that mattered — a duplicate target database registration,
or a Slack approval that cannot find its query by ``trace_id``.
"""

import logging

from sqlalchemy import inspect as sa_inspect

from .schema_contract import missing_objects

logger = logging.getLogger("web_api.schema_guard")


def verify_schema(connection) -> None:
    """Reject an incomplete schema before the application starts.

    Args:
        connection: A synchronous SQLAlchemy connection. Async callers reach
            this through ``await conn.run_sync(verify_schema)``.

    Raises:
        SystemExit: If any index, unique constraint or NOT NULL guarantee in
            ``schema_contract`` is missing.
    """
    missing = missing_objects(sa_inspect(connection))
    if not missing:
        logger.info("Schema verified: all indexes and constraints are present")
        return

    logger.critical(
        "SCHEMA ERROR: %d schema guarantees are missing: %s. See "
        "docs/architecture.md (ADR-0015) for Alembic repair instructions.",
        len(missing),
        ", ".join(missing),
    )
    raise SystemExit(1)

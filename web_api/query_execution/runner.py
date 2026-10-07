"""Shared target-database execution mechanics for every query path.

Three call sites run user SQL against a target database — ad-hoc execution, an
approved workspace re-run, and the admin preview. They had drifted apart on two
details that matter, so both now live here:

**Streaming (P1-5).** SQLAlchemy's async layer buffers the whole result of
`session.execute()` before `fetchmany()` ever runs, so a `SELECT` over eight
million rows was fully materialised in the worker's memory and *then* trimmed to
a thousand. With `QUERY_TIMEOUT_SECONDS` at 300, no statement timeout on SQL
Server before this change, and `performance_risk` not blocking by default,
`SELECT * FROM big_table` could exhaust a worker without ever meeting a gate.
Plain reads now stream and stop at the limit.

**Truncation (P2-7).** `fetchmany(size=LIMIT)` returns at most `LIMIT` rows, so
`row_count >= LIMIT` reported a result set of exactly `LIMIT` rows as truncated.
One extra row is requested and the surplus discarded, which is the only way to
tell "exactly full" from "more waiting".
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy.sql import text

from query_execution.query_analyzer import QueryPlan


@dataclass
class ExecutionResult:
    """What one statement batch produced."""

    returns_rows: bool
    rows: list[dict[str, Any]]
    #: Rows returned for a read, or rows affected for a write.
    row_count: int
    truncated: bool

    @property
    def message(self) -> str:
        if not self.returns_rows:
            return f"{self.row_count} rows affected"
        if self.truncated:
            return f"Truncated to MAX_ROW_COUNT_LIMIT ({self.row_count})"
        return f"{self.row_count} rows returned"


async def run_statement(session, plan: QueryPlan, row_limit: int) -> ExecutionResult:
    """Execute a planned query and return at most ``row_limit`` rows.

    Args:
        session: An open target-database `AsyncSession`.
        plan: The single parse of the submitted SQL.
        row_limit: Maximum rows handed back to the caller.
    """
    statement = text(plan.query)

    if plan.is_pure_read:
        # `AsyncResult` has no `returns_rows`, which is why the read/write
        # decision comes from the plan rather than from the driver. `plan`
        # only sets `is_pure_read` when every statement is a plain read, so
        # anything ambiguous falls to the buffered path below.
        streamed = await session.stream(statement)
        try:
            rows = await streamed.fetchmany(row_limit + 1)
        finally:
            await streamed.close()
        truncated = len(rows) > row_limit
        rows = rows[:row_limit]
        return ExecutionResult(
            returns_rows=True,
            rows=[dict(row._mapping) for row in rows],
            row_count=len(rows),
            truncated=truncated,
        )

    result = await session.execute(statement)
    if result.returns_rows:
        # A write with a RETURNING clause, or a statement the planner could not
        # classify. Buffered, but still capped.
        rows = result.fetchmany(size=row_limit + 1)
        truncated = len(rows) > row_limit
        rows = rows[:row_limit]
        return ExecutionResult(
            returns_rows=True,
            rows=[dict(row._mapping) for row in rows],
            row_count=len(rows),
            truncated=truncated,
        )

    return ExecutionResult(
        returns_rows=False,
        rows=[],
        row_count=result.rowcount if result.rowcount is not None else 0,
        truncated=False,
    )

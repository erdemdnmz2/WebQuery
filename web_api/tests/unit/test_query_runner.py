"""
Tests for shared target execution mechanics: streaming and truncation.

P1-5: SQLAlchemy's async layer buffers the whole result of `session.execute()`
before `fetchmany()` runs, so `SELECT * FROM big_table` was materialised in the
worker's memory in full and *then* trimmed. Reads now stream.

P1-5/P2-7: `fetchmany(size=LIMIT)` returns at most LIMIT rows, so the old
`row_count >= LIMIT` check reported a result set of exactly LIMIT rows as
truncated and the UI drew "İlk 1000 satır (kırpıldı)" over a complete answer.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from query_execution.query_analyzer import QueryAnalyzer
from query_execution.runner import run_statement

pytestmark = pytest.mark.asyncio

ANALYZER = QueryAnalyzer()


def _rows(count: int):
    rows = []
    for index in range(count):
        row = MagicMock()
        row._mapping = {"id": index}
        rows.append(row)
    return rows


def _session(stream_rows=None, execute_rows=None, returns_rows=True, rowcount=0):
    session = AsyncMock()

    streamed = AsyncMock()
    streamed.fetchmany = AsyncMock(return_value=stream_rows or [])
    streamed.close = AsyncMock()
    session.stream = AsyncMock(return_value=streamed)

    result = MagicMock()
    result.returns_rows = returns_rows
    result.fetchmany.return_value = execute_rows or []
    result.rowcount = rowcount
    session.execute = AsyncMock(return_value=result)

    session._streamed = streamed
    return session


async def test_plain_select_uses_the_streaming_path():
    session = _session(stream_rows=_rows(2))
    plan = ANALYZER.plan("SELECT id FROM users", technology="postgresql")

    outcome = await run_statement(session, plan, row_limit=1000)

    session.stream.assert_awaited_once()
    session.execute.assert_not_awaited()
    assert outcome.rows == [{"id": 0}, {"id": 1}]
    assert outcome.row_count == 2
    assert outcome.truncated is False


async def test_streaming_asks_for_one_row_beyond_the_limit():
    """The only way to tell 'exactly full' from 'more waiting'."""
    session = _session(stream_rows=_rows(5))
    plan = ANALYZER.plan("SELECT id FROM users", technology="postgresql")

    await run_statement(session, plan, row_limit=3)

    session._streamed.fetchmany.assert_awaited_once_with(4)


async def test_exactly_the_limit_is_not_reported_as_truncated():
    session = _session(stream_rows=_rows(3))
    plan = ANALYZER.plan("SELECT id FROM users", technology="postgresql")

    outcome = await run_statement(session, plan, row_limit=3)

    assert outcome.row_count == 3
    assert outcome.truncated is False
    assert outcome.message == "3 rows returned"


async def test_one_row_past_the_limit_is_truncated_and_trimmed():
    session = _session(stream_rows=_rows(4))
    plan = ANALYZER.plan("SELECT id FROM users", technology="postgresql")

    outcome = await run_statement(session, plan, row_limit=3)

    assert outcome.truncated is True
    assert len(outcome.rows) == 3
    assert "Truncated" in outcome.message


async def test_streamed_result_is_always_closed():
    session = _session(stream_rows=_rows(1))
    plan = ANALYZER.plan("SELECT id FROM users", technology="postgresql")

    await run_statement(session, plan, row_limit=10)

    session._streamed.close.assert_awaited_once()


async def test_dml_keeps_the_buffered_path():
    session = _session(returns_rows=False, rowcount=7)
    plan = ANALYZER.plan("UPDATE users SET active = 1", technology="postgresql")

    outcome = await run_statement(session, plan, row_limit=1000)

    session.execute.assert_awaited_once()
    session.stream.assert_not_awaited()
    assert outcome.returns_rows is False
    assert outcome.row_count == 7
    assert outcome.message == "7 rows affected"


async def test_write_returning_rows_is_still_capped():
    session = _session(returns_rows=True, execute_rows=_rows(4))
    plan = ANALYZER.plan(
        "UPDATE users SET active = 1 RETURNING id", technology="postgresql"
    )

    outcome = await run_statement(session, plan, row_limit=3)

    session.execute.assert_awaited_once()
    assert outcome.truncated is True
    assert len(outcome.rows) == 3


async def test_batch_mixing_a_read_and_a_write_does_not_stream():
    """`is_pure_read` is conservative: anything uncertain stays buffered."""
    plan = ANALYZER.plan(
        "SELECT id FROM users; UPDATE users SET active = 1", technology="postgresql"
    )
    assert plan.is_pure_read is False


async def test_opaque_command_does_not_stream():
    plan = ANALYZER.plan("EXEC sp_who", technology="mssql")
    assert plan.is_pure_read is False

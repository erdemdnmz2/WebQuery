"""The query block in the Slack approval notification (ADR-0019, finding P2-18).

Slack rejects the entire payload when a `section` block exceeds 3000 characters.
Before the limit was applied, a long query caused the approval notification to
be dropped: the user received "sent for approval" while nothing appeared in
the channel.
"""
from slack_integration.schemas import (
    _SLACK_SECTION_LIMIT,
    create_approval_message,
)


def _query_block(blocks: list[dict]) -> dict:
    return next(
        block
        for block in blocks
        if block["type"] == "section" and "text" in block
    )


def _message(query: str) -> list[dict]:
    return create_approval_message(
        request_id="req-1",
        username="analyst",
        machine_name="prod-db-1",
        database="customer_db",
        query=query,
        risk_score="risky_dml",
    )


def test_a_short_query_is_sent_in_full():
    """ADR-0019: a reviewer cannot evaluate a query they cannot see."""
    query = "DELETE FROM customers WHERE id = 42"

    text = _query_block(_message(query))["text"]["text"]

    assert query in text
    assert "first" not in text  # no truncation note


def test_a_long_query_is_truncated_instead_of_dropping_the_notification():
    query = "SELECT " + ", ".join(f"column_{i}" for i in range(1000)) + " FROM t"
    assert len(query) > _SLACK_SECTION_LIMIT

    text = _query_block(_message(query))["text"]["text"]

    assert len(text) <= _SLACK_SECTION_LIMIT
    assert text.startswith("*Query:*")
    assert query[:200] in text
    assert query not in text


def test_a_truncated_query_points_the_approver_at_webquery():
    query = "SELECT " + ", ".join(f"column_{i}" for i in range(1000)) + " FROM t"

    text = _query_block(_message(query))["text"]["text"]

    assert "WebQuery" in text
    assert "req-1" in text


def test_a_query_at_the_boundary_still_fits():
    """A query just below the truncation threshold must not be truncated or
    exceed the block limit: wrapper text counts against the budget."""
    query = "x" * 2700

    text = _query_block(_message(query))["text"]["text"]

    assert query in text
    assert len(text) <= _SLACK_SECTION_LIMIT

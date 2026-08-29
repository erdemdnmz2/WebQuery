"""Shared application constants."""

QUERY_STATUS_SAVED_IN_WORKSPACE = "saved_in_workspace"
QUERY_STATUS_WAITING_FOR_APPROVAL = "waiting_for_approval"
QUERY_STATUS_APPROVED_AND_EXECUTED = "approved_and_executed"
QUERY_STATUS_APPROVED_WITH_RESULTS = "approved_with_results"
QUERY_STATUS_REJECTED = "rejected"

# The SQL text of a saved query may only be rewritten while the approval flow
# does not depend on it. Editing a query that is waiting for a decision changes
# what the approver is looking at (TOCTOU); editing an approved one turns a
# single approval into an unbounded licence to run different SQL.
WORKSPACE_EDITABLE_STATUSES = frozenset(
    {QUERY_STATUS_SAVED_IN_WORKSPACE, QUERY_STATUS_REJECTED}
)

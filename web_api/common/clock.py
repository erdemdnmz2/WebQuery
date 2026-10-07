"""The one clock every `AppDateTime` write should use.

`sessions.py` and `owner/services.py` already used `datetime.now(UTC).replace(
tzinfo=None)` for their own writes (naive UTC, matching the naive
`AppDateTime` columns everywhere else). Several other writers — `create_log`,
`update_log`, `update_approval_status`, `create_login_log`, `log_in` — used
plain `datetime.now()` instead, which is the *server's local time*. The two
functions are indistinguishable in a column that carries no timezone, so two
rows in the same table sat on different axes: `ExecutionDurationMS` and
`login_duration_ms` could go negative across a DST transition, or on any
replica whose OS timezone differs from UTC, and audit ordering by timestamp
became unreliable across writers.
"""
from datetime import UTC, datetime


def db_now() -> datetime:
    """Naive UTC `datetime`, for every `AppDateTime` column in the app DB."""
    return datetime.now(UTC).replace(tzinfo=None)

"""Helpers for safely translating target-database errors.

Target database drivers may include infrastructure and credential details in
their exception text.  Keep a password-redacted version for server-side
diagnostics and expose only a scrubbed, user-safe version to API clients.
"""

import re
from typing import Final

_PASSWORD_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(
            r"(\b(?:password|passwd|pwd|pass)\s*[=:]\s*)([^;,)\s]+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(://[^:/\s]+:)([^@/\s]+)(@)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\3",
    ),
)

_CLIENT_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(
            r"\b(?:server|address|addr|uid|pwd|user|password|driver|dsn|"
            r"database|dbname|host|hostaddr|port)\s*=\s*[^;,)\s]+",
            re.IGNORECASE,
        ),
        "[bağlantı-bilgisi]",
    ),
    (
        re.compile(
            r"\bfor user\s+[\"']?[^\"'\s,)]+[\"']?",
            re.IGNORECASE,
        ),
        "for user [gizli]",
    ),
    (
        re.compile(
            r"\bserver\s+[\"']?[^\"'\s,)]+[\"']?(\s*\([^)]*\))?",
            re.IGNORECASE,
        ),
        "server [gizli]",
    ),
    (
        re.compile(
            r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
            r"(?:\.\d{1,3}){2,3}(?::\d+)?\b",
            re.IGNORECASE,
        ),
        "[iç-adres]",
    ),
    (
        re.compile(
            r"\b[\w.-]+\.(?:database\.windows\.net|rds\.amazonaws\.com|"
            r"myhuaweicloud\.com)(?::\d+)?\b",
            re.IGNORECASE,
        ),
        "[db-host]",
    ),
    (
        re.compile(
            r"\b[\w-]+\.(?:internal|local|lan|corp|intranet)\b",
            re.IGNORECASE,
        ),
        "[iç-host]",
    ),
    (
        re.compile(r"(?:[A-Za-z]:)?[\\/](?:[\w.-]+[\\/])+[\w.-]+\.py"),
        "[dosya]",
    ),
)

_USER_FIXABLE: Final[re.Pattern[str]] = re.compile(
    r"(invalid column name|invalid object name|syntax error|"
    r"unknown column|doesn't exist|does not exist|ambiguous column|"
    r"division by zero|conversion failed|arithmetic overflow|"
    r"string or binary data would be truncated|"
    r"cannot insert the value null|violation of .* constraint)",
    re.IGNORECASE,
)

_MAX_CLIENT_ERROR_LENGTH: Final[int] = 500


def redact_passwords(message: str) -> str:
    """Redact common password forms while preserving other diagnostics."""
    if not message:
        return message

    redacted = message
    for pattern, replacement in _PASSWORD_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def scrub(message: str) -> str:
    """Return a target-database error that is safe to show to an API client."""
    if not message:
        return "Sorgu çalıştırılamadı."

    cleaned = redact_passwords(message)
    for pattern, replacement in _CLIENT_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    if _USER_FIXABLE.search(cleaned):
        cleaned = re.sub(r"^\(?['\"]?[\dA-Z]{5}['\"]?,?\s*", "", cleaned)
        cleaned = re.sub(
            r"\[[^\]]*(?:Microsoft|ODBC|SQL Server|Driver)[^\]]*\]",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" '\"()")
        return cleaned[:_MAX_CLIENT_ERROR_LENGTH]

    return (
        "Sorgu çalıştırılamadı. Ayrıntılar sunucu kaydına yazıldı — "
        "destek ekibine trace_id ile başvurun."
    )

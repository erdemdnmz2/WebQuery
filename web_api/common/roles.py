"""Shared role parsing and capability helpers.

``UserDatabaseAssociation.role`` stores one or more comma-separated roles.
Keeping parsing here prevents authorization checks from interpreting the same
stored value differently in different parts of the application.
"""

from collections.abc import Iterable

READER, WRITER, DDL = "READER", "WRITER", "DDL"
ADMIN = "ADMIN"

_TIER_BY_ROLE = {READER: "ro", WRITER: "rw", DDL: "ddl"}
_TIER_RANK = {"ro": 0, "rw": 1, "ddl": 2}


def parse(role_string: str | None) -> set[str]:
    """Normalize a comma-separated role value into a set of role names."""
    if not role_string:
        return set()
    return {role.strip().upper() for role in role_string.split(",") if role.strip()}


def is_admin(role_string: str | None) -> bool:
    """Return whether a role value grants database administration capability."""
    return ADMIN in parse(role_string)


def max_tier(role_string: str | None) -> str | None:
    """Return the highest data-access tier, excluding the governance role."""
    tiers = [_TIER_BY_ROLE[role] for role in parse(role_string) if role in _TIER_BY_ROLE]
    if not tiers:
        return None
    return max(tiers, key=_TIER_RANK.__getitem__)


def any_admin(associations: Iterable[object]) -> bool:
    """Return whether any association contains the ``ADMIN`` role."""
    return any(is_admin(getattr(association, "role", None)) for association in associations)

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
_ROLE_ORDER = {READER: 0, WRITER: 1, DDL: 2, ADMIN: 3}


def parse(role_string: str | None) -> set[str]:
    """Normalize a comma-separated role value into a set of role names."""
    if not role_string:
        return set()
    return {role.strip().upper() for role in role_string.split(",") if role.strip()}


def is_admin(role_string: str | None) -> bool:
    """Return whether a role value grants database administration capability."""
    return ADMIN in parse(role_string)


def format_roles(roles: Iterable[str]) -> str:
    """Serialize normalized roles in one stable, human-readable order."""
    normalized = {role.strip().upper() for role in roles if role.strip()}
    return ",".join(sorted(normalized, key=lambda role: _ROLE_ORDER.get(role, 99)))


def max_tier(role_string: str | None) -> str | None:
    """Return the highest data-access tier, excluding the governance role."""
    tiers = [_TIER_BY_ROLE[role] for role in parse(role_string) if role in _TIER_BY_ROLE]
    if not tiers:
        return None
    return max(tiers, key=_TIER_RANK.__getitem__)


def any_admin(associations: Iterable[object]) -> bool:
    """Return whether any association contains the ``ADMIN`` role."""
    return any(is_admin(getattr(association, "role", None)) for association in associations)


CONNECTION_MODES = ("ro", "ro_rw", "ro_rw_ddl")

# A connection mode is named after the tiers it provisions, so its top tier is
# what a caller compares against. Modes are hierarchical by decision of
# OQ-2026-007: `rw` and `ddl` never exist without the tiers below them.
_TOP_TIER_BY_MODE = {"ro": "ro", "ro_rw": "rw", "ro_rw_ddl": "ddl"}
_MODE_BY_TOP_TIER = {tier: mode for mode, tier in _TOP_TIER_BY_MODE.items()}


def mode_from_credentials(
    *, has_ro: bool, has_rw: bool, has_ddl: bool
) -> str | None:
    """Derive a registration's connection mode from the tiers it stores.

    Returns ``None`` for a record that predates per-tier credentials, so a
    caller can tell "not yet migrated" apart from "read-only".
    """
    if has_ddl:
        return "ro_rw_ddl"
    if has_rw:
        return "ro_rw"
    if has_ro:
        return "ro"
    return None


def granted_tier(role_string: str | None) -> str | None:
    """Return the highest tier a role value can execute at.

    This differs from ``max_tier`` on one point: ``ADMIN`` is counted as
    ``ddl``, because ``QueryAnalyzer.check_role_permission`` lets an ADMIN run
    DDL. ``max_tier`` deliberately excludes the governance role and is kept for
    callers that ask only about explicitly granted data access.
    """
    if ADMIN in parse(role_string):
        return "ddl"
    return max_tier(role_string)


def effective_mode(connection_mode: str | None, role_string: str | None) -> str | None:
    """Intersect what a database provisions with what a role may execute.

    A READER on a ``ro_rw`` database gets ``ro``: the write tier exists but is
    unreachable for them. Showing the registration's mode instead would promise
    a capability that execution then refuses.
    """
    database_tier = _TOP_TIER_BY_MODE.get(connection_mode or "")
    user_tier = granted_tier(role_string)
    if database_tier is None or user_tier is None:
        return None
    lowest = min(database_tier, user_tier, key=_TIER_RANK.__getitem__)
    return _MODE_BY_TOP_TIER[lowest]


def exceeds_mode(connection_mode: str | None, role_string: str | None) -> str | None:
    """Return the *highest* granted tier the database cannot serve, if any.

    ``ADMIN`` is exempt: it is the governance role that administers a
    registration, and ``add_database`` grants it on every database regardless
    of which credential tiers the DBA provided.

    The answer is the highest exceeding tier, not the first one found. Walking
    the roles alphabetically happened to put ``DDL`` ahead of ``WRITER`` and so
    usually reported the right one, but that was an accident of the three role
    names; the conflict list this feeds (OQ-2026-018) has to name the tier the
    admin actually needs to remove.
    """
    database_tier = _TOP_TIER_BY_MODE.get(connection_mode or "")
    if database_tier is None:
        return None
    exceeding = [
        tier
        for role in parse(role_string)
        if (tier := _TIER_BY_ROLE.get(role))
        and _TIER_RANK[tier] > _TIER_RANK[database_tier]
    ]
    if not exceeding:
        return None
    return max(exceeding, key=_TIER_RANK.__getitem__)

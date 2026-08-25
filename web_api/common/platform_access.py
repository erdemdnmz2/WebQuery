"""Platform-scoped access checks.

Database ADMIN is intentionally not treated as platform administration. The
allowlist is a transitional boundary until the planned OWNER role exists.
"""

import os


def configured_platform_admins() -> set[str]:
    return {
        username.strip().casefold()
        for username in os.getenv("PLATFORM_ADMINS", "").split(",")
        if username.strip()
    }


def is_platform_admin(username: str | None) -> bool:
    return bool(username) and username.casefold() in configured_platform_admins()

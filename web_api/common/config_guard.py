"""Startup validation for security-sensitive application configuration."""

import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger("web_api.config_guard")

_KNOWN_BAD = {
    "",
    "change-me",
    "secret",
    "your-secret-key-here-change-in-production",
}

_PRIVILEGED_DB_USERS = {"sa", "root", "postgres", "admin"}

# QUERY_ENCRYPTION_KEY is checked separately below: it is required unless the
# plural QUERY_ENCRYPTION_KEYS (rotation) is set instead.
_REQUIRED = (
    "SECRET_KEY",
    "APP_DATABASE_URL",
    "CENTRAL_DB_USER",
    "CENTRAL_DB_PASSWORD",
    "REDIS_URL",
)


def _fail(message: str) -> None:
    logger.critical("CONFIGURATION ERROR: %s", message)
    raise SystemExit(1)


def verify_startup_config() -> None:
    """Reject missing or unsafe configuration before the app starts."""
    missing = []
    for name in _REQUIRED:
        value = (os.getenv(name) or "").strip()
        if not value or value in _KNOWN_BAD:
            missing.append(name)

    if missing:
        _fail(
            "The following environment variables are missing or use default values: "
            + ", ".join(missing)
            + ". Check your .env file."
        )

    secret_key = os.environ["SECRET_KEY"]
    if len(secret_key) < 32:
        _fail("SECRET_KEY must be at least 32 characters long.")

    # QUERY_ENCRYPTION_KEYS (plural, comma-separated, newest first) enables
    # rotation; every key in it is validated the same way QUERY_ENCRYPTION_KEY
    # is. See EncryptedText for how the list is used.
    keys_csv = os.getenv("QUERY_ENCRYPTION_KEYS")
    single_key = (os.getenv("QUERY_ENCRYPTION_KEY") or "").strip()
    candidate_keys = (
        [key.strip() for key in keys_csv.split(",") if key.strip()]
        if keys_csv
        else ([single_key] if single_key and single_key not in _KNOWN_BAD else [])
    )
    if not candidate_keys:
        _fail(
            "QUERY_ENCRYPTION_KEY or QUERY_ENCRYPTION_KEYS is not configured. "
            "At least one Fernet key is required."
        )
    for candidate in candidate_keys:
        try:
            Fernet(candidate.encode())
        except Exception as exc:
            _fail(f"QUERY_ENCRYPTION_KEY(S) contains an invalid Fernet key: {exc}")

    central_db_user = os.environ["CENTRAL_DB_USER"].strip()
    if central_db_user.lower() in _PRIVILEGED_DB_USERS:
        logger.warning(
            "CENTRAL_DB_USER='%s' — you are using a highly privileged account. "
            "See ADR-0005 for separate role-based target database credentials.",
            central_db_user,
        )

    allowed_domains = {
        domain.strip().lstrip("@").lower()
        for domain in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",")
        if domain.strip().lstrip("@")
    }
    if not allowed_domains:
        logger.warning("ALLOWED_EMAIL_DOMAINS is empty — self-registration is disabled.")

    # DEBUG is the only signal this app has for "this is a production run"
    # (see app.py, where it also gates uvicorn's --reload). A session cookie
    # sent over plain HTTP is readable by anything on the network path, so a
    # deploy that leaves DEBUG unset — production mode — must not be able to
    # leave COOKIE_SECURE off by omission.
    debug = os.getenv("DEBUG", "false").strip().lower() == "true"
    cookie_secure = os.getenv("COOKIE_SECURE", "False").strip().lower() == "true"
    if not debug and not cookie_secure:
        _fail(
            "COOKIE_SECURE must be true when DEBUG=false (production mode). "
            "Session cookies must not be sent over plain HTTP."
        )

    logger.info("Configuration verified: %d critical settings present", len(_REQUIRED))

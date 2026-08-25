"""Startup validation for security-sensitive application configuration."""

import logging
import os
import sys

from cryptography.fernet import Fernet

logger = logging.getLogger("web_api.config_guard")

_KNOWN_BAD = {
    "",
    "change-me",
    "secret",
    "your-secret-key-here-change-in-production",
}

_PRIVILEGED_DB_USERS = {"sa", "root", "postgres", "admin"}

_REQUIRED = (
    "SECRET_KEY",
    "QUERY_ENCRYPTION_KEY",
    "APP_DATABASE_URL",
    "CENTRAL_DB_USER",
    "CENTRAL_DB_PASSWORD",
)


def _fail(message: str) -> None:
    logger.critical("KONFIGÜRASYON HATASI: %s", message)
    print(f"\n❌ FATAL: {message}\n", file=sys.stderr)
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
            "Şu ortam değişkenleri eksik veya varsayılan değerde: "
            + ", ".join(missing)
            + ". .env dosyanızı kontrol edin."
        )

    secret_key = os.environ["SECRET_KEY"]
    if len(secret_key) < 32:
        _fail("SECRET_KEY en az 32 karakter olmalıdır.")

    try:
        Fernet(os.environ["QUERY_ENCRYPTION_KEY"].encode())
    except Exception as exc:  # noqa: BLE001 - all invalid Fernet inputs fail closed
        _fail(f"QUERY_ENCRYPTION_KEY geçerli bir Fernet anahtarı değil: {exc}")

    central_db_user = os.environ["CENTRAL_DB_USER"].strip()
    if central_db_user.lower() in _PRIVILEGED_DB_USERS:
        logger.warning(
            "CENTRAL_DB_USER='%s' — yüksek yetkili bir hesapla çalışıyorsunuz. "
            "Rol bazlı ayrı hedef DB kimlik bilgileri için ADR-0005'e bakın.",
            central_db_user,
        )

    allowed_domains = {
        domain.strip().lstrip("@").lower()
        for domain in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",")
        if domain.strip().lstrip("@")
    }
    if not allowed_domains:
        logger.warning("ALLOWED_EMAIL_DOMAINS boş — self-registration kapalı.")
    elif not os.getenv("PLATFORM_ADMINS", "").strip():
        logger.warning(
            "ALLOWED_EMAIL_DOMAINS tanımlı ancak PLATFORM_ADMINS boş — "
            "kullanıcılar kayıt olabilir fakat etkinleştirilemez."
        )

    logger.info("Konfigürasyon doğrulandı: %d kritik ayar mevcut", len(_REQUIRED))

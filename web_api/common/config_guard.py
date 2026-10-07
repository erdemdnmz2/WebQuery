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
    logger.critical("KONFIGÜRASYON HATASI: %s", message)
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
            "QUERY_ENCRYPTION_KEY veya QUERY_ENCRYPTION_KEYS tanımlı değil. "
            "En az bir Fernet anahtarı gereklidir."
        )
    for candidate in candidate_keys:
        try:
            Fernet(candidate.encode())
        except Exception as exc:
            _fail(f"QUERY_ENCRYPTION_KEY(S) içinde geçerli olmayan bir Fernet anahtarı var: {exc}")

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

    # DEBUG is the only signal this app has for "this is a production run"
    # (see app.py, where it also gates uvicorn's --reload). A session cookie
    # sent over plain HTTP is readable by anything on the network path, so a
    # deploy that leaves DEBUG unset — production mode — must not be able to
    # leave COOKIE_SECURE off by omission.
    debug = os.getenv("DEBUG", "false").strip().lower() == "true"
    cookie_secure = os.getenv("COOKIE_SECURE", "False").strip().lower() == "true"
    if not debug and not cookie_secure:
        _fail(
            "DEBUG=false (üretim modu) iken COOKIE_SECURE=true olmalıdır. "
            "Oturum çerezleri düz HTTP üzerinden gönderilmemelidir."
        )

    logger.info("Konfigürasyon doğrulandı: %d kritik ayar mevcut", len(_REQUIRED))

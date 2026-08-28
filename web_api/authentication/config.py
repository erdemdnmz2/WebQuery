"""
Authentication Service Config
"""
import os

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Startup config validation is responsible for rejecting missing/unsafe values.
# Keeping this as None until startup allows the guard to produce the actionable
# error instead of failing during module import with an opaque KeyError.
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
RATE_LIMITER = os.getenv("RATE_LIMITER", "3/minute")


def _email_domains() -> tuple[str, ...]:
    """Return normalized exact-match domains allowed to self-register."""
    return tuple(
        domain.strip().lstrip("@").lower()
        for domain in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",")
        if domain.strip().lstrip("@")
    )


ALLOWED_EMAIL_DOMAINS = _email_domains()
REGISTRATION_REQUIRES_ACTIVATION = (
    os.getenv("REGISTRATION_REQUIRES_ACTIVATION", "true").lower() == "true"
)


def is_registration_domain_allowed(email: str) -> bool:
    """Registration is fail-closed when no domain has been configured."""
    if not ALLOWED_EMAIL_DOMAINS:
        return False
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain in ALLOWED_EMAIL_DOMAINS

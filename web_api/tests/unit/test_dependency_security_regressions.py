"""Compatibility checks required by SPEC-0029 dependency remediation."""

from datetime import UTC, datetime

import jwt
import pytest
from cryptography.fernet import Fernet
from jwt.exceptions import InvalidAlgorithmError

from app_database.models import Databases, EncryptedText, QueryData
from authentication import config
from authentication.sessions import mint_access


@pytest.fixture(autouse=True)
def reset_fernet_cache():
    EncryptedText._fernet = None
    yield
    EncryptedText._fernet = None


def test_existing_encrypted_credentials_and_queries_remain_readable(monkeypatch):
    """Fernet values written before the cryptography upgrade still decrypt."""
    old_key = Fernet.generate_key().decode()
    monkeypatch.delenv("QUERY_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEY", old_key)

    old_fernet = Fernet(old_key.encode())
    credential_ciphertext = old_fernet.encrypt(b"previous-target-password").decode()
    query_ciphertext = old_fernet.encrypt(b"SELECT customer_id FROM customers").decode()

    credential_type = Databases.__table__.c.password_ro.type
    query_type = QueryData.__table__.c.query.type

    assert credential_type.process_result_value(credential_ciphertext, None) == "previous-target-password"
    assert query_type.process_result_value(query_ciphertext, None) == "SELECT customer_id FROM customers"


def test_pyjwt_access_tokens_preserve_claims_and_reject_other_algorithms(monkeypatch):
    """The python-jose replacement keeps the existing HS256 token contract."""
    monkeypatch.setattr(config, "SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")
    monkeypatch.setattr(config, "ALGORITHM", "HS256")

    token = mint_access(user_id=42, session_id=17)
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])

    assert payload["sub"] == "42"
    assert payload["sid"] == 17
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]

    hs512_token = jwt.encode(
        {"sub": "42", "sid": 17, "iat": datetime.now(UTC)},
        "test-only-secret-key-with-at-least-64-characters-for-hs512-checks",
        algorithm="HS512",
    )
    with pytest.raises(InvalidAlgorithmError):
        jwt.decode(
            hs512_token,
            "test-only-secret-key-with-at-least-64-characters-for-hs512-checks",
            algorithms=[config.ALGORITHM],
        )

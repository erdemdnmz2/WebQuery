"""
Regression tests for EncryptedText key rotation and decrypt-failure visibility
(P1-11).

Before this: a single QUERY_ENCRYPTION_KEY meant a key rotation had no
migration path — every existing encrypted row became undecryptable the moment
the key changed — and a failed decryption returned the raw ciphertext silently,
with nothing in the logs pointing at the cause.
"""
import logging
import os
import sys

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app_database.models import EncryptedText

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _reset_fernet_cache():
    """`EncryptedText._fernet` is a class-level cache; each test needs a clean one."""
    EncryptedText._fernet = None
    yield
    EncryptedText._fernet = None


def test_single_key_round_trips(monkeypatch):
    monkeypatch.delenv("QUERY_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEY", KEY_A)

    field = EncryptedText()
    encrypted = field.process_bind_param("secret-value", None)
    assert encrypted != "secret-value"
    assert field.process_result_value(encrypted, None) == "secret-value"


def test_rotation_decrypts_data_written_with_the_old_key(monkeypatch):
    """The core rotation scenario: encrypt with A, then rotate to [B, A]."""
    monkeypatch.delenv("QUERY_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEY", KEY_A)
    written_with_old_key = EncryptedText().process_bind_param("old-secret", None)

    EncryptedText._fernet = None
    monkeypatch.setenv("QUERY_ENCRYPTION_KEYS", f"{KEY_B},{KEY_A}")

    field = EncryptedText()
    assert field.process_result_value(written_with_old_key, None) == "old-secret"


def test_new_writes_after_rotation_use_the_new_key_first(monkeypatch):
    monkeypatch.delenv("QUERY_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEYS", f"{KEY_B},{KEY_A}")

    field = EncryptedText()
    encrypted = field.process_bind_param("new-secret", None)

    # Decryptable with only the new key: it was not encrypted with the old one.
    assert Fernet(KEY_B).decrypt(encrypted.encode()).decode() == "new-secret"
    with pytest.raises(Exception):
        Fernet(KEY_A).decrypt(encrypted.encode())


def test_decrypt_failure_falls_back_to_raw_value_but_logs_loudly(monkeypatch, caplog):
    """The defect: this used to return the raw value with no log line at all."""
    monkeypatch.delenv("QUERY_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEY", KEY_A)

    field = EncryptedText()
    with caplog.at_level(logging.ERROR):
        result = field.process_result_value("not-encrypted-legacy-plaintext", None)

    assert result == "not-encrypted-legacy-plaintext"
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_data_encrypted_with_a_dropped_key_is_visibly_unrecoverable(monkeypatch, caplog):
    """After a key is fully retired, its ciphertext is not silently swallowed."""
    monkeypatch.delenv("QUERY_ENCRYPTION_KEYS", raising=False)
    monkeypatch.setenv("QUERY_ENCRYPTION_KEY", KEY_A)
    orphaned = EncryptedText().process_bind_param("orphaned-secret", None)

    EncryptedText._fernet = None
    monkeypatch.setenv("QUERY_ENCRYPTION_KEYS", KEY_B)  # KEY_A dropped

    field = EncryptedText()
    with caplog.at_level(logging.ERROR):
        result = field.process_result_value(orphaned, None)

    assert result == orphaned  # ciphertext returned raw, not silently discarded
    assert any(record.levelno >= logging.ERROR for record in caplog.records)

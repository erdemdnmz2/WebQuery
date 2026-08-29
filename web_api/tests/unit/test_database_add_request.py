import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from owner.schemas import OwnerDatabaseCreate


def payload(**overrides):
    values = {
        "servername": "db.example.test",
        "database_name": "sales",
        "tech_name": "postgresql",
        "connection_mode": "ro",
        "initial_admin_user_id": 1,
        "username_ro": "sales_ro",
        "password_ro": "ro-password",
    }
    values.update(overrides)
    return values


def test_read_only_mode_accepts_only_ro_credentials():
    request = OwnerDatabaseCreate(**payload())

    assert request.connection_mode == "ro"


def test_read_write_mode_requires_rw_credentials():
    with pytest.raises(ValidationError, match="RW kullanıcı adı ve şifresi zorunludur"):
        OwnerDatabaseCreate(**payload(connection_mode="ro_rw"))


def test_ddl_mode_requires_all_three_credential_tiers():
    request = OwnerDatabaseCreate(
        **payload(
            connection_mode="ro_rw_ddl",
            username_rw="sales_rw",
            password_rw="rw-password",
            username_ddl="sales_ddl",
            password_ddl="ddl-password",
        )
    )

    assert request.username_ddl == "sales_ddl"


def test_read_only_mode_rejects_unselected_rw_credentials():
    with pytest.raises(ValidationError, match="RW bilgileri seçilen bağlantı modunda gönderilemez"):
        OwnerDatabaseCreate(**payload(username_rw="sales_rw"))

from common.roles import any_admin, is_admin, max_tier, parse


class Association:
    def __init__(self, role: str | None):
        self.role = role


def test_parse_normalizes_and_ignores_empty_roles():
    assert parse("reader, WRITER, , reader ") == {"READER", "WRITER"}
    assert parse(None) == set()


def test_is_admin_checks_governance_role_only():
    assert is_admin("ADMIN,READER") is True
    assert is_admin("reader,writer") is False
    assert is_admin(None) is False


def test_max_tier_ignores_admin_and_returns_highest_data_tier():
    assert max_tier("ADMIN") is None
    assert max_tier("ADMIN,READER") == "ro"
    assert max_tier("READER,WRITER") == "rw"
    assert max_tier("ADMIN,WRITER,DDL") == "ddl"


def test_any_admin_checks_all_associations():
    assert any_admin([Association("READER"), Association(" ADMIN ")]) is True
    assert any_admin([Association("READER"), Association(None)]) is False

from common.roles import (
    any_admin,
    effective_mode,
    exceeds_mode,
    granted_tier,
    is_admin,
    max_tier,
    mode_from_credentials,
    parse,
)


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


def test_mode_from_credentials_names_the_highest_provisioned_tier():
    assert mode_from_credentials(has_ro=True, has_rw=True, has_ddl=True) == "ro_rw_ddl"
    assert mode_from_credentials(has_ro=True, has_rw=True, has_ddl=False) == "ro_rw"
    assert mode_from_credentials(has_ro=True, has_rw=False, has_ddl=False) == "ro"


def test_mode_from_credentials_returns_none_for_an_unmigrated_record():
    """A record with no tier credentials is not read-only, it is unconfigured."""
    assert mode_from_credentials(has_ro=False, has_rw=False, has_ddl=False) is None


def test_granted_tier_counts_admin_as_ddl_unlike_max_tier():
    assert granted_tier("ADMIN") == "ddl"
    assert max_tier("ADMIN") is None
    assert granted_tier("READER") == "ro"
    assert granted_tier(None) is None


def test_effective_mode_narrows_the_database_mode_to_the_users_role():
    assert effective_mode("ro_rw", "READER") == "ro"
    assert effective_mode("ro_rw", "WRITER") == "ro_rw"
    assert effective_mode("ro_rw_ddl", "READER,WRITER") == "ro_rw"
    assert effective_mode("ro_rw_ddl", "ADMIN") == "ro_rw_ddl"


def test_effective_mode_never_exceeds_what_the_database_provisions():
    """An ADMIN on a read-only registration still only reaches `ro`."""
    assert effective_mode("ro", "ADMIN") == "ro"
    assert effective_mode("ro", "WRITER") == "ro"


def test_effective_mode_is_none_when_either_side_is_missing():
    assert effective_mode(None, "WRITER") is None
    assert effective_mode("ro_rw", None) is None


def test_exceeds_mode_reports_the_tier_the_database_cannot_serve():
    assert exceeds_mode("ro", "WRITER") == "rw"
    assert exceeds_mode("ro_rw", "DDL") == "ddl"
    assert exceeds_mode("ro", "READER,WRITER") == "rw"


def test_exceeds_mode_exempts_admin_and_supported_tiers():
    assert exceeds_mode("ro", "ADMIN") is None
    assert exceeds_mode("ro_rw", "WRITER") is None
    assert exceeds_mode("ro_rw_ddl", "DDL") is None
    assert exceeds_mode(None, "WRITER") is None


def test_exceeds_mode_reports_the_highest_exceeding_tier_not_the_first():
    """The conflict list must name the tier the admin has to remove (P2-20k).

    Both WRITER and DDL exceed a read-only registration; answering `rw` would
    send the admin to fix the lesser of the two.
    """
    assert exceeds_mode("ro", "READER,WRITER,DDL") == "ddl"
    assert exceeds_mode("ro", "WRITER,DDL") == "ddl"
    assert exceeds_mode("ro", "DDL,WRITER") == "ddl"

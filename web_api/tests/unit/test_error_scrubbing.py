from common.errors import redact_passwords, scrub


def test_connection_error_does_not_expose_client_infrastructure_details():
    raw = (
        "('08001', '[08001] [Microsoft][ODBC Driver 18]TCP Provider: "
        'Error code 0x2746 (10.0.14.22:1433); Login failed for user '
        '"webquery_svc"; server=sql-prod-03.corp.internal; '
        "database=PayrollProd')"
    )

    output = scrub(raw)

    assert "10.0.14.22" not in output
    assert "webquery_svc" not in output
    assert "sql-prod-03" not in output
    assert "PayrollProd" not in output
    assert output.startswith("Sorgu çalıştırılamadı.")


def test_user_fixable_sql_error_is_preserved_without_driver_noise():
    raw = "('42S22', \"[42S22] [Microsoft][ODBC Driver 18]Invalid column name 'emial'.\")"

    output = scrub(raw)

    assert "emial" in output
    assert "Microsoft" not in output
    assert "ODBC" not in output


def test_password_is_redacted_for_server_side_diagnostics():
    raw = "Login failed; server=db.internal; password=secret-value; PWD=another-secret"

    output = redact_passwords(raw)

    assert "secret-value" not in output
    assert "another-secret" not in output
    assert output.count("[REDACTED]") == 2


def test_uri_password_is_redacted():
    output = redact_passwords("postgresql://report_user:s3cret@db.internal:5432/payroll")

    assert "s3cret" not in output
    assert "report_user:[REDACTED]@db.internal" in output

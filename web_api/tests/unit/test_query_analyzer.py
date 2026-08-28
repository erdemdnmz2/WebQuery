import os
import sys

import pytest

# Add the web_api directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from query_execution.query_analyzer import QueryAnalyzer, RiskLevel


@pytest.fixture
def analyzer():
    return QueryAnalyzer()

def test_sql_injection_and_privilege_escalation(analyzer: QueryAnalyzer):
    # Test EXECUTE AS
    query = "EXECUTE AS USER = 'Admin'; SELECT * FROM users"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.SQL_INJECTION.value

    # Test dynamic execution
    query = "EXEC('DROP ' + 'TABLE ' + 'users')"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.SQL_INJECTION.value
    
    # Test unparseable/obfuscated garbage that breaks the parser
    query = "SELECT * FROM users; DROP TABLE ; ; ; SELECT"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.SQL_INJECTION.value

def test_ddl_pattern_detection(analyzer: QueryAnalyzer):
    # Test DROP TABLE
    query = "DROP TABLE users;"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.DDL_PATTERN.value


    # Test Obfuscated DROP TABLE (Hacker bypass attempt with comments)
    query = "DROP /* hacker comment */ TABLE logs"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.DDL_PATTERN.value

    # Test TRUNCATE
    query = "TRUNCATE TABLE logs"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.DDL_PATTERN.value


@pytest.mark.parametrize("technology", ["mssql", "mysql", "postgresql"])
def test_alter_table_remains_ddl_after_sqlglot_upgrade(
    analyzer: QueryAnalyzer, technology: str
):
    """SQLGlot 30 represents ALTER TABLE with ``exp.Alter``, not AlterTable."""
    query = "ALTER TABLE users ADD department VARCHAR(100)"

    result = analyzer.analyze(query, technology=technology)

    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.DDL_PATTERN.value
    assert analyzer.required_tier(query, technology=technology) == "ddl"
    assert analyzer.check_permissions_match_role(query, "READER", technology=technology) is False
    assert analyzer.check_permissions_match_role(query, "DDL", technology=technology) is True


def test_risky_pattern_detection(analyzer: QueryAnalyzer):
    # UPDATE without WHERE
    query = "UPDATE users SET status='active'"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.RISKY_PATTERN.value
    
    # DELETE without WHERE
    query = "DELETE FROM users"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.RISKY_PATTERN.value
    
    # DELETE with WHERE (Should be safe from RISKY_PATTERN)
    query = "DELETE FROM users WHERE id = 1"
    result = analyzer.analyze(query)
    assert result["return"] is True

def test_performance_risk_is_flagged_but_not_blocking(analyzer: QueryAnalyzer):
    """
    A performance risk is a signal, not a gate. The statement timeout and the
    row limit are the real protection; blocking here fills the approval queue
    with ordinary reporting queries and trains the approver to wave things
    through. The risk is still recorded so the audit trail keeps it.
    """
    # Wildcard LIKE
    query = "SELECT * FROM users WHERE name LIKE '%john%'"
    result = analyzer.analyze(query)
    assert result["return"] is True
    assert result["risk_type"] == RiskLevel.PERFORMANCE.value
    assert result["warnings"]

    # CROSS JOIN
    query = "SELECT * FROM users CROSS JOIN products"
    result = analyzer.analyze(query)
    assert result["return"] is True
    assert result["risk_type"] == RiskLevel.PERFORMANCE.value


def test_ordinary_reporting_join_is_not_flagged(analyzer: QueryAnalyzer):
    """Four tables is a normal report, not a risk. See MAX_JOINS."""
    query = (
        "SELECT a.id FROM A a "
        "JOIN B b ON a.id = b.id "
        "JOIN C c ON b.id = c.id "
        "JOIN D d ON c.id = d.id"
    )
    result = analyzer.analyze(query)
    assert result["return"] is True
    assert result["risk_type"] is None


def test_join_count_above_max_joins_is_flagged(analyzer: QueryAnalyzer):
    """MAX_JOINS is the highest ordinary count, so the ninth join trips it."""
    joins = " ".join(
        f"JOIN T{n} t{n} ON t{n}.id = a.id" for n in range(9)
    )
    result = analyzer.analyze(f"SELECT a.id FROM A a {joins}")
    assert result["risk_type"] == RiskLevel.PERFORMANCE.value


def test_performance_blocks_can_be_switched_on(monkeypatch):
    """An installation that wants the old gate keeps it behind one setting."""
    from query_execution import config

    monkeypatch.setattr(config, "PERFORMANCE_BLOCKS", True)
    analyzer = QueryAnalyzer()

    result = analyzer.analyze("SELECT * FROM users WHERE name LIKE '%john%'")

    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.PERFORMANCE.value


def test_max_joins_is_read_from_config(monkeypatch):
    from query_execution import config

    monkeypatch.setattr(config, "MAX_JOINS", 1)
    analyzer = QueryAnalyzer()

    result = analyzer.analyze(
        "SELECT a.id FROM A a JOIN B b ON a.id = b.id JOIN C c ON b.id = c.id"
    )

    assert result["risk_type"] == RiskLevel.PERFORMANCE.value

def test_safe_query(analyzer: QueryAnalyzer):
    # Standard safe query with WHERE clause and normal LIKE
    query = "SELECT id, name FROM users WHERE name LIKE 'john%'"
    result = analyzer.analyze(query)
    assert result["return"] is True
    assert result["risk_type"] is None


class TestParseFailureIsNotAPermissionDecision:
    """
    A query that will not parse tells us nothing about the user's role. The
    permission check used to swallow the parse error and return False, so a
    typo reached the user as "your role is not authorized" - sending them to
    their administrator instead of to their SQL. See SPEC-0012 BR-06.
    """

    def test_unparseable_query_raises_parse_error(self):
        import sqlglot.errors

        from query_execution.query_analyzer import QueryAnalyzer

        analyzer = QueryAnalyzer()
        with pytest.raises(sqlglot.errors.ParseError):
            # The editor's placeholder text: a SELECT with a bare FROM.
            analyzer.check_permissions_match_role("SELECT TOP 100 *\nFROM", "READER")

    def test_valid_select_still_allowed_for_reader(self):
        from query_execution.query_analyzer import QueryAnalyzer

        analyzer = QueryAnalyzer()
        assert analyzer.check_permissions_match_role("SELECT 1", "READER") is True

    def test_reader_still_blocked_from_delete(self):
        from query_execution.query_analyzer import QueryAnalyzer

        analyzer = QueryAnalyzer()
        assert analyzer.check_permissions_match_role("DELETE FROM Customer", "READER") is False


class TestDangerousFunctionBlocklist:
    """
    ``_check_sql_injection`` only ever looked at ``exp.Command`` nodes, so
    ``SELECT pg_read_file('/etc/passwd')`` - an ``exp.Anonymous`` function call -
    was never examined at all.
    """

    @pytest.mark.parametrize(
        ("query", "technology"),
        [
            ("SELECT pg_read_file('/etc/passwd')", "postgresql"),
            ("SELECT pg_ls_dir('/')", "postgresql"),
            ("SELECT dblink_exec('dbname=x', 'DROP TABLE y')", "postgresql"),
            ("SELECT lo_import('/etc/shadow')", "postgresql"),
            ("SELECT load_file('/etc/passwd')", "mysql"),
            ("SELECT * FROM openrowset('SQLNCLI', 'x', 'SELECT 1')", "mssql"),
        ],
    )
    def test_blocked_function_is_rejected(self, analyzer, query, technology):
        result = analyzer.analyze(query, technology=technology)

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value
        assert result["reason"]

    def test_quoting_the_name_does_not_bypass_the_blocklist(self, analyzer):
        """The engine resolves a quoted call to the same function."""
        result = analyzer.analyze('SELECT "pg_read_file"(\'/etc/passwd\')', technology="postgresql")

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value

    def test_nested_call_is_found(self, analyzer):
        result = analyzer.analyze(
            "SELECT id FROM t WHERE name = pg_read_file('/etc/passwd')",
            technology="postgresql",
        )

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value

    def test_similarly_named_function_is_not_blocked(self, analyzer):
        result = analyzer.analyze("SELECT my_pg_read_file_wrapper(1)", technology="postgresql")

        assert result["return"] is True


class TestSleepIsBounded:
    """Sleep is a denial-of-service lever, so it is bounded rather than banned."""

    def test_short_sleep_is_allowed(self, analyzer):
        assert analyzer.analyze("SELECT pg_sleep(1)", technology="postgresql")["return"] is True

    def test_long_sleep_is_blocked(self, analyzer):
        result = analyzer.analyze("SELECT pg_sleep(600)", technology="postgresql")

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value

    def test_unreadable_argument_is_blocked(self, analyzer):
        """If we cannot tell how long it sleeps, the answer is no."""
        result = analyzer.analyze("SELECT pg_sleep((SELECT MAX(id) FROM t))", technology="postgresql")

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value


class TestExplainAnalyze:
    """
    ``EXPLAIN ANALYZE`` really executes the statement it wraps, and sqlglot
    parses the whole thing as an opaque command - so no AST check sees inside.
    """

    @pytest.mark.parametrize(
        "query",
        [
            "EXPLAIN ANALYZE UPDATE orders SET status = 'x'",
            "EXPLAIN ANALYSE DELETE FROM orders",
            "explain (analyze, buffers) select * from orders",
            "SELECT 1; EXPLAIN ANALYZE DELETE FROM orders",
        ],
    )
    def test_explain_analyze_is_blocked(self, analyzer, query):
        result = analyzer.analyze(query, technology="postgresql")

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value

    def test_plain_explain_is_allowed(self, analyzer):
        result = analyzer.analyze("EXPLAIN SELECT * FROM orders", technology="postgresql")

        assert result["return"] is True


class TestBatchTierMixing:
    """
    Only DDL mixing is rejected. Read plus write in one batch is an ordinary
    unit of work: it runs on one connection, in one transaction, under the
    ``rw`` account that can already do both.
    """

    def test_select_and_update_batch_is_allowed(self, analyzer):
        query = (
            "SELECT * FROM orders WHERE id = 42; "
            "UPDATE orders SET status = 'approved' WHERE id = 42"
        )

        result = analyzer.analyze(query)

        assert result["return"] is True
        assert analyzer.check_tier_consistency(query) is None
        assert analyzer.required_tier(query) == "rw"

    def test_schema_change_mixed_with_data_is_rejected(self, analyzer):
        query = "SELECT * FROM orders; ALTER TABLE orders ADD note VARCHAR(100)"

        result = analyzer.analyze(query)

        assert result["return"] is False
        assert result["risk_type"] == RiskLevel.BLOCKED_OPERATION.value
        assert analyzer.check_tier_consistency(query) is not None

    def test_ddl_alone_is_not_a_mixing_problem(self, analyzer):
        """A pure DDL batch still routes through the normal DDL risk path."""
        query = "ALTER TABLE orders ADD note VARCHAR(100)"

        assert analyzer.check_tier_consistency(query) is None
        assert analyzer.analyze(query)["risk_type"] == RiskLevel.DDL_PATTERN.value


class TestHardBlockedRisks:
    """
    The administrator bypass skips the approval requirement, not the security
    check. ``hard_block_reason`` is what the other execution paths consult.
    """

    def test_hard_block_reason_reports_blocked_function(self, analyzer):
        from query_execution.query_analyzer import hard_block_reason

        assert hard_block_reason(analyzer, "SELECT pg_read_file('/etc/passwd')", "postgresql")

    def test_hard_block_reason_ignores_reviewable_risk(self, analyzer):
        """A WHERE-less DELETE is an approval question, not a hard block."""
        from query_execution.query_analyzer import hard_block_reason

        assert hard_block_reason(analyzer, "DELETE FROM orders") is None

    def test_hard_blocked_set_covers_injection_and_blocked_operations(self):
        from query_execution.query_analyzer import HARD_BLOCKED_RISKS

        assert RiskLevel.SQL_INJECTION.value in HARD_BLOCKED_RISKS
        assert RiskLevel.BLOCKED_OPERATION.value in HARD_BLOCKED_RISKS
        assert RiskLevel.PERFORMANCE.value not in HARD_BLOCKED_RISKS
        assert RiskLevel.RISKY_PATTERN.value not in HARD_BLOCKED_RISKS

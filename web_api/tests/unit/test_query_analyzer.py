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

def test_performance_risk_detection(analyzer: QueryAnalyzer):
    # Wildcard LIKE
    query = "SELECT * FROM users WHERE name LIKE '%john%'"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.PERFORMANCE.value

    # CROSS JOIN
    query = "SELECT * FROM users CROSS JOIN products"
    result = analyzer.analyze(query)
    assert result["return"] is False
    assert result["risk_type"] == RiskLevel.PERFORMANCE.value
    
    # Multiple JOINs
    query = "SELECT a.id FROM A a JOIN B b ON a.id = b.id JOIN C c ON b.id = c.id JOIN D d ON c.id = d.id"
    result = analyzer.analyze(query)
    assert result["return"] is False
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

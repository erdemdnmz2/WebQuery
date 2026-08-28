"""
Query Analyzer
SQL query security and performance analysis via AST parsing
"""
import re
from enum import Enum

import sqlglot
from sqlglot import exp

from common.roles import parse


class RiskLevel(Enum):
    """Query risk levels"""
    SQL_INJECTION = "sql_injection_risk"
    DDL_PATTERN = "ddl_pattern"
    RISKY_PATTERN = "risky_pattern"
    PERFORMANCE = "performance_risk"
    BLOCKED_OPERATION = "blocked_operation"


# Risks that no role may skip. Everything else is a judgement call that an
# administrator may take responsibility for; these are not. There is no
# supported path through WebQuery for shell execution, filesystem access or
# remote SQL, so "who is asking" is not a relevant question for them.
HARD_BLOCKED_RISKS = frozenset(
    {RiskLevel.SQL_INJECTION.value, RiskLevel.BLOCKED_OPERATION.value}
)

_DIALECT_BY_TECHNOLOGY = {
    "mssql": "tsql",
    "mysql": "mysql",
    "postgresql": "postgres",
    "postgres": "postgres",
}

_BLOCKED_FUNCTIONS = frozenset({
    # SQL Server - operating system / remote access
    "xp_cmdshell", "xp_regread", "xp_regwrite", "xp_dirtree", "xp_fileexist",
    "sp_oacreate", "sp_oamethod", "sp_execute_external_script",
    "openrowset", "opendatasource", "openquery",
    # PostgreSQL - filesystem / cluster control / remote SQL
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "lo_put",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "dblink", "dblink_connect", "dblink_exec",
    # MySQL
    "load_file", "sys_exec", "sys_eval",
})

# Sleep functions are a denial-of-service lever rather than an escape, so they
# are bounded instead of blocked outright.
_SLEEP_FUNCTIONS = frozenset({"pg_sleep", "pg_sleep_for", "sleep", "waitfor"})
_MAX_SLEEP_SECONDS = 5

# EXPLAIN ANALYZE really executes the statement it wraps, and sqlglot parses the
# whole thing as an opaque ``exp.Command`` - so no AST check can see inside it.
# ``[^;]*`` keeps the match inside a single statement; the pattern is not
# anchored because the dangerous form can sit anywhere in a batch. PostgreSQL
# accepts the British spelling as a synonym, so ANALYSE has to match too.
_EXPLAIN_ANALYZE_RE = re.compile(r"\bEXPLAIN\b[^;]*\bANALY[SZ]E\b", re.IGNORECASE)

_DDL_TYPES = (exp.Drop, exp.Create, exp.Alter, exp.TruncateTable)
_DML_TYPES = (exp.Insert, exp.Update, exp.Delete, exp.Merge)


def _function_names(stmt: exp.Expression) -> set[str]:
    """
    Every function call name in the tree, lowercased.

    Quoted calls are caught too: ``"pg_read_file"(...)`` resolves to the same
    function in the engine, but sqlglot puts an Identifier in ``.this`` instead
    of a string. Missing that difference means quoting bypasses the blocklist.
    """
    names: set[str] = set()
    for func in stmt.find_all(exp.Func):
        if isinstance(func, exp.Anonymous):
            names.add(_anonymous_name(func))
            continue
        # ``sql_name`` is only defined for concrete function classes; the base
        # class raises rather than returning a name.
        try:
            sql_name = func.sql_name()
        except NotImplementedError:
            continue
        if sql_name:
            names.add(sql_name.lower())
    return names - {""}


def _anonymous_name(call: exp.Anonymous) -> str:
    """Resolve the callee name of an anonymous function call, quoted or not."""
    raw = call.this
    if isinstance(raw, str):
        return raw.lower()
    name = getattr(raw, "name", None) or getattr(raw, "this", None)
    return name.lower() if isinstance(name, str) else ""


def hard_block_reason(
    analyzer: "QueryAnalyzer", query: str, technology: str = "mssql"
) -> str | None:
    """
    Reason a query trips a check nobody may skip, or None.

    Only the hard-blocked subset is consulted, so paths that legitimately run
    queries an administrator already reviewed - an approved workspace, an admin
    preview - keep working. What they must not do is offer a second door to the
    checks that have no door at all.
    """
    analysis = analyzer.analyze(query, technology=technology)
    if analysis.get("risk_type") in HARD_BLOCKED_RISKS:
        return analysis.get("reason") or "Bu sorgu güvenlik politikası gereği engellendi."
    return None


class QueryAnalyzer:
    """
    Analyzes SQL queries for security and performance using Abstract Syntax Trees (AST).
    All methods are strictly typed and documented.
    """

    max_joins: int
    performance_blocks: bool

    def __init__(self) -> None:
        """Initializes the QueryAnalyzer with risk thresholds."""
        from query_execution import config

        self.max_joins = config.MAX_JOINS
        self.performance_blocks = config.PERFORMANCE_BLOCKS

    def _dialect(self, technology: str) -> str:
        """Map a registered technology name onto a sqlglot dialect."""
        return _DIALECT_BY_TECHNOLOGY.get(technology.lower().strip(), "tsql")

    def analyze(self, query: str, technology: str = "mssql") -> dict[str, any]:
        """
        Analyzes SQL query and performs risk assessment using sqlglot with target database dialect.

        Args:
            query: SQL query to analyze.
            technology: Target database technology (e.g., mssql, mysql, postgresql).

        Returns:
            dict[str, any]: ``risk_type`` (str | None), ``return`` (bool), and -
            when a check has something specific to say - ``reason`` (str) and
            ``warnings`` (list[str]).
        """
        result: dict[str, any] = {"risk_type": None, "return": True}
        q: str = query.strip()
        dialect: str = self._dialect(technology)

        # Checked before parsing: sqlglot sees EXPLAIN ANALYZE as one opaque
        # command, so by the time we have an AST the wrapped statement is gone.
        explain_block = self.check_explain(q)
        if explain_block:
            result["risk_type"] = RiskLevel.BLOCKED_OPERATION.value
            result["reason"] = explain_block
            result["return"] = False
            return result

        try:
            # Parse all statements in the query using the matched dialect.
            statements = sqlglot.parse(q, read=dialect)
        except sqlglot.errors.ParseError:
            # If the SQL is malformed or uses obfuscated syntax that breaks the parser,
            # block it entirely to prevent bypasses.
            result["risk_type"] = RiskLevel.SQL_INJECTION.value
            result["reason"] = "Sorgu ayrıştırılamadı ve güvenlik gereği engellendi."
            result["return"] = False
            return result

        mixed_ddl = self._mixed_ddl_batch(statements)
        if mixed_ddl:
            result["risk_type"] = RiskLevel.BLOCKED_OPERATION.value
            result["reason"] = mixed_ddl
            result["return"] = False
            return result

        for stmt in statements:
            if not stmt:
                continue

            dangerous = self._check_dangerous_functions(stmt)
            if dangerous:
                result["risk_type"] = RiskLevel.BLOCKED_OPERATION.value
                result["reason"] = dangerous
                result["return"] = False
                return result

            if self._check_sql_injection(stmt):
                result["risk_type"] = RiskLevel.SQL_INJECTION.value
                result["return"] = False
                return result

            if self._check_ddl(stmt):
                result["risk_type"] = RiskLevel.DDL_PATTERN.value
                result["return"] = False
                return result

            if self._check_risky_dml(stmt):
                result["risk_type"] = RiskLevel.RISKY_PATTERN.value
                result["return"] = False
                return result

            if self._check_performance(stmt):
                result["risk_type"] = RiskLevel.PERFORMANCE.value
                # A performance risk is a warning by default, not a block. The
                # statement timeout and the row limit are the real protection;
                # this is a signal. Blocking here fills the approval queue with
                # ordinary reporting queries, and an approver who waves those
                # through mechanically will wave the dangerous ones through too.
                result["return"] = not self.performance_blocks
                if result["return"]:
                    result.setdefault("warnings", []).append(
                        "Sorgu ağır olabilir (çok sayıda JOIN veya baştan-sona joker)."
                    )
                else:
                    return result

        return result

    def check_explain(self, query: str) -> str | None:
        """EXPLAIN ANALYZE runs the statement it wraps - block it."""
        if _EXPLAIN_ANALYZE_RE.search(query):
            return ("EXPLAIN ANALYZE, sarılan sorguyu gerçekten çalıştırır ve "
                    "bu nedenle izin verilmiyor. Düz EXPLAIN kullanın.")
        return None

    def check_tier_consistency(self, query: str, technology: str = "mssql") -> str | None:
        """
        Reject a batch that mixes schema changes with data statements.

        Deliberately narrower than "all statements must share a tier". A
        ``SELECT`` next to an ``UPDATE`` is an ordinary unit of work: it runs on
        one connection, in one transaction, under the ``rw`` account that can
        already do both, and splitting it would cost atomicity for no gain.

        A DDL statement is different. It runs under the separate, higher
        privileged ``ddl`` account, that account is off by default, and a batch
        that changes schema and data at once gives an approver a single
        classification for two very different actions. Those go in separate
        requests.
        """
        try:
            statements = sqlglot.parse(query.strip(), read=self._dialect(technology))
        except sqlglot.errors.ParseError:
            return "Sorgu ayrıştırılamadı."
        return self._mixed_ddl_batch(statements)

    def _mixed_ddl_batch(self, statements: list[exp.Expression | None]) -> str | None:
        """Return a rejection reason when a batch mixes DDL with other tiers."""
        tiers = {self._statement_tier(stmt) for stmt in statements if stmt}
        if len(tiers) > 1 and "ddl" in tiers:
            return ("Şema değiştiren ifadeler veri sorgularıyla aynı istekte "
                    "gönderilemez. Şema değişikliğini ayrı çalıştırın.")
        return None

    def _statement_tier(self, stmt: exp.Expression) -> str:
        """Classify one statement as ``ro``, ``rw`` or ``ddl``."""
        if isinstance(stmt, _DDL_TYPES) or any(stmt.find_all(_DDL_TYPES)):
            return "ddl"
        if isinstance(stmt, exp.Select) and stmt.args.get("into"):
            return "ddl"
        if isinstance(stmt, _DML_TYPES) or any(stmt.find_all(_DML_TYPES)):
            return "rw"
        return "ro"

    def required_tier(self, query: str, technology: str = "mssql") -> str:
        """Classify a query as ``ro``, ``rw`` or ``ddl``.

        This is deliberately not an authorization decision. An unparsable
        statement receives the highest tier so a caller can safely fail closed.
        """
        try:
            statements = sqlglot.parse(query.strip(), read=self._dialect(technology))
        except sqlglot.errors.ParseError:
            return "ddl"

        tier = "ro"
        for statement in statements:
            if not statement:
                continue
            statement_tier = self._statement_tier(statement)
            if statement_tier == "ddl":
                return "ddl"
            if statement_tier == "rw":
                tier = "rw"
        return tier

    def _check_dangerous_functions(self, stmt: exp.Expression) -> str | None:
        """Return a rejection reason for a blocked function name, else None."""
        for name in _function_names(stmt):
            if name in _BLOCKED_FUNCTIONS:
                return f"'{name}' fonksiyonu güvenlik politikası gereği engellidir."

        for call in stmt.find_all(exp.Anonymous):
            fname = _anonymous_name(call)
            if fname not in _SLEEP_FUNCTIONS:
                continue
            arg = (call.expressions or [None])[0]
            seconds = None
            if isinstance(arg, exp.Literal) and arg.is_number:
                try:
                    seconds = float(arg.this)
                except ValueError:
                    seconds = None
            # Unreadable argument is blocked too - if we are not sure, no.
            if seconds is None or seconds > _MAX_SLEEP_SECONDS:
                return (f"'{fname}' çağrısı engellendi "
                        f"(en fazla {_MAX_SLEEP_SECONDS} saniye).")
        return None

    def _check_sql_injection(self, stmt: exp.Expression) -> bool:
        """Check for privilege escalation or dynamic execution."""
        for cmd in stmt.find_all(exp.Command):
            sql_upper = cmd.sql().upper()
            if any(danger in sql_upper for danger in ["EXECUTE AS", "XP_CMDSHELL", "EXEC ", "EXEC("]):
                return True
        return False

    def _check_ddl(self, stmt: exp.Expression) -> bool:
        """Check for structural changes to the database."""
        if isinstance(stmt, _DDL_TYPES):
            return True
        # Also check nested nodes
        for _ in stmt.find_all(_DDL_TYPES):
            return True
        return False

    def _check_risky_dml(self, stmt: exp.Expression) -> bool:
        """Check for UPDATE or DELETE without a WHERE clause."""
        dml_types = (exp.Delete, exp.Update)
        for node in stmt.find_all(dml_types):
            if not node.args.get("where"):
                return True
        return False

    def _check_performance(self, stmt: exp.Expression) -> bool:
        """Check for heavy joins or leading/trailing wildcards."""
        joins = list(stmt.find_all(exp.Join))

        # ``max_joins`` is the highest join count still considered ordinary, so
        # the comparison is strict: MAX_JOINS=8 allows eight and flags nine.
        if len(joins) > self.max_joins:
            return True

        for j in joins:
            if "CROSS" in j.sql().upper():
                return True

        for like in stmt.find_all(exp.Like):
            pattern = like.expression.name if hasattr(like.expression, 'name') else ""
            if pattern.startswith("%") and pattern.endswith("%"):
                return True

        return False

    def check_permissions_match_role(self, query: str, role: str, technology: str = "mssql") -> bool:
        """
        Validates if the operations in the SQL query match the user's roles (comma-separated):
        - READER: Only SELECT (read) queries are allowed. DML/DDL are blocked.
        - WRITER: SELECT, INSERT, UPDATE, DELETE are allowed. DDL are blocked.
        - ADMIN: All queries (including DDL) are allowed.

        Returns:

            bool: True if query is permitted under at least one of the roles, False otherwise.
        """
        q = query.strip()
        dialect = self._dialect(technology)
        # A query that will not parse is not a permission decision. Swallowing the
        # parse error here made every typo surface as "your role is not authorized",
        # which sends the user to their administrator instead of to their SQL.
        # The caller turns this into a syntax error; the query is still blocked.
        statements = sqlglot.parse(q, read=dialect)

        roles_list = parse(role)

        for stmt in statements:
            if not stmt:
                continue

            has_ddl = isinstance(stmt, _DDL_TYPES) or any(isinstance(node, _DDL_TYPES) for node in stmt.find_all(_DDL_TYPES))

            dml_types = (exp.Insert, exp.Update, exp.Delete)
            has_dml = isinstance(stmt, dml_types) or any(isinstance(node, dml_types) for node in stmt.find_all(dml_types))

            # Existing ADMIN associations continue to allow DDL during the
            # credential migration; the selected DB still needs a DDL account.
            if has_ddl:
                if "DDL" not in roles_list and "ADMIN" not in roles_list:
                    return False
                continue

            # DML statement requires WRITER or ADMIN.
            if has_dml:
                if "WRITER" not in roles_list and "ADMIN" not in roles_list:
                    return False
                continue

            # Read statement requires a read-capable role.
            allowed_roots = (exp.Select, exp.Union, exp.CTE, exp.Subquery)
            is_read = isinstance(stmt, allowed_roots) or any(isinstance(node, exp.Select) for node in stmt.find_all(exp.Select))
            if is_read:
                if not {"READER", "WRITER", "DDL", "ADMIN"}.intersection(roles_list):
                    return False
                continue

            # Unknown utility statements require a high-capability role.
            if "DDL" not in roles_list and "ADMIN" not in roles_list:
                return False

        return True

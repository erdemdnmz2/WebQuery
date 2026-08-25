"""
Query Analyzer
SQL query security and performance analysis via AST parsing
"""
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

class QueryAnalyzer:
    """
    Analyzes SQL queries for security and performance using Abstract Syntax Trees (AST).
    All methods are strictly typed and documented.
    """
    
    max_joins: int

    def __init__(self) -> None:
        """Initializes the QueryAnalyzer with risk thresholds."""
        self.max_joins = 3

    def analyze(self, query: str, technology: str = "mssql") -> dict[str, any]:
        """
        Analyzes SQL query and performs risk assessment using sqlglot with target database dialect.
        
        Args:
            query: SQL query to analyze.
            technology: Target database technology (e.g., mssql, mysql, postgresql).
        
        Returns:
            dict[str, any]: A dictionary containing risk_type (str | None) and return (bool).
        """
        result: dict[str, any] = {"risk_type": None, "return": True}
        q: str = query.strip()
        
        # Map technology to sqlglot dialect
        dialect_map: dict[str, str] = {
            "mssql": "tsql",
            "mysql": "mysql",
            "postgresql": "postgres",
            "postgres": "postgres"
        }
        dialect: str = dialect_map.get(technology.lower().strip(), "tsql")
        
        try:
            # Parse all statements in the query using the matched dialect.
            statements = sqlglot.parse(q, read=dialect)
        except sqlglot.errors.ParseError:
            # If the SQL is malformed or uses obfuscated syntax that breaks the parser,
            # block it entirely to prevent bypasses.
            result["risk_type"] = RiskLevel.SQL_INJECTION.value
            result["return"] = False
            return result
            
        for stmt in statements:
            if not stmt:
                continue
                
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
                result["return"] = False
                return result
                
        return result

    def _check_sql_injection(self, stmt: exp.Expression) -> bool:
        """Check for privilege escalation or dynamic execution."""
        for cmd in stmt.find_all(exp.Command):
            sql_upper = cmd.sql().upper()
            if any(danger in sql_upper for danger in ["EXECUTE AS", "XP_CMDSHELL", "EXEC ", "EXEC("]):
                return True
        return False

    def _check_ddl(self, stmt: exp.Expression) -> bool:
        """Check for structural changes to the database."""
        ddl_types = (exp.Drop, exp.Create, exp.AlterTable, exp.TruncateTable)
        if isinstance(stmt, ddl_types):
            return True
        # Also check nested nodes
        for _ in stmt.find_all(ddl_types):
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
        
        if len(joins) >= self.max_joins:
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
        dialect_map = {
            "mssql": "tsql",
            "mysql": "mysql",
            "postgresql": "postgres",
            "postgres": "postgres"
        }
        dialect = dialect_map.get(technology.lower().strip(), "tsql")
        # A query that will not parse is not a permission decision. Swallowing the
        # parse error here made every typo surface as "your role is not authorized",
        # which sends the user to their administrator instead of to their SQL.
        # The caller turns this into a syntax error; the query is still blocked.
        statements = sqlglot.parse(q, read=dialect)

        roles_list = parse(role)

        for stmt in statements:
            if not stmt:
                continue

            ddl_types = (exp.Drop, exp.Create, exp.AlterTable, exp.TruncateTable)
            has_ddl = isinstance(stmt, ddl_types) or any(isinstance(node, ddl_types) for node in stmt.find_all(ddl_types))

            dml_types = (exp.Insert, exp.Update, exp.Delete)
            has_dml = isinstance(stmt, dml_types) or any(isinstance(node, dml_types) for node in stmt.find_all(dml_types))

            # DDL statement requires ADMIN
            if has_ddl:
                if "ADMIN" not in roles_list:
                    return False
                continue

            # DML statement requires WRITER or ADMIN
            if has_dml:
                if "WRITER" not in roles_list and "ADMIN" not in roles_list:
                    return False
                continue

            # Read statement (SELECT) requires READER, WRITER, or ADMIN
            allowed_roots = (exp.Select, exp.Union, exp.CTE, exp.Subquery)
            is_read = isinstance(stmt, allowed_roots) or any(isinstance(node, exp.Select) for node in stmt.find_all(exp.Select))
            if is_read:
                if "READER" not in roles_list and "WRITER" not in roles_list and "ADMIN" not in roles_list:
                    return False
                continue

            # For any other utility statement, require at least WRITER or ADMIN to be safe
            if "WRITER" not in roles_list and "ADMIN" not in roles_list:
                return False

        return True

"""
Query Analyzer
SQL query security and performance analysis via AST parsing
"""
import sqlglot
from sqlglot import exp
from enum import Enum

class RiskLevel(Enum):
    """Query risk levels"""
    SQL_INJECTION = "sql_injection_risk"
    DDL_PATTERN = "ddl_pattern"
    RISKY_PATTERN = "risky_pattern"
    PERFORMANCE = "performance_risk"

class QueryAnalyzer:
    """
    Analyzes SQL queries for security and performance using Abstract Syntax Trees (AST)
    
    Checked risks:
        - SQL Injection / Privilege Escalation (EXECUTE AS, EXEC)
        - DDL commands (CREATE, DROP, ALTER, TRUNCATE)
        - Risky DML commands (DELETE/UPDATE without WHERE clause)
        - Performance issues (multiple JOINs, CROSS JOIN, wildcard LIKE)
    """
    
    def __init__(self):
        self.max_joins = 3

    def analyze(self, query: str):
        """
        Analyzes SQL query and performs risk assessment using sqlglot
        
        Args:
            query: SQL query to analyze
        
        Returns:
            Dict: {
                "risk_type": str | None (risk type, None if none),
                "return": bool (can query be executed?)
            }
        """
        result = {"risk_type": None, "return": True}
        q = query.strip()
        
        try:
            # Parse all statements in the query.
            # Using tsql dialect since WebQuery often interacts with MSSQL.
            statements = sqlglot.parse(q, read="tsql")
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

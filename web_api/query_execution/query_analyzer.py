"""
Query Analyzer
SQL query security and performance analysis
"""
import re
from enum import Enum

class RiskLevel(Enum):
    """Query risk levels"""
    SQL_INJECTION = "sql_injection_risk"
    DDL_PATTERN = "ddl_pattern"
    RISKY_PATTERN = "risky_pattern"
    PERFORMANCE = "performance_risk"

class QueryAnalyzer:
    """
    Analyzes SQL queries for security and performance
    
    Checked risks:
        - SQL Injection attacks
        - DDL commands (CREATE, DROP, ALTER, TRUNCATE)
        - Risky DML commands (DELETE/UPDATE without WHERE clause)
        - Performance issues (multiple JOINs, CROSS JOIN, wildcard LIKE)
    """
    
    def __init__(self):
        """Defines query patterns and compiles regexes"""
        self.sql_injection_patterns = [
            re.compile(r"'.*\s+OR\s+.*='", re.IGNORECASE),
            re.compile(r"'.*;\s*DROP\s+TABLE\s+", re.IGNORECASE),
            re.compile(r"'.*UNION\s+SELECT\s+", re.IGNORECASE),
            re.compile(r"--", re.IGNORECASE),
            re.compile(r"/\*.*\*/", re.IGNORECASE | re.DOTALL),
        ]
        self.ddl_patterns = [
            re.compile(r'\bDROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX)\s+\w+', re.IGNORECASE),
            re.compile(r'\bCREATE\s+(?:TABLE|DATABASE|SCHEMA|INDEX)\s+\w+', re.IGNORECASE),
            re.compile(r'\bALTER\s+TABLE\s+\w+\s+(?:ADD|DROP|MODIFY)', re.IGNORECASE),
            re.compile(r'\bTRUNCATE\s+TABLE\s+\w+', re.IGNORECASE),
        ]
        self.risky_patterns = [
            re.compile(r'\bDELETE\s+FROM\s+\w+\s*(?:;|$)', re.IGNORECASE),
            re.compile(r'\bUPDATE\s+\w+\s+SET\s+.*(?:;|$)', re.IGNORECASE),
            re.compile(r'\bSELECT\s+\*\s+FROM\s+\w+\s*(?:;|$)', re.IGNORECASE),
        ]
        self.performance_patterns = [
            re.compile(r'\bSELECT\s+.*\bFROM\s+\w+\s+(?:\w+\s+)?JOIN\s+.*JOIN\s+.*JOIN', re.IGNORECASE),
            re.compile(r'\bORDER\s+BY\s+\w+\s+DESC\s+LIMIT\s+\d{4,}', re.IGNORECASE),
            re.compile(r'\bLIKE\s+[\'"]%.*%[\'"]', re.IGNORECASE),
            re.compile(r'\bCROSS\s+JOIN\b', re.IGNORECASE),
        ]

    def analyze(self, query: str):
        """
        Analyzes SQL query and performs risk assessment
        
        Args:
            query: SQL query to analyze
        
        Returns:
            Dict: {
                "risk_type": str | None (risk type, None if none),
                "return": bool (can query be executed?)
            }
        
        Risk Priority Order:
            1. SQL Injection (highest risk)
            2. DDL Pattern (database structure change)
            3. Risky Pattern (DELETE/UPDATE without WHERE clause)
            4. Performance Risk (may run slow)
        
        Note:
            Returns False for the first risk found, True if no risk
        """
        result = {}
        q = query.strip()
        for pattern in self.sql_injection_patterns:
            if pattern.search(q):
                result["risk_type"] = RiskLevel.SQL_INJECTION.value
                result["return"] = False
                return result
        for pattern in self.ddl_patterns:
            if pattern.search(q):
                result["risk_type"] = RiskLevel.DDL_PATTERN.value
                result["return"] = False
                return result
        for pattern in self.risky_patterns:
            if pattern.search(q):
                result["risk_type"] = RiskLevel.RISKY_PATTERN.value
                result["return"] = False
                return result
        for pattern in self.performance_patterns:
            if pattern.search(q):
                result["risk_type"] = RiskLevel.PERFORMANCE.value
                result["return"] = False
                return result
        result["risk_type"] = None
        result["return"] = True
        return result

"""
Query Analyzer
SQL query güvenlik ve performans analizi
"""
import re
from enum import Enum

class RiskLevel(Enum):
    """Query risk seviyeleri"""
    SQL_INJECTION = "sql_injection_risk"
    DDL_PATTERN = "ddl_pattern"
    RISKY_PATTERN = "risky_pattern"
    PERFORMANCE = "performance_risk"

class QueryAnalyzer:
    """
    SQL query'lerini güvenlik ve performans açısından analiz eder
    
    Kontrol edilen riskler:
        - SQL Injection saldırıları
        - DDL komutları (CREATE, DROP, ALTER, TRUNCATE)
        - Riskli DML komutları (WHERE clause olmayan DELETE/UPDATE)
        - Performans sorunları (çoklu JOIN, CROSS JOIN, wildcard LIKE)
    """
    
    def __init__(self):
        """Query pattern'lerini tanımlar ve regex'leri derler"""
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
        SQL query'sini analiz eder ve risk değerlendirmesi yapar
        
        Args:
            query: Analiz edilecek SQL query
        
        Returns:
            Dict: {
                "risk_type": str | None (risk tipi, yoksa None),
                "return": bool (query çalıştırılabilir mi?)
            }
        
        Risk Öncelik Sırası:
            1. SQL Injection (en yüksek risk)
            2. DDL Pattern (veritabanı yapısı değişikliği)
            3. Risky Pattern (WHERE clause olmadan DELETE/UPDATE)
            4. Performance Risk (yavaş çalışabilir)
        
        Note:
            İlk bulunan risk için False döner, risk yoksa True döner
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

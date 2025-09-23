import re
from enum import Enum

class RiskLevel(Enum):
    SQL_INJECTION = "sql_injection_risk"
    DDL_PATTERN = "ddl_pattern"
    RISKY_PATTERN = "risky_pattern"
    PERFORMANCE = "performance_risk"

sql_injection_patterns = [
    re.compile(r"'.*\s+OR\s+.*='", re.IGNORECASE), # Authentication bypass saldırısını tespit eder
    re.compile(r"'.*;\s*DROP\s+TABLE\s+", re.IGNORECASE), # Tablo silme saldırısını tespit eder
    re.compile(r"'.*UNION\s+SELECT\s+", re.IGNORECASE), # Yetkisiz veri çekme saldırısını tespit eder
    re.compile(r"--", re.IGNORECASE), # SQL yorum karakteri ile bypass saldırısını tespit eder
    re.compile(r"/\*.*\*/", re.IGNORECASE | re.DOTALL), # Multi-line yorum ile filter bypass saldırısını tespit eder
]

ddl_patterns = [
    re.compile(r'\bDROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX)\s+\w+', re.IGNORECASE), # Veritabanı objelerini silme komutlarını tespit eder
    re.compile(r'\bCREATE\s+(?:TABLE|DATABASE|SCHEMA|INDEX)\s+\w+', re.IGNORECASE), # Yetkisiz obje oluşturma komutlarını tespit eder
    re.compile(r'\bALTER\s+TABLE\s+\w+\s+(?:ADD|DROP|MODIFY)', re.IGNORECASE), # Tablo yapısını değiştirme komutlarını tespit eder
    re.compile(r'\bTRUNCATE\s+TABLE\s+\w+', re.IGNORECASE), # Tablo verilerini tamamen silme
]

risky_patterns = [
    re.compile(r'\bDELETE\s+FROM\s+\w+\s*(?:;|$)', re.IGNORECASE),       # WHERE koşulu olmayan DELETE komutlarını tespit eder
    re.compile(r'\bUPDATE\s+\w+\s+SET\s+.*(?:;|$)', re.IGNORECASE),      # WHERE koşulu olmayan UPDATE komutlarını tespit eder
    re.compile(r'\bSELECT\s+\*\s+FROM\s+\w+\s*(?:;|$)', re.IGNORECASE),  # WHERE koşulu olmayan SELECT * komutlarını tespit eder
]

performance_patterns = [
    re.compile(r'\bSELECT\s+.*\bFROM\s+\w+\s+(?:\w+\s+)?JOIN\s+.*JOIN\s+.*JOIN', re.IGNORECASE), # 3 veya daha fazla JOIN içeren sorguları tespit eder
    re.compile(r'\bORDER\s+BY\s+\w+\s+DESC\s+LIMIT\s+\d{4,}', re.IGNORECASE),                    # Büyük LIMIT değerleri ile performans riskli sorguları tespit eder
    re.compile(r'\bLIKE\s+[\'"]%.*%[\'"]', re.IGNORECASE),                                        # Başında wildcard olan LIKE sorgularını tespit eder
    re.compile(r'\bCROSS\s+JOIN\b', re.IGNORECASE),                                               # Cartesian product oluşturan CROSS JOIN sorgularını tespit eder
]


def analyze_query(query : str):
    result = {}
    for pattern in sql_injection_patterns:
        if pattern.search(query.strip()):
            result["risk_type"] = RiskLevel.SQL_INJECTION.value
            result["return"] = False
            return result
    
    for pattern in ddl_patterns:
        if pattern.search(query.strip()):
            result["risk_type"] = RiskLevel.DDL_PATTERN.value
            result["return"] = False
            return result
    
    for pattern in risky_patterns:
        if pattern.search(query.strip()):
            result["risk_type"] = RiskLevel.RISKY_PATTERN.value
            result["return"] = False
            return result
    
    for pattern in performance_patterns:
        if pattern.search(query.strip()):
            result["risk_type"] = RiskLevel.PERFORMANCE.value
            result["return"] = False
            return result
        
    result["risk_type"] = None
    result["return"] = True

    return result
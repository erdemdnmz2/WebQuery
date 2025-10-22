"""
Query Execution Service Config

Konfigürasyon Parametreleri:
    MULTIPLE_QUERY_COUNT: Tek seferde çalıştırılabilecek maksimum query sayısı
    MAX_ROW_COUNT_WARNING: Bu sayıdan fazla satır dönerse warning loglanır
    MAX_ROW_COUNT_LIMIT: Response'da döndürülecek maksimum satır sayısı
    RATE_LIMITER: Query endpoint'leri için rate limit (örn: "10/minute")
"""
import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

MULTIPLE_QUERY_COUNT = int(os.getenv("MULTIPLE_QUERY_COUNT", "10"))
MAX_ROW_COUNT_WARNING = int(os.getenv("MAX_ROW_COUNT_WARNING", "10000"))
MAX_ROW_COUNT_LIMIT = int(os.getenv("MAX_ROW_COUNT_LIMIT", "1000"))
RATE_LIMITER = os.getenv("QUERY_RATE_LIMITER", "10/minute")

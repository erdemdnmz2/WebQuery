"""
Query Execution Service Config

Konfigürasyon Parametreleri:
    MAX_ROW_COUNT_WARNING: Bu sayıdan fazla satır dönerse warning loglanır
    MAX_ROW_COUNT_LIMIT: Response'da döndürülecek maksimum satır sayısı
    RATE_LIMITER: Query endpoint'leri için rate limit (örn: "10/minute")
    MAX_JOINS: Olağan sayılan en yüksek JOIN sayısı; üstü performans riski
    PERFORMANCE_BLOCKS: Performans riski sorguyu engellesin mi (varsayılan: hayır)
"""
import os

from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

MAX_ROW_COUNT_WARNING = int(os.getenv("MAX_ROW_COUNT_WARNING", "10000"))
MAX_ROW_COUNT_LIMIT = int(os.getenv("MAX_ROW_COUNT_LIMIT", "1000"))
RATE_LIMITER = os.getenv("QUERY_RATE_LIMITER", "10/minute")

# Bir raporlama sorgusu kolaylıkla dört beş tabloya dokunur. Eşik dar
# tutulduğunda onay kuyruğu sıradan sorgularla dolar ve onaylayan
# mekanikleşir; onay kuyruğunun kalitesi bir güvenlik özelliğidir.
MAX_JOINS = int(os.getenv("MAX_JOINS", "8"))

# Performans riski varsayılan olarak yalnız uyarıdır. Gerçek koruma sorgu
# zaman aşımı ve satır sınırıdır.
PERFORMANCE_BLOCKS = os.getenv("PERFORMANCE_BLOCKS", "false").lower() == "true"

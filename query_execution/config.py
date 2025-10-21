"""
Query Execution Service Config
"""
import os

MULTIPLE_QUERY_COUNT = int(os.getenv("MULTIPLE_QUERY_COUNT", "10"))
MAX_ROW_COUNT_WARNING = int(os.getenv("MAX_ROW_COUNT_WARNING", "10000"))
MAX_ROW_COUNT_LIMIT = int(os.getenv("MAX_ROW_COUNT_LIMIT", "1000"))

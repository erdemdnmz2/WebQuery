"""
Query Execution Service Config

Configuration parameters:
    MAX_ROW_COUNT_WARNING: Log a warning when more rows are returned
    MAX_ROW_COUNT_LIMIT: Maximum number of rows returned in the response
    RATE_LIMITER: Rate limit for query endpoints (for example, "10/minute")
    MAX_JOINS: Highest normal JOIN count; above this is a performance risk
    PERFORMANCE_BLOCKS: Whether to block queries with performance risks (default: no)
"""
import os

from dotenv import load_dotenv

# Load the .env file.
load_dotenv()

MAX_ROW_COUNT_WARNING = int(os.getenv("MAX_ROW_COUNT_WARNING", "10000"))
MAX_ROW_COUNT_LIMIT = int(os.getenv("MAX_ROW_COUNT_LIMIT", "1000"))
RATE_LIMITER = os.getenv("QUERY_RATE_LIMITER", "10/minute")

# A reporting query can easily touch four or five tables. If the threshold is
# too narrow, the approval queue fills with ordinary queries and reviewers
# become mechanical; approval queue quality is a security property.
MAX_JOINS = int(os.getenv("MAX_JOINS", "8"))

# Performance risk is a warning by default. The real safeguards are the query
# timeout and row limit.
PERFORMANCE_BLOCKS = os.getenv("PERFORMANCE_BLOCKS", "false").lower() == "true"

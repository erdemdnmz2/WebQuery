"""
Database Provider Configuration
Erişilebilir SQL Server instance listesi
"""
import os
from typing import List

# Environment'tan virgülle ayrılmış server listesi al, yoksa default kullan
_server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]

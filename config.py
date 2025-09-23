# Database configs

SERVER_NAMES = [
    ""
]

DATABASE_URL = (
    "mssql+aioodbc://localhost/dba_application_db"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

ADMIN_DATABASE_URL = (
    "mssql+aioodbc://localhost/AdventureWorks2022"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

#Authentication config

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2880 #token süresi
COOKIE_TOKEN_EXPIRE_MINUTES = 172800 # çerez süresi
SESSION_TIMEOUT = 7200

# Email config

SMTP_HOST = "smtp.gmail.com"  # Gmail SMTP sunucu adresi
SMTP_PORT = 587  # Gmail SMTP port numarası (TLS için standart)
SMTP_USER = ""  # Gönderici email adresi
SMTP_PASSWORD = ""  # Gmail hesabı şifresi (App Password önerilir)
SMTP_TLS = True  # TLS şifreleme kullan (güvenlik için)
SMTP_SSL = False  

ADMIN_EMAIL = ""

SLACK_URL = ""

DANGEROUS_SQL_KEYWORDS = [
    'drop', 'truncate', 'alter', 'create', 'rename', 
    'insert', 'update', 'delete', 'merge',
    'grant', 'revoke', 'deny',
    'shutdown', 'reconfigure', 'exec', 'execute',
    'xp_cmdshell', 'sp_configure', 'sp_addlogin', 'sp_addsrvrolemember'
]

message_format = """
Hello,

The result of your SQL query below:

Database: {database_name}
User: {username}
Date: {execution_time}

Query:
{query}

Result:
- Total record count: {total_rows}

Best regards,
DBA Application
"""

approval_message_format = """
*New SQL Query Approval Request*

*User:* {username}
*Date:* {request_time}
*Database:* {database_name}
*Machine Name:* {servername}
*Risk type:* {risk_type}

*Query:*
```{query}```

Please approve or reject the execution of this query.
"""

#Rate limiter configs

RATE_LIMITER = '3/minute'

#Multiple query count

MULTIPLE_QUERY_COUNT = 2
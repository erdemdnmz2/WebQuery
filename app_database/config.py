import os

DATABASE_URL = os.getenv(
    "APP_DATABASE_URL",
    (
        "mssql+aioodbc://localhost/dba_application_db"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&trusted_connection=yes"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
)
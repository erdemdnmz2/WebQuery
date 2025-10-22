import os

db_user = os.getenv("DB_USER", "sa")
db_password = os.getenv("DB_PASSWORD", "")

DATABASE_URL = os.getenv(
    "APP_DATABASE_URL",
    (
        f"mssql+aioodbc://{db_user}:{db_password}@localhost/dba_application_db"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
)
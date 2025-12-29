import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import create_engine, text, make_url
from app_database.config import DATABASE_URL
from app_database.models import Base
import os

def create_database_and_user_if_not_exists():
    """
    Checks if the target database exists and creates it if not.
    Also handles custom user creation if DB_USER is not 'sa'.
    Uses a synchronous SQLAlchemy engine with AUTOCOMMIT isolation level.
    """
    print("Checking database and user configuration...")
    try:
        # Parse the configured URL (which might use a custom user)
        url = make_url(DATABASE_URL)
        target_db = url.database
        target_user = url.username
        target_password = url.password
        host = url.host
        
        # We need to connect as 'sa' to create DBs and Users.
        # We assume the password provided in env is the SA password 
        # (since docker-compose sets MSSQL_SA_PASSWORD=${DB_PASSWORD})
        sa_url = url.set(
            username='sa', 
            password=target_password, 
            database='master', 
            drivername='mssql+pyodbc'
        )
        
        # Create engine with AUTOCOMMIT (required for CREATE DATABASE)
        engine = create_engine(sa_url, echo=True, isolation_level="AUTOCOMMIT")
        
        with engine.connect() as conn:
            # 1. Create Database if not exists
            result = conn.execute(text(f"SELECT 1 FROM sys.databases WHERE name = '{target_db}'"))
            if not result.scalar():
                print(f"Database '{target_db}' does not exist. Creating...")
                conn.execute(text(f"CREATE DATABASE {target_db}"))
                print(f"Database '{target_db}' created successfully.")
            else:
                print(f"Database '{target_db}' already exists.")

            # 2. Create User if not 'sa'
            if target_user and target_user.lower() != 'sa':
                print(f"Checking configuration for user '{target_user}'...")
                
                # Check if Login exists
                login_check = conn.execute(text(f"SELECT 1 FROM sys.server_principals WHERE name = '{target_user}'"))
                if not login_check.scalar():
                    print(f"Login '{target_user}' does not exist. Creating...")
                    # Create Login
                    conn.execute(text(f"CREATE LOGIN {target_user} WITH PASSWORD = '{target_password}'"))
                    print(f"Login '{target_user}' created.")
                
                # Switch to target database to create User and assign roles
                conn.execute(text(f"USE {target_db}"))
                
                # Check if User exists in DB
                user_check = conn.execute(text(f"SELECT 1 FROM sys.database_principals WHERE name = '{target_user}'"))
                if not user_check.scalar():
                    print(f"User '{target_user}' does not exist in database '{target_db}'. Creating...")
                    conn.execute(text(f"CREATE USER {target_user} FOR LOGIN {target_user}"))
                    conn.execute(text(f"ALTER ROLE db_owner ADD MEMBER {target_user}"))
                    print(f"User '{target_user}' created and added to db_owner role.")
                else:
                    print(f"User '{target_user}' already exists in database.")

        engine.dispose()
    except Exception as e:
        print(f"Warning: Could not check/create database or user: {e}")
        print("Proceeding to table creation (this might fail if user/db doesn't exist)...")

async def init_models():
    # First ensure the database and user exist
    create_database_and_user_if_not_exists()

    print("Creating database tables...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_models())

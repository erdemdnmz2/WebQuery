from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from typing import Dict
import models
import config
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError

# user_id, servername(database_name, Engine)

# mysql+mysqlconnector://<username>:<password>@<server>:<port>/dbname this is for mysql
#                  (user_id,(servername, dict(database, engine)))
engine_cache: Dict[int, Dict[str, Dict[str, AsyncEngine]]] = {} # ask here: do users connect with different username/password or the same? engine cache or connection pool depends on this
all_db_names: list[str] = []
db_info: Dict[str, list[str]] = {}

session_cache: Dict[int, Dict] = {}
# create an environment file or config

conn_string = (
    "mssql+aioodbc://{username}:{password}@{servername}/{database}" ## {servername}
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&TrustServerCertificate=yes"
    )

# mandatory databases to connect for user management, logging will be added later

DATABASE_URL = (
    "mssql+aioodbc://localhost/dba_application_db"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

app_engine = create_async_engine(
    config.DATABASE_URL,
    pool_size=20,          # For CRUD operations
    max_overflow=30,       # For peak times
    pool_timeout=20,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={"timeout": 30, "autocommit": True}
)

AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=app_engine)

@asynccontextmanager
async def get_app_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# for external engines that users want to connect to
# can this be written in a single function?
    
def create_conn_string(username, password,servername ,database_name):
    return conn_string.format(
        username = username,
        password = password,
        servername=servername,
        database = database_name
    )

async def test_user_connection(username, password, servername):
    conn_str1 = conn_string.format(
        username = username,
        password = password,
        servername = servername,
        database = "master"
    )
    engine = create_async_engine(
        conn_str1,
        pool_size = 1,
        max_overflow = 1        
    )
    try:
        async with engine.connect() as conn:
            pass
        return True
    except SQLAlchemyError as e:
        #print(f"Error: {e}")
        return False
    finally:
        await engine.dispose()
        engine = None

async def init_engine_cache():
    global engine_cache
    engine_cache = {}

async def get_db_info():
    global db_info
    db_info = {} 
    
    for server in config.SERVER_NAMES: 
        try:
            master_conn_str = (
                f"mssql+aioodbc://{server}/master"
                "?driver=ODBC+Driver+18+for+SQL+Server"
                "&trusted_connection=yes"
                "&TrustServerCertificate=yes"
            )
            temp_engine = create_async_engine(master_conn_str)

            async with temp_engine.connect() as connection:
                results = await connection.execute(text("SELECT name FROM sys.databases"))
                db_names = results.scalars().all()
                db_names = db_names[4:]
                db_info[server] = list(db_names)
                print(f"{server}: {len(db_names)} databases found - {db_names}")

            await temp_engine.dispose()
            temp_engine = None
            
        except Exception as e:
            print(f"Could not connect to {server}: {str(e)}")
            db_info[server] = [] 
            
    print(f"Final db_info after processing: {db_info}")
    return db_info

# (user_id,(servername, dict(database, engine)))
def get_db_info_by_user_id(user_id: int):
    user_dict = engine_cache[user_id]
    response = {}
    for servername, databases in user_dict.items():
        response[servername] = list(databases.keys())
    return response

def get_engine(user_id: int, server_name: str, database_name: str) -> AsyncEngine:
    return engine_cache[user_id][server_name][database_name]

async def get_servername(user: models.User, database_name):
    try:
        engine = get_engine(user_id=user.id, database_name=database_name)
        if engine:
            async with get_session(user, database_name) as session:
                result = await session.execute(text("SELECT @@SERVERNAME"))
                server_name = result.fetchone()
                if server_name:
                    return server_name[0]
                else:
                    return "Server Not Found"
        else:
            return "Connection Error"
    except Exception as e:
        return "Server Not Found"

@asynccontextmanager
async def get_session(user: models.User, server_name: str, database_name: str):
    if engine_cache[user.id][server_name][database_name] is None:
        conn_str = create_conn_string(
            username=user.username, 
            password=user.password, 
            servername=server_name,
            database_name=database_name
        )
        engine_cache[user.id][server_name][database_name] = create_async_engine(
            conn_str,
            pool_size=1,
            max_overflow=1,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={"timeout": 30, "autocommit": True}
        )
    
    engine = engine_cache[user.id][server_name][database_name]
    AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 
    
async def add_user_to_cache(user_id: int, username: str, password: str):
    engine_cache[user_id] = {}
    for server_name, databases in db_info.items():

        if not await test_user_connection(username=username, password=password, servername=server_name):
            continue
        engine_cache[user_id][server_name] = {}
        for db_name in databases:
            conn_str = create_conn_string(username, password, server_name, db_name)
            engine_cache[user_id][server_name][db_name] = create_async_engine(
                conn_str,
                pool_size=1,
                max_overflow=1,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                connect_args={"timeout": 30, "autocommit": True}
            )

async def close_engines():
    for user_id in engine_cache.keys():
        for server_name in engine_cache[user_id].keys():
            for database_name in engine_cache[user_id][server_name].keys():
                engine = engine_cache[user_id][server_name][database_name]
                if engine is not None:
                    await engine.dispose()
                    engine_cache[user_id][server_name][database_name] = None
    await app_engine.dispose()

async def close_user_engines(user_id: int):
    if user_id in engine_cache:
        for server_name in engine_cache[user_id]:
            for db_name in engine_cache[user_id][server_name]:
                engine = engine_cache[user_id][server_name][db_name]
                if engine is not None:
                    await engine.dispose()
        engine_cache.pop(user_id, None)

def get_db_info_db():
    return db_info

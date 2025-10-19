from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from typing import Dict
import models as models
from database_provider.config import SERVER_NAMES
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from sqlalchemy.exc import SQLAlchemyError

class DatabaseProvider:
    def __init__(self):
        self.engine_cache: Dict[int, Dict[str, Dict[str, AsyncEngine]]] = {}
        self.db_info: Dict[str, list[str]] = {} 
        
        self.connection_string = (
            "mssql+aioodbc://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            )
        
        self._get_db_info()

        
    def _create_connection_string(self, username: str, password: str, database: str, server: str):
        return self.connection_string.format(
        username = username,
        password = password,
        servername=server,
        database = database
    )

    def get_db_info_by_user_id(self, user_id: int):
        user_dict = self.engine_cache[user_id]
        response = {}
        for servername, databases in user_dict.items():
            response[servername] = list(databases.keys())
        return response
    
    #TODO init e ekle
    async def get_db_info(self):
        
        for server in SERVER_NAMES: 
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
                    self.db_info[server] = list(db_names)
                    print(f"{server}: {len(db_names)} databases found - {db_names}")

                await temp_engine.dispose()
                temp_engine = None
                
            except Exception as e:
                print(f"Could not connect to {server}: {str(e)}")
                self.db_info[server] = [] 
                
        print(f"Final db_info after processing: {self.db_info}")
    
    @asynccontextmanager
    async def get_session(self, user: models.User, server_name: str, database_name: str):
        engine = self.engine_cache[user.id][server_name][database_name]
        if engine is None:
            conn_str = self._create_connection_string(
                username=user.username, 
                password=user.password, 
                servername=server_name,
                database_name=database_name
            )
            engine = self.engine_cache[user.id][server_name][database_name] = create_async_engine(
                conn_str,
                pool_size=1,
                max_overflow=1,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                connect_args={"timeout": 30, "autocommit": True}
            )
        #Session erişimi optimize edildi zincirleme değişken metoduyla
        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close_engines(self):
        for user_id in self.engine_cache.keys():
            for server_name in self.engine_cache[user_id].keys():
                for database_name in self.engine_cache[user_id][server_name].keys():
                    engine = self.engine_cache[user_id][server_name][database_name]
                    if engine is not None:
                        await engine.dispose()
                        self.engine_cache[user_id][server_name][database_name] = None

    async def close_user_engines(self,user_id: int):
        if user_id in self.engine_cache:
            for server_name in self.engine_cache[user_id]:
                for db_name in self.engine_cache[user_id][server_name]:
                    engine = self.engine_cache[user_id][server_name][db_name]
                    if engine is not None:
                        await engine.dispose()
            self.engine_cache.pop(user_id, None) 

    async def add_user_to_cache(self, user_id: int, username: str, password: str):
        self.engine_cache[user_id] = {}
        for server_name, databases in self.db_info.items():
            self.engine_cache[user_id][server_name] = {}
            for db_name in databases:
                conn_str = self.create_conn_string(username, password, server_name, db_name)
                self.engine_cache[user_id][server_name][db_name] = create_async_engine(
                    conn_str,
                    pool_size=1,
                    max_overflow=1,
                    pool_timeout=30,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                    connect_args={"timeout": 30, "autocommit": True}
                )
    
    def get_db_info(self):
        return self.db_info
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app_database.config import DATABASE_URL
from app_database.models import Base

async def init_models():
    print("Creating database tables...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_models())

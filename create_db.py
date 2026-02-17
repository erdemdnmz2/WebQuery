import asyncio
from app_database import AppDatabase
from app_database.models import Base

async def init_db():
    print("Initializing database...")
    try:
        # AppDatabase'i başlat (engine'i oluşturur)
        db = AppDatabase()
        
        # Tabloları oluştur (Base.metadata kullanarak)
        # Direkt metadata üzerinden create_all işlemini yapıyoruz
        async with db.app_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        print("Database tables created successfully!")
        
        # Engine'i kapat
        await db.app_engine.dispose()
        
    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(init_db())

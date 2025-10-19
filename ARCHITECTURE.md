# WebQuery - Yeni Modüler Mimari Kullanım Kılavuzu

## 📁 Proje Yapısı

```
WebQuery/
├── app_new.py              # Ana uygulama (router'ları toplar)
├── dependencies.py         # Ortak dependency fonksiyonları
├── app_database/           # Uygulama veritabanı (User, Workspace, Log)
│   ├── app_database.py     # AppDatabase sınıfı
│   ├── models.py
│   ├── schemas.py
│   └── config.py
├── database_provider/      # Kullanıcıya özel DB bağlantıları
│   ├── database.py         # DatabaseProvider sınıfı
│   ├── models.py
│   └── config.py
├── authentication/         # Kimlik doğrulama modülü
│   ├── router.py
│   ├── services.py
│   └── schemas.py
├── query_execution/        # Sorgu çalıştırma modülü
│   ├── router.py
│   ├── services.py
│   └── models.py
├── auth.py                 # JWT ve token yönetimi
├── middlewares.py          # Auth middleware
└── config.py               # Global config
```

## 🚀 Nasıl Çalışır?

### 1. Uygulama Başlatma (`app_new.py`)

```python
# Lifespan sırasında tek bir kez oluşturulur:
app.state.app_db = AppDatabase()              # Uygulama DB
app.state.db_provider = DatabaseProvider()    # Kullanıcı DB'leri
await app.state.db_provider.get_db_info()     # DB listesi yüklenir
```

### 2. Dependency Injection (`dependencies.py`)

Tüm router'lar bu fonksiyonları kullanır:

```python
from dependencies import get_app_db, get_db_provider, get_session_cache, get_fernet
```

### 3. Router'larda Kullanım

#### Authentication Router Örneği

```python
from fastapi import APIRouter, Depends
from dependencies import get_app_db, get_db_provider, get_session_cache, get_fernet
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider

router = APIRouter(prefix="/api/auth")

@router.post("/login")
async def login(
    user: LoginSchema,
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider),
    session_cache: dict = Depends(get_session_cache),
    fernet: Fernet = Depends(get_fernet)
):
    # 1. Kullanıcı doğrulama (app_db)
    async with app_db.get_app_db() as db:
        authenticated_user = await authenticate(db, user.email, user.password)
    
    # 2. Session cache'e şifreyi şifreli kaydet
    session_cache[user_id] = {
        "user_password": fernet.encrypt(user.password.encode()),
        "addition_date": datetime.now()
    }
    
    # 3. DatabaseProvider cache'i ısıt
    await db_provider.add_user_to_cache(user_id, username, password)
    
    return {"token": token}
```

#### Query Execution Router Örneği

```python
@router.post("/execute")
async def execute_query(
    query_request: QuerySchema,
    current_user = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider),
    session_cache: dict = Depends(get_session_cache),
    fernet: Fernet = Depends(get_fernet)
):
    # 1. Session'dan şifreyi al
    encoded_pw = session_cache[current_user.id]["user_password"]
    current_user.password = fernet.decrypt(encoded_pw).decode()
    
    # 2. Log oluştur (app_db)
    log = await app_db.create_log(current_user, query, machine_name)
    
    # 3. Sorgu çalıştır (db_provider)
    async with db_provider.get_session(
        current_user,
        query_request.servername,
        query_request.database_name
    ) as session:
        result = await session.execute(text(query))
        rows = result.fetchall()
    
    # 4. Log güncelle
    await app_db.update_log(log.id, successfull=True, row_count=len(rows))
    
    return {"data": rows}
```

## 📋 Sorumluluklar

### AppDatabase
- Kullanıcı kayıt/giriş
- Workspace yönetimi
- Log tutma (action, login)
- Tek bir engine ile uygulama DB'sine bağlanır

### DatabaseProvider
- Kullanıcıya özel engine cache yönetimi
- Hedef sunucu ve DB listesi (`db_info`)
- `get_session()`: Kullanıcı kimliğiyle hedef DB'ye session açar
- `add_user_to_cache()`: Login sonrası engine'leri oluşturur
- `close_user_engines()`: Logout sonrası temizlik

### Session Cache
- Kullanıcının plaintext DB şifresini **şifreli** saklar
- Login'de doldurulur
- Query sırasında decrypt edilir
- Logout'ta temizlenir

## 🔑 Önemli Notlar

1. **Tek Instance**: `app.state` üzerinden her yerde aynı instance kullanılır
2. **Engine Cache**: DatabaseProvider içinde kullanıcı bazlı tutulur
3. **Session Cache**: Şifreler Fernet ile şifrelenir
4. **Login Akışı**: 
   - Kullanıcı doğrula → Session cache'e ekle → Engine cache ısıt
5. **Query Akışı**:
   - Session'dan şifre al → Log oluştur → Sorgu çalıştır → Log güncelle
6. **Logout Akışı**:
   - Cookie sil → Logout log → Engine'leri kapat → Session temizle

## 🛠️ Yeni Router Ekleme

1. Yeni klasör oluştur (ör. `workspace/`)
2. İçine `router.py`, `services.py`, `schemas.py` ekle
3. `router.py` içinde dependency'leri kullan:
   ```python
   from dependencies import get_app_db, get_db_provider
   ```
4. `app_new.py`'de include et:
   ```python
   from workspace.router import router as workspace_router
   app.include_router(workspace_router, tags=["Workspace"])
   ```

## 🚀 Çalıştırma

```bash
python app_new.py
```

veya

```bash
uvicorn app_new:app --reload
```

## ✅ Avantajlar

- ✅ Temiz sorumluluk ayrımı
- ✅ Test edilebilir (dependency injection)
- ✅ Tek engine cache, kaynak verimliliği
- ✅ Modüler yapı, kolay genişletme
- ✅ Type-safe (AppDatabase, DatabaseProvider tipleri)

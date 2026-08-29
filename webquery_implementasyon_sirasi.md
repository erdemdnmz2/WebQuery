# WebQuery — Uygulama Sırası

**Tarih:** 2026-08-21
**Kaynak:** `webquery_iyilestirme_plani.md` — aynı içerik, bağımlılık sırasına dizilmiş
**Yaklaşım:** Her adım → *neden burada → açtığı kapı → problem → tam kod → doğrulama → efor*

---

## Nasıl okunmalı

Bu belge ana planın **yeniden sıralanmış** hâli. İçerik birebir aynı — problem
açıklamaları, kod blokları, testler, hiçbiri kısaltılmadı. Değişen tek şey sıra.

**Neden yeniden sıralandı:** ana plan konuya göre düzenliydi (fazlar), bağımlılığa
göre değil. Üç yerde sıra fiilen bozuktu:

| Madde | Ana planda | Gerçekte |
|---|---|---|
| `4.1` Alembic | Faz 4 | **Her şeyden önce** — `1.2`, `2.1`, `3.1` buna bağlı |
| `4.4` `roles.py` | Faz 4 | **`3.1`'den önce** — yoksa `max_tier` ikinci kez yazılır |
| `3.3` sqlglot | `3.2`'den sonra | **`3.2`'den önce** — yoksa yeni testler toptan kırılır |

**Madde numaraları korundu.** `3.1` burada da `3.1`; metin içindeki çapraz atıflar
(*"bkz. 1.3'teki Karar 3"*) aynen çalışıyor. Adım numaraları (**Adım 1**, **Adım 2**…)
yürütme sırasını, madde numaraları konuyu gösteriyor. Gövde metinlerinde geçen
*"Faz 3"* gibi ifadeler ana plandaki konu gruplarına atıftır.

Her blok bir **geçiş kontrolü** ile bitiyor. O kontrol geçmeden sonraki bloğa
başlamayın — bloğun tüm anlamı, sonrakinin üzerine kurulacağı zemini garanti etmek.

---

## Bağımlılık haritası

```
                        ┌──────────────┐
                        │ 4.1 Alembic  │  ← her şey buna bağlı
                        └──────┬───────┘
             ┌─────────────────┼─────────────────┬──────────────┐
             ▼                 ▼                 ▼              ▼
       ┌──────────┐      ┌──────────┐      ┌──────────┐   ┌──────────┐
       │ 0.5      │      │ 1.1      │      │ 2.1  2.3 │   │ 3.1      │
       │ blacklist│      │ AuditLog │      │ kimlik   │   │ kademe   │
       └──────────┘      └────┬─────┘      └──────────┘   └────┬─────┘
                              ▼                                 │
                       ┌─────────────┐                          │
                       │ 1.2  +  1.3 │  ← ayrılamaz             │
                       └─────────────┘                          │
                                                                │
  ┌──────────────┐                                              │
  │ 0.1 config   │──────────────────────────────────────────────┤
  │ _guard       │   (Fernet anahtarı + CONFIRMATION_SECRET)    │
  └──────┬───────┘                                              │
         ▼                                                      │
  ┌──────────────┐    ┌──────────────┐                          │
  │ 0.4 sa       │    │ 4.4 roles.py │──────────────────────────┤
  └──────────────┘    └──────────────┘                          │
                                                    ┌───────────┴───────────┐
                                                    ▼                       ▼
                                              ┌──────────┐            ┌──────────┐
                                              │ 4.5 ölü  │            │ 3.3 →    │
                                              │ kod      │            │ 3.2 →    │
                                              └──────────┘            │ 3.4      │
                                                                      └──────────┘
```

Hiçbir şeye bağlı olmayanlar (istediğiniz yerde, paralel): `0.2`, `0.3`, `2.2`,
`2.4`, `4.3`, `4.6`

---

## Blokların özeti

| Blok | İçerik | Süre | Atlanabilir mi |
|---|---|---|---|
| **0** — Zemin | `4.1` `4.2` `0.1` `0.4` | ~1,5 gün | **Hayır** |
| **1** — Kanama durdurma | `0.2` `0.3` `0.5` | ~6 saat | Hayır (üçü de 🔴) |
| **2** — Denetlenebilirlik | `4.4` `1.1` `1.2` `1.3` | ~2,5 gün | Hayır (`1.3` 🔴) |
| **3** — Kimlik | `2.1` `2.2` `2.4` `2.3` | ~3 gün | **Evet** — ertelenebilir |
| **4** — Savunma derinliği | `3.1` `4.5` `3.3` `3.2` | ~2,5 gün | Hayır — asıl getiri |
| **5** — Cila | `4.3` `4.6` | ~1 gün | Evet |

**Toplam ≈ 11 iş günü kod**, gözden geçirme ve dağıtım payıyla ~14 gün.
Blok 3 ertelenirse Blok 4'ün sonuna kadar ≈ 8 iş günü.

---

# Blok 0 — Zemin

**Süre:** ~1,5 gün

**Hiçbir şey başlamadan önce.** Dört madde, toplam ~1,5 gün, ve sonrasındaki her
maddenin doğru çalışmasının şartı. Bu bloğu atlayıp Blok 4'e geçemezsiniz — `3.1`
buradaki üç maddeye birden bağlı.

## Adım 1 · `4.1` — Alembic'e geçin ⭐

**Neden burada — her şeyden önce:** Blok 2'den itibaren **var olan tablolara yeni
kolon** ekleniyor: `QueryData`'ya üç kolon, `User`'a `is_active`, `Databases`'e altı
kimlik kolonu. `create_all()` var olan bir tabloya kolon **eklemez** — ve hata da
vermez, sessizce atlar. Alembic yoksa sonraki maddelerin yarısı yazıldığı gibi
görünüp çalışmaz; ilk yazma denemesinde patlar.

**Açtığı kapı:** `0.5`, `1.1`, `1.2`, `2.1`, `2.3`, `3.1` — yani gerçek işin tamamı.

### Problem

```python
await app.state.app_db.create_tables()   # SQLAlchemy create_all()
```

Bu **sadece olmayan tabloyu yaratır**. Var olan tabloya kolon eklemez. Yani Faz 1-3'te eklediğiniz her kolon (`AuditLog`, `User.is_active`, `UserSession`, `Databases.username_ro`, `QueryData.decision_reason`) **production'da oluşmayacak** ve uygulama ilk sorguda `Invalid column name` ile patlayacak.

**Bu yüzden Alembic, Faz 1'e başlamadan önce kurulmalı.** Sıralamada Faz 4'te ama zamanlamada önce.

### Çözüm

```bash
pip install alembic
cd web_api
alembic init migrations
```

`alembic.ini`:
```ini
# Bağlantı dizesi env'den okunur — sırlar dosyada durmaz
sqlalchemy.url =
```

`migrations/env.py`:
```python
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.getenv("ENV_FILE", ".env"))

from app_database.models import Base
target_metadata = Base.metadata

config = context.config

# Async URL'i sync sürücüye çevir — Alembic senkron çalışır.
url = os.environ["APP_DATABASE_URL"]
url = (url.replace("+aioodbc", "+pyodbc")
          .replace("+asyncpg", "+psycopg2")
          .replace("+aiomysql", "+pymysql")
          .replace("+aiosqlite", ""))
config.set_main_option("sqlalchemy.url", url)

if config.config_file_name:
    fileConfig(config.config_file_name)


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,              # tip değişikliklerini de yakala
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

**Mevcut şemayı baseline alın** (bu adım kritik — yoksa Alembic var olan tabloları yeniden yaratmaya çalışır):

```bash
# 1. Mevcut modellerden ilk revizyonu üret
alembic revision --autogenerate -m "baseline: mevcut sema"

# 2. Üretilen dosyayı GÖZDEN GEÇİRİN — autogenerate mükemmel değildir

# 3. Var olan veritabanını "bu revizyon uygulanmış" diye işaretleyin
alembic stamp head
```

Sonra her model değişikliği için:
```bash
alembic revision --autogenerate -m "audit log tablosu ekle"
alembic upgrade head
```

`app.py`'dan `create_tables()` çağrısını **kaldırın**:

```python
    try:
        app.state.app_db = AppDatabase()
        async with app.state.app_db.app_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✓ AppDatabase connection successful")
        # await app.state.app_db.create_tables()   ← KALDIRILDI
        # Şema Alembic ile yönetilir: `alembic upgrade head`
        # Uygulamanın şema değiştirmesi, iki instance aynı anda açıldığında
        # yarış üretir ve geri alınabilir değildir.
    except Exception as e:
        ...
```

`entrypoint.sh`'a ekleyin:
```bash
#!/bin/sh
set -e
echo "Migration'lar uygulanıyor..."
alembic upgrade head
echo "Uygulama başlatılıyor..."
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}"
```

**Efor:** ~4 saat.

## Adım 2 · `4.2` — CI kurun

**Neden burada:** Bundan sonraki on beş maddenin her biri test yazıyor. CI en sona
bırakılırsa o testler yazıldıkları gün dışında hiç çalışmaz ve üç hafta sonra
hangisinin bozulduğunu bilemezsiniz.

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push: { branches: [main, master] }
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Bağımlılıklar
        run: |
          pip install -r web_api/requirements.txt
          pip install pytest-cov ruff

      - name: Lint
        run: ruff check web_api/

      - name: Testler
        working-directory: web_api
        env:
          # CI için gerçek ama tek kullanımlık sırlar — kodda varsayılan YOK
          SECRET_KEY: ci-test-key-for-github-actions-only-not-production
          QUERY_ENCRYPTION_KEY: ${{ secrets.CI_FERNET_KEY }}
          APP_DATABASE_URL: sqlite+aiosqlite:///./test.db
          CENTRAL_DB_USER: ci_user
          CENTRAL_DB_PASSWORD: ci_pass
        run: pytest -v --cov=. --cov-report=term-missing

      - name: Sır sızıntısı taraması
        run: |
          # Kodda kalmış bağlantı dizesi / anahtar var mı?
          ! grep -rn --include='*.py' \
              -E "(password|secret|api_key)\s*=\s*['\"][^'\"]{8,}" web_api/ \
            || (echo "Kodda gömülü sır bulundu" && exit 1)
```

**Efor:** ~2 saat.

## Adım 3 · `0.1` — Sessiz fail-open sırları kapat

**Neden burada:** İki sebep. Birincisi acil — `SECRET_KEY` bilinen bir değerse herkes
geçerli JWT üretebilir. İkincisi sıralama: `3.1` hedef veritabanı şifrelerini
`EncryptedText` ile saklayacak; Fernet anahtarı hâlâ fail-open ise o şifreler
**repo'yu gören herkesin açabildiği** bir anahtarla şifrelenir. "Şifreli" görünür,
değildir.

> `3.4`'ü uygulayacaksanız `CONFIRMATION_SECRET`'i **bu adımda** zorunlu sırlar
> listesine ekleyin. Sonradan eklemeyi hatırlamak zorunda kalmayın.

**Açtığı kapı:** `0.4`, `3.1`, `3.4`

### Problem

İki yerde, env değişkeni yoksa uygulama **kaynak kodda yazan bir sırla** çalışmaya devam ediyor:

```python
# app_database/models.py:51-55
key = os.getenv("QUERY_ENCRYPTION_KEY")
if not key:
    key = base64.urlsafe_b64encode(b"thirty-two-bytes-consistent-key!")

# authentication/config.py:9
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
```

### Neden önemli

Birincisi: `.env` dosyası unutulursa/bozuksa audit log'daki tüm sorgu metinleri **repo'yu gören herkesin açabildiği** bir anahtarla şifrelenir. "Şifreli" görünür, değildir.

İkincisi daha kötü: `SECRET_KEY` bilinen bir değerse **herkes geçerli JWT üretebilir**. Login gerekmez, `{"sub": "1"}` imzalayıp cookie'ye koymak yeterli.

Her ikisi de **sessizce** olur — ne log, ne uyarı.

### Çözüm

Yeni dosya — `common/config_guard.py`:

```python
"""
Startup Configuration Guard
Uygulama, güvenlik açısından kritik ayarlar eksikse AÇILMAZ.

Gerekçe: bir sırrın varsayılanı olmamalıdır. Varsayılan varsa, o varsayılan
bir gün production'da çalışır ve kimse fark etmez.
"""
import os
import sys
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("web_api.config_guard")

# Bu değerler kodda geçmişte varsayılan olarak bulunuyordu.
# Biri hâlâ kullanılıyorsa açılmayı reddediyoruz.
_KNOWN_BAD = {
    "your-secret-key-here-change-in-production",
    "change-me",
    "secret",
    "",
}

_REQUIRED = (
    "SECRET_KEY",
    "QUERY_ENCRYPTION_KEY",
    "APP_DATABASE_URL",
    "CENTRAL_DB_USER",
    "CENTRAL_DB_PASSWORD",
)


def _fail(msg: str) -> None:
    logger.critical("KONFIGÜRASYON HATASI: %s", msg)
    print(f"\n❌ FATAL: {msg}\n", file=sys.stderr)
    raise SystemExit(1)


def verify_startup_config() -> None:
    """
    Uygulama açılmadan önce çağrılır. Eksik/zayıf sır varsa SystemExit(1).

    Test ortamı için: conftest.py içinde gerçek değerler set edilmeli,
    burada istisna YOK. Bir istisna eklenirse, o istisna bir gün prod'da
    çalışır.
    """
    missing = []
    for name in _REQUIRED:
        val = (os.getenv(name) or "").strip()
        if not val or val in _KNOWN_BAD:
            missing.append(name)

    if missing:
        _fail(
            "Şu ortam değişkenleri eksik veya varsayılan değerde: "
            + ", ".join(missing)
            + "\n   .env dosyanızı kontrol edin. Örnek için .env.example'a bakın."
        )

    # SECRET_KEY entropi kontrolü — 32 karakterden kısa bir HS256 anahtarı
    # brute-force'a açıktır.
    if len(os.environ["SECRET_KEY"]) < 32:
        _fail("SECRET_KEY en az 32 karakter olmalıdır. "
              "Üretmek için: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")

    # QUERY_ENCRYPTION_KEY gerçekten geçerli bir Fernet anahtarı mı?
    # Değilse ilk şifreleme denemesinde patlarız — o an audit log yazılırken olur.
    try:
        Fernet(os.environ["QUERY_ENCRYPTION_KEY"].encode())
    except Exception as e:
        _fail(f"QUERY_ENCRYPTION_KEY geçerli bir Fernet anahtarı değil: {e}\n"
              "   Üretmek için: python -c \"from cryptography.fernet import Fernet; "
              "print(Fernet.generate_key().decode())\"")

    logger.info("Konfigürasyon doğrulandı: %d kritik ayar mevcut", len(_REQUIRED))
```

`models.py:48-56` değişikliği:

```python
    @classmethod
    def _get_fernet(cls):
        if cls._fernet is None:
            key = os.getenv("QUERY_ENCRYPTION_KEY")
            if not key:
                # Fail-closed. Buraya düşmek, config_guard'ın atlandığı
                # anlamına gelir (ör. bir script AppDatabase'i doğrudan
                # import etti). Sessizce zayıf anahtar üretmektense patla.
                raise RuntimeError(
                    "QUERY_ENCRYPTION_KEY tanımlı değil. Şifreleme yapılamaz."
                )
            cls._fernet = Fernet(key)
        return cls._fernet
```

`authentication/config.py:9`:

```python
SECRET_KEY = os.environ["SECRET_KEY"]   # KeyError erken ve gürültülü — istediğimiz bu
```

`app.py` lifespan'ın **en başına**:

```python
from common.config_guard import verify_startup_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_startup_config()      # ← her şeyden önce
    print("🚀 Application starting...")
    ...
```

`.env.example`'a ekleyin:

```bash
# ZORUNLU — varsayılanı yoktur, uygulama bunlar olmadan açılmaz.
# Üret: python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=

# Üret: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
QUERY_ENCRYPTION_KEY=
```

### Doğrulama

```bash
cd web_api && SECRET_KEY= python -c "import app"   # SystemExit(1) vermeli
```

Test ekleyin — `tests/unit/test_config_guard.py`:

```python
import pytest
from common.config_guard import verify_startup_config

def test_bos_secret_key_acilmayi_engeller(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(SystemExit):
        verify_startup_config()

def test_bilinen_varsayilan_reddedilir(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    with pytest.raises(SystemExit):
        verify_startup_config()

def test_kisa_secret_key_reddedilir(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "kisa")
    with pytest.raises(SystemExit):
        verify_startup_config()
```

**Efor:** ~1 saat. **Risk:** Yok — sadece açılış sıkılaştırması. Deploy öncesi `.env`'in dolu olduğundan emin olun.

## Adım 4 · `0.4` — `sa` varsayılanını kaldır

**Neden burada:** `config_guard` `CENTRAL_DB_USER`/`PASSWORD`'ü zaten zorunlu kıldığı
için bu adım artık risksiz. `0.1`'den önce yapılırsa uygulama hiç açılmaz.

`database_provider/config.py:17-22`:

```python
DB_USER = os.getenv("DB_USER", "sa")            # ← varsayılan kalkmalı
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER", DB_USER)
CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD", DB_PASSWORD)
```

Faz 0.1'deki `config_guard` `CENTRAL_DB_USER`/`CENTRAL_DB_PASSWORD`'ü zaten zorunlu kılıyor. Varsayılanları temizleyin:

```python
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER") or DB_USER
CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD") or DB_PASSWORD
```

Ayrıca `config_guard`'a bir uyarı ekleyin:

```python
    # sa / root ile çalışmak Faz 3'e kadar kabul edilebilir ama sessiz olmamalı.
    if os.getenv("CENTRAL_DB_USER", "").lower() in {"sa", "root", "postgres", "admin"}:
        logger.warning(
            "CENTRAL_DB_USER='%s' — yüksek yetkili bir hesapla çalışıyorsunuz. "
            "Rol bazlı ayrı kimlik bilgileri için Faz 3'e bakın.",
            os.getenv("CENTRAL_DB_USER"))
```

**Efor:** 15 dakika.

### ✅ Blok 0 geçiş kontrolü

Bu kontrol geçmeden sonraki bloğa başlamayın.

Uygulama yalnızca eksiksiz bir `.env` ile açılıyor; şema değişikliği artık Alembic'ten
geçiyor; CI yeşil ve kırmızı bir test merge'ü engelliyor.

---

# Blok 1 — Kanama durdurma

**Süre:** ~6 saat

Üçü de birbirinden bağımsız, **paralel yürütülebilir.** Hiçbiri sonraki blokların
önkoşulu değil, ama üçü de 🔴: bugün açık olan şeyleri kapatıyorlar.

## Adım 5 · `0.2` — Ham veritabanı hatalarını temizle

**Neden burada:** Bağımsız — sırası önemli değil, bu blokta üçü paralel yürütülebilir.
Aciliyeti yüksek: sunucu adı, iç IP ve servis hesabı adı şu an doğrudan istemciye
gidiyor.

### Problem

```python
# query_execution/services.py:261-270
except Exception as e:
    error_msg: str = str(e)
    ...
    raise QueryExecutionError(error_msg, original_exception=e)
```

Ve handler bunu doğrudan JSON'a koyuyor (`app.py:157-166`). Sonuç, kullanıcının gördüğü:

```
('08001', '[08001] [Microsoft][ODBC Driver 18 for SQL Server]TCP Provider:
 Error code 0x2746 (10.0.14.22:1433) ... Login failed for user
 "webquery_svc" ... database "PayrollProd" on server "sql-prod-03.corp.internal"')
```

Sunucu adı, iç IP, servis hesabı adı, veritabanı adı — hepsi istemciye gitti.

### Neden önemli

Bu bilgiler bir saldırganın "keşif" aşamasının tamamı. Ayrıca SQL hataları **tablo ve kolon adlarını** sızdırır (`Invalid column name 'salary_net'`), ki maskeleme kurallarınızın gizlemeye çalıştığı şema bilgisi budur.

### Çözüm

Yeni dosya — `common/errors.py`:

```python
"""
Kullanıcıya dönecek hata mesajlarının temizlenmesi.

İlke: kullanıcı NE olduğunu öğrenmeli, NEREDE olduğunu değil.
Tam hata trace_id ile log'da durur; destek ekibi oradan bakar.
"""
import re
from typing import Final

_PATTERNS: Final = [
    # Bağlantı dizesi parçaları: server=..., uid=..., pwd=..., driver=...
    (re.compile(r"\b(server|address|addr|uid|pwd|user|password|driver|dsn|database|dbname|host|hostaddr|port)\s*=\s*[^;,\)\s]+",
                re.IGNORECASE), "[bağlantı-bilgisi]"),
    # 'Login failed for user "xxx"' — servis hesabı adı
    (re.compile(r'\bfor user\s+["\']?[^"\'\s,\)]+["\']?', re.IGNORECASE),
     "for user [gizli]"),
    # Sunucu adresleri (parantez içi IP dahil)
    (re.compile(r'\bserver\s+["\']?[^"\'\s,\)]+["\']?(\s*\([^)]*\))?', re.IGNORECASE),
     "server [gizli]"),
    # RFC1918 iç IP'ler
    (re.compile(r'\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}(?::\d+)?\b'),
     "[iç-adres]"),
    # Bulut ve iç alan adları
    (re.compile(r'\b[\w.-]+\.(?:database\.windows\.net|rds\.amazonaws\.com|myhuaweicloud\.com)(?::\d+)?\b',
                re.IGNORECASE), "[db-host]"),
    (re.compile(r'\b[\w-]+\.(?:internal|local|lan|corp|intranet)\b', re.IGNORECASE),
     "[iç-host]"),
    # Dosya yolları (stack trace parçaları)
    (re.compile(r'(?:[A-Za-z]:)?[\\/](?:[\w.-]+[\\/])+[\w.-]+\.py'), "[dosya]"),
]

# Kullanıcının GERÇEKTEN görmesi gereken hatalar — bunlar kendi SQL'i hakkında
# ve düzeltmesi için gerekli. Şema adı sızdırırlar, ama sorgusunu yazan zaten
# o şemaya erişim yetkisi olan kişidir.
_USER_FIXABLE = re.compile(
    r"(invalid column name|invalid object name|syntax error|"
    r"unknown column|doesn't exist|does not exist|ambiguous column|"
    r"division by zero|conversion failed|arithmetic overflow|"
    r"string or binary data would be truncated|"
    r"cannot insert the value null|violation of .* constraint)",
    re.IGNORECASE,
)

_MAX_LEN = 500


def scrub(message: str) -> str:
    """
    Hata mesajını istemciye gösterilebilir hale getirir.

    Kullanıcının düzeltebileceği SQL hataları (yazım hatası, olmayan kolon)
    geçirilir — sadece bağlantı/altyapı detayı temizlenir.
    Diğer her şey jenerik mesaja indirgenir.
    """
    if not message:
        return "Sorgu çalıştırılamadı."

    cleaned = message
    for pattern, replacement in _PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    if _USER_FIXABLE.search(cleaned):
        # ODBC/driver ön eklerini at: "('42S22', '[42S22] [Microsoft][ODBC ...]"
        cleaned = re.sub(r"^\(?['\"]?[\dA-Z]{5}['\"]?,?\s*", "", cleaned)
        cleaned = re.sub(r"\[[^\]]*(?:Microsoft|ODBC|SQL Server|Driver)[^\]]*\]", "",
                         cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" '\"()")
        return cleaned[:_MAX_LEN]

    return ("Sorgu çalıştırılamadı. Ayrıntılar sunucu kaydına yazıldı — "
            "destek ekibine trace_id ile başvurun.")
```

`query_execution/services.py:261-270` değişikliği:

```python
        except Exception as e:
            error_msg: str = str(e)
            # Tam hata SADECE log'a. Kullanıcıya temizlenmiş hali gider.
            logger.error("Query execution failed [log_id=%s]: %s",
                         log_id, error_msg, exc_info=True)
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id, successfull=False, error=error_msg
                )
            from common.errors import scrub
            raise QueryExecutionError(scrub(error_msg), original_exception=e)
```

Aynı değişiklik `workspaces/services.py:377-379`'da da yapılmalı.

`app.py` handler'ında `error` alanını da düzeltin — şu an `message` ile aynı ama backward-compat için duruyor:

```python
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.code,
            "message": exc.message,     # zaten scrub'lanmış
            "error": exc.message,
            "trace_id": trace_id
        }
    )
```

### Doğrulama

`tests/unit/test_error_scrubbing.py`:

```python
from common.errors import scrub

def test_baglanti_hatasi_host_sizdirmaz():
    raw = ("('08001', '[08001] [Microsoft][ODBC Driver 18]TCP Provider: "
           "Error code 0x2746 (10.0.14.22:1433); Login failed for user "
           '"webquery_svc"; server=sql-prod-03.corp.internal\')')
    out = scrub(raw)
    assert "10.0.14.22" not in out
    assert "webquery_svc" not in out
    assert "sql-prod-03" not in out
    assert "corp.internal" not in out

def test_kullanicinin_duzeltebilecegi_hata_gecer():
    raw = "('42S22', \"[42S22] [Microsoft][ODBC Driver 18]Invalid column name 'emial'.\")"
    out = scrub(raw)
    assert "emial" in out          # kullanıcı yazım hatasını görmeli
    assert "Microsoft" not in out  # driver gürültüsü gitmeli
```

**Efor:** ~2 saat.

## Adım 6 · `0.3` — Sorgu zaman aşımı

**Neden burada:** Bağımsız. Ama bir uyarı: bu madde `get_engine`'e `connect_args`
parametresi ekliyor ve `3.1` aynı fonksiyonu baştan yazacak. **O sırada
`connect_args`'ı korumayı unutmayın** — düşerse sorgu zaman aşımı sessizce kaybolur
ve kimse fark etmez.

### Problem

Hiçbir yerde sorgu timeout'u yok. `pool_timeout=30` var ama o **pool'dan bağlantı almak** için. Bir kullanıcının kartezyen JOIN'i saatlerce çalışır, bağlantıyı ve async worker'ı tutar.

### Neden önemli

Bu, tek kullanıcının tüm platformu durdurabildiği en kolay yol — kötü niyet bile gerekmez, yanlış bir JOIN yeter. Ayrıca `MAX_ROW_COUNT_LIMIT=1000` sadece **kaç satır okuduğunuzu** sınırlar; sunucu 50 milyon satırı hesaplamayı yine de bitirmek zorundadır.

### Çözüm

`database_provider/config.py`'a ekleyin:

```python
# Sorgu zaman aşımı (saniye). MAX_ROW_COUNT_LIMIT satır sayısını sınırlar,
# bu SÜREYİ sınırlar — ikisi farklı şeyler.
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "300"))


def get_connect_args(tech: str, timeout_seconds: int) -> dict:
    """
    Teknolojiye göre driver seviyesinde zaman aşımı argümanları.

    MSSQL'de sunucu tarafı statement_timeout YOKTUR — T-SQL'de böyle bir
    ayar yok. Timeout istemci tarafında (pyodbc/aioodbc) uygulanır.
    PostgreSQL ve MySQL'de sunucu tarafı ayar mevcut ve tercih edilir,
    çünkü istemci bağlantıyı bıraksa bile sunucu sorguyu öldürür.
    """
    tech = tech.lower().strip()

    if tech == "mssql":
        # pyodbc Connection.timeout — saniye cinsinden sorgu zaman aşımı
        return {"timeout": timeout_seconds}

    if tech in ("postgresql", "postgres"):
        return {
            "command_timeout": timeout_seconds,          # asyncpg istemci tarafı
            "server_settings": {                          # sunucu tarafı — asıl koruma
                "statement_timeout": str(timeout_seconds * 1000),
                "idle_in_transaction_session_timeout": str((timeout_seconds + 30) * 1000),
            },
        }

    if tech == "mysql":
        return {"connect_timeout": 15}   # SET SESSION ile tamamlanır (aşağıda)

    return {}


# MySQL'de sunucu tarafı sınır bağlantı sonrası SET ile kurulur.
# (max_execution_time yalnızca SELECT'leri etkiler — MySQL'in sınırı.)
SESSION_INIT_SQL = {
    "mysql": "SET SESSION max_execution_time = {ms}",
}
```

`database_provider/engine_cache.py` — `get_engine` imzasına `connect_args` ekleyin:

```python
    async def get_engine(self, url: str, db_uuid: str = None,
                         connect_args: dict | None = None) -> AsyncEngine:
        cache_key = db_uuid if db_uuid is not None else self._hash_key(url)
        async with self.lock:
            if cache_key in self._cache:
                self._cache[cache_key].last_accessed = datetime.now()
                self._stats["request_count"] += 1
                return self._cache[cache_key].engine

            if self._stats["engine_count"] >= self._max_engines:
                await self._evict_lru()

            engine = create_async_engine(
                url,
                pool_size=50,
                max_overflow=100,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=False,
                connect_args=connect_args or {},      # ← YENİ
            )
            ...
```

`database_provider/database.py` — `get_session`:

```python
from database_provider.config import (
    create_connection_string, get_driver_for_technology,
    get_connect_args, SESSION_INIT_SQL, QUERY_TIMEOUT_SECONDS,
    CENTRAL_DB_USER, CENTRAL_DB_PASSWORD,
)
from sqlalchemy import text

    @asynccontextmanager
    async def get_session(self, user: models.User, db_uuid: str):
        if db_uuid not in self.db_by_uuid:
            raise ValueError(f"Database with UUID '{db_uuid}' not found in configuration.")

        db_entry = self.db_by_uuid[db_uuid]
        servername = db_entry["servername"]
        database_name = db_entry["database_name"]
        tech = db_entry["technology"]
        driver = get_driver_for_technology(tech)

        conn_str = create_connection_string(
            tech=tech, driver=driver, servername=servername,
            database=database_name,
            username=CENTRAL_DB_USER, password=CENTRAL_DB_PASSWORD,
        )

        engine = await self.engine_cache.get_engine(
            conn_str,
            db_uuid=db_uuid,
            connect_args=get_connect_args(tech, QUERY_TIMEOUT_SECONDS),   # ← YENİ
        )

        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                # Sunucu tarafı oturum sınırı (yalnızca gerektiren motorlar için)
                init_sql = SESSION_INIT_SQL.get(tech.lower().strip())
                if init_sql:
                    await session.execute(
                        text(init_sql.format(ms=QUERY_TIMEOUT_SECONDS * 1000))
                    )
                yield session
            finally:
                await session.close()
```

> **Not:** `connect_args` engine oluşturulurken sabitlenir ve engine cache'te tutulur. Bu, timeout'un tüm kullanıcılar için aynı olması demek. Kullanıcı bazlı timeout istenirse cache anahtarını `(db_uuid, timeout)` yapmak gerekir — şu an gerek yok.

### Doğrulama

PostgreSQL hedefinde:
```sql
SELECT pg_sleep(400);
```
300 saniyede `canceling statement due to statement timeout` almalısınız.

MSSQL hedefinde:
```sql
WAITFOR DELAY '00:06:00';
```
pyodbc `timeout` hatası vermeli.

**Efor:** ~3 saat (test dahil).

## Adım 7 · `0.5` — Blacklist tablosunu temizle

**Neden burada:** `4.1`'e bağlı (yeni index ekliyor). Onun dışında bağımsız.

### Problem

`BlacklistedTokens` tablosu **her istekte** sorgulanıyor (`auth_middleware.py:69`) ve hiç temizlenmiyor. `expires_at` kolonu var, kullanılmıyor.

### Çözüm

`app_database/app_database.py`'a ekleyin:

```python
from sqlalchemy import delete

    async def purge_expired_blacklist(self) -> int:
        """
        Süresi dolmuş JTI kayıtlarını siler.

        Süresi dolmuş bir token zaten `exp` kontrolünde reddedilir, dolayısıyla
        blacklist'te tutmanın hiçbir güvenlik değeri yoktur — sadece her istekte
        taranan tabloyu büyütür.
        """
        async with self.get_app_db() as db:
            async with db.begin():
                result = await db.execute(
                    delete(BlacklistedToken).where(
                        BlacklistedToken.expires_at < datetime.now()
                    )
                )
                return result.rowcount or 0
```

`app.py` lifespan'a periyodik görev:

```python
import asyncio

async def _blacklist_cleanup_loop(app_db, interval_seconds: int = 3600):
    """Saatte bir süresi dolmuş token kayıtlarını sil."""
    logger = logging.getLogger("web_api.cleanup")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            n = await app_db.purge_expired_blacklist()
            if n:
                logger.info("Blacklist temizliği: %d süresi dolmuş kayıt silindi", n)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Blacklist temizliği başarısız")

# lifespan içinde, AppContext'ten sonra:
    cleanup_task = asyncio.create_task(_blacklist_cleanup_loop(app.state.app_db))
    app.state.cleanup_task = cleanup_task

# finally bloğunda:
        task = getattr(app.state, "cleanup_task", None)
        if task:
            task.cancel()
```

Ayrıca index ekleyin (`models.py`):

```python
class BlacklistedToken(Base):
    __tablename__ = "BlacklistedTokens"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jti = Column(String(100), unique=True, index=True, nullable=False)
    expires_at = Column(AppDateTime, nullable=False, index=True)   # ← index eklendi
```

**Efor:** ~1 saat.

### ✅ Blok 1 geçiş kontrolü

Bu kontrol geçmeden sonraki bloğa başlamayın.

Bağlantı hatası içeren bir sorgu çalıştırın — cevapta host, IP veya kullanıcı adı
geçmemeli. `SELECT pg_sleep(400)` zaman aşımına düşmeli. `BlacklistedTokens` tablosu
saatlik temizleniyor.

---

# Blok 2 — Denetlenebilirlik

**Süre:** ~2,5 gün

Bu bloğun çıktısı: *"Bu kullanıcı Payroll DB'sine nasıl ADMIN oldu?"* sorusunun
cevaplanabilir olması — ve onay yolundaki yarışın kapanması.

## Adım 8 · `4.4` — Rol split mantığını tek yere topla

**Neden burada, Faz 4'te değil:** `role.split(",")` deseni şu an dört dosyada
kopyalanmış. `3.1` beşinci bir kopya daha ekleyecek ve `max_tier()` mantığını içine
gömecek. Bu maddeyi `3.1`'den **önce** yaparsanız o kopya hiç doğmaz. Sonra
yaparsanız iki uygulamayı birleştirmek zorunda kalırsınız ve aradaki ince farkı
gözden kaçırmak kolaydır.

Bir saatlik iş. Ertelemenin hiçbir faydası yok.

**Açtığı kapı:** `3.1`

`role.split(",")` deseni 4 dosyada tekrarlanıyor. `common/roles.py`:

```python
"""
Rol çözümlemesi. UserDatabaseAssociation.role virgülle ayrılmış birden fazla
rol tutabilir ("READER,WRITER"). Bu ayrıştırma tek bir yerde yapılmalı —
dört kopya, dördünün ayrı ayrı yanlış olması demektir.
"""
from typing import Iterable

# Veri erişim rolleri — her biri bir bağlantı kademesine karşılık gelir.
READER, WRITER, DDL = "READER", "WRITER", "DDL"

# Yönetişim rolü — onay verme, maskeleme yönetimi, kullanıcı ekleme.
# Hiçbir veri kademesi VERMEZ; 3.1'deki ayrıma bakın.
ADMIN = "ADMIN"

_TIER_BY_ROLE = {READER: "ro", WRITER: "rw", DDL: "ddl"}
_TIER_RANK = {"ro": 0, "rw": 1, "ddl": 2}


def parse(role_string: str | None) -> set[str]:
    """'reader, WRITER ' → {'READER', 'WRITER'}"""
    if not role_string:
        return set()
    return {r.strip().upper() for r in role_string.split(",") if r.strip()}


def is_admin(role_string: str | None) -> bool:
    """Yönetişim yetkisi — onay verebilir mi? Veri erişimiyle İLGİSİ YOK."""
    return ADMIN in parse(role_string)


def max_tier(role_string: str | None) -> str | None:
    """
    Kullanıcının erişebileceği en yüksek bağlantı kademesi: 'ro' | 'rw' | 'ddl'.

    ADMIN burada bilinçli olarak yok sayılır — yönetişim rolü veri erişimi
    vermez. "ADMIN,READER" olan bir kullanıcı onay verebilir ama yalnızca
    okuyabilir.

    Veri rolü hiç yoksa None döner — 'ro' DEĞİL. Salt `ADMIN` rolü olan bir
    kullanıcının yönetişim yetkisi vardır, veri erişimi yoktur; ona sessizce
    okuma vermek 3.1'deki ayrımı iptal ederdi.
    """
    tiers = [_TIER_BY_ROLE[r] for r in parse(role_string) if r in _TIER_BY_ROLE]
    if not tiers:
        return None
    return max(tiers, key=lambda t: _TIER_RANK[t])


def any_admin(assocs: Iterable) -> bool:
    """Verilen ilişkilerden herhangi birinde ADMIN var mı?"""
    return any(is_admin(getattr(a, "role", None)) for a in assocs)
```

Şu 4 noktayı bununla değiştirin:
- `dependencies.py:114`
- `authentication/router.py:150`
- `query_execution/services.py:129`
- `admin/services.py:310, 406, 452`

**Efor:** ~1 saat.

## Adım 9 · `1.1` — Genel audit tablosu

**Neden burada:** Bir sonraki adımda yazılacak `decide()` fonksiyonu
`common/audit.log_in` ve `common/audit_actions.AuditAction`'ı import ediyor. Bu madde
yapılmadan o dosyalar yok ve uygulama açılmaz.

**Açtığı kapı:** `1.2`, `1.3`

### Problem

`ActionLogging` sorgu çalıştırmayı iyi kaydediyor. Ama şunların **hiçbiri** kaydedilmiyor:

- Kullanıcıya veritabanı yetkisi verme (`associate_user_to_database`)
- Veritabanı ekleme (`add_database`)
- Masking kuralı değiştirme (`save_masking_rules`)
- Web üzerinden onay/red
- Kullanıcı kaydı

Yani "bu kullanıcı Payroll DB'sine nasıl ADMIN oldu?" sorusunun cevabı sistemde yok.

### Çözüm

`app_database/models.py`'a yeni model:

```python
class AuditLog(Base):
    """
    Genel amaçlı, append-only denetim kaydı.

    ActionLogging sorgu ÇALIŞTIRMA olaylarını tutar; bu tablo diğer her şeyi:
    yetkilendirme değişiklikleri, onay kararları, yapılandırma değişiklikleri.

    Kural: bu tabloda UPDATE veya DELETE yapılmaz. Bir kayıt yanlışsa
    düzeltmesi yeni bir kayıttır.
    """
    __tablename__ = "AuditLog"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(AppDateTime, nullable=False, default=datetime.now, index=True)

    # Eylemi yapan
    actor_user_id = Column(Integer, ForeignKey("Users.id"), nullable=True, index=True)
    actor_username = Column(String(50), nullable=True)   # anlık kopya —
                                                          # kullanıcı silinse de kayıt okunabilir
    actor_slack_id = Column(String(20), nullable=True)   # Slack yolu için

    # Ne yapıldı.
    # SAEnum DEĞİL, düz String — bilinçli tercih. Eylem kümesi zamanla büyür ve
    # native bir DB enum'u her yeni değer için migration ister. Migration'dan
    # önce deploy olursa insert ÇALIŞMA ZAMANINDA patlar; log_in hata yutmadığı
    # için de denetlediği yetki değişikliğini geri alır. Yani unutulan bir
    # migration, yetkilendirmeyi tamamen bozar.
    # Geçerli değerler Python tarafında zorlanır: common/audit_actions.AuditAction
    action = Column(String(64), nullable=False, index=True)

    # Neye yapıldı (bkz. AuditTarget)
    target_type = Column(String(32), nullable=True)
    target_id = Column(String(64), nullable=True, index=True)

    # Ayrıntı (JSON string)
    details = Column(AppText, nullable=True)

    # Bağlam
    client_ip = Column(String(45), nullable=True)
    trace_id = Column(String(36), nullable=True, index=True)
```

Yeni dosya — `common/audit_actions.py`:

```python
"""
Denetim eylemi sözlüğü.

DEĞİŞMEZLİK KURALI: buradaki string değerler denetim tablosuna yazılır ve
geçmiş kayıt olarak orada kalır. Yeni üye EKLENEBİLİR; mevcut bir üyenin
DEĞERİ asla değiştirilemez, üye silinemez. Bir eylem kullanımdan kalkarsa
üyeyi bırakın, sadece çağırmayı bırakın — eski satırlar okunabilir kalmalı.

Enum'un asıl faydası tip güvenliği değil, SORGULANABİLİRLİK: denetim log'u
`WHERE action = 'grant_database_access'` diye sorgulanır ve bir yerde
`grant_database_acess` yazılırsa satır yazılır ama hiçbir sorgu bulmaz.
"""
from enum import StrEnum       # Python 3.11+ (Dockerfile: python:3.11-slim)


class AuditAction(StrEnum):
    # --- Yetkilendirme (en kritik grup) ---
    GRANT_DATABASE_ACCESS   = "grant_database_access"
    REVOKE_DATABASE_ACCESS  = "revoke_database_access"
    CHANGE_DATABASE_ROLE    = "change_database_role"

    # --- Kullanıcı yaşam döngüsü ---
    USER_CREATED     = "user_created"
    USER_REGISTERED  = "user_registered"
    USER_DISABLED    = "user_disabled"
    USER_ENABLED     = "user_enabled"
    PASSWORD_CHANGED = "password_changed"

    # --- Sorgu onayı ---
    APPROVE_QUERY = "approve_query"
    REJECT_QUERY  = "reject_query"
    PREVIEW_QUERY = "preview_query"

    # --- Yapılandırma ---
    ADD_DATABASE         = "add_database"
    REMOVE_DATABASE      = "remove_database"
    UPDATE_MASKING_RULES = "update_masking_rules"

    # --- Oturum (durum değiştirmeyen) ---
    LOGIN           = "login"
    LOGIN_FAILED    = "login_failed"
    LOGOUT          = "logout"
    SESSION_REVOKED = "session_revoked"


class AuditTarget(StrEnum):
    USER      = "user"
    DATABASE  = "database"
    WORKSPACE = "workspace"
    QUERY     = "query"
    SESSION   = "session"
    MASKING   = "masking_rule"


# Hangi fonksiyonun kullanılacağı kuralı — yorum değil, VERİ.
# Buradaki eylemler bir veritabanı durum değişikliğini kaydeder ve bu yüzden
# o değişiklikle AYNI transaction'da yazılmak zorundadır.
STATE_CHANGING: frozenset[AuditAction] = frozenset({
    AuditAction.GRANT_DATABASE_ACCESS,
    AuditAction.REVOKE_DATABASE_ACCESS,
    AuditAction.CHANGE_DATABASE_ROLE,
    AuditAction.USER_CREATED,
    AuditAction.USER_DISABLED,
    AuditAction.USER_ENABLED,
    AuditAction.APPROVE_QUERY,
    AuditAction.REJECT_QUERY,
    AuditAction.ADD_DATABASE,
    AuditAction.REMOVE_DATABASE,
    AuditAction.UPDATE_MASKING_RULES,
})
```

> **Yazarken katı, okurken hoşgörülü.** Veritabanından düz string geri gelir,
> enum üyesi değil. `row.action == AuditAction.GRANT_DATABASE_ACCESS`
> karşılaştırması çalışır (StrEnum str'e eşittir), ama `AuditAction(row.action)`
> ile **zorlamayın**: rolling deploy sırasında yeni sürümün yazdığı bir satırı
> eski sürüm okuyabilir ve görüntüleme ekranı `ValueError` ile patlar.

Yeni dosya — `common/audit.py`:

```python
"""
Denetim kaydı yardımcısı.

TASARIM NOTU — neden `session` parametresi var:
Denetim kaydı, kaydettiği durum değişikliğiyle AYNI TRANSACTION'da yazılmalıdır.
Ayrı bir transaction kullanılırsa iki tutarsızlık mümkün olur:
  • değişiklik commit oldu, audit insert'i patladı → izsiz değişiklik
  • audit yazıldı, değişiklik rollback oldu       → olmayan olayın kaydı
Çağıran zaten bir session tutuyorsa onu geçsin; tutmuyorsa `log_standalone`.
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app_database.models import AuditLog
from common.audit_actions import STATE_CHANGING, AuditAction, AuditTarget

logger = logging.getLogger("web_api.audit")


def _row(actor, action, target_type, target_id, details,
         client_ip, trace_id, actor_slack_id) -> AuditLog:
    return AuditLog(
        created_at=datetime.now(),
        actor_user_id=getattr(actor, "id", None) if actor else None,
        actor_username=getattr(actor, "username", None) if actor else None,
        actor_slack_id=actor_slack_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=json.dumps(details, default=str, ensure_ascii=False) if details else None,
        client_ip=client_ip,
        trace_id=trace_id,
    )


async def log_in(
    session: AsyncSession,
    *,
    actor: Any = None,
    action: AuditAction,
    target_type: Optional[AuditTarget] = None,
    target_id: Optional[Any] = None,
    details: Optional[dict] = None,
    client_ip: Optional[str] = None,
    trace_id: Optional[str] = None,
    actor_slack_id: Optional[str] = None,
) -> None:
    """
    Çağıranın transaction'ı içine denetim kaydı ekler. Commit ÇAĞIRANIN işi.
    Bu fonksiyon hata yutmaz — audit yazılamıyorsa değişiklik de olmamalı.
    """
    session.add(_row(actor, action, target_type, target_id, details,
                     client_ip, trace_id, actor_slack_id))


async def log_standalone(app_db, *, action: AuditAction, **kwargs) -> None:
    """
    Kendi transaction'ında yazar. Yalnızca durum değişikliğine BAĞLI OLMAYAN
    olaylar için (login, logout gibi). Hata yutar — bir login kaydının
    yazılamaması login'i engellememelidir.
    """
    # try BLOĞUNDAN ÖNCE: bu bir programlama hatası ve yutulmamalı. Durum
    # değiştiren bir eylemi buradan geçirmek, tam olarak yukarıda anlatılan
    # "değişiklik oldu, kayıt yok" senaryosunu üretir.
    if action in STATE_CHANGING:
        raise ValueError(
            f"{action} bir durum değişikliğidir — log_in(session, ...) kullanın "
            f"ki denetim kaydı değişiklikle aynı transaction'da yazılsın."
        )
    kwargs["action"] = action
    try:
        async with app_db.get_app_db() as db:
            async with db.begin():
                await log_in(db, **kwargs)
    except Exception:
        logger.exception("Denetim kaydı yazılamadı: action=%s", kwargs.get("action"))
```

### Uygulama noktaları

`admin/services.py:552` — `associate_user_to_database` (en kritik):

```python
    async def associate_user_to_database(
        self, user_id: int, database_id: int, role: str,
        admin_user: User, client_ip: str | None = None,
    ) -> dict[str, Any]:
        async with self.app_db.get_app_db() as db:
            async with db.begin():
                # ... mevcut yetki kontrolleri ...

                existing = await db.get(UserDatabaseAssociation, (user_id, database_id))
                previous_role = existing.role if existing else None

                # ... mevcut ekleme/güncelleme mantığı ...

                # AYNI transaction içinde denetim kaydı
                from common.audit import log_in
                await log_in(
                    db,
                    actor=admin_user,
                    action=AuditAction.GRANT_DATABASE_ACCESS,
                    target_type=AuditTarget.USER,
                    target_id=user_id,
                    details={
                        "database_id": database_id,
                        "new_role": role,
                        "previous_role": previous_role,
                    },
                    client_ip=client_ip,
                )
        return {"success": True, ...}
```

Aynı deseni şuralara uygulayın:

| Konum | action |
|---|---|
| `admin/services.py` `add_database` | `add_database` |
| `admin/services.py` `save_masking_rules` | `update_masking_rules` |
| `admin/services.py` `approve` | `approve_query` |
| `admin/services.py` `reject_query_by_workspace_id` | `reject_query` |
| `authentication/router.py` `register` | `user_registered` |
| `authentication/router.py` `login` (başarısız) | `login_failed` |

`StrEnum` oldukları için bu değerler **zaten string**: SQLAlchemy `String`
kolonu doğrudan kabul eder, `.value` yazmanıza gerek yok, mevcut string
karşılaştırmaları da çalışmaya devam eder.

### Sorgulama

Bu tablo işe yarar olmalı — bir sorgu ekleyin (`admin/router.py`):

```python
@router.get("/audit_log")
async def get_audit_log(
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = 200,
    admin_user: User = Depends(admin_required),
    app_db: AppDatabase = Depends(get_app_db),
):
    """Denetim kayıtlarını filtreli olarak döner (en yeniden eskiye)."""
    # Filtreyi DOĞRULA. Doğrulamazsanız `?action=grant_database_acess` boş
    # sonuç döner ve boş sonuç "hiç yetki verilmemiş" diye okunur — denetim
    # log'unda yapılabilecek en kötü yanlış çıkarım.
    # "Üye asla silinmez" kuralı sayesinde her geçmiş eylem enum'da mevcuttur,
    # dolayısıyla bu doğrulama hiçbir meşru sorguyu engellemez.
    if action is not None:
        try:
            action = AuditAction(action)
        except ValueError:
            raise HTTPException(
                400,
                f"Bilinmeyen eylem: '{action}'. Geçerli değerler: "
                + ", ".join(sorted(a.value for a in AuditAction))
            )

    async with app_db.get_app_db() as db:
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000))
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if target_type:
            stmt = stmt.where(AuditLog.target_type == target_type)
        if target_id:
            stmt = stmt.where(AuditLog.target_id == str(target_id))
        rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id, "at": r.created_at, "actor": r.actor_username,
            "action": r.action, "target": f"{r.target_type}:{r.target_id}",
            "details": json.loads(r.details) if r.details else None,
            "ip": r.client_ip,
        }
        for r in rows
    ]
```

### Değişmezlik kuralını teste sabitleyin

Yorumda kalan bir kural bir gün ihlal edilir. `tests/unit/test_audit_actions.py`:

```python
from common.audit_actions import AuditAction, STATE_CHANGING

# Denetim tablosuna yazılmış geçmiş değerleri temsil eder. Buradaki bir satırı
# DEĞİŞTİRMEK veya SİLMEK, geçmiş kayıtları sorgulanamaz hale getirir.
# Yeni eylem eklerken buraya da ekleyin.
FROZEN = {
    "GRANT_DATABASE_ACCESS": "grant_database_access",
    "REVOKE_DATABASE_ACCESS": "revoke_database_access",
    "CHANGE_DATABASE_ROLE": "change_database_role",
    "USER_CREATED": "user_created",
    "USER_REGISTERED": "user_registered",
    "USER_DISABLED": "user_disabled",
    "USER_ENABLED": "user_enabled",
    "PASSWORD_CHANGED": "password_changed",
    "APPROVE_QUERY": "approve_query",
    "REJECT_QUERY": "reject_query",
    "PREVIEW_QUERY": "preview_query",
    "ADD_DATABASE": "add_database",
    "REMOVE_DATABASE": "remove_database",
    "UPDATE_MASKING_RULES": "update_masking_rules",
    "LOGIN": "login",
    "LOGIN_FAILED": "login_failed",
    "LOGOUT": "logout",
    "SESSION_REVOKED": "session_revoked",
}


def test_enum_degerleri_donmus():
    for name, value in FROZEN.items():
        assert getattr(AuditAction, name).value == value, (
            f"{name} değeri değişmiş. Denetim tablosundaki eski satırlar hâlâ "
            f"'{value}' tutuyor — yeniden adlandırma yapılamaz."
        )


def test_hicbir_uye_silinmemis():
    eksik = set(FROZEN) - {a.name for a in AuditAction}
    assert not eksik, f"Silinmiş denetim eylemi: {eksik}"


def test_state_changing_uyeleri_gecerli():
    # Yazım hatasıyla STATE_CHANGING'e giren düz bir string, kuralı sessizce
    # devre dışı bırakır — üyelerin gerçekten enum üyesi olduğunu doğrula.
    for a in STATE_CHANGING:
        assert isinstance(a, AuditAction)
```

**Efor:** ~1 gün.

## Adım 10 · `1.2` — Onay yarışını kapat

**Neden burada — ve neden `1.3` ile birlikte:** Bu ikisi **tek bir iştir.** Aynı yarışı
iki farklı dosyada kapatıyorlar. Yalnızca `1.2` yapılırsa yarış web tarafında kapanır,
Slack tarafında açık kalır — ve Slack tarafında ayrıca **hiçbir yetki kontrolü yok**,
kanaldaki herkes onaylayabiliyor. Yarış kapanmaz, sadece taraf değiştirir.

`4.1` ve `1.1` önkoşul.

> ### Başlamadan önce — iki bağımlılık
>
> **① Bu maddeyi 1.3 ile birlikte yapın.** 1.2 düzeltmeyi `admin/services.py`'ye,
> 1.3 aynı düzeltmeyi Slack listener'a taşıyor. Sadece 1.2'yi uygularsanız yarış
> kapanmaz, **taraf değiştirir**: web tarafı koşullu yazar, Slack tarafı hâlâ
> koşulsuz üstüne yazar. Gerçek hayatta en olası çakışma da tam olarak bu ikisi
> arasında — bir admin Slack'ten onaylarken diğeri web panelinden reddediyor.
>
> **② Ön koşul: 4.1 (Alembic).** Bu madde `QueryData`'ya üç yeni kolon ekliyor.
> `create_all()` var olan bir tabloya kolon **eklemez** — hata da vermez, sessizce
> hiçbir şey yapar. Sonra `UPDATE ... SET decision_reason=...` çalışma anında
> patlar. Alembic kurulu değilse bu maddeye başlamayın.

### Problem

Aynı hata iki fonksiyonda birden var.

`reject_query_by_workspace_id` — `admin/services.py:387-412`:

```python
query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
query_data = query_result.scalars().first()      # ① OKU
...
query_data.status = "rejected"                   # ② YAZ
await db.commit()
```

`approve` — `admin/services.py:433-467`:

```python
query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
query_data = query_result.scalars().first()      # ① OKU
...
query_data.status = new_status                   # ② YAZ
await db.commit()
```

Bu desene **oku-değiştir-yaz** (read-modify-write) denir ve burada iki ayrı kusuru
var.

**Kusur 1 — durum hiç kontrol edilmiyor.** Kodda `if query_data.status ==
"waiting_for_approval"` diye bir satır yok. Eşzamanlılık olmasa bile: zaten
reddedilmiş bir sorgu tekrar onaylanabilir, zaten onaylanmış bir sorgu sonradan
reddedilebilir, çalıştırılmış bir sorgu yeniden karara bağlanabilir. Bir admin
sabah reddettiği sorguyu başka bir admin öğleden sonra onaylayabilir ve hiçbir şey
buna itiraz etmez. Bu bir yarış bile değil, sadece eksik doğrulama.

**Kusur 2 — iki eşzamanlı karar.**

```
t0   Mehmet: SELECT status  →  "waiting_for_approval"
t1   Ayşe:   SELECT status  →  "waiting_for_approval"     ← ikisi de "beklemede" görüyor
t2   Mehmet: status = "approved"   →  COMMIT
t3   Ayşe:   status = "rejected"   →  COMMIT               ← Mehmet'in kararını ezdi
```

Son yazan kazanır. Kötü olan kısım şu: **Mehmet ekranda "Sorgu onaylandı" mesajını
gördü.** Ayşe de "başarılı" gördü. İkisi de kendi kararının uygulandığını sanıyor;
gerçekte sadece biri uygulandı ve hangisi olduğu milisaniyelere bağlı.

Tehlikeli yön belli: Ayşe bir sorguyu riskli bulup **reddettiyse** ve Mehmet'in
onayı sonra yazılırsa, sorgu çalıştırılabilir hâle gelir — Ayşe ise engellediğini
sanır.

### Neden oluyor — mekanizma

Üç şeyin bir araya gelmesi. Düzeltmeyi anlamak için üçünü de bilmek gerekiyor.

**1. `SELECT` hiçbir şeyi kilitlemez.** Düz bir okuma, varsayılan izolasyon
seviyesinde (READ COMMITTED — PostgreSQL, SQL Server, MySQL'de standart) satırı
kilitlemez. Değeri okur, çıkar, arkasında iz bırakmaz. Okuduğunuz andan itibaren o
değer bayatlamaya başlar. *(Kilitleyen bir okuma da vardır — `SELECT ... FOR
UPDATE`. Bu yarışı çözmenin alternatif yolu odur; kodda kullanılmıyor.)*

**2. `query_data.status = "rejected"` veritabanına gitmez.** Bu bir Python
nesnesinin alanına atama. SQLAlchemy o anda hiçbir şey göndermez, sadece "bu nesne
kirlendi" diye not alır. Gerçek `UPDATE` cümlesi `await db.commit()` anında
üretilip gönderilir.

**3. Üretilen `UPDATE`'in `WHERE`'inde sadece birincil anahtar vardır.**
`UPDATE QueryData SET status='rejected' WHERE id=42` — mevcut duruma hiç bakmaz.
"Arada ne olduysa oldu, ben yazarım" der.

Gerçek akış:

```
SELECT id=42            → kilit YOK, okur, çıkar → "waiting_for_approval"
    ⋮
    ⋮   satır bu süre boyunca TAMAMEN SERBEST
    ⋮   (başka bir admin buraya girip commit edebilir)
    ⋮
commit()  →  UPDATE ... WHERE id=42  → KİLİTLE → yaz → BIRAK
                                        ↑ status'e bakmadan
```

**Transaction bunu çözmez.** Mevcut kod zaten tek transaction içinde —
`get_app_db()` ile açılıyor, `commit()` ile kapanıyor, yarış yine de oluşuyor.
Transaction'ın sözü *"yazdıklarım ya hep birlikte olur ya hiç olmaz"*dır; *"ben
okuduktan sonra kimse dokunmadı"* değil. Bunlar farklı garantiler ve buradaki sorun
ikincisi.

**Python tarafına `if` koymak da yetmez.** Akla gelen ilk çözüm şudur:

```python
if query_data.status != "waiting_for_approval":
    raise BaseServiceException("Zaten karara bağlanmış")
```

Bu Kusur 1'i çözer, Kusur 2'yi çözmez:

```
t0   Mehmet: SELECT → "waiting"   ✓ if geçti
t1   Ayşe:   SELECT → "waiting"   ✓ if geçti          ← ikisi de kontrolü geçti
t2   Mehmet: UPDATE → COMMIT
t3   Ayşe:   UPDATE → COMMIT                          ← if geçmişti, ama bayatlamıştı
```

Kontrol ile yazma arasında boşluk olduğu sürece açık kapanmaz. Bunun adı **TOCTOU**
— *time-of-check to time-of-use*. Boşluk ne kadar küçültülürse küçültülsün, boşluk
olduğu sürece yeterli değildir.

### Çözüm — kontrolü ve yazmayı tek cümleye sıkıştır

Birim "transaction" değil, **statement** (SQL cümlesi). Bir SQL cümlesi kendi
içinde bölünemez: veritabanı satırı kilitler, `WHERE`'i değerlendirir, `SET`'i
uygular, kilidi bırakır. Araya girilecek bir an yoktur.

Kilit sayısı değişmiyor — ikisinde de tek kilit var. Değişen, kilidin **neyi
kapsadığı**:

```
ESKİ:  KİLİTLE → [ yaz ] → BIRAK
                   ↑ kontrol kilidin DIŞINDA yapılmış, çoktan bayatlamış

YENİ:  KİLİTLE → [ kontrol et → yaz ] → BIRAK
                   ↑ kontrol kilidin İÇİNDE, taze veriyle
```

Desenin adı **compare-and-swap**: *"değer hâlâ X ise Y yap, değilse hiçbir şey
yapma."*

İki `UPDATE` gerçekten çakışırsa veritabanı işi kendisi halleder: ikincisi kilidin
çözülmesini bekler, sonra `WHERE`'i **yeni değere göre yeniden değerlendirir**,
tutmadığı için satırı atlar. Python tarafında yapılacak bir şey yok.

Not: yarış **ortadan kalkmıyor** — araya biri hâlâ girebilir. Değişen şu: kaybeden
taraf sessizce üstüne yazmak yerine `rowcount = 0` alıyor ve açık bir hataya
dönüşüyor. Eşzamanlılık kontrolünde hedeflenen genelde budur: çakışmayı yok etmek
değil, **çakışmayı görünür kılmak**.

### Uygulama

**Önce import.** `admin/services.py:5` şu an:

```python
from sqlalchemy import inspect, delete
```

`update` yok. Eklenmezse ilk çalıştırmada `NameError`:

```python
from sqlalchemy import inspect, delete, update
```

**Durum metnini doğrulayın.** Koşul `"waiting_for_approval"` metnine dayanıyor.
Bu değer `query_execution/services.py:162`'de yazılıyor ve `admin/services.py:218`'de
zaten filtre olarak kullanılıyor — yani tutuyor. Ama bu metin ileride değişirse
`WHERE` hiç eşleşmez, `rowcount` hep `0` döner ve **hiçbir onay çalışmaz**. Sabiti
tek yere alın:

```python
# app_database/models.py veya common/constants.py
QUERY_STATUS_PENDING = "waiting_for_approval"
```

**Kod:**

```python
from sqlalchemy import update

    async def approve(self, workspace_id: int, show_results: bool,
                      admin_user: User, client_ip: str | None = None) -> dict[str, Any]:
        async with self.app_db.get_app_db() as db:
            async with db.begin():
                workspace = (await db.execute(
                    select(Workspace).where(Workspace.id == workspace_id)
                )).scalars().first()
                if not workspace:
                    raise WorkspaceNotFoundError("Workspace not found")

                query_data = (await db.execute(
                    select(QueryData).where(QueryData.id == workspace.query_id)
                )).scalars().first()
                if not query_data:
                    raise WorkspaceNotFoundError("Query data not found")

                # ... admin yetki kontrolü (mevcut kod) ...

                new_status = "approved_with_results" if show_results else "approved"

                # ATOMİK GEÇİŞ: yalnızca hâlâ bekleyen bir istek karara bağlanabilir.
                # Bu WHERE koşulu, iki eşzamanlı kararın ikisinin de yazmasını
                # engelleyen TEK şeydir — Python tarafındaki kontrol yeterli değil.
                result = await db.execute(
                    update(QueryData)
                    .where(
                        QueryData.id == query_data.id,
                        QueryData.status == "waiting_for_approval",
                    )
                    .values(status=new_status)
                )
                if result.rowcount == 0:
                    # Yarışı kaybettik ya da istek zaten karara bağlanmış.
                    current = (await db.execute(
                        select(QueryData.status).where(QueryData.id == query_data.id)
                    )).scalar_one_or_none()
                    raise BaseServiceException(
                        f"Bu istek zaten karara bağlanmış (durum: {current}). "
                        f"Sayfayı yenileyin."
                    )

                workspace.show_results = show_results
                workspace.description = (
                    f"{admin_user.username} tarafından onaylandı "
                    f"({'çalıştırılabilir' if show_results else 'çalıştırılamaz'})"
                )

                # ActionLogging'i de güncelle — web yolu bunu yapmıyordu
                await db.execute(
                    update(ActionLogging)
                    .where(ActionLogging.trace_id == query_data.uuid)
                    .values(
                        approval_status=ApprovalStatus.APPROVED,
                        approved_execution=True,
                        approved_by=admin_user.username,
                        approved_at=datetime.now(),
                    )
                )

                from common.audit import log_in
                from common.audit_actions import AuditAction, AuditTarget
                await log_in(
                    db, actor=admin_user, action=AuditAction.APPROVE_QUERY,
                    target_type=AuditTarget.WORKSPACE, target_id=workspace_id,
                    details={"show_results": show_results,
                             "risk_type": query_data.risk_type,
                             "trace_id": query_data.uuid},
                    client_ip=client_ip,
                )

        return {"success": True, "status": new_status,
                "message": "Sorgu onaylandı."}
```

`reject_query_by_workspace_id` için de aynı desen — ve **gerekçe zorunlu**:

```python
    async def reject_query_by_workspace_id(
        self, workspace_id: int, admin_user: User,
        reason: str, client_ip: str | None = None,
    ):
        reason = (reason or "").strip()
        if not reason:
            raise BaseServiceException(
                "Red gerekçesi zorunludur. Kullanıcı neyi düzeltmesi "
                "gerektiğini bilmeli."
            )
        # ... atomik UPDATE (status == "waiting_for_approval" koşuluyla) ...
        workspace.description = f"Reddedildi ({admin_user.username}): {reason}"
```

`QueryData`'ya gerekçe kolonu ekleyin:

```python
class QueryData(Base):
    ...
    decision_reason = Column(String(500), nullable=True)
    decided_by = Column(String(50), nullable=True)
    decided_at = Column(AppDateTime, nullable=True)
```

`admin/router.py:56` — gerekçeyi body'den alın:

```python
class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)

@router.post("/reject_query/{workspace_id}")
async def reject_query(
    workspace_id: int,
    body: RejectRequest,
    request: Request,
    admin_user: User = Depends(admin_required),
    admin_service: AdminService = Depends(get_admin_service),
):
    client_ip = request.client.host if request.client else None
    return await admin_service.reject_query_by_workspace_id(
        workspace_id, admin_user, reason=body.reason, client_ip=client_ip
    )
```

### Router de değişiyor

`admin/router.py:56-72` şu an gerekçe almıyor ve servisten dönen sözlüğe bakıyor.
İkisi de değişmeli:

```python
class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)

@router.post("/reject_query/{workspace_id}")
async def reject_query(
    workspace_id: int,
    body: RejectRequest,
    request: Request,
    current_admin: User = Depends(admin_required),
    service: AdminService = Depends(get_admin_service),
):
    client_ip = request.client.host if request.client else None
    # Servis artık sözlük döndürmüyor, exception fırlatıyor.
    # Yarışı kaybeden istek BaseServiceException alır → 409 döner.
    return await service.reject_query_by_workspace_id(
        workspace_id, current_admin, reason=body.reason, client_ip=client_ip
    )
```

Frontend tarafında: **409'u ayrı ele alın.** Kullanıcıya "hata oluştu" demek yanlış
— doğru mesaj "bu istek başkası tarafından karara bağlandı, sayfayı yenileyin".

### Doğrulama

```python
# tests/integration/test_approval_race.py
import asyncio
import pytest
from common.exceptions import BaseServiceException


@pytest.mark.asyncio
async def test_iki_esanli_karar_biri_kazanir(app_db, admin_user, pending_workspace):
    """İki eşzamanlı karar: tam olarak biri geçer, diğeri açık hata alır."""
    sonuclar = await asyncio.gather(
        decide(app_db, workspace_id=pending_workspace.id,
               decision="approve_with_results", actor=admin_user),
        decide(app_db, workspace_id=pending_workspace.id,
               decision="reject", actor=admin_user, reason="riskli"),
        return_exceptions=True,
    )
    gecen  = [r for r in sonuclar if not isinstance(r, Exception)]
    duesen = [r for r in sonuclar if isinstance(r, BaseServiceException)]

    assert len(gecen) == 1,  "tam olarak bir karar geçmeliydi"
    assert len(duesen) == 1, "kaybeden taraf açık hata almalıydı"
    assert "zaten karara bağlanmış" in str(duesen[0])


@pytest.mark.asyncio
async def test_karara_baglanmis_istek_tekrar_karara_baglanamaz(
    app_db, admin_user, pending_workspace
):
    await decide(app_db, workspace_id=pending_workspace.id,
                 decision="reject", actor=admin_user, reason="riskli")

    with pytest.raises(BaseServiceException, match="zaten karara bağlanmış"):
        await decide(app_db, workspace_id=pending_workspace.id,
                     decision="approve_with_results", actor=admin_user)


@pytest.mark.asyncio
async def test_gerekce_olmadan_reddedilemez(app_db, admin_user, pending_workspace):
    with pytest.raises(BaseServiceException, match="gerekçe"):
        await decide(app_db, workspace_id=pending_workspace.id,
                     decision="reject", actor=admin_user, reason="   ")
```

> **Testlerin sınırı:** Test veritabanı SQLite ise satır seviyesinde kilit yoktur —
> SQLite tüm dosyayı kilitler, yazmalar sıraya girer. Koşullu `UPDATE`'in **mantığı**
> yine doğru doğrulanır (ikinci yazma commit edilmiş değeri görür, `WHERE` tutmaz,
> `rowcount = 0`), ama gerçek eşzamanlı kilit davranışı doğrulanmaz. Üretim
> motorunda (PostgreSQL / SQL Server) bir kez elle teyit edin.

> **`rowcount` uyarısı — SQL Server:** Bir trigger veya oturum ayarı `SET NOCOUNT ON`
> yapıyorsa sürücü `rowcount` olarak `-1` döndürebilir. Bu durumda `== 0` kontrolü
> yanlış tarafa düşer ve **yarışı kaybeden taraf kazanmış sanılır**. MSSQL
> kullanıyorsanız yukarıdaki ilk testi üretim motoruna karşı bir kez çalıştırın;
> `rowcount` `-1` dönüyorsa kontrolü `if res.rowcount != 1:` şekline çevirin.

**Efor:** ~4 saat (1.3 ile birlikte yapılırsa bu süre 1.3'ün içinde erir).

## Adım 11 · `1.3` — Web ve Slack onay yollarını birleştir

**Neden burada:** Bir önceki adımla **aynı iş.** Ayrı bir sprint'e bölmeyin.

Bu madde 🔴 çünkü canlı bir yetkilendirme açığı kapatıyor: `_resolve_approver`
kimliği titizlikle doğruluyor ama yetkiyi hiç sormuyor.

> **Düzeltme:** Bu bölümün ilk yazımında Slack yolunun `QueryData.status` ve
> `Workspace.show_results` alanlarını yazmadığı belirtilmişti. Kod kontrol edildi:
> ikisini de yazıyor (`listener.py:207-212` ve `listener.py:277-282`). Aşağıdaki
> tablo ve gerekçe düzeltilmiş hâlidir — ve ortaya çıkan asıl sorun, tutarsızlıktan
> daha ciddi.

### Problem

| | Web (`admin/services.py`) | Slack (`listener.py`) |
|---|---|---|
| `QueryData.status` yazılıyor | ✅ | ✅ |
| `Workspace.show_results` yazılıyor | ✅ | ✅ |
| `ActionLogging.approval_status` yazılıyor | ❌ | ✅ |
| Hedef veritabanında ADMIN yetkisi kontrolü | ✅ | ❌ |
| Koşullu (atomik) durum geçişi | ❌ | ❌ |
| Kullanıcıya sonuç, yazmadan **sonra** bildiriliyor | ✅ | ❌ |

Üç ayrı sorun var ve biri diğerlerinden çok daha ağır.

#### ① Slack yolunda yetkilendirme kontrolü yok 🔴

`_resolve_approver` (`listener.py:68-160`) Slack hesabının gerçek olduğunu
titizlikle doğruluyor: silinmiş mi, bot mu, misafir mi, e-posta var mı, formatı
geçerli mi. Bunların hepsi doğru ve iyi yazılmış — ama hepsi **kimlik** doğrulaması.

**Yetki** doğrulaması hiç yok:

- Eşleşen WebQuery kullanıcısının o veritabanında `ADMIN` rolü olup olmadığına
  bakılmıyor.
- Daha kötüsü: eşleşen bir WebQuery kullanıcısı **hiç yoksa**, fonksiyon
  e-postayı dize olarak döndürüyor (`listener.py:158`) ve onay akışı hiçbir şey
  olmamış gibi devam ediyor.

Pratik sonuç: **Slack kanalındaki onay mesajını gören herkes butona basıp riskli
sorguyu onaylayabilir.** WebQuery hesabı olması bile gerekmiyor. Aynı işlem web
arayüzünde `UserDatabaseAssociation` üzerinden ADMIN kontrolünden geçiyor
(`admin/services.py:450-452`).

Bu, 1.3'ü bir "tutarlılık düzenlemesi" olmaktan çıkarıp **açık kapatma** maddesi
yapıyor. Faz 1'in içindeki en yüksek öncelikli iş budur.

#### ② Web yolu denetim izine yazmıyor 🟠

`update_approval_status` yalnızca `listener.py:226`, `listener.py:296` ve
`query_execution/services.py:149`'dan çağrılıyor. `admin/services.py:approve` hiç
çağırmıyor.

Sonuç: web arayüzünden onaylanan bir sorgu `ActionLogging` tablosunda **hiç
onaylanmamış** görünüyor — `approved_by` boş, `approved_at` boş. Denetim izine
bakan biri "bu sorgu kimin onayıyla çalıştı?" sorusuna cevap bulamıyor. Slack'ten
onaylananlar için cevap var, web'den onaylananlar için yok.

#### ③ Slack yolu sonucu yazmadan önce bildiriyor 🟠

```python
await respond(replace_original=True, blocks=[],
              text=f"✅ Query approved by <@{slack_user_id}>. ...")   # listener.py:193-197

async with self.app_db.get_app_db() as session:
    try:
        ...
        await session.commit()
    except Exception as e:
        logger.error(f"[Slack] Approval DB update failed for {request_id}: {e}")  # listener.py:221
```

Mesaj **önce** gidiyor, yazma **sonra** deneniyor, yazma hatası yalnızca loglanıyor.
Veritabanı yazması başarısız olursa Slack'te "✅ Query approved" yazıyor, buton
kayboluyor, sistemde ise hiçbir şey değişmemiş oluyor. Onaylayan kişi işini
bitirdiğini sanıyor; kullanıcı ise sorgunun hâlâ beklemede olduğunu görüyor ve
kimse neden olduğunu bilmiyor.

### Çözüm

QueryHub'ın `core_decide.py` desenini uygulayın: **tek karar fonksiyonu, iki çağıran.**

Yeni dosya — `approval/service.py`:

```python
"""
Transport-bağımsız onay/red hattı.

Web paneli ve Slack butonu AYNI fonksiyonu çağırır. Bu, iki yüzeyin
farklı davranmasını yapısal olarak imkânsız kılar — birinin düzeltilip
diğerinin unutulması mümkün değildir.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import select, update

from app_database.app_database import AppDatabase
from app_database.models import (
    ActionLogging, ApprovalStatus, Databases, QueryData,
    User, UserDatabaseAssociation, Workspace,
)
from common.audit import log_in
from common.audit_actions import AuditAction, AuditTarget
from common.exceptions import BaseServiceException

logger = logging.getLogger(__name__)

Decision = Literal["approve_with_results", "approve_no_results", "reject"]


@dataclass
class DecisionOutcome:
    workspace_id: int
    query_uuid: str
    new_status: str
    requester_user_id: int
    decided_by: str


async def decide(
    app_db: AppDatabase,
    *,
    workspace_id: int,
    decision: Decision,
    actor: Optional[User],
    actor_slack_id: Optional[str] = None,
    actor_display_name: Optional[str] = None,
    reason: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> DecisionOutcome:
    """
    Bekleyen bir isteği atomik olarak karara bağlar.

    `actor` WebQuery kullanıcısıdır (web yolu). Slack yolunda kullanıcı
    e-posta ile eşleştirilemeyebilir; o durumda `actor=None` ve
    `actor_slack_id` + `actor_display_name` verilir.

    Raises:
        BaseServiceException: istek bulunamazsa, zaten karara bağlanmışsa,
                              veya aktörün o veritabanında ADMIN yetkisi yoksa.
    """
    if decision == "reject" and not (reason or "").strip():
        raise BaseServiceException("Red gerekçesi zorunludur.")

    async with app_db.get_app_db() as db:
        async with db.begin():
            workspace = (await db.execute(
                select(Workspace).where(Workspace.id == workspace_id)
            )).scalars().first()
            if not workspace:
                raise BaseServiceException("Workspace bulunamadı.")

            query_data = (await db.execute(
                select(QueryData).where(QueryData.id == workspace.query_id)
            )).scalars().first()
            if not query_data:
                raise BaseServiceException("Sorgu kaydı bulunamadı.")

            db_entry = (await db.execute(
                select(Databases).where(
                    Databases.servername == query_data.servername,
                    Databases.database_name == query_data.database_name,
                )
            )).scalars().first()
            if not db_entry:
                raise BaseServiceException("Hedef veritabanı kayıtlı değil.")

            # Yetki: aktör bu veritabanında ADMIN olmalı.
            # actor None ise (Slack'te eşleşmeyen kullanıcı) reddedilir —
            # kimliği doğrulanamayan biri onay veremez.
            if actor is None:
                raise BaseServiceException(
                    "Onaylayan kullanıcı WebQuery hesabıyla eşleştirilemedi."
                )
            assoc = (await db.execute(
                select(UserDatabaseAssociation).where(
                    UserDatabaseAssociation.user_id == actor.id,
                    UserDatabaseAssociation.database_id == db_entry.id,
                )
            )).scalars().first()
            if not assoc or "ADMIN" not in [r.strip().upper()
                                            for r in assoc.role.split(",")]:
                raise BaseServiceException(
                    "Bu veritabanı için yönetici yetkiniz yok."
                )

            # Kendi sorgusunu onaylayamaz — onayın tüm anlamı ikinci çift göz.
            # Bu kontrol kaldırılırsa onay akışı bir formaliteye döner.
            # Politika ve tek-admin durumu için "Onay yetkisi kimde?" bölümüne bakın.
            if actor.id == query_data.user_id:
                raise BaseServiceException(
                    "Kendi sorgunuzu onaylayamazsınız. Başka bir yönetici onaylamalı."
                )

            # --- Atomik durum geçişi ---
            status_map = {
                "approve_with_results": "approved_with_results",
                "approve_no_results": "approved",
                "reject": "rejected",
            }
            new_status = status_map[decision]

            res = await db.execute(
                update(QueryData)
                .where(QueryData.id == query_data.id,
                       QueryData.status == "waiting_for_approval")
                .values(
                    status=new_status,
                    decision_reason=reason,
                    decided_by=actor.username,
                    decided_at=datetime.now(),
                )
            )
            if res.rowcount == 0:
                current = (await db.execute(
                    select(QueryData.status).where(QueryData.id == query_data.id)
                )).scalar_one_or_none()
                raise BaseServiceException(
                    f"Bu istek zaten karara bağlanmış (durum: {current})."
                )

            # --- Workspace ---
            workspace.show_results = (decision == "approve_with_results")
            workspace.description = (
                f"Reddedildi ({actor.username}): {reason}" if decision == "reject"
                else f"Onaylandı ({actor.username})"
            )

            # --- ActionLogging ---
            await db.execute(
                update(ActionLogging)
                .where(ActionLogging.trace_id == query_data.uuid)
                .values(
                    approval_status=(ApprovalStatus.REJECTED if decision == "reject"
                                     else ApprovalStatus.APPROVED),
                    approved_execution=(decision == "approve_with_results"),
                    approved_by=actor.username,
                    approved_by_slack_id=actor_slack_id,
                    approved_at=datetime.now(),
                )
            )

            # --- Denetim ---
            await log_in(
                db, actor=actor, actor_slack_id=actor_slack_id,
                action=(AuditAction.REJECT_QUERY if decision == "reject"
                        else AuditAction.APPROVE_QUERY),
                target_type=AuditTarget.WORKSPACE, target_id=workspace_id,
                details={"decision": decision, "reason": reason,
                         "risk_type": query_data.risk_type,
                         "trace_id": query_data.uuid,
                         "surface": "slack" if actor_slack_id else "web"},
                client_ip=client_ip,
            )

            outcome = DecisionOutcome(
                workspace_id=workspace_id,
                query_uuid=query_data.uuid,
                new_status=new_status,
                requester_user_id=query_data.user_id,
                decided_by=actor.username,
            )

    logger.info("Karar verildi: workspace=%s decision=%s by=%s",
                workspace_id, decision, outcome.decided_by)
    return outcome
```

### Onay yetkisi kimde?

Bu soru kodda üç ayrı yerde cevaplanıyor ve üçü tutarsız. Karar tek yerde
verilmeli, `decide()` içinde.

#### Bugünkü durum

Temel doğru: o veritabanında `ADMIN` rolü olan herkes onaylayabilir
(`admin/services.py:452`). Ama üç boşluk var:

**① Admin'in kendi riskli sorgusu hiç onaya düşmüyor.**

```python
# query_execution/services.py:145
if not query_analysis["return"] and not is_db_admin:

# workspaces/services.py:317
# enforce approval only for non-admins
if not is_db_admin:
```

Yani admin için onay akışı **fiilen yok**. Riskli sorgu yazar, doğrudan çalışır.

**② Slack'ten onaylayan için hiçbir yetki kontrolü yok** — yukarıdaki ① numaralı
soruna bakın; kanaldaki herkes basabiliyor.

**③ Kendi sorgusunu onaylama engeli yok.** Bugün önemsiz görünüyor çünkü ① yüzünden
admin'in sorgusu zaten onaya düşmüyor. ① düzeltildiği anda kritik hale geliyor.

#### Karar 1: Kim onaylayabilir? → `ADMIN`, o veritabanı için

Zaten böyle; tek eksik Slack tarafında da uygulanması.

3.1'deki rol ayrımından sonra bu daha temiz hale geliyor: `ADMIN` artık *sadece*
yönetişim demek, veri kademesi vermiyor. Bir kişi `ADMIN,READER` olabilir —
**onaylar ama kendisi yazamaz.**

Bu en sağlıklı onaylayıcı profilidir: onayladığı şeyi kendi başına yapamayan kişi.
Onayın bağımsızlığı buradan gelir.

#### Karar 2: Kendi sorgusunu onaylayabilir mi? → Hayır

`decide()` içindeki `actor.id == query_data.user_id` kontrolü bunu uyguluyor.

**Ama gerçek bir maliyeti var:** bir veritabanında tek admin varsa ve o kişi riskli
bir sorgu yazarsa, onaylayacak kimse kalmaz. İki seçenek:

| | **(a) Katı — tavsiye edilen** | **(b) Esnek** |
|---|---|---|
| Kendi onayı | Her zaman reddedilir | Tek admin varsa izin verilir |
| Gereksinim | Veritabanı başına ≥2 admin | Yok |
| Denetim izi | — | `self_approved: true` işareti |
| Riski | Tek admin varsa iş durur | Kural fiilen delinebilir |

**(a) tavsiye ediliyor.** Bir kişi hem riskli sorgu yazıp hem onaylayabiliyorsa,
onay akışı sıfır güvence sağlıyor demektir — ve bunu düz bir şekilde bilmek,
kimsenin okumadığı bir bayrağa sahip olmaktan iyidir. İkinci admin eklemek ucuz.

Takımınızda veritabanı başına gerçekten tek sorumlu varsa (b) meşru bir tercihtir.
O durumda `decide()`'daki kontrolü şuna çevirin ve **durumu görünür tutun**:

```python
            if actor.id == query_data.user_id:
                # Tek admin istisnası: onaylayacak başka kimse yoksa kilitlenmeyelim.
                # Ama bu bir istisna, norm değil — ayrı bir eylem olarak kaydedilir
                # ki denetimde göze batsın.
                diger_adminler = (await db.execute(
                    select(func.count(UserDatabaseAssociation.id)).where(
                        UserDatabaseAssociation.database_id == db_entry.id,
                        UserDatabaseAssociation.user_id != actor.id,
                        UserDatabaseAssociation.role.ilike("%ADMIN%"),
                    )
                )).scalar_one()
                if diger_adminler > 0:
                    raise BaseServiceException(
                        "Kendi sorgunuzu onaylayamazsınız. "
                        "Bu veritabanında başka yöneticiler var."
                    )
                self_approved = True
```

Her iki seçenekte de `config_guard`'a şu kontrolü ekleyin:

```python
# Tek admin'i olan veritabanları, onay akışının güvence sağlamadığı
# veritabanlarıdır. Açılışta uyarı ver — sessizce yaşamasın.
```

#### Karar 3: Admin'in sorgusu onaya düşmeli mi? → **Hayır** (karar verildi)

> **Karar geçmişi — iki kez revize edildi, son hâli budur.**
> ① *"Evet, onaya düşmeli"* → fazla kesindi. ② *"Teyide düşmeli"* → ara
> öneriydi. ③ **Kabul edilen: admin onay ve teyit akışlarının ikisine de
> girmez.** Sert bloklar admin için de geçerli kalır.

`ADMIN` rolü *"bu kişi güvenilir"* demek değil, *"bu kişi onay verebilir"*
demek — ve bu ikisinin farkı gerçek. Ama pratik gerekçe bunu yeniyor:

**Admin'in hedef veritabanında kendi hesabı var.** WebQuery'de kurulan kapı onu
durdurmuyor, SSMS'e yönlendiriyor — ve o an denetim izi tamamen kayboluyor.
Baypas edilebilen bir kontrol için ödenen bekleme bedeli, karşılığında bir şey
almıyor. (Gerekçenin tamamı ve kontrol hiyerarşisi **3.4.1**'de.)

Dolayısıyla:

- **Sert bloklar** (injection, `xp_cmdshell`) — herkes için, admin dahil.
  Bunlar bir yetki sorusu değil; bu yol o riskler için var değil.
- **Diğer riskler, yıkıcı DML, teyit gerektiren her şey** — admin için atlanır,
  ama `ActionLogging`'e `risk_type` ile yazılır. İz kalır.
- **Kademe düzeni admin için de aynen işler.** Admin'in `SELECT`'i `ro`
  hesabıyla, `UPDATE`'i `rw` hesabıyla gider. Bu bir onay meselesi değil,
  bağlantı meselesi — ve 3.1 baypas edilmiyor.

Kod: `query_execution/services.py:145`'teki `is_db_admin` bypass'ı **korunur**.
3.2.5 bunun nihai hâlini gösteriyor (sert blok her zaman, diğerleri loglanır).

> **Bunun bir sonucu var — Karar 2 fiilen devre dışı kalıyor.** Admin'in sorgusu
> hiçbir zaman onay kuyruğuna girmediğine göre, admin'in onaylayacağı kendi
> sorgusu da hiç oluşmuyor. `decide()`'daki self-approval kontrolü **kalsın** —
> ama artık canlı bir politika değil, derinlik savunması: bypass bir gün
> kaldırılırsa kontrolü yeniden yazmak zorunda kalmayın.
>
> Tek-admin kilidi de böylece **ortadan kalkıyor**. Karar 2'deki katı/esnek
> tablosu ve `config_guard` uyarısı artık gerekli değil; isterseniz uyarıyı
> bilgi amaçlı bırakın.

**Bu kararın bağlı olduğu olgu:** admin'lerin üretim veritabanlarında kendi
hesaplarının bulunması. 3.4.5'teki hedefe geçilirse (üretimde insan hesabı yok)
bu karar **yeniden değerlendirilmelidir** — o dünyada WebQuery gerçekten tek
kapı olur ve baypas argümanı çöker.

#### Ortaya çıkan politika

| Durum | Normal kullanıcı | ADMIN |
|---|---|---|
| Sert blok listesi (injection vb.) | Reddedilir | **Reddedilir** |
| Geri alınamaz (`DROP`, `TRUNCATE`) | Onay | Serbest — kademesi elveriyorsa |
| Etki > eşik, ya da kritik tablo | Onay | Serbest |
| Yıkıcı DML, eşik altı | Teyit | Serbest |
| Diğer | Serbest | Serbest |

Her satırda, sorgu yine **kendi kademesinin hesabıyla** çalışır. "Serbest"
demek "her şeyi yapabilir" demek değil — `ro` ile bağlanan bir oturum yazamaz.
Onay kapısı açılıyor, kademe kapısı açılmıyor.

Onaylayan kişi normal kullanıcının isteğinde o veritabanının herhangi bir
`ADMIN`'idir.

**Doğrulama:**

```python
@pytest.mark.asyncio
async def test_kendi_sorgusunu_onaylayamaz(app_db, admin_a, admin_b, ws_by_admin_a):
    with pytest.raises(BaseServiceException, match="Kendi sorgunuzu"):
        await decide(app_db, workspace_id=ws_by_admin_a.id,
                     decision="approve_with_results", actor=admin_a)

    # Başka bir admin onaylayabilmeli
    sonuc = await decide(app_db, workspace_id=ws_by_admin_a.id,
                         decision="approve_with_results", actor=admin_b)
    assert sonuc.new_status == "approved_with_results"


@pytest.mark.asyncio
async def test_admin_riskli_sorgusu_onaya_duser(query_service, admin_user):
    """is_db_admin bypass'ı kalktı: admin de onay beklemeli."""
    sonuc = await query_service.execute_query(
        user=admin_user, query="DELETE FROM Musteriler", ...
    )
    assert sonuc["status"] == "waiting_for_approval"
```

### Çağıranların değişimi

**Web** — `admin/services.py`: `approve` ve `reject_query_by_workspace_id`
gövdelerini silin, `approval.service.decide()` çağrısına indirin. Sözlük döndürmeyi
bırakıp exception fırlatsınlar (router zaten `BaseServiceException`'ı çeviriyor).

**Slack** — `listener.py`: iki handler da aşağıdaki sıraya geçmeli. Sıra önemli,
çünkü ③ numaralı sorun tam olarak sıradan kaynaklanıyor:

```python
async def handle_approve_with_results(self, ack, body, respond):
    await ack()
    slack_user_id = body["user"]["id"]
    request_id    = body["actions"][0]["value"]

    # 1) Kimlik çöz — başarısızsa hiçbir şey yapma
    try:
        approver_username, approver_slack_id = await self._resolve_approver(slack_user_id)
    except ValueError as e:
        await respond(replace_original=False, text=f"⛔ Approval blocked: {e}")
        return

    # 2) Slack kullanıcısını GERÇEK bir WebQuery kullanıcısına bağla.
    #    _resolve_approver eşleşme bulamazsa e-posta dizesi döndürüyor —
    #    o dize ile onay VERİLEMEZ. Yetki kontrolü bir User nesnesi ister.
    actor = await self._lookup_webquery_user(approver_username)
    if actor is None:
        await respond(
            replace_original=False,
            text="⛔ Bu Slack hesabı bir WebQuery kullanıcısıyla eşleşmiyor; "
                 "onay veremezsiniz.",
        )
        return

    # 3) Kararı ver — ADMIN kontrolü, atomik geçiş ve denetim kaydı decide() içinde
    try:
        outcome = await decide(
            self.app_db,
            workspace_id=await self._workspace_id_for(request_id),
            decision="approve_with_results",
            actor=actor,
            actor_slack_id=approver_slack_id,
        )
    except BaseServiceException as e:
        # Yarışı kaybettik, yetki yok, ya da istek zaten karara bağlanmış.
        await respond(replace_original=False, text=f"⛔ {e.message}")
        return

    # 4) Kullanıcıya ANCAK ŞİMDİ haber ver — yazma başarılı olduktan sonra.
    await respond(
        replace_original=True, blocks=[],
        text=f"✅ Query approved by <@{slack_user_id}>. (ID: {request_id})",
    )
```

Dikkat edilecek üç nokta:

1. **`respond` en sona taşındı.** Artık "onaylandı" mesajı yalnızca veritabanı
   yazması gerçekten commit edildiyse gidiyor.
2. **Hata yolları `replace_original=False` kullanıyor** — orijinal mesaj ve
   butonlar duruyor, böylece yetkili biri sonra basabiliyor.
3. **`actor` bir `User` nesnesi olmak zorunda.** `decide()` içindeki ADMIN kontrolü
   `UserDatabaseAssociation`'a bakıyor; elinizde sadece e-posta dizesi varsa o
   kontrol yapılamaz, o yüzden erken reddediliyor.

Ayrıca iki küçük yardımcı gerekiyor:

```python
async def _lookup_webquery_user(self, username_or_email: str) -> User | None:
    """Onay verenin gerçek WebQuery hesabını döndürür; yoksa None."""
    async with self.app_db.get_app_db() as session:
        return (await session.execute(
            select(User).where(
                (User.username == username_or_email) | (User.email == username_or_email)
            )
        )).scalars().first()


async def _workspace_id_for(self, query_uuid: str) -> int:
    """Slack butonu query_uuid taşıyor; decide() workspace_id istiyor."""
    async with self.app_db.get_app_db() as session:
        ws = (await session.execute(
            select(Workspace)
            .join(QueryData, Workspace.query_id == QueryData.id)
            .where(QueryData.uuid == query_uuid)
        )).scalars().first()
        if ws is None:
            raise BaseServiceException("Bu onay isteği artık geçerli değil.")
        return ws.id
```

Alternatif: Slack mesajının `value` alanına `query_uuid` yerine `workspace_id`
koyun — o zaman `_workspace_id_for` gerekmez. Ama mevcut mesajlar `query_uuid`
taşıdığı için geçiş sırasında ikisini de desteklemek daha güvenli.

### Doğrulama

```python
@pytest.mark.asyncio
async def test_webquery_hesabi_olmayan_slack_kullanicisi_onaylayamaz(...):
    """En kritik test: ① numaralı açığın kapandığını doğrular."""
    ...

@pytest.mark.asyncio
async def test_admin_olmayan_kullanici_slackten_onaylayamaz(...):
    """WebQuery hesabı var ama o veritabanında ADMIN değil → reddedilmeli."""
    ...

@pytest.mark.asyncio
async def test_web_onayi_actionlogging_e_yaziliyor(...):
    """② numaralı boşluk: web'den onaylayınca approved_by dolmalı."""
    ...

@pytest.mark.asyncio
async def test_yazma_basarisizsa_slack_onaylandi_demiyor(...):
    """③ numaralı sıra hatası: decide() patlarsa respond 'approved' dememeli."""
    ...
```

**Efor:** ~1 gün (1.2 bu sürenin içinde).

### ✅ Blok 2 geçiş kontrolü

Bu kontrol geçmeden sonraki bloğa başlamayın.

`tests/integration/test_approval_race.py` geçiyor: aynı workspace'i aynı anda onaylayıp
reddetmeye çalışan iki istekten biri 409 alıyor. Slack'ten, o veritabanında ADMIN
olmayan biri onaylayamıyor. Bir kullanıcıya yetki verin — `AuditLog`'da
`grant_database_access` satırını görün.

---

# Blok 3 — Kimlik yaşam döngüsü

**Süre:** ~3 gün

Yalnızca `4.1`'e bağlı, başka hiçbir şeye. **Zaman darsa ertelenebilir** — Blok 4'ün
önünde durmuyor.

## Adım 12 · `2.1` — Kullanıcı devre dışı bırakma

**Neden burada:** `4.1`'e bağlı (yeni kolon). Bu blok Blok 4'ün önünde durmuyor —
zaman darsa ertelenebilir. Ama `2.1` olmadan bir kullanıcıyı sistemden çıkarmanın
yolu yok, o yüzden çok uzun ertelemeyin.

### Problem

`User` modelinde `is_active` yok. Bir kullanıcıyı çıkarmanın tek yolu satırı silmek (FK'ler yüzünden zor) — ve elindeki token 24 saat daha çalışır.

### Çözüm

```python
class User(Base):
    __tablename__ = 'Users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String)
    email = Column(String(50), unique=True)

    # --- YENİ: yaşam döngüsü ---
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    disabled_at = Column(AppDateTime, nullable=True)
    disabled_by = Column(String(50), nullable=True)
    created_at = Column(AppDateTime, nullable=False, default=datetime.now)
    last_login_at = Column(AppDateTime, nullable=True)
```

`authentication/services.py:get_current_user` — kullanıcı çekildikten sonra:

```python
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
        user = result.scalars().first()

    if user is None:
        raise credentials_exception

    # Devre dışı bırakılmış hesap, geçerli token'a rağmen BİR SONRAKİ İSTEKTE
    # kilitlenir. Token'ın süresinin dolmasını beklemek offboarding değildir.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hesabınız devre dışı bırakılmış.",
        )

    return user
```

`authentication/router.py:login` — giriş kapısında da:

```python
        if not authenticated_user or not authenticated_user.check_password(user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")

        if not authenticated_user.is_active:
            # Aynı jenerik mesaj: hesabın var olup olmadığını sızdırmıyoruz.
            raise HTTPException(status_code=400, detail="Invalid email or password")
```

Admin endpoint'i (`admin/router.py`):

```python
@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: int, request: Request,
    admin_user: User = Depends(admin_required),
    app_db: AppDatabase = Depends(get_app_db),
):
    """Kullanıcıyı devre dışı bırakır ve tüm oturumlarını sonlandırır."""
    client_ip = request.client.host if request.client else None
    async with app_db.get_app_db() as db:
        async with db.begin():
            target = await db.get(User, user_id)
            if not target:
                raise HTTPException(404, "Kullanıcı bulunamadı")
            if target.id == admin_user.id:
                raise HTTPException(400, "Kendi hesabınızı devre dışı bırakamazsınız")

            target.is_active = False
            target.disabled_at = datetime.now()
            target.disabled_by = admin_user.username

            await log_in(db, actor=admin_user, action="user_disabled",
                         target_type="user", target_id=user_id,
                         details={"username": target.username},
                         client_ip=client_ip)
    return {"success": True}
```

**Efor:** ~3 saat.

## Adım 13 · `2.2` — Kaydı kapat

**Neden burada:** Tamamen bağımsız. `2.1` ve `2.4` ile paralel yürütülebilir.

### Problem

`POST /api/register` herkese açık. Bir SQL gateway'inde bu bir varsayım hatası.

### Çözüm — iki seçenek

**Seçenek A (basit, önerilen): kaydı tamamen kapat, kullanıcıyı admin yaratsın.**

```python
# authentication/config.py
SELF_REGISTRATION_ENABLED = os.getenv("SELF_REGISTRATION_ENABLED", "false").lower() == "true"
```

```python
# authentication/router.py:78
@router.post("/register")
@limiter.limit(config.RATE_LIMITER)
async def register(...):
    if not config.SELF_REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Kendi kendine kayıt kapalı. Hesap için yöneticinize başvurun."
        )
    ...
```

Ve `admin/router.py`'a kullanıcı yaratma endpoint'i:

```python
@router.post("/users")
async def create_user(
    body: schemas.UserCreate, request: Request,
    admin_user: User = Depends(admin_required),
    app_db: AppDatabase = Depends(get_app_db),
):
    """Yönetici tarafından kullanıcı oluşturma."""
    client_ip = request.client.host if request.client else None
    async with app_db.get_app_db() as db:
        async with db.begin():
            exists = (await db.execute(
                select(User).where(User.email == body.email)
            )).scalars().first()
            if exists:
                raise HTTPException(400, "Bu e-posta zaten kayıtlı")

            new_user = User(username=body.username, email=body.email)
            new_user.set_password(body.password)   # politika kontrolü içinde
            db.add(new_user)
            await db.flush()

            await log_in(db, actor=admin_user, action="user_created",
                         target_type="user", target_id=new_user.id,
                         details={"username": body.username, "email": body.email},
                         client_ip=client_ip)
    return {"success": True, "user_id": new_user.id}
```

**Seçenek B: e-posta alan adı allowlist'i** — kayıt açık kalsın ama sadece şirket alan adı:

```python
ALLOWED_EMAIL_DOMAINS = [
    d.strip().lower() for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",") if d.strip()
]

# register içinde:
    if ALLOWED_EMAIL_DOMAINS:
        domain = user.email.rsplit("@", 1)[-1].lower()
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise HTTPException(403, "Bu e-posta alan adı ile kayıt yapılamaz.")
```

Yeni kullanıcı yine hiçbir DB'ye bağlı olmadığı için sorgu çalıştıramaz — ama artık sisteme rastgele hesap da girmez.

**Efor:** ~2 saat.

## Adım 14 · `2.4` — Kullanıcı adı bazlı giriş kısıtlaması

**Neden burada:** Tamamen bağımsız. `2.1` ve `2.2` ile paralel yürütülebilir.

### Problem

`slowapi` IP bazlı, 3/dakika. Reverse proxy arkasında tüm istekler tek IP'den görünür. Kullanıcı adı bazlı sayaç yok.

### Çözüm

`common/login_throttle.py`:

```python
"""
Giriş denemesi kısıtlayıcı — kullanıcı adı VE IP bazlı kayan pencere.

Bellek içi ve process başına. Tek process çalışan bir kurulum için yeterli;
çok process'e geçilirse tabloya taşınmalı (not: Redis de olur).

KDF'DEN ÖNCE kontrol edilir: kilitlenmiş bir saldırgan bcrypt CPU'sunu da
yakamamalı — rounds=14 ile bu tek başına bir DoS vektörüdür.
"""
import os
import threading
import time
from collections import deque

_LOCK = threading.Lock()
_FAILURES: dict[str, deque] = {}
_MAX_KEYS = 20_000

MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_MINUTES", "15")) * 60


def _prune(key: str, now: float) -> deque:
    q = _FAILURES.get(key)
    if q is None:
        q = _FAILURES[key] = deque()
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if not q:
        _FAILURES.pop(key, None)
    return q


def retry_after_seconds(*keys: str) -> int:
    """Verilen anahtarlardan biri doluysa kaç saniye beklenmesi gerektiği, yoksa 0."""
    now = time.time()
    worst = 0
    with _LOCK:
        for key in keys:
            q = _prune(key, now)
            if len(q) >= MAX_FAILURES:
                wait = int(WINDOW_SECONDS - (now - q[0])) + 1
                worst = max(worst, wait)
    return worst


def record_failure(*keys: str) -> None:
    now = time.time()
    with _LOCK:
        if len(_FAILURES) > _MAX_KEYS:
            for k in list(_FAILURES):
                _prune(k, now)
        for key in keys:
            _prune(key, now).append(now)


def clear(key: str) -> None:
    """Başarılı girişte kullanıcı sayacını sıfırla — IP'yi DEĞİL
    (aynı adresten başka hesaplara saldırı sürüyor olabilir)."""
    with _LOCK:
        _FAILURES.pop(key, None)
```

`login` içinde:

```python
from common import login_throttle

@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(user, response, request, app_db=Depends(get_app_db)):
    client_ip = request.client.host if request.client else "unknown"
    ukey, ipkey = f"u:{user.email.lower()}", f"ip:{client_ip}"

    # bcrypt'ten ÖNCE
    wait = login_throttle.retry_after_seconds(ukey, ipkey)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Çok fazla başarısız deneme. ~{max(1, wait // 60)} dakika sonra tekrar deneyin.",
        )

    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user = result.scalars().first()

    if not authenticated_user or not authenticated_user.check_password(user.password) \
            or not authenticated_user.is_active:
        login_throttle.record_failure(ukey, ipkey)
        raise HTTPException(status_code=400, detail="Invalid email or password")

    login_throttle.clear(ukey)
    ...
```

**Efor:** ~2 saat.

## Adım 15 · `2.3` — Kısa access token + refresh token

**Neden burada:** Bloğun en büyük maddesi ve tek başına duruyor. Oturum iptali
gerçekten gerekiyorsa yapın; gerekmiyorsa Blok 4'ten **sonraya** bırakın — hiçbir
şeyin önünde durmuyor.

Bu, Faz 2'nin en büyük parçası ve **oturum iptali için ön koşul**.

### Problem

24 saatlik tek token. Çalınırsa 24 saat geçerli. "Bu kullanıcının oturumunu kapat" komutu yazılamıyor çünkü sunucuda oturum diye bir kayıt yok.

### Çözüm

**Yeni model** (`app_database/models.py`):

```python
class UserSession(Base):
    """
    Sunucu tarafı oturum kaydı.

    Access token kısa ömürlü ve durumsuzdur (JWT). Refresh token uzun ömürlü,
    opak ve BU TABLODA tutulur — dolayısıyla iptal edilebilir. Token'ın
    kendisi değil, SHA-256 özeti saklanır: veritabanı sızarsa token'lar
    kullanılamaz.
    """
    __tablename__ = "UserSessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False, index=True)

    refresh_hash = Column(String(64), nullable=False, unique=True, index=True)
    prev_refresh_hash = Column(String(64), nullable=True, index=True)
    last_refresh_at = Column(AppDateTime, nullable=True)

    created_at = Column(AppDateTime, nullable=False, default=datetime.now)
    expires_at = Column(AppDateTime, nullable=False, index=True)
    revoked_at = Column(AppDateTime, nullable=True, index=True)
    revoked_reason = Column(String(200), nullable=True)

    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(300), nullable=True)
```

**Yeni servis** (`authentication/sessions.py`):

```python
"""
Oturum katmanı: kısa JWT + veritabanı destekli refresh token.

TASARIM:
  • access token 20 dakika, durumsuz, her istekte imza+exp+iptal kontrolü
  • refresh token 12 saat, opak, tek kullanımlık, rotasyonlu
  • rotasyonda YENİDEN DOĞRULAMA: kullanıcı hâlâ aktif mi?
  • iptal = revoked_at damgası → bir sonraki istekte etkili

Neden tek kullanımlık + tekrar tespiti:
  Çalınan bir refresh token, meşru kullanıcı bir sonraki yenilemeyi yaptığında
  geçersizleşir. Saldırgan onu tekrar kullanmaya çalıştığında "süperseded hash"
  eşleşir → hırsızlık şüphesi → tüm oturum iptal edilir.

Neden grace penceresi:
  İki sekme aynı anda yenilerse ikinci istek de "süperseded hash" ile gelir.
  Bu hırsızlık değil, yarış. 30 saniyelik pencere bunu soğurur; uzun süredir
  rotate edilmiş bir token hâlâ yakalanır.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, UTC
from typing import Optional

from jose import jwt
from sqlalchemy import select, update

from app_database.models import User, UserSession
from authentication import config

ACCESS_TTL_MINUTES = int(__import__("os").getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TTL_HOURS = int(__import__("os").getenv("REFRESH_TOKEN_EXPIRE_HOURS", "12"))
REFRESH_GRACE_SECONDS = int(__import__("os").getenv("REFRESH_GRACE_SECONDS", "30"))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_access(user_id: int, session_id: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": session_id,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TTL_MINUTES),
        },
        config.SECRET_KEY,
        algorithm=config.ALGORITHM,
    )


async def create_session(app_db, user_id: int, client_ip: str | None,
                         user_agent: str | None) -> tuple[int, str]:
    """Yeni oturum yaratır. (session_id, refresh_token) döner."""
    token = secrets.token_urlsafe(48)
    async with app_db.get_app_db() as db:
        async with db.begin():
            sess = UserSession(
                user_id=user_id,
                refresh_hash=_hash(token),
                expires_at=datetime.now() + timedelta(hours=REFRESH_TTL_HOURS),
                client_ip=client_ip,
                user_agent=(user_agent or "")[:300],
            )
            db.add(sess)
            await db.flush()
            return sess.id, token


async def session_alive(app_db, session_id: int, user_id: int) -> bool:
    """
    Her istekte çağrılan iptal kontrolü — tek indexli sorgu.

    `user_id` de kontrol ediliyor: token hem `sub` hem `sid` taşır ve bu ikisinin
    birbirine ait olduğunu doğrulayan başka hiçbir şey yok. İmza anahtarı
    olmadan sahte token üretilemez, ama tek engelin imza olmasını istemiyoruz.
    """
    async with app_db.get_app_db() as db:
        row = (await db.execute(
            select(UserSession.id).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(),
            )
        )).first()
        return row is not None


async def rotate_refresh(app_db, refresh_token: str) -> Optional[dict]:
    """
    Refresh token'ı doğrular ve döndürür.

    Dönüş:
      {"session_id", "user_id", "refresh_token"}  → başarı
      {"reuse": True}                             → tekrar tespit edildi, oturum iptal
      None                                        → bilinmeyen/süresi dolmuş/iptal
    """
    old_hash = _hash(refresh_token)
    new_token = secrets.token_urlsafe(48)
    now = datetime.now()

    async with app_db.get_app_db() as db:
        async with db.begin():
            # 1) Normal yol
            res = await db.execute(
                update(UserSession)
                .where(UserSession.refresh_hash == old_hash,
                       UserSession.revoked_at.is_(None),
                       UserSession.expires_at > now)
                .values(refresh_hash=_hash(new_token),
                        prev_refresh_hash=old_hash,
                        last_refresh_at=now)
            )
            if res.rowcount == 1:
                sess = (await db.execute(
                    select(UserSession).where(
                        UserSession.refresh_hash == _hash(new_token))
                )).scalars().first()
                return {"session_id": sess.id, "user_id": sess.user_id,
                        "refresh_token": new_token}

            # 2) Grace penceresi — iki sekme yarışı
            grace_cutoff = now - timedelta(seconds=REFRESH_GRACE_SECONDS)
            res = await db.execute(
                update(UserSession)
                .where(UserSession.prev_refresh_hash == old_hash,
                       UserSession.revoked_at.is_(None),
                       UserSession.expires_at > now,
                       UserSession.last_refresh_at > grace_cutoff)
                .values(refresh_hash=_hash(new_token),
                        prev_refresh_hash=old_hash,
                        last_refresh_at=now)
            )
            if res.rowcount == 1:
                sess = (await db.execute(
                    select(UserSession).where(
                        UserSession.refresh_hash == _hash(new_token))
                )).scalars().first()
                return {"session_id": sess.id, "user_id": sess.user_id,
                        "refresh_token": new_token}

            # 3) Tekrar tespiti — grace dışında süperseded hash
            res = await db.execute(
                update(UserSession)
                .where(UserSession.prev_refresh_hash == old_hash,
                       UserSession.revoked_at.is_(None))
                .values(revoked_at=now,
                        revoked_reason="refresh token tekrar kullanımı tespit edildi")
            )
            if res.rowcount > 0:
                return {"reuse": True}

    return None


async def revoke_session(app_db, session_id: int, reason: str) -> None:
    async with app_db.get_app_db() as db:
        async with db.begin():
            await db.execute(
                update(UserSession)
                .where(UserSession.id == session_id,
                       UserSession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(), revoked_reason=reason)
            )


async def revoke_user_sessions(app_db, user_id: int, reason: str) -> int:
    """Bir kullanıcının TÜM oturumlarını sonlandırır — acil durum düğmesi."""
    async with app_db.get_app_db() as db:
        async with db.begin():
            res = await db.execute(
                update(UserSession)
                .where(UserSession.user_id == user_id,
                       UserSession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(), revoked_reason=reason)
            )
            return res.rowcount or 0
```

**Router değişiklikleri:**

```python
# authentication/router.py

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

def _set_session_cookies(response: Response, access: str, refresh: str) -> None:
    secure = os.getenv("COOKIE_SECURE", "False").lower() == "true"
    response.set_cookie(
        key=ACCESS_COOKIE, value=access,
        httponly=True, samesite="strict", secure=secure,
        max_age=sessions.ACCESS_TTL_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE, value=refresh,
        httponly=True, samesite="strict", secure=secure,
        max_age=sessions.REFRESH_TTL_HOURS * 3600,
        path="/api",          # refresh SADECE /api altına gider
    )


@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(user, response, request, app_db=Depends(get_app_db)):
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user = result.scalars().first()

    if not authenticated_user or not authenticated_user.check_password(user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    if not authenticated_user.is_active:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    client_ip = request.client.host if request.client else "unknown"
    session_id, refresh = await sessions.create_session(
        app_db, authenticated_user.id, client_ip,
        request.headers.get("user-agent"),
    )
    access = sessions.mint_access(authenticated_user.id, session_id)
    _set_session_cookies(response, access, refresh)

    await app_db.create_login_log(user_id=authenticated_user.id, client_ip=client_ip)
    return {"access_token": access}


@router.post("/refresh")
async def refresh_session(request: Request, response: Response,
                          app_db: AppDatabase = Depends(get_app_db)):
    """
    Yeniden doğrulama kontrol noktası.
    Sadece token yenilemez — kullanıcının HÂLÂ yetkili olduğunu da doğrular.
    """
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(401, "Refresh token yok")

    rotated = await sessions.rotate_refresh(app_db, token)
    if rotated is None:
        raise HTTPException(401, "Oturum süresi doldu")
    if rotated.get("reuse"):
        raise HTTPException(401, "Güvenlik nedeniyle oturum sonlandırıldı. Tekrar giriş yapın.")

    # Kullanıcı hâlâ aktif mi? Yenileme, offboarding'in etkili olduğu andır.
    async with app_db.get_app_db() as db:
        user = await db.get(User, rotated["user_id"])
    if user is None or not user.is_active:
        await sessions.revoke_session(app_db, rotated["session_id"], "hesap devre dışı")
        raise HTTPException(401, "Hesabınız devre dışı bırakılmış")

    access = sessions.mint_access(rotated["user_id"], rotated["session_id"])
    _set_session_cookies(response, access, rotated["refresh_token"])
    return {"ok": True}


@router.post("/logout")
async def logout(response, request, current_user=Depends(get_current_user),
                 app_db=Depends(get_app_db), db_provider=Depends(get_db_provider)):
    # Sunucu tarafı oturumu iptal et — sadece cookie silmek yetmez.
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            if payload.get("sid"):
                await sessions.revoke_session(app_db, int(payload["sid"]), "logout")
        except Exception:
            logger.warning("logout: token çözülemedi", exc_info=True)

    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api")
    await app_db.update_login_log(user_id=current_user.id)
    return {"message": "Successfully logged out"}
```

`get_current_user` içinde `sid` kontrolü:

```python
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if user_id is None or session_id is None:
        raise credentials_exception

    if not await sessions.session_alive(app_db, int(session_id), int(user_id)):
        raise credentials_exception
```

**Frontend tarafı** (`frontend/services/api.ts`) — 401 alınca bir kez refresh dene:

```typescript
let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  // Eşzamanlı 401'lerin hepsi tek bir refresh isteğine yönlensin,
  // yoksa N istek N rotasyon tetikler ve tekrar-tespiti tetiklenir.
  if (!refreshing) {
    refreshing = fetch("/api/refresh", { method: "POST", credentials: "include" })
      .then((r) => r.ok)
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

export async function apiFetch(input: RequestInfo, init: RequestInit = {}) {
  let res = await fetch(input, { ...init, credentials: "include" });
  if (res.status === 401 && !String(input).includes("/api/refresh")) {
    if (await tryRefresh()) {
      res = await fetch(input, { ...init, credentials: "include" });
    } else {
      window.location.href = "/login";
    }
  }
  return res;
}
```

> **Dikkat:** Refresh eşzamanlılığı kritik. Sekmeli kullanımda `refreshing` promise paylaşımı olmazsa grace penceresi bile yetmeyebilir. Yukarıdaki tek-uçuş (single-flight) deseni bunu çözer.

**Efor:** ~2 gün (frontend dahil).

### ✅ Blok 3 geçiş kontrolü

Bu kontrol geçmeden sonraki bloğa başlamayın.

Devre dışı bırakılan bir kullanıcının açık oturumu bir sonraki istekte reddediliyor.
Kapalı kayıt uç noktası 403 dönüyor.

---

# Blok 4 — Savunma derinliği

**Süre:** ~4,5 gün

**Asıl getiri burada.** Sadece bir blok yapacaksanız bu blok. Uygulama katmanını
"tek savunma" olmaktan çıkarır.

## Adım 16 · `3.1` — Rol bazlı veritabanı kimlik bilgileri ⭐

**Önkoşulları:** `4.1` (altı yeni kolon), `0.1` (şifreler gerçek bir Fernet anahtarıyla
şifrelensin), `4.4` (`max_tier`).

**Karar kaydı:** OQ-2026-002 cevaplandı. Bu adımda veritabanı başına ve role göre
ayrı hedef DB kimlik bilgileri kullanılacak; hesapları DBA hedef sunucuda manuel
oluşturacak, admin gerçek bilgileri WebQuery'ye girecek, WebQuery ise şifreleri
şifreli saklayacak. Ayrıntılar: `docs/specs/SPEC-0002` ve `docs/adr/ADR-0005`.

**Bu madde tek parça yapılmalı.** İçindeki `4b` ayrı bir madde gibi görünüyor ama
değil: kademe cache anahtarına eklenmezse bir kullanıcının `rw` sorgusu engine'i
cache'e koyar, sonraki `ro` sorgusu aynı anahtarı bulur ve **yazma yetkili bağlantıyı
kullanır.** Ayrımın tamamı o satıra bağlı.

**Kendi içinde kademeli yürütün** — aşağıdaki 7 adımlı geçiş stratejisini izleyin.
3. adım sırasında sistem karışık modda çalışır; admin listesine "kimlik bilgisi:
kademeli / merkezi" sütunu eklemeden 4. adıma geçmeyin.

**Açtığı kapı:** `4.5`, `3.4`

**Listedeki en yüksek getirili tek değişiklik bu.**

### Problem

```python
# database_provider/database.py:83-85
username=CENTRAL_DB_USER,
password=CENTRAL_DB_PASSWORD,
```

Her kullanıcı, her rol, her sorgu → aynı yüksek yetkili hesap. `check_permissions_match_role()` bir READER'ın DELETE atmasını engelliyor; bu kontrol atlanırsa **arkasında hiçbir şey yok**.

### Neden bu kadar önemli

Bu değişiklik yapıldıktan sonra, Faz 3'ün geri kalanındaki tüm analyzer iyileştirmeleri **ikinci savunma hattı** olur. Bir parser boşluğu, bir yeni endpoint, bir refactor hatası — hiçbiri tek başına yıkıcı olmaz, çünkü bağlantının kendisi yetkisiz.

### Önce şu ayrım: hangi veritabanı?

Bu maddede en sık karışan şey bu, netleştirmeden devam etmeyin. Ortada **iki farklı
veritabanı** var:

| | **WebQuery'nin kendi DB'si** | **Hedef veritabanları** |
|---|---|---|
| İçinde ne var | `Users`, `Databases`, `QueryData`, `Workspaces`, `AuditLog` | Müşteri / üretim verisi |
| Sahibi kim | WebQuery | Başkası (DBA ekibi, müşteri) |
| Şemasını kim yönetir | WebQuery — **Alembic burayı migrate eder** | WebQuery **değil** |
| Kim bağlanır | Uygulamanın kendisi | Kullanıcı sorguları |

`Databases` tablosu, hedef veritabanlarının **kayıt defteri**. Her satır bir hedef
DB'yi tarif ediyor: hangi sunucuda, hangi isimde, hangi teknolojide — ve **hangi
hesapla bağlanılacak**.

Yani aşağıda modele eklenen `username_ro` / `password_ro`, WebQuery'nin kendi
DB'sinde *saklanan* ama **hedef DB'ye ait** kimlik bilgileridir. Depolandığı yer ile
ait olduğu yer farklı.

**Alembic hedef veritabanına dokunmaz.** Bu maddede Alembic'in yaptığı tek şey:

```sql
ALTER TABLE Databases ADD COLUMN username_ro VARCHAR(100) NULL;
-- ... ve diğer üç kolon. Hepsi WebQuery'nin KENDİ veritabanında.
```

Yani "artık bu bilgiyi tutabiliyorum" demek. Aşağıdaki `CREATE LOGIN` / `CREATE ROLE`
scriptleri **migration değildir** — tamamen ayrı, elle çalıştırılan operasyon
adımlarıdır.

### O hesapları kim yaratıyor?

**İnsan. Hedef veritabanının DBA'i. Elle. Her hedef DB için bir kere.**

WebQuery yaratmamalı, ve bu bir kolaycılık değil — tasarımın tam merkezi:

> `CREATE LOGIN` ve `GRANT` çalıştırabilmek için yüksek yetkili bir hesap gerekir.
> WebQuery'nin elinde öyle bir hesap olsaydı, **kendine istediği yetkiyi
> verebilirdi.** O zaman "ro hesabı yazamaz" garantisi çöker — çünkü uygulama
> istediği an ro hesabına yazma yetkisi verebilir.

Bu maddenin tüm amacı *"uygulama katmanı yanılsa bile veritabanı reddeder"*
garantisini kurmak. Hesap yaratma yetkisini uygulamaya verirseniz o garanti kalmaz.
Kural tek cümle: **WebQuery, kendi yetkisini değiştirebilecek bir hesap tutmamalı.**

### Uçtan uca akış

```
1. DBA        hedef sunucuda provisioning scriptini çalıştırır
              → webquery_ro ve webquery_rw hesapları oluşur

2. DBA        iki (kullanıcı, şifre) çiftini güvenli kanaldan admin'e verir
              (şifre yöneticisi, kasa — e-posta/Slack DEĞİL)

3. Admin      WebQuery'de "Veritabanı Ekle" formunu doldurur,
              dört değeri YAPIŞTIRIR

4. WebQuery   şifreleri EncryptedText ile şifreleyip Databases tablosuna yazar

5. Sorgu anı  analyzer kademeyi belirler (ro / rw)
              → o kademenin hesabıyla bağlanılır
```

WebQuery'nin sorumluluğu 4. ve 5. adımlar. 1–3 arası insan işi ve öyle kalmalı.

### Neden env değişkeni değil de tabloda?

Şu an tek merkezi hesap var, `CENTRAL_DB_USER` env'den okunuyor ve bu yeterli.
Bu maddeden sonra **her hedef DB'nin kendi iki hesabı** olacak: 20 hedef veritabanı
= 40 kimlik bilgisi. Üstelik yeni veritabanı çalışma anında ekleniyor — env
değişkeni eklemek için uygulamayı yeniden başlatmak gerekirdi.

O yüzden kimlik bilgileri yapılandırmadan **veriye** dönüşüyor: satır başına bir
çift, `EncryptedText` ile şifreli.

> ### ⚠️ Bu madde 0.1'e bağlı — sırayı atlamayın
>
> `EncryptedText` şifreleme anahtarını env'den okuyor ve anahtar yoksa **sabit bir
> yedeğe** düşüyor (`app_database/models.py:51-55`).
>
> 0.1 yapılmadan 3.1 yapılırsa: veritabanı dökümü alan biri, kaynak kodda duran ve
> herkesin görebildiği sabit anahtarla **tüm hedef veritabanı şifrelerini** çözer.
> Bu durumda 3.1 güvenlik kazandırmaz — bütün üretim şifrelerini tek bir yerde
> toplayıp açık bir anahtarla kilitlemiş olur. Önceki durumdan **daha kötüdür**.

### Çözüm

**1. Veritabanı tarafında roller oluşturun** (hedef sunucularda, bir kereye mahsus):

```sql
-- SQL Server örneği. Her hedef veritabanı için.
CREATE LOGIN webquery_ro WITH PASSWORD = '<güçlü>';
CREATE LOGIN webquery_rw WITH PASSWORD = '<güçlü>';

USE [HedefVeritabani];
CREATE USER webquery_ro FOR LOGIN webquery_ro;
CREATE USER webquery_rw FOR LOGIN webquery_rw;

ALTER ROLE db_datareader ADD MEMBER webquery_ro;

ALTER ROLE db_datareader ADD MEMBER webquery_rw;
ALTER ROLE db_datawriter ADD MEMBER webquery_rw;
-- DDL yetkisi VERİLMİYOR: şema değişikliği bu yoldan yapılmaz.
```

```sql
-- PostgreSQL örneği
CREATE ROLE webquery_ro LOGIN PASSWORD '<güçlü>';
CREATE ROLE webquery_rw LOGIN PASSWORD '<güçlü>';

GRANT CONNECT ON DATABASE hedefdb TO webquery_ro, webquery_rw;
GRANT USAGE ON SCHEMA public TO webquery_ro, webquery_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO webquery_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO webquery_rw;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO webquery_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO webquery_rw;
```

**2. Model** (`app_database/models.py`):

```python
class Databases(Base):
    __tablename__ = "Databases"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    servername = Column(String(100), nullable=False)
    database_name = Column(String(100), nullable=False)
    technology = Column(String(100), nullable=False)
    uuid = Column(AppUUID, nullable=False, index=True, default=lambda: str(uuid.uuid4()))

    # --- Kademe bazlı kimlik bilgileri ---
    # DİKKAT: bunlar HEDEF veritabanına ait hesaplardır, WebQuery'nin kendi
    # veritabanına ait değil. Burada sadece SAKLANIYORLAR.
    #
    # Hesapları WebQuery yaratmaz — hedef sunucunun DBA'i elle yaratır ve
    # değerleri admin'e verir; admin "Veritabanı Ekle" formuna yapıştırır.
    # WebQuery'nin hesap yaratabilmesi için CREATE LOGIN yetkisi olan bir
    # hesap tutması gerekirdi; o hesapla kendi kısıtlarını da kaldırabilirdi
    # ve bu maddenin tüm anlamı kaybolurdu.
    #
    # Her kademe için AYRI hesap. Sorgu 'ro' sınıflanırsa yalnızca okuma
    # yetkisi olan hesapla bağlanılır — sınıflandırma yanlış olsa bile
    # veritabanı yazmayı reddeder.
    username_ro = Column(String(100), nullable=True)
    password_ro = Column(EncryptedText, nullable=True)
    username_rw = Column(String(100), nullable=True)
    password_rw = Column(EncryptedText, nullable=True)

    # DDL kademesi — VERİTABANI BAZINDA OPSİYONEL, varsayılanı NULL.
    # NULL = "bu veritabanında DDL yapılamaz" ve doğru varsayılan budur.
    # Bir webquery_ddl hesabı yaratmak, uygulamanın sürekli elinin altında
    # DROP TABLE yetkisi olan bir hesap bulundurması demektir — bu maddenin
    # kaldırdığı riski daraltılmış hâlde geri getirir. WebQuery bir sorgu
    # aracıdır, şema göçü aracı değil; şema değişikliği DBA'in normal
    # değişiklik sürecinden geçmelidir, bir web formundan değil.
    # Yalnızca gerçekten gerekiyorsa, ilgili veritabanı için doldurun.
    username_ddl = Column(String(100), nullable=True)
    password_ddl = Column(EncryptedText, nullable=True)

    # Geriye dönük uyumluluk (kaldırılacak).
    #
    # Bu iki kolon şu an DOLU ama İÇİ BOŞ. admin/services.py:504
    # generate_secure_credentials() ile "webquery_user_a3f9c1b2" gibi rastgele
    # bir kullanıcı adı ve rastgele bir şifre üretip buraya yazıyor — ama hedef
    # veritabanında öyle bir hesap YOK, kimse yaratmıyor, ve hiçbir kod bu
    # değerleri geri okumuyor. Bağlantı hâlâ env'deki CENTRAL_DB_USER ile
    # kuruluyor (database_provider/database.py:79-86).
    #
    # Yani model kimlik bilgisi tutuyormuş gibi görünüyor, gerçekte tutmuyor.
    # Bu madde onu gerçeğe çeviriyor: rastgele üretim kaldırılacak, yerine
    # DBA'in verdiği gerçek değerler alınacak.
    db_username = Column(String(100), nullable=True)
    db_password = Column(EncryptedText, nullable=True)

    __table_args__ = (
        UniqueConstraint("servername", "database_name", name="uq_server_database"),
    )
```

**3. Kademe çözümleme** (`query_execution/query_analyzer.py`'a ekleyin):

```python
    def required_tier(self, query: str, technology: str = "mssql") -> str:
        """
        Sorgunun ihtiyaç duyduğu en yüksek kademeyi döner: 'ro' | 'rw' | 'ddl'.

        ÖNEMLİ: Bu fonksiyon bir YETKİ kararı değildir, bir SINIFLANDIRMADIR.
        Parse edilemeyen sorgu 'ddl' döner (fail-closed) — 'ro' dönmek,
        bloke edilmiş bir sorguya en düşük kademeyi vermek olurdu.
        """
        dialect = self._dialect(technology)
        try:
            statements = sqlglot.parse(query.strip(), read=dialect)
        except Exception:
            return "ddl"      # fail-closed

        ddl_types = (exp.Drop, exp.Create, exp.AlterTable, exp.TruncateTable)
        dml_types = (exp.Insert, exp.Update, exp.Delete, exp.Merge)

        tier = "ro"
        for stmt in statements:
            if not stmt:
                continue
            if isinstance(stmt, ddl_types) or any(True for _ in stmt.find_all(ddl_types)):
                return "ddl"
            if isinstance(stmt, dml_types) or any(True for _ in stmt.find_all(dml_types)):
                tier = "rw"
            # SELECT ... INTO yeni tablo yaratır — SELECT ile başlar ama DDL'dir.
            if isinstance(stmt, exp.Select) and stmt.args.get("into"):
                return "ddl"
        return tier
```

**4. Provider** (`database_provider/database.py`):

```python
    @asynccontextmanager
    async def get_session(self, user: models.User, db_uuid: str, tier: str = "ro"):
        """
        Kademe eşleşmeli bağlantı sağlar.

        `tier` sorgunun sınıflandırmasıdır: 'ro' salt okuma hesabıyla,
        'rw' yazma hesabıyla bağlanır. 'ddl' için hesap YOK — şema
        değişikliği bu yoldan yapılmaz, isteyen DBA'ya gider.
        """
        if tier == "ddl":
            raise ValueError(
                "DDL sorguları WebQuery üzerinden çalıştırılamaz. "
                "Şema değişiklikleri için veritabanı ekibine başvurun."
            )
        if db_uuid not in self.db_by_uuid:
            raise ValueError(f"Database with UUID '{db_uuid}' not found.")

        db_entry = self.db_by_uuid[db_uuid]
        creds = self._credentials_for(db_uuid, tier)
        if creds is None:
            raise ValueError(
                f"Bu veritabanı için '{tier.upper()}' kademesinde kimlik bilgisi "
                f"tanımlı değil. Yöneticinize başvurun."
            )
        username, password = creds
        tech = db_entry["technology"]

        conn_str = create_connection_string(
            tech=tech, driver=get_driver_for_technology(tech),
            servername=db_entry["servername"], database=db_entry["database_name"],
            username=username, password=password,
        )
        # Cache anahtarı kademeyi de içermeli — yoksa 'ro' isteği
        # cache'teki 'rw' engine'ini bulur ve tüm ayrım çöker.
        engine = await self.engine_cache.get_engine(
            conn_str, db_uuid=db_uuid, tier=tier,
            connect_args=get_connect_args(tech, QUERY_TIMEOUT_SECONDS),
        )
        ...
```

> **Bu satır kritik:** kademe cache anahtarına girmezse, bir kullanıcının `rw` sorgusu engine'i cache'e koyar, sonraki `ro` sorgusu aynı anahtarı bulur ve **yazma yetkili bağlantıyı kullanır.** Tüm mekanizma buna bağlı.

### 4b. Engine cache'in de değişmesi gerekiyor

Kademeyi anahtara eklemek tek başına yetmiyor. `database_provider/engine_cache.py`
bu maddeyle birlikte dört yerden kırılıyor.

#### ① Kapasite matematiği üçe katlanıyor

`engine_cache.py:74-81` şu an her engine için:

```python
create_async_engine(url, pool_size=50, max_overflow=100, ...)
```

Yani engine başına hedef veritabanına **150 bağlantıya kadar**, ve `max_engines=100`.

```
ÖNCE:  N veritabanı  →  N engine
SONRA: N veritabanı  →  3N engine   (ro + rw + ddl)
```

30 hedef veritabanı = 30 yerine 90 engine ve aynı sunuculara **üç kat bağlantı**.

Bu sorun bugün de var — PostgreSQL'in varsayılan `max_connections` değeri 100'dür,
yani tek bir engine tam doluluğa giderse zaten sınırı aşar. Bu madde onu yaratmıyor,
**üçe katlıyor**. Havuz kademe bazlı olmalı, çünkü kademeler eşit yük taşımıyor:

```python
# Trafiğin neredeyse tamamı 'ro'. 'ddl' hem nadir hem de doğası gereği seri.
_POOL_BY_TIER = {
    "ro":  dict(pool_size=10, max_overflow=20),
    "rw":  dict(pool_size=5,  max_overflow=10),
    "ddl": dict(pool_size=1,  max_overflow=2),
}
```

`max_engines` de yeniden hesaplanmalı: `3 × beklenen_veritabanı_sayısı + pay`.
Hedef sunucunun `max_connections` değerini öğrenip toplam tavanın altında kaldığınızı
doğrulayın — bu bir tahmin işi değil, çarpma işlemi.

#### ② Geçersiz kılma artık zorunlu — daha önce değildi

Bu madde öncesinde kimlik bilgileri env'den geliyordu; değiştirmek uygulamayı yeniden
başlatmayı gerektiriyordu, o da cache'i zaten temizliyordu. Bu maddeden sonra kimlik
bilgileri `Databases` satırında ve **çalışma anında değiştirilebilir**.

Ama `engine_cache.py:66-69`:

```python
if cache_key in self._cache:
    self._cache[cache_key].last_accessed = datetime.now()
    return self._cache[cache_key].engine     # ← url TAMAMEN YOK SAYILIYOR
```

İsabet varsa yeni `url` çöpe gidiyor. Sonuç:

> `ro` şifresi sızdı, admin döndürdü. Cache'teki engine **sızmış şifreyle**
> bağlanmaya devam ediyor — TTL dolana kadar. Yeni şifre hiçbir işe yaramıyor.

Şifre döndürmenin tüm amacı bu senaryoydu ve cache onu etkisiz kılıyor.

#### ③ `owner_id` artık eşleşmiyor

`engine_cache.py:86` `owner_id=cache_key` atıyor; kademe eklenince bu
`"a3f9...:ro"` oluyor. `close_user_engines:159` ise `entry.owner_id == db_uuid`
karşılaştırıyor — çıplak uuid ile. Bu fonksiyon zaten bozuktu (4.5'e bakın:
`current_user.id` ile çağrılıyor), ama **düzeltilse bile** artık eşleşmez.

Bir veritabanının üç engine'ini birden bulabilmek için `db_uuid` ve `tier` ayrı
alanlar olmalı — anahtarı parse etmeye ya da prefix aramaya gerek kalmasın.

#### ④ Çözüm: kimlik bilgisi parmak izi

②'yi "her kimlik bilgisi değişiminde geçersiz kılmayı unutmayın" diyerek çözmek,
bu planın başka yerlerde kaçındığı türden bir çözüm olurdu — insan hafızasına bağlı.
Yapısal hâli, parmak izini entry'ye koyup isabet anında karşılaştırmak:

```python
@dataclass
class EngineCacheEntry:
    engine: AsyncEngine
    last_accessed: datetime = field(default_factory=datetime.now)
    db_uuid: Optional[str] = None    # ayrı alanlar — anahtar parse edilmesin
    tier: Optional[str] = None
    cred_fingerprint: str = ""       # bağlantı dizesinin hash'i


async def get_engine(self, url: str, db_uuid: str, tier: str, **kw) -> AsyncEngine:
    cache_key = f"{db_uuid}:{tier}"
    fingerprint = self._hash_key(url)      # şifreyi düz metin tutmaz

    async with self.lock:
        entry = self._cache.get(cache_key)

        if entry is not None:
            if entry.cred_fingerprint != fingerprint:
                # Kimlik bilgisi değişmiş. Eski engine geçersiz — kimsenin
                # açıkça geçersiz kılmasını beklemeden at.
                await entry.engine.dispose()
                del self._cache[cache_key]
                self._stats["engine_count"] -= 1
            else:
                entry.last_accessed = datetime.now()
                self._stats["request_count"] += 1
                return entry.engine

        if self._stats["engine_count"] >= self._max_engines:
            await self._evict_lru()

        engine = create_async_engine(
            url, pool_timeout=30, pool_recycle=1800, pool_pre_ping=False,
            **_POOL_BY_TIER[tier], **kw,
        )
        self._cache[cache_key] = EngineCacheEntry(
            engine=engine, db_uuid=db_uuid, tier=tier,
            cred_fingerprint=fingerprint,
        )
        self._stats["engine_count"] += 1
        self._stats["request_count"] += 1
        return engine


async def close_database_engines(self, db_uuid: str) -> int:
    """
    Bir veritabanının TÜM kademelerindeki engine'leri kapatır.
    Veritabanı silindiğinde veya kimlik bilgileri döndürüldüğünde çağrılır.

    Eski close_user_engines'in yerini alır — o fonksiyon owner_id'yi
    kullanıcı ID'siyle karşılaştırıyordu ve hiç eşleşmiyordu (4.5).
    """
    if not db_uuid:
        return 0
    async with self.lock:
        keys = [k for k, e in self._cache.items() if e.db_uuid == db_uuid]
        for key in keys:
            entry = self._cache.pop(key)
            await entry.engine.dispose()
            self._stats["engine_count"] -= 1
        if keys:
            logger.info("Kapatılan engine sayısı: %d (db_uuid=%s)", len(keys), db_uuid)
        return len(keys)
```

Parmak izi kontrolü, şifre döndürmeyi **bir sonraki sorguda** etkili kılıyor —
kimsenin bir yeri çağırmayı hatırlamasına gerek kalmadan. `close_database_engines`
yine de gerekli (veritabanı silinince bağlantıları hemen kapatmak için) ama artık
*doğruluğun* değil *hijyenin* parçası: unutulursa sistem yanlış çalışmaz, sadece
gereksiz bağlantı bir süre açık kalır.

**Doğrulama:**

```python
@pytest.mark.asyncio
async def test_kademeler_ayri_engine_alir(cache):
    ro = await cache.get_engine("postgresql+asyncpg://ro:p1@h/db", "uuid-1", "ro")
    rw = await cache.get_engine("postgresql+asyncpg://rw:p2@h/db", "uuid-1", "rw")
    assert ro is not rw, "kademeler aynı engine'i paylaşamaz"


@pytest.mark.asyncio
async def test_sifre_degisince_engine_yenilenir(cache):
    """Şifre döndürüldüğünde cache eski bağlantıyı vermemeli."""
    eski = await cache.get_engine("postgresql+asyncpg://ro:ESKI@h/db", "uuid-1", "ro")
    yeni = await cache.get_engine("postgresql+asyncpg://ro:YENI@h/db", "uuid-1", "ro")
    assert eski is not yeni, "değişen kimlik bilgisi eski engine'i geçersiz kılmalı"


@pytest.mark.asyncio
async def test_veritabani_kapatinca_tum_kademeler_gider(cache):
    await cache.get_engine("postgresql+asyncpg://ro:p@h/db", "uuid-1", "ro")
    await cache.get_engine("postgresql+asyncpg://rw:p@h/db", "uuid-1", "rw")
    await cache.get_engine("postgresql+asyncpg://ro:p@h/db2", "uuid-2", "ro")

    kapatilan = await cache.close_database_engines("uuid-1")
    assert kapatilan == 2
    assert cache.get_cache_stats()["engine_count"] == 1   # uuid-2 durmalı
```

**5. Servis** (`query_execution/services.py`):

```python
            # Kademe belirle
            required_tier = self.analyzer.required_tier(query, technology=technology)

            # Rol-kademe uyumu.
            #
            # DİKKAT: ADMIN burada veri kademesi VERMEZ. Aşağıdaki
            # "ADMIN iki şeyi birden ifade ediyor" bölümüne bakın —
            # ADMIN yönetişim rolüdür (onay verme, maskeleme yönetimi),
            # veri erişim rolü değil. Veri erişimi READER / WRITER / DDL
            # rolleriyle verilir ve bir kullanıcı ikisine birden sahip
            # olabilir: "ADMIN,READER" → onaylayabilir, sadece okuyabilir.
            # 4.4'teki common/roles.py kullanılır — bu mantığın ikinci bir
            # kopyası olmamalı. max_tier() ADMIN'i saymaz ve veri rolü hiç
            # yoksa None döner.
            role_max = roles.max_tier(user_role)
            if role_max is None:
                raise QueryAnalysisRejectedError(
                    "Bu veritabanında veri erişim rolünüz yok. "
                    "Yöneticinizden READER veya WRITER isteyin."
                )

            tier_rank = {"ro": 0, "rw": 1, "ddl": 2}
            if tier_rank[required_tier] > tier_rank[role_max]:
                raise QueryAnalysisRejectedError(
                    f"Bu sorgu '{required_tier.upper()}' yetkisi gerektiriyor, "
                    f"sizin en yüksek yetkiniz '{role_max.upper()}'."
                )

            # ... risk analizi, onay akışı ...

            async with self.database_provider.get_session(
                user=user, db_uuid=db_uuid, tier=required_tier
            ) as session:
                ...
```

### `add_database` de değişiyor

Şu an (`admin/services.py:504`) kimlik bilgisi **uyduruluyor**:

```python
db_username, db_password = generate_secure_credentials()   # ← KALDIRILACAK
```

Yerine dört değer çağırandan gelmeli. `generate_secure_credentials()` bu maddeden
sonra hiçbir yerde kullanılmıyor — `common/security.py`'den de silin (4.5 ile
birlikte).

```python
async def add_database(
    self, servername: str, database_name: str, tech_name: str,
    admin_user: User,
    *,
    username_ro: str, password_ro: str,
    username_rw: str, password_rw: str,
) -> dict[str, Any]:
    ...
    database = Databases(
        servername=servername,
        database_name=database_name,
        technology=tech_name,
        username_ro=username_ro, password_ro=password_ro,
        username_rw=username_rw, password_rw=password_rw,
        uuid=db_uuid,
    )
```

Form/endpoint şeması da genişliyor:

```python
class AddDatabaseRequest(BaseModel):
    servername: str
    database_name: str
    technology: str
    username_ro: str = Field(..., min_length=1)
    password_ro: str = Field(..., min_length=1)
    username_rw: str = Field(..., min_length=1)
    password_rw: str = Field(..., min_length=1)
```

> **Bağlantıyı kaydetmeden önce test edin.** Yanlış yapıştırılmış bir şifre, ancak
> ilk sorgu denendiğinde ortaya çıkar ve o an kullanıcının karşısına anlamsız bir
> bağlantı hatası olarak düşer. `add_database` içinde her iki hesapla da bir
> `SELECT 1` deneyin; biri bile bağlanamıyorsa kaydı reddedin ve hangi kademenin
> başarısız olduğunu söyleyin.
>
> Aynı testte `ro` hesabının gerçekten yazamadığını da doğrulayabilirsiniz —
> geçici bir tabloya `INSERT` deneyip **hata almayı beklemek**. Hata gelmezse
> provisioning yanlış yapılmış demektir ve bunu kurulum anında öğrenmek, altı ay
> sonra öğrenmekten iyidir.

### Kademe kişinin değil, ifadenin özelliğidir

Bu maddede ikinci en sık karışan nokta: *"sadece ro ve rw varsa admin ne yapacak?"*

Cevap: admin de aynı iki hesabı kullanır. `ro`/`rw`, "bu kullanıcı ne kadar
yetkili" demek değil — **"bu SQL cümlesi ne yapıyor"** demek.

```
Admin  SELECT * FROM Musteriler    →  ro  hesabıyla bağlanılır
Admin  UPDATE Musteriler SET ...   →  rw  hesabıyla bağlanılır
Reader SELECT * FROM Musteriler    →  ro  hesabıyla bağlanılır   ← aynı hesap
```

Admin'in kendine ait bir hesabı yok, çünkü kademe *kimin sorduğunu* değil *ne
yapıldığını* tarif ediyor. Admin bir `SELECT` çalıştırıyorsa o `SELECT`'in yazma
yetkisine ihtiyacı yoktur; dolayısıyla yazma yetkili bir bağlantı da açılmamalıdır.

Bu madde mevcut yetki kontrolünü **kaldırmıyor**, yanına ikinci bir kapı koyuyor:

| | **Yetki kapısı** | **Kademe kapısı** |
|---|---|---|
| Sorusu | *Kim soruyor?* | *Ne yapılıyor?* |
| Kaynağı | `UserDatabaseAssociation.role` | SQL'in kendisi (`required_tier`) |
| Nerede uygulanır | Uygulama katmanı | Veritabanı hesabı |
| Aşılırsa | Yetkisiz işlem denenir | Veritabanı reddeder |

Bir READER `DELETE` denerse yetki kapısı reddeder. O kontrol bir hata yüzünden
atlanırsa bile `ro` hesabı silemez. İkinci kapının varlık sebebi tam olarak budur.

### `ADMIN` şu an iki ayrı şeyi birden ifade ediyor 🟠

Mevcut kodda `ADMIN` rolü aynı anda iki anlama geliyor:

**① Yönetişim** — sorgu onaylayabilme, maskeleme kuralı yönetme, kullanıcı ekleme
(`admin/services.py:452` ve altı yerde daha)

**② Yetenek** — DDL çalıştırabilme (`query_execution/query_analyzer.py:168-171`)

Pratik sonucu şu: **birine sorgu onaylama yetkisi vermek için ona aynı zamanda
tablo silme yetkisi vermek zorundasınız.** Onay veren kişi ile şema değiştiren kişi
genelde aynı kişi değildir; güvenlik açısından *olmaması* tercih edilir — onaylayan
kişinin onayladığı şeyi kendi başına yapamaması, onayın anlamlı olmasını sağlar.

İkisi ayrılmalı:

| Rol | Ne verir | Kademe |
|---|---|---|
| `READER` | Veri okuma | `ro` |
| `WRITER` | Veri yazma | `rw` |
| `DDL` | Şema değiştirme | `ddl` |
| `ADMIN` | Onay verme, maskeleme yönetimi, kullanıcı ekleme | **hiçbiri** |

Roller birleşebilir: `"ADMIN,READER"` → onaylayabilir, sadece okuyabilir.
`"ADMIN,WRITER"` → onaylayabilir ve yazabilir.

**Bu bir davranış değişikliğidir — göç gerektirir.** Şu an `role="ADMIN"` olan
kullanıcılar yeni modelde veri erişimini kaybeder. Alembic revizyonunda mevcut
satırları taşıyın:

```python
def upgrade():
    # Mevcut ADMIN'ler bugün fiilen DDL dahil her şeyi yapabiliyor.
    # Erişimi bir gecede daraltmak üretimi kırar; önce eşdeğerini yaz,
    # sonra ekiple konuşup tek tek daralt.
    op.execute("""
        UPDATE UserDatabaseAssociation
        SET role = 'ADMIN,WRITER'
        WHERE UPPER(role) = 'ADMIN'
    """)
```

> **Karar: `ADMIN,WRITER` — (a) şıkkı, onaylandı.** Alternatif `ADMIN,DDL` idi
> ve admin'in WebQuery üzerinden `DROP`/`CREATE`/`ALTER` da çalıştırabilmesi
> anlamına gelirdi. Bunun bedeli `username_ddl`'in doldurulması, yani
> uygulamanın elinin altında sürekli **tablo silebilen bir hesap** bulunması —
> 3.1'in kaldırmak için var olduğu şeyin geri gelmesi.
>
> `ADMIN,WRITER` ile admin pratikte insanların yazdığı her sorguyu
> çalıştırabiliyor; dışarıda kalan tek kategori DDL, ki o da zaten nadir ve
> DBA'e gitmesi normal olan kategori. **`username_ddl` NULL kalır.**
>
> Karar geri alınamaz değil: `username_ddl` veritabanı bazında ve nullable.
> Yarın tek bir veritabanı için gerçekten gerekirse yalnızca onu doldurun.

`DDL` bilinçli olarak verilmiyor: bugün DDL yetkisi olan kullanıcıların çoğu onu
hiç kullanmamıştır. Gerçekten kullananları `AuditLog`'dan tespit edip (1.1 sonrası)
tek tek `DDL` ekleyin. Kimse kullanmıyorsa `username_ddl` hiç doldurulmaz ve
kademe tamamen kapalı kalır — hedeflenen son durum budur.

`check_permissions_match_role()` de aynı ayrıma çekilmeli: `has_ddl` artık
`"ADMIN" in roles_list` değil `"DDL" in roles_list` aramalı.

### Geçiş stratejisi

Bu değişikliği kademeli yapın, tek seferde değil:

1. Kolonları ekleyin, boş bırakın
2. `_credentials_for()` boşsa `CENTRAL_DB_*`'e düşsün (geçici geriye dönük uyum)
3. Veritabanlarını tek tek `webquery_ro`/`webquery_rw` ile donatın — her biri için
   DBA scripti çalıştırır, sonra kimlik bilgileri WebQuery'ye girilir
4. Hepsi donatıldıktan sonra fallback'i kaldırın ve `config_guard`'a "kimlik bilgisi
   eksik veritabanı var" uyarısı ekleyin
5. `db_username` / `db_password` kolonlarını ve `generate_secure_credentials()`
   fonksiyonunu silin; `close_user_engines`'i `close_database_engines` ile
   değiştirin ve kimlik bilgisi güncelleyen her yoldan çağırın
6. `ADMIN` rolünü yönetişim/yetenek olarak ayırın (yukarıdaki göç), `DDL` rolünü
   yalnızca gerçekten ihtiyacı kanıtlanmış kullanıcılara verin
7. `username_ddl` / `password_ddl` alanlarını **boş bırakın**; bir veritabanında
   DDL gerçekten gerekiyorsa yalnızca o veritabanı için doldurun

3. adım sırasında sistem **karışık modda** çalışır: bazı veritabanları kademe bazlı
hesapla, bazıları hâlâ `CENTRAL_DB_*` ile. Bu normaldir ve geçişin amacı budur —
ama hangi veritabanının hangi modda olduğunu görebilmeniz gerekir. Admin
listesinde bir "kimlik bilgisi: kademeli / merkezi" sütunu gösterin, yoksa 4. adıma
ne zaman geçebileceğinizi bilemezsiniz.

**Efor:** ~2 gün kod + hedef sunucu sayısına göre operasyon.

## Adım 17 · `4.5` — Ölü kodu temizle

**Neden burada, `3.1`'den sonra:** `close_user_engines` çağrısı siliniyor ama yerine
geçecek `close_database_engines` `3.1` ile geliyor. Önce yapılırsa ortada ne eski ne
yeni fonksiyon kalır.

`engine_cache.py:151-167` — `close_user_engines(db_uuid)`:

```python
    async def close_user_engines(self, db_uuid: str):
        for key, entry in self._cache.items():
            if entry.owner_id == db_uuid:   # owner_id BİR db_uuid'dir
```

Çağıran (`authentication/router.py:205`):
```python
await db_provider.close_user_engines(current_user.id)   # ← bir user_id geçiyor
```

`owner_id` her zaman `db_uuid` (veya artık `db_uuid:tier`), `current_user.id` bir tamsayı. **Karşılaştırma hiçbir zaman eşleşmiyor** — fonksiyon sessizce hiçbir şey yapmıyor.

Merkezi kimlik kullanıldığı için pool zaten paylaşımlı; kullanıcı bazlı kapatmanın
anlamı yok. **Çağrıyı** kaldırın:

```python
# authentication/router.py logout içinden çıkarın:
# await db_provider.close_user_engines(current_user.id)
```

**Fonksiyonun kendisi** ise silinmiyor, yerini alan bir şey var: 3.1'deki
`close_database_engines(db_uuid)`. İkisi farklı sorulara cevap veriyor —
eskisi "bu *kullanıcının* motorlarını kapat" demeye çalışıyordu (ki anlamsız,
motorlar kullanıcıya değil veritabanına ait), yenisi "bu *veritabanının* tüm
kademelerini kapat" diyor (ki kimlik bilgisi döndürüldüğünde ve veritabanı
silindiğinde gerçekten gerekli).

Sıra: 3.1'i yaptıysanız `close_database_engines` zaten var, sadece bu çağrıyı
silin. 3.1'i henüz yapmadıysanız fonksiyonu şimdilik olduğu yerde bırakın —
çağrısız duran ölü bir fonksiyon, yanlış çağrılan bir fonksiyondan zararsızdır.

**Efor:** 15 dakika.

## Adım 18 · `3.3` — sqlglot'u güncelleyin

**Neden burada — ana plandakinin tersine, `3.2`'den ÖNCE:** sqlglot AST düğüm
isimlerini sürümler arası değiştiriyor (`exp.AlterTable` gibi). Önce `3.2`'yi yazıp
sonra yükseltirseniz yeni yazdığınız analyzer testleri toptan kırılır ve hangisinin
gerçek hata, hangisinin sürüm farkı olduğunu ayırmak zorunda kalırsınız.

Önce yükseltin, **mevcut** testleri düzeltin, sonra yeni kod yazın.

**Açtığı kapı:** `3.2`, `3.4`

`requirements.txt`'te `sqlglot==23.6.3`. Güncel sürüm 27.x. Aradaki sürümlerde çok sayıda parser düzeltmesi var ve **parser doğruluğu doğrudan güvenlik kontrolünüzün doğruluğu**.

```bash
pip install -U sqlglot
```

Güncelleme sonrası `tests/unit/test_query_analyzer.py`'yi mutlaka çalıştırın — sqlglot AST düğüm isimlerini sürümler arası değiştirebiliyor (`exp.AlterTable` gibi).

**Efor:** ~2 saat (test düzeltmeleri dahil).

## Adım 19 · `3.2` — Analyzer sertleştirme

**Neden burada:** `3.3`'e bağlı — yükseltilmiş sqlglot üzerine yazılmalı.

`3.2.5` artık nihai hâlinde: sert bloklar herkes için, diğer riskler admin için
atlanıp loglanıyor. Bu **bilinçli bir karardır** (`1.3`, Karar 3) — kaldırmadan önce
oradaki gerekçeyi okuyun.

### 3.2.1 — Tehlikeli fonksiyon blocklist'i

**Problem:** `_check_sql_injection` yalnızca `exp.Command` node'larına bakıyor. `SELECT pg_read_file('/etc/passwd')` bir `exp.Anonymous` fonksiyon çağrısıdır → hiç kontrol edilmiyor.

```python
# query_execution/query_analyzer.py

_BLOCKED_FUNCTIONS = frozenset({
    # SQL Server — işletim sistemi / uzak erişim
    "xp_cmdshell", "xp_regread", "xp_regwrite", "xp_dirtree", "xp_fileexist",
    "sp_oacreate", "sp_oamethod", "sp_execute_external_script",
    "openrowset", "opendatasource", "openquery",
    # PostgreSQL — dosya sistemi / küme kontrolü / uzak SQL
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "lo_put",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "dblink", "dblink_connect", "dblink_exec",
    "pg_sleep",          # DoS kaldıracı — argüman sınırı için ayrıca bakılır
    # MySQL
    "load_file", "sys_exec", "sys_eval",
})

_MAX_SLEEP_SECONDS = 5


def _function_names(stmt: exp.Expression) -> set[str]:
    """
    Ağaçtaki tüm fonksiyon çağrı adları (küçük harf).

    Tırnaklı çağrılar da yakalanır: "pg_read_file"(...) — motor bunu aynı
    fonksiyona çözer, ama sqlglot .this alanına string yerine Identifier koyar.
    Bu ayrımı gözden kaçırmak, tırnak koyarak blocklist'i atlamak demektir.
    """
    names: set[str] = set()
    for func in stmt.find_all(exp.Func):
        if isinstance(func, exp.Anonymous):
            raw = func.this
            if isinstance(raw, str):
                names.add(raw.lower())
            else:
                n = getattr(raw, "name", None) or getattr(raw, "this", None)
                if isinstance(n, str):
                    names.add(n.lower())
            continue
        try:
            sql_name = func.sql_name()
            if sql_name:
                names.add(sql_name.lower())
        except Exception:
            pass
    return names


    def _check_dangerous_functions(self, stmt: exp.Expression) -> str | None:
        """Yasaklı fonksiyon adı → engelleme gerekçesi, yoksa None."""
        for name in _function_names(stmt):
            if name in _BLOCKED_FUNCTIONS:
                if name == "pg_sleep":
                    continue      # aşağıda argümanına bakılıyor
                return f"'{name}' fonksiyonu güvenlik politikası gereği engellidir."

        for call in stmt.find_all(exp.Anonymous):
            raw = call.this
            fname = (raw if isinstance(raw, str)
                     else getattr(raw, "name", "") or "").lower()
            if fname in {"pg_sleep", "pg_sleep_for", "sleep", "waitfor"}:
                arg = (call.expressions or [None])[0]
                secs = None
                if isinstance(arg, exp.Literal) and arg.is_number:
                    try:
                        secs = float(arg.this)
                    except ValueError:
                        secs = None
                # Argüman okunamıyorsa da engelle — "emin değilsek hayır".
                if secs is None or secs > _MAX_SLEEP_SECONDS:
                    return (f"'{fname}' çağrısı engellendi "
                            f"(en fazla {_MAX_SLEEP_SECONDS} saniye).")
        return None
```

`analyze()` döngüsüne ekleyin:

```python
        for stmt in statements:
            if not stmt:
                continue

            dangerous = self._check_dangerous_functions(stmt)
            if dangerous:
                result["risk_type"] = RiskLevel.SQL_INJECTION.value
                result["reason"] = dangerous
                result["return"] = False
                return result
            ...
```

### 3.2.2 — Çoklu statement kademe tutarlılığı

**Problem:** `SELECT 1; UPDATE t SET x=1 WHERE id=1` — bir READER için `check_permissions_match_role` reddeder, ama bir WRITER için tek batch olarak geçer ve onaylayan "bu bir SELECT" diye bakabilir.

```python
    def check_tier_consistency(self, query: str, technology: str = "mssql") -> str | None:
        """
        Tüm statement'lar aynı kademede mi?

        Karışık kademe reddedilir: tek bağlantı, tek kademe kimlik bilgisiyle
        çalışılıyor ve onaylayan kişi tek bir sınıflandırma görüyor. Kullanıcı
        SELECT'lerini ve UPDATE'lerini ayrı isteklere bölsün.
        """
        dialect = self._dialect(technology)
        try:
            statements = [s for s in sqlglot.parse(query.strip(), read=dialect) if s]
        except Exception:
            return "Sorgu ayrıştırılamadı."

        if len(statements) <= 1:
            return None

        tiers = set()
        ddl_types = (exp.Drop, exp.Create, exp.AlterTable, exp.TruncateTable)
        dml_types = (exp.Insert, exp.Update, exp.Delete, exp.Merge)
        for stmt in statements:
            if isinstance(stmt, ddl_types) or any(True for _ in stmt.find_all(ddl_types)):
                tiers.add("ddl")
            elif isinstance(stmt, dml_types) or any(True for _ in stmt.find_all(dml_types)):
                tiers.add("rw")
            else:
                tiers.add("ro")

        if len(tiers) > 1:
            return (f"Karışık yetki kademeleri ({', '.join(sorted(tiers))}). "
                    f"Okuma ve yazma sorgularını ayrı isteklerde gönderin — "
                    f"böylece her biri kendi kademesinde incelenir.")
        return None
```

### 3.2.3 — EXPLAIN muamelesi

**Problem:** `EXPLAIN ANALYZE UPDATE ...` sarılan statement'ı **gerçekten çalıştırır**. sqlglot bunu opak `exp.Command` olarak parse eder → analyzer içini göremez.

```python
import re

_EXPLAIN_ANALYZE_RE = re.compile(r"^\s*EXPLAIN\b[^;]*\bANALY[SZ]E\b", re.IGNORECASE)
#                                                        ↑ ANALYSE de yakalanmalı
#                                    PostgreSQL İngiliz yazımını eş anlamlı kabul eder;
#                                    sadece ANALYZE aramak bu formu tamamen kaçırır.

    def check_explain(self, query: str) -> str | None:
        """EXPLAIN ANALYZE, sarılan statement'ı ÇALIŞTIRIR — engelle."""
        if _EXPLAIN_ANALYZE_RE.search(query):
            return ("EXPLAIN ANALYZE, sarılan sorguyu gerçekten çalıştırır ve "
                    "bu nedenle izin verilmiyor. Düz EXPLAIN kullanın.")
        return None
```

### 3.2.4 — `max_joins` eşiği

**Problem:** `max_joins = 3` — normal bir raporlama sorgusu bunu geçer ve **bloke edilip onaya düşer**. Onay kuyruğu gürültüyle dolar; onaylayan mekanikleşir; gerçekten tehlikeli olan da onaylanır.

**Onay kuyruğunun kalitesi bir güvenlik özelliğidir.**

```python
# query_execution/config.py
MAX_JOINS = int(os.getenv("MAX_JOINS", "8"))
PERFORMANCE_BLOCKS = os.getenv("PERFORMANCE_BLOCKS", "false").lower() == "true"
```

```python
    def __init__(self) -> None:
        from query_execution import config
        self.max_joins = config.MAX_JOINS
        self.performance_blocks = config.PERFORMANCE_BLOCKS

    # analyze() içinde:
            if self._check_performance(stmt):
                result["risk_type"] = RiskLevel.PERFORMANCE.value
                # Performans riski varsayılan olarak UYARI, engelleme değil.
                # Zaman aşımı (Faz 0.3) ve satır sınırı gerçek korumadır;
                # bu sadece bir işaret.
                result["return"] = not self.performance_blocks
                if result["return"]:
                    result.setdefault("warnings", []).append(
                        "Sorgu ağır olabilir (çok sayıda JOIN veya baştan-sona joker)."
                    )
                else:
                    return result
```

### 3.2.5 — Admin'in analiz atlamasını daralt

**Problem:**
```python
# services.py:145
if not query_analysis["return"] and not is_db_admin:
```
DB admin'i için SQL injection, DDL, WHERE'siz DELETE — **hepsi** atlanıyor.

**Çözüm:** *Onay gerekliliğini* atlatın, *güvenlik kontrolünü* değil:

```python
            query_analysis = self.analyzer.analyze(query, technology=technology)
            risk_level = query_analysis.get("risk_type")

            # Bazı riskler kimsenin atlayamayacağı türden: kabuk çalıştırma,
            # dosya okuma, uzak SQL. Bunlar bir yetki sorusu değil — bu yol
            # onlar için var değil.
            HARD_BLOCK = {RiskLevel.SQL_INJECTION.value}
            if risk_level in HARD_BLOCK:
                await self.app_db.update_log(
                    log_id=log_id, successfull=False,
                    error=f"Hard block: {risk_level}")
                raise QueryAnalysisRejectedError(
                    query_analysis.get("reason")
                    or "Bu sorgu güvenlik politikası gereği engellendi."
                )

            # Diğer riskler admin için onay gerektirmez, ama LOGLANIR.
            #
            # NOT: Bu hâl bir ARA ADIMDIR, nihai hedef değil. 3.4'e bakın:
            # bypass tamamen kaldırılıyor ve yerine "admin geçer" değil,
            # "yıkıcı DML herkes için teyit ister" konuyor. Ölçüt kişiye
            # bakmadığı için admin istisnasına gerek kalmıyor. Aşağıdaki
            # kod 3.4.2 uygulanana kadar geçerli — sert bloklar her zaman
            # yürürlükte, diğerleri en azından iz bırakıyor.
            if not query_analysis["return"]:
                if is_db_admin:
                    logger.warning(
                        "Admin riskli sorgu çalıştırıyor: user=%s risk=%s db=%s",
                        user.username, risk_level, database_name)
                    # risk_level zaten ActionLogging'e yazıldı — iz kalıyor.
                else:
                    # ... mevcut onay akışı ...
```

**Efor (3.2 tümü):** ~1 gün + test.

## Adım 20 · `3.4` — Kontrol hiyerarşisi, yıkıcı DML teyidi ve platform rolü ◐ Kısmen tamamlandı

> **2026-08-29 kararı:** Bu adımın yıkıcı DML teyidi kısmı (`3.4.2`) çekirdek
> uygulama sırasından çıkarıldı. Teyit, tüm hedef veritabanları için zorunlu değildir; ihtiyaç
> duyulan hedef veritabanı eklenirken etkinleştirilebilecek isteğe bağlı bir
> politika olarak daha sonra uygulanacaktır. Ayrıntı ve iş kalemleri:
> [`docs/inbox/OPTIONAL-DESTRUCTIVE-DML-CONFIRMATION.md`](docs/inbox/OPTIONAL-DESTRUCTIVE-DML-CONFIRMATION.md).
>
> **Uygulama durumu:** `3.4.1`, `3.4.3`teki admin sert-blok sınırı ve
> `3.4.4`teki kalıcı OWNER modülü tamamlandı. `Users.is_platform_owner`,
> CLI bootstrap, startup guard, `/api/owner/*`, ilk DB ADMIN'in atomik atanması
> ve OWNER arayüzü SPEC-0021 / ADR-0017 uyarınca uygulanmıştır. OWNER olmak
> otomatik sorgu veya DB ADMIN yetkisi vermez.
>
> `3.1`deki `ro`/`rw` kademe ayrımı ve `3.2`deki sert analiz blokları bu
> karardan etkilenmez. `CONFIRMATION_SECRET` yalnız inbox özelliği planlanıp
> etkinleştirildiğinde zorunludur. Bu bölümdeki önceki tasarım notları tarihsel
> bağlam olarak korunmuştur. `3.4.4`teki platform kapsamlı veritabanı kaydı
> yetkisi, DML teyidinden bağımsızdır; sonraki adımların önkoşulu değildir ve
> ayrı planlanmalıdır.

**Önkoşulları:** `3.3` (sqlglot builder API'si sürüme duyarlı), `3.1` (sayım sorgusu
`ro` kademesinde çalışıyor — o kademe olmadan yapılamaz), `0.1`
(`CONFIRMATION_SECRET`).

Bloğun en değerli parçası `3.4.2`: `WHERE`'siz `DELETE`'i **herkes için** yakalıyor,
kimseyi bekletmeden.

Bu bölüm 1.2, 1.3 ve 3.2.5'te verilen onay kararlarını **yeniden çerçeveliyor.**
Önce hangi kontrolün hangi işi yaptığı, sonra kod.

### 3.4.1 — Kontrolleri doğru sıraya koymak

Planın ilk hâlinde onay akışı riskli sorgunun *birincil* kontrolüydü. Yanlış
yerdeydi. Kontroller şu sırayla denenmeli:

| # | Kontrol | Neye dayanır | Baypas edilebilir mi |
|---|---|---|---|
| 1 | **Yetkiyi hiç vermemek** | Hesap o işi yapamıyor | Hayır |
| 2 | **Hatayı mekanik zorlaştırmak** | Transaction + satır sayısı + açık commit | Hayır |
| 3 | **Bilgilendirilmiş teyit** | Kişi ne yaptığını görerek onaylıyor | Zor |
| 4 | **İkinci insan onayı** | Politika | **Evet** |
| 5 | Loglayıp ummak | — | — |

Çoğu ekip 4'ten başlar, çünkü uygulaması en kolay olan odur. 4'ün baypas
edilebilir olması teorik değil: onay bekleyen kullanıcının elinde SSMS/Workbench
varsa oradan çalıştırır ve o an WebQuery'nin logunda **hiçbir şey** olmaz.

> **Aşırı sıkı bir kapı, korumaya çalıştığı denetim izini yok eder.** Bu bir
> gerekçe değil, gözlem: kontrolü tasarlarken insanların ondan kaçma maliyetini
> de hesaba katmak zorundasınız. 4. seviye, 1-3'ün çözemediği şeyler için
> saklanmalı.

Bir de şu: sürekli onaylayan bir insan lastik damgaya döner, ve rutin olarak
onaylayan bir onaylayıcı **hiç onay olmamasından daha kötüdür** — çünkü sahte
güvence üretir. Onay akışını dar tutmak, onu ciddiye alınır tutmanın yoludur.

> ### ⚠️ Bu bölümün varsayımı — açıkça yazılmalı
>
> Tablodaki 4. satırın "Evet" olmasının sebebi, admin'lerin hedef
> veritabanlarında **kendi hesaplarının bulunması**. Bu değişirse — ki 3.1'in
> nihai hedefi tam olarak budur: hedef veritabanında insan hesabı yok, sadece
> `webquery_ro`/`webquery_rw` — WebQuery gerçekten tek kapı olur ve onay akışı
> gerçek bir güvenceye döner.
>
> **Kararı belirleyen şey tercih değil, bu olgu.** Uygulamaya başlamadan önce
> cevaplayın: *admin'lerinizin üretim veritabanlarında kendi hesapları var mı?*
> Cevap "var" ise bu bölüm geçerlidir. "Yok"a dönerse bu bölüm yeniden
> değerlendirilmeli ve onay akışı genişletilmelidir.

### 3.4.2 — Yıkıcı DML: kör çalıştırma yok

`WHERE`'siz `DELETE` bu planın en çok atıf yaptığı risk. Doğru çözümü ikinci bir
insan değil — **etkilenen satır sayısını commit'ten önce göstermek.**

Bu, hatayı *herkes* için yakalıyor: admin, WRITER, fark etmiyor. Kimseyi
beklemiyor. Baypas dürtüsü yaratmıyor. Ve `WHERE` unutmanın gerçek düzeltmesi
bu — kişi "2.146.883 satır etkilenecek" yazısını görünce zaten durur.

**1. Analyzer'a iki fonksiyon** (`query_execution/query_analyzer.py`):

```python
    _DESTRUCTIVE = (exp.Delete, exp.Update)

    def is_destructive(self, query: str, technology: str = "mssql") -> bool:
        """DELETE veya UPDATE içeriyor mu?"""
        try:
            statements = sqlglot.parse(query.strip(), read=self._dialect(technology))
        except Exception:
            return True          # parse edilemiyorsa yıkıcı say — fail-closed
        return any(
            isinstance(s, self._DESTRUCTIVE)
            or any(True for _ in s.find_all(self._DESTRUCTIVE))
            for s in statements if s
        )

    def count_equivalent(self, query: str, technology: str = "mssql") -> str | None:
        """
        DELETE/UPDATE'i eşdeğer SELECT COUNT(*)'a çevirir.

        Amaç: sorguyu ÇALIŞTIRMADAN kaç satırı etkileyeceğini öğrenmek.

        Neden transaction açıp rollback etmiyoruz: o da bir yöntemdir, ama
        büyük bir DELETE'te üretimde yazma kilidi tutar ve teyit ekranında
        bekleyen kullanıcı boyunca o kilit açık kalır. Bu yol salt okumadır.

        None dönerse çeviri yapılamadı (çoklu cümle, JOIN'li UPDATE, CTE...).
        Çağıran taraf FAIL-CLOSED davranmalı: "tahmin edilemedi" bir geçiş
        sebebi değil, onaya düşürme sebebidir.
        """
        dialect = self._dialect(technology)
        try:
            statements = sqlglot.parse(query.strip(), read=dialect)
        except Exception:
            return None

        if len(statements) != 1 or statements[0] is None:
            return None                       # tek cümle değilse çevirme
        stmt = statements[0]

        if not isinstance(stmt, (exp.Delete, exp.Update)):
            return None
        if stmt.args.get("joins") or stmt.args.get("using") or stmt.args.get("with"):
            return None                       # JOIN'li form — güvenli çeviri yok

        table = stmt.args.get("this")
        if not isinstance(table, exp.Table):
            return None

        counted = exp.select(exp.Count(this=exp.Star())).from_(table)
        where = stmt.args.get("where")
        if where is not None:
            counted = counted.where(where.this)

        return counted.sql(dialect=dialect)
```

> `WHERE`'siz bir `DELETE`'te `where` None olur ve sonuç `SELECT COUNT(*) FROM T`
> — yani tablonun tamamı. Görmek istediğiniz sayı tam olarak budur.

> **Not:** builder API'si (`exp.select`, `exp.Count`) sqlglot sürümüne duyarlıdır.
> 3.3'teki yükseltmeden **sonra** yazın ve testle sabitleyin.

**2. Servis akışı** (`query_execution/services.py`, kademe kontrolünden sonra,
çalıştırmadan önce):

```python
            if self.analyzer.is_destructive(query, technology=technology):
                count_sql = self.analyzer.count_equivalent(query, technology=technology)

                if count_sql is None:
                    # Etkiyi hesaplayamadık. Bu bir geçiş sebebi DEĞİL.
                    raise ApprovalRequiredError(
                        "Bu sorgunun etki alanı otomatik hesaplanamadı; "
                        "yönetici onayına gönderildi."
                    )

                # Sayım 'ro' kademesinde yapılır — sayarken yazma ihtimali yok.
                async with self.database_provider.get_session(
                    user=user, db_uuid=db_uuid, tier="ro"
                ) as ro_session:
                    affected = (await ro_session.execute(text(count_sql))).scalar_one()

                if affected >= config.APPROVAL_ROW_THRESHOLD or is_critical_table:
                    raise ApprovalRequiredError(
                        f"{affected:,} satır etkilenecek — yönetici onayı gerekiyor."
                    )

                if not self._confirmation_valid(confirmation_token, query, user):
                    raise ConfirmationRequiredError(
                        affected_rows=affected,
                        confirmation_token=self._sign_confirmation(query, user),
                        message=f"Bu sorgu {affected:,} satırı etkileyecek. Onaylıyor musunuz?",
                    )
```

**3. Teyit jetonu — sunucuda durum tutmadan:**

```python
    def _sign_confirmation(self, query: str, user: User) -> str:
        """
        'Bu kullanıcı TAM OLARAK bu sorgu için sayıyı gördü' bilgisini taşır.

        Sorgu bir karakter değişirse jeton geçersiz olur — kullanıcı sayıyı
        görüp sonra WHERE'i silemez. Sunucu tarafında oturum/state gerekmez.
        """
        return self._confirmation_hmac(query, user, int(time.time()) // 300)

    def _confirmation_valid(self, token: str | None, query: str, user: User) -> bool:
        if not token:
            return False
        pencere = int(time.time()) // 300
        # Şimdiki ve bir önceki pencere — jeton 5-10 dk geçerli.
        return any(
            hmac.compare_digest(token, self._confirmation_hmac(query, user, p))
            for p in (pencere, pencere - 1)
        )

    def _confirmation_hmac(self, query: str, user: User, pencere: int) -> str:
        payload = f"{user.id}:{hashlib.sha256(query.encode()).hexdigest()}:{pencere}"
        return hmac.new(config.CONFIRMATION_SECRET.encode(),
                        payload.encode(), hashlib.sha256).hexdigest()
```

```python
# query_execution/config.py
APPROVAL_ROW_THRESHOLD = int(os.getenv("APPROVAL_ROW_THRESHOLD", "10000"))
CONFIRMATION_SECRET = os.getenv("CONFIRMATION_SECRET")
```

> `CONFIRMATION_SECRET`'i **0.1'deki zorunlu sırlar listesine ekleyin.** Boş
> kalırsa jeton imzalanamaz; sessizce boş string'e düşerse jeton sahtelenebilir.

**4. Veritabanı tarafında ikinci kemer (MySQL):**

```sql
SET sql_safe_updates = 1;
```

Anahtar kolon içermeyen `UPDATE`/`DELETE`'i **sunucu** reddeder — yani 1. seviye
bir kontrol, tartışmasız en iyisi. `rw` bağlantısının `connect_args`'ına ekleyin.

Uyarısı var: indekssiz bir kolona göre yazılmış meşru `DELETE`'leri de reddeder.
Açıp gerçek sorgularınızla deneyin; çok sıkı geliyorsa bu maddeyi atlayıp
3.4.2'nin uygulama katmanı çözümüyle yetinin.

**Doğrulama:**

```python
def test_wheresiz_delete_tum_tabloyu_sayar(analyzer):
    sql = analyzer.count_equivalent("DELETE FROM Musteriler")
    assert "COUNT(*)" in sql.upper() and "WHERE" not in sql.upper()

def test_whereli_delete_kosulu_korur(analyzer):
    sql = analyzer.count_equivalent("DELETE FROM Loglar WHERE tarih < '2020-01-01'")
    assert "WHERE" in sql.upper() and "2020-01-01" in sql

def test_cevrilemeyen_form_none_doner(analyzer):
    # JOIN'li UPDATE — güvenli çeviri yok, fail-closed
    assert analyzer.count_equivalent(
        "UPDATE m SET m.aktif = 0 FROM Musteriler m JOIN Siparisler s ON s.id = m.id"
    ) is None

@pytest.mark.asyncio
async def test_jeton_sorgu_degisince_gecersiz(service, user):
    jeton = service._sign_confirmation("DELETE FROM T WHERE id = 1", user)
    assert not service._confirmation_valid(jeton, "DELETE FROM T", user)
```

Sondaki test bu mekanizmanın tamamını taşıyor: kullanıcı dar bir sorgunun sayısını
görüp `WHERE`'i silerek gönderemez.

### 3.4.3 — Onay hangi eksende tetiklenmeli

Bugünkü (ve planın ilk hâlindeki) tetikleyici analyzer'ın `risk_type`'ı. Yanlış
eksen. `DELETE FROM Loglar WHERE tarih < '2020'` ile `DELETE FROM Musteriler`
aynı `risk_type`'ı alır ama aynı şey değildir.

Doğru eksen **geri alınabilirlik ve etki alanı**:

| Ölçüt | Sonuç |
|---|---|
| Sert blok listesi (injection, `xp_cmdshell`) | **Reddedilir** — teyitle bile geçilmez, admin dahil |
| Aktör o veritabanında `ADMIN` | **Atlanır** — loglanır, bekletilmez |
| Geri alınamaz (`DROP`, `TRUNCATE`) | **Onay** — ikinci insan |
| Etkilenen satır > `APPROVAL_ROW_THRESHOLD` | **Onay** |
| Hedef, işaretli kritik tablo | **Onay** |
| Yıkıcı DML, eşik altı | **Teyit** — kendisi |
| Diğer | Serbest |

Sıra önemli: sert blok en üstte, admin istisnası hemen altında. Yani admin
`xp_cmdshell`'i yine çalıştıramaz, ama `WHERE`'siz `DELETE` için beklemez.

> **`is_db_admin` istisnası bilinçli bir karardır, unutulmuş bir satır değil.**
> Gerekçesi 1.3'teki Karar 3'te: admin'in hedef veritabanında kendi hesabı
> olduğu sürece bu kapı onu durdurmuyor, SSMS'e yönlendiriyor — ve denetim izi
> orada kayboluyor. Bu istisnayı kaldırmadan önce Karar 3'ü okuyun; kaldırmanın
> doğru olduğu bir dünya var (3.4.5) ve bugün o dünyada değiliz.

Geri kalan satırlar kişiye bakmıyor: ölçüt cümlenin kendisi, tıpkı 3.1'deki
kademe ayrımında olduğu gibi. *Kim soruyor* değil, *ne yapılıyor*.

Kritik tablo işaretlemesi için `Databases`'e eşlik eden basit bir liste yeter:

```python
class CriticalTables(Base):
    """Onayı zorunlu kılan tablolar. Veritabanı başına, ADMIN yönetir."""
    __tablename__ = "CriticalTables"
    id = Column(Integer, primary_key=True, autoincrement=True)
    database_id = Column(Integer, ForeignKey("Databases.id"), nullable=False)
    table_name = Column(String(128), nullable=False)
    __table_args__ = (UniqueConstraint("database_id", "table_name"),)
```

### 3.4.4 — Platform seviyesi yetki boşluğu 🟠

**Bulgu — platform seviyesi işler veritabanı seviyesi bir rolle korunuyor:**

```python
# dependencies.py:100
"""Dependency: ensures current_user is admin on at least one database."""
```

**Herhangi bir** veritabanında ADMIN olmak yetiyor. Ardından:

```python
# admin/services.py:517
# Automatically associate the adding admin user as ADMIN for this database
assoc = UserDatabaseAssociation(user_id=admin_user.id, role="ADMIN", is_admin=True)
```

Sonuç: bir test veritabanının admin'i platforma yeni veritabanı kaydedebilir ve
otomatik olarak onun da admin'i olur. `add_database`'in veritabanı bazında
kontrolü **olamaz** — kayıt anında veritabanı henüz yoktur. Yani bu eksik bir
`if` değil, **eksik bir rol**.

(`associate_user_to_database` buna karşılık düzgün scope'lu — `admin/services.py:569`
aktörün *o* veritabanındaki ADMIN'liğini arıyor. Sorun genel değil, yalnızca
platform seviyesi işlerde.)

**Tarihsel çözüm — `PLATFORM_ADMINS` allowlist (ADR-0017 ile superseded):**

Bu açık için yeni bir rol modeli gerekmiyor. Eksik olan tek şey, veritabanına
ait olmayan işleri koruyan ayrı bir kapı:

```python
# dependencies.py
# Platform seviyesi işler (veritabanı kaydetme / silme) bir veritabanına ait
# DEĞİLDİR, dolayısıyla veritabanı bazlı ADMIN kontrolüyle korunamazlar.
# Şema değişikliği yok, göç yok, UI'da yeni kavram yok.
_PLATFORM_ADMINS = {u.strip().lower()
                    for u in os.getenv("PLATFORM_ADMINS", "").split(",") if u.strip()}


async def platform_admin_required(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.username.lower() not in _PLATFORM_ADMINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem platform yöneticisi gerektirir.",
        )
    return current_user
```

`admin/router.py`'da `add_database` ve `remove_database` uç noktalarında
`admin_required` yerine bunu kullanın. `config_guard`'a ekleyin:

```python
    # Boş bırakılırsa veritabanı kaydetme herkese açık kalır.
    if not os.getenv("PLATFORM_ADMINS", "").strip():
        logger.warning(
            "PLATFORM_ADMINS boş — veritabanı kaydetme/silme işlemleri "
            "herhangi bir veritabanının ADMIN'ine açık.")
```

**Neden tam rol değil, allowlist:**

Açığın gerçek şiddeti düşük. Somut olarak yapılabilecek şey: zaten kimlik
bilgilerine sahip olunan bir veritabanını platforma kaydedip onun ADMIN'i olmak.
**Var olan** bir veritabanına kendine erişim vermek mümkün değil —
`associate_user_to_database` düzgün scope'lu. Üstelik 1.1'den sonra
`ADD_DATABASE` denetim kaydına yazılıyor: korumasız ama düşük etkili **ve izli**.

Buna karşılık yeni bir rolün sürekli maliyeti var: her yetki kontrolü iki
eksenli olur, UI'da yeni bir kavram, bootstrap scripti, göç, ve ince bir yerde
yanlış yapma riski. Allowlist bu işin %90'ını %5 maliyetle yapıyor.

**Gerçek `OWNER` rolüne geçiş durumu: tamamlandı (2026-08-29).**

Üçünden biri doğru olduğunda — hiçbiri olmadan erken:

- **Veritabanı sayısı ~10'u aştığında** — artık kimsenin hepsinin ADMIN'i
  olması mantıklı değildir
- **Birbirini görmemesi gereken ekipler olduğunda** — A ekibinin ADMIN'i
  B ekibinin veritabanını listeleyememeli
- **3.4.5'e gerçekten geçildiğinde** — üretimde insan hesabı kalmadığında
  WebQuery kritik altyapı olur ve platform yönetişimi ciddi bir mesele hâline
  gelir

O gün geldiğinde tasarım şudur:

```python
# app_database/models.py, User içinde
# Veritabanı bazlı DEĞİL, kullanıcı bazlı. UserDatabaseAssociation'a değil
# User'a konur, çünkü kapsamı bir veritabanı değil, platformun kendisi.
is_platform_owner = Column(Boolean, nullable=False, default=False)
```

| `OWNER` ne yapabilir | |
|---|---|
| Veritabanı kaydetme | ✅ |
| Veritabanı silme | ❌ Bu sürümün kapsamı dışında |
| Yeni veritabanına ilk ADMIN'i atama | ✅ |
| Ek DB ADMIN atama / geri alma | ✅ Son ADMIN korunur |
| Yeni kayıtta kademe kimlik bilgilerini girme | ✅ |
| Mevcut kimlik bilgilerini döndürme | ❌ Bu sürümün kapsamı dışında |
| **Herhangi bir** veritabanında onaylayabilme | ❌ Ayrı DB ADMIN ilişkisi gerekir |
| Kullanıcı devre dışı bırakma (2.1) | ✅ |
| Sorgu kademesi (`ro`/`rw`/`ddl`) | ❌ Hâlâ READER/WRITER/DDL'den gelir |

> **İlke: `OWNER` yetenek vermez, kapsam verir.** Bu, 3.1'deki `ADMIN`
> ayrımının bir kat yukarıdaki tekrarı. `ADMIN`'i yönetişim/yetenek diye
> ayırdıktan sonra `OWNER`'ı "her şeyi yapabilen" diye tanımlamak, aynı hatayı
> yeni bir isimle geri getirmek olurdu. `OWNER` *hangi veritabanlarında*
> yönetişim yapabileceğinizi genişletir, *ne yapabileceğinizi* değil.

İlk `OWNER` yalnızca komut satırından atanmalıdır (`scripts/bootstrap_owner.py`) —
UI'dan atanabilmesi, "OWNER olmayan biri OWNER atayabilir" demek olurdu.

**Break-glass — bu da `OWNER` değildir, ayrıdır:**

Gece 3'te üretime müdahale gerekebilir; bu meşru. Ama cevabı kalıcı bir
süperkullanıcı değil:

| | Kalıcı süperkullanıcı | Break-glass |
|---|---|---|
| Süre | Sınırsız | Süreli (örn. 60 dk), otomatik kapanır |
| Gerekçe | — | Zorunlu, serbest metin |
| Bildirim | Log satırı | **Slack kanalına alarm** |
| Anlamı | "Bu kişi her zaman her şeyi yapabilir" | "Bu kişi şu 60 dk'da, herkesin gözü önünde, şu gerekçeyle yaptı" |

Ve şunu bilerek kurun: WebQuery zaten tek yol değil — DBA'in kendi erişimi var.
Acil durum yolunun WebQuery **olması zorunlu değil ve olmaması daha iyi**, çünkü
olması WebQuery'nin acil-durum-seviyesi bir kimlik bilgisini 7/24 taşıması
demek. Yılda iki kez kullanılan bir yetki için sürekli taşınan bir risk.

### 3.4.5 — Uzun vadeli hedef

Olgun kurumlarda insanların üretim veritabanında **kendi hesabı yoktur.** Erişim
bir broker üzerinden gider (Teleport, StrongDM, AWS RDS IAM auth, Cloud SQL IAM),
broker kişiyi doğrular, kısa ömürlü kimlik üretir, oturumu kaydeder.

**3.1 bu modelin kendisidir** — WebQuery broker, `webquery_ro`/`webquery_rw` de
brokerin kimliği. Eksik olan tek parça, insanların kendi hesaplarının
kaldırılması. Bu bir WebQuery değişikliği değil, organizasyon değişikliği; ama
en yüksek kaldıraçlı madde odur ve 3.4.1'deki varsayımı ortadan kaldırır.

> **Düzenlemeye tabi sektör istisnası:** SOX, PCI-DSS veya bankacılık
> kapsamındaysanız üretim değişikliği için belgelenmiş onay çoğu zaman
> *zorunludur* — teknik faydası için değil, kanıt olduğu için. O durumda
> 3.4.3'teki tabloyu genişletin: teyit yeterli sayılan satırlar da onaya
> düşsün. Kontrolü teknik gerekçeyle savunmanız gerekmez, uyum gerekçesiyle
> zaten kalır.

**Efor:** Çekirdek plan dışında. Uygulanacağı zaman kapsamı inbox kaydındaki
spec/ADR ile netleştirilecek.

### ✅ Blok 4 geçiş kontrolü

Bu kontrol geçmeden sonraki bloğa başlamayın.

Bir `SELECT` çalıştırın — hedef veritabanının oturum görünümünde bağlantının
`webquery_ro` ile açıldığını doğrulayın. Bir `UPDATE` çalıştırın, `webquery_rw` görün.
`ro` hesabıyla elle `UPDATE` deneyin — veritabanı reddetmeli. Yıkıcı DML teyidi
bu geçiş kontrolünün parçası değildir; etkinleştirilecek hedef veritabanları
için inbox kaydına göre ayrıca doğrulanacaktır.

---

# Blok 5 — Cila

**Süre:** ~1 gün

Hiçbir şeyin önünde durmuyor.

## Adım 21 · `4.3` — `print()` → `logging`

**Neden burada:** Hiçbir şeyin önünde durmuyor. İstediğiniz zaman yapabilirsiniz;
sona bırakmak en az maliyetli.

`logging_config.py` ve `TraceMiddleware` zaten var ama tutarlı kullanılmıyor. En kötüsü:

```python
# database_provider/database.py:37,44,52
print(f"[DEBUG set_db_info] Input info: {info}")
print(f"[DEBUG set_db_info] Processing db_data: {db_data}")
print(f"[DEBUG set_db_info] Built db_by_uuid: {self.db_by_uuid}")
```

Bu, **tüm veritabanı yapılandırmasını stdout'a döküyor** — sunucu adları, veritabanı adları, UUID'ler. Container log'una gider, log toplama sistemine gider.

Toplu değiştirme:

```bash
cd web_api
grep -rn "print(" --include="*.py" . | grep -v test | grep -v migrations
```

Her dosyada:
```python
import logging
logger = logging.getLogger(__name__)

# print(f"[DEBUG set_db_info] Input info: {info}")
logger.debug("set_db_info: %d sunucu yapılandırıldı", len(info))
#                          ↑ içeriği değil, ÖZETİ logla
```

Ve `logging_config.py`'a seviye kontrolü:

```python
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
```

**Efor:** ~3 saat.

## Adım 22 · `4.6` — Streaming sonuç (opsiyonel, yük artarsa)

**Neden burada:** Opsiyonel. Yalnızca yük gerçekten artarsa.

`session.execute()` sonucu **tamamen belleğe** alır, sonra `fetchmany(1000)` çağrılır. 800 bin satırlık bir SELECT için 1000 satır isteseniz de 800 bin satır belleğe gelir.

```python
            async with self.database_provider.get_session(
                user=user, db_uuid=db_uuid, tier=required_tier
            ) as session:
                # stream() sunucu tarafı imleç kullanır: satırlar talep edildikçe
                # gelir. Sınıra ulaşınca döngüyü kırıyoruz ve geri kalanı hiç
                # okunmuyor — bellek kullanımı satır sayısından bağımsız kalıyor.
                result = await session.stream(text(query))

                raw_data: list[dict] = []
                truncated = False
                async for row in result:
                    if len(raw_data) >= config.MAX_ROW_COUNT_LIMIT:
                        truncated = True
                        break
                    raw_data.append(dict(row._mapping))

                row_count = len(raw_data)
                message = (f"MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT}) "
                           f"sınırına kırpıldı" if truncated
                           else f"{row_count} satır döndü")
```

> **Not:** `stream()` DML için `rowcount` vermez. Yalnızca `returns_rows` olan yolda kullanın; DML yolu `execute()` ile kalsın.

**Efor:** ~4 saat + yük testi.

---

# Sıra bozulursa ne olur

| Yanlış sıra | Sonucu |
|---|---|
| `1.1` / `3.1`, `4.1`'den önce | `create_all()` var olan tabloya kolon eklemez ve **hata vermez**. Kod yazıldığı gibi görünür, kolonlar yoktur, ilk yazma denemesinde patlar |
| `3.1`, `0.1`'den önce | Hedef veritabanı şifreleri repo'daki sabit Fernet anahtarıyla şifrelenir. Bir veritabanı dökümü **tüm hedef sunucu şifrelerini** açar |
| `3.1`, `4.4`'ten önce | `max_tier` mantığı `3.1`'in içine gömülür; `4.4` sonra ikinci bir kopya yaratır. İki uygulama zamanla ayrışır |
| `1.2` / `1.3`, `1.1`'den önce | `decide()` `log_in` ve `AuditAction`'ı import ediyor — dosyalar yok, uygulama açılmaz |
| `1.2` tek başına, `1.3`'süz | Yarış web tarafında kapanır, Slack tarafında açık kalır. Slack'teki yetki açığı da açık kalır — kanaldaki herkes onaylamaya devam eder |
| `3.3`, `3.2`/`3.4`'ten sonra | Yeni yazılan analyzer testleri toptan kırılır; gerçek hata ile sürüm farkını ayırmak zorunda kalırsınız |
| `4.5`, `3.1`'den önce | `close_user_engines` silinir, yerine geçecek `close_database_engines` henüz yoktur |
| `3.4`, `3.1`'den önce | Sayım sorgusu `ro` kademesinde çalıştırılamaz — o kademe yoktur |
| `3.1`, `0.3`'ü ezerse | `get_engine` baştan yazılırken `connect_args` düşerse sorgu zaman aşımı sessizce kaybolur |

---

# Kontrol listesi

```
BLOK 0 — ZEMİN                                            ~1,5 gün
□  1. 4.1  Alembic                                  1 gün   ⭐ ÖNCE BU
□  2. 4.2  CI                                       2 sa
□  3. 0.1  config_guard (+ CONFIRMATION_SECRET)     1 sa    🔴
□  4. 0.4  sa varsayılanı                          15 dk    🔴
   └─ geçiş: eksik .env ile uygulama açılmıyor, CI yeşil

BLOK 1 — KANAMA DURDURMA (üçü paralel)                    ~6 saat
□  5. 0.2  Hata mesajı temizleme                    2 sa    🔴
□  6. 0.3  Sorgu zaman aşımı                        3 sa    🔴
□  7. 0.5  Blacklist temizliği                      1 sa    🔴
   └─ geçiş: hata mesajında host yok, uzun sorgu kesiliyor

BLOK 2 — DENETLENEBİLİRLİK                                ~2,5 gün
□  8. 4.4  common/roles.py                          1 sa    ← 3.1'in önkoşulu
□  9. 1.1  AuditLog + eylem enum'u                  1 gün   🟠
□ 10. 1.2  Onay yarışını kapat                      4 sa    🟠 ┐ ayrılamaz
□ 11. 1.3  Web/Slack birleştir + yetki açığı        1 gün   🔴 ┘
   └─ geçiş: yarış testi geçiyor, Slack'te ADMIN aranıyor

BLOK 3 — KİMLİK (ertelenebilir)                           ~3 gün
□ 12. 2.1  User.is_active                           3 sa    🟠 ┐
□ 13. 2.2  Kaydı kapat                              2 sa    🟠 ├ paralel
□ 14. 2.4  Giriş kısıtlaması                        2 sa    🟠 ┘
□ 15. 2.3  Refresh token + oturum iptali            2 gün   🟠
   └─ geçiş: devre dışı kullanıcının oturumu reddediliyor

BLOK 4 — SAVUNMA DERİNLİĞİ                                ~2,5 gün
□ 16. 3.1  Kademe kimlik + engine cache (4b dahil)  2 gün   ⭐ EN YÜKSEK GETİRİ
□ 17. 4.5  Ölü kod                                 15 dk
□ 18. 3.3  sqlglot güncelle                         2 sa    ← 3.2'den ÖNCE
□ 19. 3.2  Analyzer sertleştirme                    1 gün   🟡
↷ 20. 3.4  Hedef DB bazlı isteğe bağlı DML teyidi          INBOX
   └─ geçiş: SELECT ro ile, UPDATE rw ile bağlanıyor;
             DML teyidi etkinse ayrı inbox kabul kriterleri uygulanır

BLOK 5 — CİLA                                             ~1 gün
□ 21. 4.3  print() → logging                        3 sa    🟡
□ 22. 4.6  Streaming (yük artarsa)                  4 sa    ⚪
```

---

# Sadece bir blok yapacaksanız

**Blok 4.** Ama Blok 0'ı atlayarak oraya başlayamazsınız — `3.1` hem Alembic'e, hem
`config_guard`'a, hem `roles.py`'a bağlı. En kısa anlamlı yol beş adım:

```
4.1 → 0.1 → 4.4 → 3.1 → 4.5
```

≈ 4,5 gün. Bu beş madde uygulama katmanını "tek savunma" olmaktan çıkarır ve
buradaki diğer maddelerin her birinin hata payını küçültür.

---

# Bir Not

Bu listedeki maddelerin çoğu "eksik özellik" değil, **varsayım düzeltmesi**.
WebQuery'nin mimarisi sağlam: modül deseni tutarlı, tip anotasyonları her yerde,
DI temiz, bcrypt yapılandırması pek çok projeden sıkı, Slack kimlik doğrulaması
titiz.

Değişmesi gereken şey mimari değil, **neyin garanti edildiği**. Şu an WebQuery
şunu garanti ediyor: *"Riskli sorguyu tespit eder, onaya düşürür, loglar."*
Blok 4'ten sonra şunu garanti edecek: *"Riskli sorguyu tespit eder; tespit
yanılırsa veritabanı reddeder; her iki durumda da iz kalır."*

İkinci cümle, üretim veritabanının önünde durmak için gereken cümle.

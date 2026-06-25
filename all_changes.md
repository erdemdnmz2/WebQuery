# WebQuery SaaS Migration - Complete Character-by-Character Code Diffs & Full Files

This document contains the word-for-word, character-by-character code diffs for all modified files, followed by the full contents of all newly created files, and finally the full contents of all modified Python (.py) and Shell (.sh) files during this pair programming session.

---

## Part 1: Modified Files (Git Diffs)

diff --git a/.env.example b/.env.example
index 980f64f..75906b1 100644
--- a/.env.example
+++ b/.env.example
@@ -13,6 +13,12 @@
 DB_USER=sa
 DB_PASSWORD=YourStrongPassword123!
 
+# Target Database Central Service Account (Merkezi Hesap)
+# Hedef veritabanlarında sorgu çalıştırmak için kullanılan merkezi servis kullanıcısı
+CENTRAL_DB_USER=webquery_service
+CENTRAL_DB_PASSWORD=YourStrongServicePassword123!
+
+
 # SQL Server Instance'ları (virgülle ayrılmış liste)
 # Birden fazla server için: SERVER1,SERVER2,SERVER3
 # Tek server için: localhost veya SERVER_NAME
diff --git a/README.md b/README.md
index cc129fa..c85d0d2 100644
--- a/README.md
+++ b/README.md
@@ -1,331 +1,153 @@
-## WebQuery
+# WebQuery - Enterprise SQL Execution Platform
 
 ![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
 ![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
 ![License](https://img.shields.io/badge/license-MIT-green)
+![Architecture](https://img.shields.io/badge/architecture-modular-orange)
 
-Çoklu veritabanı desteği ile sorgu analizi ve güvenli yürütme özellikleri sunan FastAPI tabanlı bir uygulama. MSSQL, MySQL ve PostgreSQL veritabanlarına bağlanabilir. Kimlik doğrulama (JWT), hız sınırlama, çoklu sorgu yürütme ve risk analizi içerir.
-
-## Özellikler
-- **Çoklu Veritabanı Desteği**: MSSQL, MySQL, PostgreSQL
-- **Gelişmiş Connection Pooling**: `EngineCache` ile sunucu kaynaklarını yormayan akıllı bağlantı yönetimi (LRU, TTL, Active Connection Check)
-- **Risk Analizi ve Onay Mekanizması**: Tehlikeli sorgular için otomatik tespit ve Admin onay süreci
-- **Workspace Yönetimi**: Sorguları kaydetme, düzenleme ve paylaşma
-- JWT ile kullanıcı doğrulama ve oturum yönetimi
-- Hız sınırlama (slowapi)
-- Otomatik driver seçimi ve connection string yönetimi
-
-## Mimari ve Teknolojiler
-- **Backend**: FastAPI 0.116.x, Uvicorn
-- **ORM**: SQLAlchemy 2.x (async)
-- **Drivers**: 
-  - MSSQL: `aioodbc` / `pyodbc`
-  - MySQL: `aiomysql`
-  - PostgreSQL: `asyncpg`
-- **Güvenlik**: python-jose (JWT), cryptography (Fernet), bcrypt
-- **Konfigürasyon**: python-dotenv
-
-## Proje Yapısı
-Modüler bir mimari benimsenmiştir:
-- `app_database/`: Uygulama içi veritabanı (User, Log, Workspace) modelleri ve işlemleri
-- `database_provider/`: Hedef veritabanlarına (MSSQL, MySQL, PG) bağlantı yönetimi (`EngineCache`)
-- `query_execution/`: Sorgu çalıştırma, risk analizi (`QueryAnalyzer`) ve loglama
-- `admin/`: Yönetici onay mekanizması ve işlemleri
-- `workspaces/`: Kullanıcı çalışma alanları yönetimi
-- `authentication/`: Login, register ve token işlemleri
-- `middlewares/`: Auth ve rate limiting middleware'leri
-
-## Gelişmiş Özellikler Detayı
-
-### 1. Akıllı Engine Cache (Connection Management)
-Uygulama, veritabanı bağlantılarını `EngineCache` sınıfı ile yönetir. Bu yapı, "Web Query Tool" senaryosu için özel olarak optimize edilmiştir:
-- **Pool Size = 0**: Sunucuda boşta (idle) bağlantı tutulmaz. Her sorgu bittiğinde bağlantı kapatılır.
-- **Max Overflow = 20**: Anlık yoğunlukta 20 eşzamanlı bağlantıya kadar izin verilir.
-- **LRU Eviction**: Cache dolduğunda en az kullanılan engine silinir.
-- **TTL Cleanup**: Belirli bir süre kullanılmayan engine'ler arka planda temizlenir.
-- **Active Check**: Temizlik sırasında, o an sorgu çalıştıran engine'ler (`checkedout > 0`) korunur, işlem yarıda kesilmez.
-
-### 2. Sorgu Risk Analizi (Query Analyzer)
-Her sorgu çalıştırılmadan önce `QueryAnalyzer` tarafından taranır. Riskler 4 seviyede değerlendirilir:
-1.  **SQL Injection**: `UNION SELECT`, `OR 1=1`, yorum satırları (`--`, `/*`) vb.
-2.  **DDL (Yapısal Değişiklik)**: `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
-3.  **Riskli DML**: `WHERE` koşulu olmayan `DELETE` veya `UPDATE` işlemleri.
-4.  **Performans**: 3'ten fazla `JOIN`, `CROSS JOIN`, `LIKE '%...%'`, büyük `LIMIT` + `ORDER BY`.
-
-**Onay Mekanizması**: Riskli bulunan sorgular (Admin değilse) doğrudan çalıştırılmaz. "Onay Bekliyor" durumuna alınır. Adminler bu sorguları inceleyip onaylayabilir veya reddedebilir.
-
-### 3. Workspace Sistemi
-Kullanıcılar sorgularını "Workspace" olarak kaydedebilir. Her workspace:
-- Bir SQL sorgusu içerir.
-- Sorgunun son çalışma durumu ve risk seviyesini tutar.
-- Admin onayı gerekiyorsa durumunu takip eder.
-
-## Gereksinimler
-
-### Python ve Temel Bağımlılıklar
-- Python 3.11+
-- `requirements.txt` içindeki tüm paketler
-
-### Veritabanı Driver'ları (Zorunlu)
-
-Kullanmayı planladığınız veritabanı teknolojisine göre ilgili driver'ların sisteminizde kurulu olması **zorunludur**:
-
-#### **MSSQL (Microsoft SQL Server)**
-- **ODBC Driver 18 for SQL Server** (sistem seviyesinde kurulu olmalı)
-- Windows: [Microsoft Download Center](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
-- Linux: [Linux ODBC Driver Installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
-- Python paketleri: `aioodbc`, `pyodbc` (requirements.txt'te mevcut)
-
-#### **MySQL**
-- **MySQL Client Libraries** (opsiyonel, bazı sistemlerde gerekebilir)
-- Python paketleri: `aiomysql`, `PyMySQL` (requirements.txt'te mevcut)
-
-#### **PostgreSQL**
-- **PostgreSQL Client** (asyncpg için genellikle gerekli değil)
-- Python paketi: `asyncpg` (requirements.txt'te mevcut)
-
-### Veritabanı Erişimi
-- İlgili veritabanı sunucusuna erişim (kullanıcı adı/şifre)
-- Gerekli izinler (SELECT, INSERT vb.)
-
-## Hızlı Başlangıç (Geliştirme)
-1) Depoyu klonla
-```powershell
-git clone https://github.com/erdemdnmz2/WebQuery
-cd WebQuery
-```
+WebQuery is a powerful, secure, and production-ready enterprise SQL execution platform built on FastAPI. It allows teams to safely run, share, and audit queries across multiple target databases (MSSQL, MySQL, PostgreSQL). 
 
-2) Sanal ortam ve bağımlılıklar
-```powershell
-python -m venv venv
-.\venv\Scripts\pip.exe install -r requirements.txt
-```
+Designed with zero-trust B2B security principles, WebQuery eliminates the need to store individual database credentials by employing a **Centralized Service Account Architecture** coupled with advanced AST-based query analysis, global error translation, and a real-time request tracing system.
 
-3) Ortam dosyası
-- `.env.example` dosyasını kopyalayıp değerleri düzenleyin:
-```powershell
-Copy-Item .env.example .env
-```
-- Bu dosyada tanımlı değişkenler: DB_USER, DB_PASSWORD, SQL_SERVER_NAMES, SECRET_KEY, JWT ayarları, rate limit, sorgu limitleri, HOST ve PORT (tam liste için `.env.example`’a bakın).
+---
 
-4) Çalıştırma (dev)
-- Varsayılan olarak `.env` okunur; isterseniz özel dosya seçebilirsiniz:
-```powershell
-$env:ENV_FILE = ".env"          # veya ".env.staging" / ".env.production"
-.\venv\Scripts\python.exe -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
-```
+## Architecture & Core Features
 
-## Production Çalıştırma (Önerilen Yol)
-1) Kodu sunucuya kopyalayın (ENV dosyaları hariç)
-2) Sunucuda `.env.production` oluşturun ve güvenli değerleri yazın
-3) Sunucuda bağımlılıkları kurun ve uygulamayı başlatın
+### 1. Centralized Service Account Architecture (Zero-Trust Security)
+* **No User-Stored Credentials:** Individual database passwords are never requested, stored, or cached (removing any risk of credential leaks).
+* **Central Credentials:** Connections to target databases are established dynamically using highly restricted central service credentials (`CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD`) defined securely in the environment.
+* **Granular Audit Logging:** Although execution is centralized, every query is strictly audited. The platform logs the exact user, trace ID, timestamp, and machine name for every action in the `ActionLogging` table.
+* **Stateless JWT Authorization:** Session management is completely stateless. Authenticated requests use cryptographically signed JWT tokens stored in secure, HttpOnly cookies, completely eliminating the need for a Redis credential cache.
 
-```powershell
-python -m venv venv
-.\venv\Scripts\pip.exe install -r requirements.txt
+### 2. Intelligent Connection Pooling & Engine Cache
+* **Zero Idle Connections:** Connection engines to target databases are managed by an advanced `EngineCache`. It sets `pool_size=0` to release idle server-side connections immediately after query execution.
+* **Max Overflow Handling:** Dynamically allows up to 20 concurrent connections during peak query bursts.
+* **LRU Eviction & TTL Cleanup:** Least Recently Used (LRU) engines are evicted when the cache limit is reached. A background task cleans up expired engines based on a configurable Time-to-Live (TTL), while ensuring active, currently executing engines (`checkedout > 0`) are safely protected.
 
-# Uygulamaya hangi .env dosyasını kullanacağını söyleyin
-$env:ENV_FILE = ".env.production"
-.\venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
-```
+### 3. Dynamic SQL Risk Analysis (AST Parsing)
+Before execution, every query is analyzed by a custom `QueryAnalyzer` utilizing the `sqlglot` library for abstract syntax tree (AST) parsing. It supports target-specific SQL dialects (`tsql`, `mysql`, `postgres`) and grades queries into four risk levels:
+1. **SQL Injection:** Checks for structural anomalies (e.g., `UNION SELECT`, `OR 1=1`, inline comments).
+2. **DDL (Structural Modifications):** Detects `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
+3. **Risky DML:** Blocks `DELETE` or `UPDATE` statements lacking a `WHERE` clause.
+4. **Performance Anomalies:** Flagging queries with more than 3 `JOIN`s, `CROSS JOIN`s, un-indexed `LIKE '%...%'`, or massive `LIMIT` operations.
 
-> Not: Docker kullanacaksanız gizli bilgileri imajın içine koymayın. Konfigürasyonu runtime’da verin:
-```powershell
-docker run --env-file C:\path\to\.env.production -p 8000:8000 yourimage:tag
-```
+> [!NOTE]
+> **Approval Workflow:** Risky queries submitted by non-admin users are automatically put into a "Pending Approval" state. Authorized administrators can inspect, approve, or reject these queries via Slack or the Admin Panel.
 
-## Docker ile Çalıştırma
+### 4. Advanced Request Tracing & Auditing Middleware
+* **Trace ID Generation:** The `TraceMiddleware` automatically assigns a unique UUID (Trace ID) to every incoming HTTP request and attaches it as the `X-Request-ID` header in the response.
+* **Context-Aware Auditing:** Utilizes Python `contextvars` to dynamically propagate the active Trace ID and authenticated User ID to all logging handlers. Every log entry automatically prints the trace context without passing request objects down the call stack.
 
-Proje, tüm bağımlılıkları (MSSQL, Redis, Nginx) içeren bir `docker-compose.yml` ile birlikte gelir. Tek komutla tüm sistemi ayağa kaldırabilirsiniz.
+### 5. Unified Error Translation (Exception Translation Pattern)
+* **Modular Domain Exceptions:** Low-level infrastructure, driver, or database errors (such as SQLAlchemy or network exceptions) are caught at the service boundary and translated into domain-specific exceptions (e.g., `WorkspaceNotFoundError`, `QueryExecutionError`, `UserAlreadyExistsError`).
+* **Global Handling:** A centralized exception handler intercepts all domain exceptions, logs their detailed tracebacks internally, and returns a clean, secure, and standardized JSON response containing `success: false`, the enterprise `error_code`, a safe client-facing `message`, and the associated `trace_id`.
 
-### Servis Mimarisi
-```
-                    ┌─────────────┐
-         :80        │    Nginx    │
-  Kullanıcı ──────► │  (Reverse   │
-                    │   Proxy)    │
-                    └──────┬──────┘
-                   /               \
-            /api /                   \ /
-    ┌───────▼──────┐           ┌─────▼───────┐
-    │  Backend     │           │  Frontend   │
-    │  (FastAPI)   │           │  (React +   │
-    │  :8080       │           │   Nginx)    │
-    └──┬───────┬───┘           └─────────────┘
-       │       │
-  ┌────▼──┐ ┌──▼────┐
-  │ MSSQL │ │ Redis │
-  │ :1433 │ │ :6379 │
-  └───────┘ └───────┘
-```
+---
 
-### Ön Gereksinimler
-- [Docker](https://docs.docker.com/get-docker/) (20.10+)
-- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)
+## Directory Structure
 
-### Hızlı Başlangıç (Docker)
-1) `.env` dosyasını oluşturun:
-```bash
-cp .env.example .env
-# .env dosyasını düzenleyip en azından DB_PASSWORD ayarlayın
-```
+WebQuery adopts a clean, modular package architecture:
 
-2) Tüm servisleri başlatın:
-```bash
-docker-compose up -d --build
 ```
-
-3) Logları izleyin:
-```bash
-docker-compose logs -f web    # Backend logları
-docker-compose logs -f        # Tüm servisler
+web_api/
+│
+├── common/                  # Centralized utilities (Exceptions, Logging, Rate Limiting)
+│   ├── exceptions.py        # BaseServiceException and global hierarchy
+│   ├── logging_config.py    # Custom contextvars logger formatting
+│   └── limiter.py           # Consolidated, shared slowapi Limiter
+│
+├── middlewares/             # FastAPI Middlewares (Trace ID, Stateless Auth)
+│   ├── trace_middleware.py  # Request ID generation and log context binding
+│   └── auth_middleware.py   # JWT validation and user context binding
+│
+├── database_provider/       # Connection management and target DB sessions
+│   ├── database.py          # DatabaseProvider session generator
+│   ├── engine_cache.py      # LRU and TTL-based SQLAlchemy connection engine caching
+│   └── config.py            # Central and target database driver configurations
+│
+├── query_execution/         # SQL execution, AST risk analysis, and audit logging
+│   ├── services.py          # QueryService with SELECT and DML execution safety
+│   └── router.py            # Query execution HTTP entrypoints
+│
+├── workspaces/              # User workspace management (Saved queries and metadata)
+├── authentication/          # User registration, stateless login, and cookies
+├── admin/                   # Administrative actions (Database registration, manual approvals)
+└── tests/                   # Test Suite (Unit and Integration tests with SQLite in-memory)
 ```
 
-4) Erişim:
-   - **Uygulama**: http://localhost (Nginx üzerinden)
-   - **API**: http://localhost/api
-   - **Health Check**: http://localhost/api/health
+---
+
+## Driver Requirements
 
-### Servisler ve Portlar
+To connect to target databases, the corresponding system-level drivers and client libraries must be installed on your host machine:
 
-| Servis | Image | Port | Açıklama |
-|--------|-------|------|----------|
-| `nginx` | nginx:latest | **80** → 80 | Reverse proxy (frontend + API) |
-| `web` | Dockerfile (root) | **8080** → 8080 | FastAPI backend |
-| `frontend` | Dockerfile (frontend/) | - | React SPA (Nginx ile serve) |
-| `db` | mssql/server:2022 | **1433** → 1433 | SQL Server veritabanı |
-| `redis` | redis:alpine | **6379** → 6379 | Session/cache store |
+### **Microsoft SQL Server (MSSQL)**
+* **ODBC Driver 18 for SQL Server** (System-level installation is mandatory).
+  * Windows: [Microsoft ODBC Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
+  * Linux/macOS: [ODBC Installation Guide](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
+  * Python packages: `aioodbc`, `pyodbc` (included in requirements)
 
-### Docker Ortam Değişkenleri
-`docker-compose.yml` aşağıdaki değişkenleri `.env` dosyasından okur:
+### **MySQL**
+* Python packages: `aiomysql`, `PyMySQL` (included in requirements)
 
-| Değişken | Docker Default | Açıklama |
-|----------|---------------|----------|
-| `DB_PASSWORD` | *(zorunlu)* | SQL Server SA şifresi |
-| `DB_USER` | `sa` | SQL Server kullanıcısı |
-| `PORT` | `8080` | Backend port |
-| `HOST` | `0.0.0.0` | Backend bind adresi |
+### **PostgreSQL**
+* Python package: `asyncpg` (included in requirements)
 
-> **Önemli:** `DB_PASSWORD` güçlü bir şifre olmalıdır (SQL Server 2022 gereksinimleri: en az 8 karakter, büyük-küçük harf, rakam veya özel karakter).
+---
 
-### Yararlı Docker Komutları
+## Quick Start (Development)
+
+### 1. Clone the Repository
+```bash
+git clone https://github.com/erdemdnmz2/WebQuery
+cd WebQuery
+```
+
+### 2. Set Up Virtual Environment and Install Dependencies
 ```bash
-# Servisleri durdur
-docker-compose down
+python -m venv .venv
+source .venv/bin/activate  # On Windows: .venv\Scripts\activate
+pip install -r web_api/requirements.txt
+```
 
-# Servisleri durdur ve veritabanı verisini sil
-docker-compose down -v
+### 3. Configure Environment Variables
+Copy the template `.env.example` to `.env` and configure your credentials:
+```bash
+cp .env.example .env
+```
 
-# Sadece backend'i yeniden derle
-docker-compose up -d --build web
+Ensure the following variables are set correctly:
+* `DB_USER` and `DB_PASSWORD` (For the WebQuery metadata application database)
+* `CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD` (Central service account for target database executions)
+* `SECRET_KEY` (Strong secret key for JWT signatures)
+* `SQL_SERVER_NAMES` (Comma-separated list of target servers, e.g., `localhost`)
 
-# Container'a bağlan (debug)
-docker-compose exec web bash
+### 4. Initialize Database
+Initialize the SQLite metadata database (or MSSQL if configured):
+```bash
+cd web_api
+python create_db.py
 ```
 
-## Ortam Değişkenleri (dotenv)
-- Uygulama başında `app.py` içinde şu mantık vardır:
-  - `ENV_FILE` değişkeni set edilmişse o dosya yüklenir (örn: `.env.production`)
-  - Aksi halde `.env` yüklenir
-- Diğer modüller `os.getenv()` ile bu değerleri okur.
-
-### Hangi dosyalar repo’ya girer?
-- `.env.example` → EVET, commit’leyin (örnek ve dokümantasyon amaçlı)
-- `.env`, `.env.production`, `.env.*` → HAYIR, gizli bilgiler; repo’ya eklemeyin
-
-## CORS (Önemli)
-Geliştirmede `*` kullanılabilir; production'da sadece izinli origin'leri tanımlayın.
-Örnek (internal): `http://10.1.1.1:80`
-
-## Çoklu Veritabanı Yapılandırması
-
-### Desteklenen Veritabanı Tipleri
-Uygulama şu veritabanı teknolojilerini destekler:
-- **MSSQL** → Driver: `aioodbc`
-- **MySQL** → Driver: `aiomysql`
-- **PostgreSQL** → Driver: `asyncpg`
-
-### Databases Tablosu Yapısı
-Uygulama başlangıcında `Databases` tablosundan veritabanı bilgileri okunur:
-
-```sql
-CREATE TABLE Databases (
-    id INT PRIMARY KEY IDENTITY(1,1),
-    servername NVARCHAR(100) NOT NULL,      -- Sunucu adresi
-    database_name NVARCHAR(100) NOT NULL,   -- Veritabanı adı
-    technology NVARCHAR(100) NOT NULL       -- mssql, mysql, postgresql
-);
+### 5. Run the Application
+Start the Uvicorn development server:
+```bash
+python app.py
 ```
+The API will be accessible at `http://localhost:8080` with interactive Swagger docs at `http://localhost:8080/docs`.
 
-### Örnek Kayıtlar
-```sql
--- MSSQL Sunucu
-INSERT INTO Databases (servername, database_name, technology)
-VALUES ('localhost', 'Northwind', 'mssql'),
-       ('localhost', 'AdventureWorks', 'mssql');
-
--- MySQL Sunucu
-INSERT INTO Databases (servername, database_name, technology)
-VALUES ('mysql-server-1', 'ecommerce', 'mysql'),
-       ('mysql-server-1', 'analytics', 'mysql');
-
--- PostgreSQL Sunucu
-INSERT INTO Databases (servername, database_name, technology)
-VALUES ('postgres-server-1', 'production_db', 'postgresql'),
-       ('postgres-server-1', 'staging_db', 'postgresql');
+---
+
+## Testing
+
+WebQuery comes with a comprehensive testing suite that executes completely in memory using an SQLite async memory database (`sqlite+aiosqlite:///:memory:`) to verify routes, middlewares, error translation, and SQL execution without modifying any external resources.
+
+Run the test suite using pytest:
+```bash
+pytest
 ```
 
-### Otomatik Driver Seçimi
-Uygulama, `technology` alanına göre otomatik olarak doğru driver'ı seçer ve connection string oluşturur. Manuel konfigürasyona gerek yoktur.
-
-## Veritabanı Notları
-
-### MSSQL (SQL Server)
-- SQL Authentication kullanılır: `.env` içinde `DB_USER` ve `DB_PASSWORD`.
-- Uygulama DB'sinde user oluşturun ve uygun rol verin (kolay yol: `db_owner`).
-- Diğer veri tabanlarında sadece okuma gerekiyorsa ilgili DB'de `CREATE USER ... FOR LOGIN ...; GRANT SELECT TO ...` yeterlidir.
-
-### MySQL
-- MySQL server'da kullanıcı oluşturun ve gerekli izinleri verin
-- Örnek: `CREATE USER 'user'@'%' IDENTIFIED BY 'password'; GRANT SELECT ON db.* TO 'user'@'%';`
-
-### PostgreSQL
-- PostgreSQL'de kullanıcı ve izinleri ayarlayın
-- Örnek: `CREATE USER myuser WITH PASSWORD 'mypass'; GRANT CONNECT ON DATABASE mydb TO myuser;`
-
-## Sık Karşılaşılan Sorunlar
-
-### Driver Sorunları
-- **"ODBC Driver bulunamadı"** (MSSQL): 
-  - Sunucuya "ODBC Driver 18 for SQL Server" kurun
-  - Test: `odbcinst -j` (Linux) veya ODBC Data Sources (Windows)
-  
-- **"No module named 'aiomysql'"** (MySQL):
-  - `pip install aiomysql PyMySQL` çalıştırın
-  
-- **"No module named 'asyncpg'"** (PostgreSQL):
-  - `pip install asyncpg` çalıştırın
-
-### Bağlantı Sorunları
-- **"Login failed"**: 
-  - `DB_USER/DB_PASSWORD` doğru mu?
-  - İlgili DB'de USER bağlı mı?
-  - `Databases` tablosunda kayıt var mı?
-  
-- **"Technology not supported"**:
-  - `Databases` tablosunda `technology` alanı doğru mu? (mssql, mysql, postgresql)
-  
-- **"Connection timeout"**:
-  - Sunucu erişilebilir mi?
-  - Firewall kuralları doğru mu?
-
-### Diğer Sorunlar
-- **"CORS hatası"**: Production'da izinli origin eklediniz mi?
-- **"Database not found"**: `Databases` tablosuna kayıt eklediniz mi?
-
-## Lisans
-Bu proje [MIT License](LICENSE) altında lisanslanmıştır.
-
-## Katkıda Bulunma
-Katkıda bulunmak isterseniz lütfen [CONTRIBUTING.md](CONTRIBUTING.md) dosyasını inceleyin. Pull request'lerinizi bekliyoruz!
+---
 
+## License
+This project is licensed under the MIT License.
diff --git a/web_api/admin/services.py b/web_api/admin/services.py
index 3dd17f6..abeb46d 100644
--- a/web_api/admin/services.py
+++ b/web_api/admin/services.py
@@ -10,6 +10,12 @@ from database_provider import DatabaseProvider
 from .schemas import AdminApprovals
 from query_execution import config
 
+import logging
+from common.exceptions import BaseServiceException
+from workspaces.exceptions import WorkspaceNotFoundError
+
+logger = logging.getLogger(__name__)
+
 class BaseAdminService:
     """
     Base class for all admin services.
@@ -229,13 +235,13 @@ class AdminApprovalService(BaseAdminService):
                 workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                 workspace: Workspace | None = workspace_result.scalars().first()
                 if not workspace:
-                    return {"success": False, "error": "Workspace not found"}
+                    raise WorkspaceNotFoundError("Workspace not found")
                 
                 # 2. Fetch related QueryData
                 query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                 query_data: QueryData | None = query_result.scalars().first()
                 if not query_data:
-                    return {"success": False, "error": "Query data not found"}
+                    raise WorkspaceNotFoundError("Query data not found for this workspace")
                 
                 # 3. Update status and description
                 new_status: str = ""
@@ -254,18 +260,18 @@ class AdminApprovalService(BaseAdminService):
                 
                 await db.commit()
                 
+                logger.info(f"Query in workspace {workspace_id} approved by admin (Executable: {show_results})")
                 return {
                     "success": True,
                     "status": new_status,
                     "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
                 }
+            except BaseServiceException:
+                raise
             except Exception as e:
                 await db.rollback()
-                print(f"Approval failed: {e}")
-                return {
-                    "success": False,
-                    "error": f"Approval failed: {str(e)}"
-                }
+                logger.error(f"Approval failed for workspace {workspace_id}: {e}")
+                raise BaseServiceException(f"Approval failed: {str(e)}", original_exception=e)
 
 class AdminDBAdditionService(BaseAdminService):
     """
@@ -292,13 +298,16 @@ class AdminDBAdditionService(BaseAdminService):
                 ))
                 existing_db: Databases | None = existing.scalars().first()
                 if existing_db:
-                    return {"success": False, "error": "Database already exists"}
+                    raise BaseServiceException("Database already exists")
 
                 database: Databases = Databases(servername=servername, database_name=database_name, technology=tech_name)
                 db.add(database)
                 await db.commit()
+                logger.info(f"Database '{database_name}' on server '{servername}' successfully added by admin")
                 return {"success": True, "message": "Database added successfully"}
+            except BaseServiceException:
+                raise
             except Exception as e:
                 await db.rollback()
-                print(f"Error adding database: {e}")
-                return {"success": False, "error": str(e)}
+                logger.error(f"Error adding database: {e}")
+                raise BaseServiceException(f"Error adding database: {str(e)}", original_exception=e)
diff --git a/web_api/app.py b/web_api/app.py
index b7600ac..d7f511f 100644
--- a/web_api/app.py
+++ b/web_api/app.py
@@ -10,12 +10,19 @@ import asyncio
 env_file = os.getenv("ENV_FILE", ".env")
 load_dotenv(env_file)
 
-from fastapi import FastAPI
+from common.logging_config import setup_logging
+setup_logging()
+
+from fastapi import FastAPI, Request
+from fastapi.responses import JSONResponse
+from common.exceptions import BaseServiceException
+from middlewares.trace_middleware import TraceMiddleware
+import logging
 from contextlib import asynccontextmanager
-from slowapi import Limiter, _rate_limit_exceeded_handler
+from slowapi import _rate_limit_exceeded_handler
 from slowapi.middleware import SlowAPIMiddleware
-from slowapi.util import get_remote_address
 from slowapi.errors import RateLimitExceeded
+from common.limiter import limiter
 import uvicorn
 from starlette.middleware.cors import CORSMiddleware
 from sqlalchemy import text
@@ -103,11 +110,11 @@ app = FastAPI(
     lifespan=lifespan
 )
 
-limiter = Limiter(key_func=get_remote_address)
 app.state.limiter = limiter
 app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
 
 app.add_middleware(AuthMiddleware)
+app.add_middleware(TraceMiddleware)
 app.add_middleware(SlowAPIMiddleware)
 
 cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "*")
@@ -121,6 +128,30 @@ app.add_middleware(
     allow_headers=["*"],
 )
 
+@app.exception_handler(BaseServiceException)
+async def service_exception_handler(request: Request, exc: BaseServiceException):
+    logger = logging.getLogger("web_api.exception")
+    if exc.original_exception:
+        logger.error(
+            f"Service Exception [{exc.code}] on {request.url.path}: {exc.message} - "
+            f"Underlying Error: {type(exc.original_exception).__name__}: {exc.original_exception}",
+            exc_info=exc.original_exception
+        )
+    else:
+        logger.warning(f"Service Exception [{exc.code}] on {request.url.path}: {exc.message}")
+    
+    trace_id = getattr(request.state, "request_id", "-")
+    return JSONResponse(
+        status_code=exc.status_code,
+        content={
+            "success": False,
+            "error_code": exc.code,
+            "message": exc.message,
+            "error": exc.message,  # Backward compatibility
+            "trace_id": trace_id
+        }
+    )
+
 from authentication.router import router as auth_router
 app.include_router(auth_router, tags=["Authentication"])
 
diff --git a/web_api/app_database/config.py b/web_api/app_database/config.py
index 03d686c..e3e15f4 100644
--- a/web_api/app_database/config.py
+++ b/web_api/app_database/config.py
@@ -1,13 +1,13 @@
 """
 Application Database Configuration
 
-Uygulama veritabanı bağlantı ayarları.
-Kullanıcı yönetimi, loglama ve workspace verilerini tutan veritabanı için kullanılır.
+Application metadata database connection settings.
+Used for user management, auditing logs, and workspace configuration storage.
 
 Environment Variables:
-    DB_USER: SQL Server kullanıcı adı (default: "sa")
-    DB_PASSWORD: SQL Server şifresi (default: "")
-    APP_DATABASE_URL: Tam connection string (override için)
+    DB_USER: SQL Server username (default: "sa")
+    DB_PASSWORD: SQL Server password (default: "")
+    APP_DATABASE_URL: Full connection string (optional override)
 """
 import os
 from dotenv import load_dotenv
diff --git a/web_api/authentication/__init__.py b/web_api/authentication/__init__.py
index e69de29..34a84a4 100644
--- a/web_api/authentication/__init__.py
+++ b/web_api/authentication/__init__.py
@@ -0,0 +1,3 @@
+from .exceptions import UserAlreadyExistsError, InvalidCredentialsError
+
+__all__ = ["UserAlreadyExistsError", "InvalidCredentialsError"]
diff --git a/web_api/authentication/router.py b/web_api/authentication/router.py
index cd58146..5928c65 100644
--- a/web_api/authentication/router.py
+++ b/web_api/authentication/router.py
@@ -4,11 +4,11 @@ FastAPI router for user login, registration, logout, and self-information.
 Strictly typed and documented.
 """
 from fastapi import APIRouter, HTTPException, Response, Request, Depends
-from datetime import datetime
 import os
 from typing import Any
-from slowapi import Limiter
-from slowapi.util import get_remote_address
+from common.limiter import limiter
+
+from authentication.exceptions import UserAlreadyExistsError
 
 from authentication import config
 from authentication import schemas
@@ -20,7 +20,7 @@ from app_database.models import User
 
 router = APIRouter(prefix="/api")
 
-limiter = Limiter(key_func=get_remote_address)
+# Using centralized limiter
 
 
 @router.post("/login", response_model=schemas.Token)
@@ -102,7 +102,7 @@ async def register(
         existing_user: User | None = result.scalars().first()
         
         if existing_user:
-            raise HTTPException(status_code=400, detail="Email already registered")
+            raise UserAlreadyExistsError("Email already registered")
         
         new_user: User = User(
             username=user.username,
diff --git a/web_api/authentication/services.py b/web_api/authentication/services.py
index 52e2bfc..2423479 100644
--- a/web_api/authentication/services.py
+++ b/web_api/authentication/services.py
@@ -1,11 +1,11 @@
 """
 Authentication Service Layer
-JWT token oluşturma, doğrulama ve kullanıcı yetkilendirme işlemleri
+JWT token generation, verification, and user authorization operations.
 """
 from datetime import datetime, timedelta, UTC
 from typing import Optional
 from jose import JWTError, jwt
-from fastapi import HTTPException, status, Request, Depends
+from fastapi import HTTPException, status, Request
 from sqlalchemy.future import select
 
 from authentication import config
@@ -16,14 +16,14 @@ from app_database.app_database import AppDatabase
 
 def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
     """
-    JWT access token oluşturur
+    Generates a new JWT access token.
     
     Args:
-        data: Token içeriği (genellikle {"sub": user_id})
-        expires_delta: Token geçerlilik süresi (varsayılan: config.ACCESS_TOKEN_EXPIRE_MINUTES)
-    
+        data: Payload content (typically {"sub": user_id}).
+        expires_delta: Token expiration duration (defaults to config.ACCESS_TOKEN_EXPIRE_MINUTES).
+        
     Returns:
-        JWT token string
+        str: Generated JWT token string.
     """
     to_encode = data.copy()
     expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
@@ -34,13 +34,13 @@ def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -
 
 def verify_token(token: str) -> Optional[dict]:
     """
-    JWT token'ı doğrular
+    Validates a JWT token.
     
     Args:
-        token: JWT token string
-    
+        token: JWT token string.
+        
     Returns:
-        Token payload veya None
+        Optional[dict]: Decoded token payload if valid, otherwise None.
     """
     try:
         payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
@@ -51,13 +51,13 @@ def verify_token(token: str) -> Optional[dict]:
 
 def get_user_id_from_payload(payload: dict) -> Optional[str]:
     """
-    Token payload'ından user_id çıkarır
+    Extracts the user_id (sub) from the token payload.
     
     Args:
-        payload: JWT token payload
-    
+        payload: Decoded JWT token payload.
+        
     Returns:
-        User ID string veya None
+        Optional[str]: User ID string if present, otherwise None.
     """
     try:
         user_id = payload.get("sub")
@@ -70,26 +70,26 @@ async def get_current_user(
     request: Request
 ) -> User:
     """
-    Request'ten JWT token alır, doğrular ve User nesnesini döndürür
+    Extracts JWT token from Request, validates it, and returns the User object.
     
     Args:
-        request: FastAPI Request nesnesi
-    
+        request: FastAPI Request object.
+        
     Returns:
-        User: Authenticated user
-    
+        User: Authenticated user.
+        
     Raises:
-        HTTPException: Token geçersiz veya kullanıcı bulunamaz ise
+        HTTPException: If token is invalid or user is not found.
     """
-    # AppDatabase instance'ını request state'den al (Circular import önlemek için)
+    # Retrieve AppDatabase instance from request state to prevent circular imports
     app_db: AppDatabase = request.app.state.app_db
 
-    # Token'ı sadece cookie'den al
+    # Retrieve token solely from cookies
     token = request.cookies.get("access_token")
     
     credentials_exception = HTTPException(
         status_code=status.HTTP_401_UNAUTHORIZED,
-        detail="Geçersiz token",
+        detail="Invalid token",
         headers={"WWW-Authenticate": "Bearer"}
     )
     
@@ -106,7 +106,7 @@ async def get_current_user(
         print(f"JWT Error: {str(e)}")
         raise credentials_exception
     
-    # AppDatabase'den user'ı çek
+    # Retrieve user from AppDatabase
     async with app_db.get_app_db() as db:
         result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
         user = result.scalars().first()
diff --git a/web_api/database_provider/config.py b/web_api/database_provider/config.py
index 80654bb..a5ee2d4 100644
--- a/web_api/database_provider/config.py
+++ b/web_api/database_provider/config.py
@@ -1,15 +1,15 @@
 """
 Database Provider Configuration
-Erişilebilir SQL Server instance listesi ve connection string template
+List of accessible SQL Server instances and connection string templates.
 """
 import os
 from typing import List
 from dotenv import load_dotenv
 
-# .env dosyasını yükle
+# Load .env file
 load_dotenv()
 
-# Environment'tan virgülle ayrılmış server listesi al, yoksa default kullan
+# Retrieve comma-separated server list from environment, otherwise use default
 _server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
 SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]
 
@@ -17,6 +17,10 @@ SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip
 DB_USER = os.getenv("DB_USER", "sa")
 DB_PASSWORD = os.getenv("DB_PASSWORD", "")
 
+# Central service account credentials for executing queries on target databases
+CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER", DB_USER)
+CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD", DB_PASSWORD)
+
 # Engine Cache Cleanup Interval (seconds)
 # Default: 1800 seconds (30 minutes)
 TIME_INTERVAL_FOR_CACHE = int(os.getenv("ENGINE_CACHE_TTL_SECONDS", "1800"))
@@ -31,13 +35,13 @@ TECHNOLOGY_DRIVER_MAP = {
 
 def get_driver_for_technology(technology: str) -> str:
     """
-    Database technology'sine göre uygun driver'ı döndürür.
+    Returns the appropriate driver for a given database technology.
     
     Args:
-        technology: Database teknolojisi (mssql, mysql, postgresql, vb.)
+        technology: Database technology (e.g., mssql, mysql, postgresql, etc.).
         
     Returns:
-        str: İlgili driver adı (aioodbc, aiomysql, asyncpg)
+        str: Corresponding driver name (e.g., aioodbc, aiomysql, asyncpg).
         
     Example:
         >>> get_driver_for_technology("mssql")
@@ -50,22 +54,23 @@ def get_driver_for_technology(technology: str) -> str:
     tech = technology.lower().strip()
     return TECHNOLOGY_DRIVER_MAP.get(tech, "aioodbc")  # default: aioodbc
 
-# Connection string builder fonksiyonları
+
+# Connection string builder functions
 def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
     """
-    Kullanıcıya özel database connection string oluşturur.
-    Technology'ye göre uygun format kullanır.
+    Generates a database connection string using centralized or custom credentials.
+    Formats the string dynamically based on the technology.
     
     Args:
-        tech: Kullanılacak teknoloji örn: mssql, mysql, postgresql
-        driver: Kullanılacak driver örn: aioodbc, aiomysql, asyncpg
-        username: Database kullanıcı adı
-        password: Database şifresi
-        servername: Database server adı (ör: localhost, server1)
-        database: Bağlanılacak veritabanı adı
+        tech: Database technology e.g., mssql, mysql, postgresql.
+        driver: Database driver e.g., aioodbc, aiomysql, asyncpg.
+        username: Database username.
+        password: Database password.
+        servername: Database server hostname or IP.
+        database: Target database name.
         
     Returns:
-        str: İstenilen connection string
+        str: Formatted connection string.
     """
     tech = tech.lower()
     
@@ -84,7 +89,7 @@ def create_connection_string(tech: str, driver: str, username: str, password: st
         # PostgreSQL
         return f"postgresql+{driver}://{username}:{password}@{servername}/{database}"
     else:
-        # Default olarak MSSQL formatını kullan
+        # Fallback to MSSQL format
         return (
             f"{tech}+{driver}://{username}:{password}@{servername}/{database}"
             "?driver=ODBC+Driver+18+for+SQL+Server"
@@ -92,19 +97,20 @@ def create_connection_string(tech: str, driver: str, username: str, password: st
             "&connection timeout=30"
         )
 
+
 def get_master_connection_string(server: str) -> str:
     """
-    Master database'e bağlanmak için connection string oluşturur.
-    Veritabanı listesini almak için kullanılır (sys.databases sorgusu).
+    Generates a connection string for connecting to the master database.
+    Used for administrative metadata retrieval (e.g., sys.databases query).
     
     Args:
-        server: SQL Server instance adı
+        server: SQL Server instance name or address.
         
     Returns:
-        str: Master database için connection string
+        str: Connection string for the master database.
         
     Note:
-        DB_USER ve DB_PASSWORD environment variable'larından alınır
+        DB_USER and DB_PASSWORD are fetched from the environment variables.
     """
     return (
         f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
diff --git a/web_api/database_provider/database.py b/web_api/database_provider/database.py
index 5eb4595..579eacc 100644
--- a/web_api/database_provider/database.py
+++ b/web_api/database_provider/database.py
@@ -9,8 +9,8 @@ import app_database.models as models
 from database_provider.config import (
     create_connection_string, 
     get_driver_for_technology,
-    DB_USER,
-    DB_PASSWORD
+    CENTRAL_DB_USER,
+    CENTRAL_DB_PASSWORD
 )
 from contextlib import asynccontextmanager
 from .engine_cache import EngineCache
@@ -77,8 +77,8 @@ class DatabaseProvider:
             driver=driver,
             servername=servername,
             database=database_name,
-            username=DB_USER,
-            password=DB_PASSWORD,
+            username=CENTRAL_DB_USER,
+            password=CENTRAL_DB_PASSWORD,
         )
         
         engine = await self.engine_cache.get_engine(conn_str, owner_id=user.id)
diff --git a/web_api/dependencies.py b/web_api/dependencies.py
index 0a7e737..d586ca3 100644
--- a/web_api/dependencies.py
+++ b/web_api/dependencies.py
@@ -1,6 +1,6 @@
 """
-Ortak Dependency Injection Fonksiyonları
-Tüm router'lar bu fonksiyonları kullanarak app.state'ten instance'ları alır
+Common Dependency Injection Functions
+All routers use these functions to retrieve service instances from app.state.
 """
 from fastapi import Request
 from fastapi import Depends, HTTPException, status
@@ -12,19 +12,20 @@ from app_database.models import Workspace, User
 
 from query_execution.services import QueryService
 from workspaces.services import WorkspaceService
+from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError
 
 def get_app_db(request: Request) -> AppDatabase:
     """
-    AppDatabase instance'ını döndürür.
-    Kullanım: app_db: AppDatabase = Depends(get_app_db)
+    Returns the AppDatabase instance.
+    Usage: app_db: AppDatabase = Depends(get_app_db)
     """
     return request.app.state.app_db
 
 
 def get_db_provider(request: Request) -> DatabaseProvider:
     """
-    DatabaseProvider instance'ını döndürür.
-    Kullanım: db_provider: DatabaseProvider = Depends(get_db_provider)
+    Returns the DatabaseProvider instance.
+    Usage: db_provider: DatabaseProvider = Depends(get_db_provider)
     """
     return request.app.state.db_provider
 
@@ -33,8 +34,8 @@ def get_db_provider(request: Request) -> DatabaseProvider:
 
 def get_query_service(request: Request) -> QueryService:
     """
-    QueryService instance'ını döndürür.
-    Kullanım: query_service: QueryService = Depends(get_query_service)
+    Returns the QueryService instance.
+    Usage: query_service: QueryService = Depends(get_query_service)
     """
     app_db = get_app_db(request)
     db_provider = get_db_provider(request)
@@ -44,8 +45,8 @@ def get_query_service(request: Request) -> QueryService:
 
 def get_workspace_service(request: Request) -> WorkspaceService:
     """
-    WorkspaceService instance'ını döndürür.
-    Kullanım: workspace_service: WorkspaceService = Depends(get_workspace_service)
+    Returns the WorkspaceService instance.
+    Usage: workspace_service: WorkspaceService = Depends(get_workspace_service)
     """
     app_db = get_app_db(request)
     return WorkspaceService(app_db=app_db)
@@ -54,8 +55,8 @@ from admin.services import AdminService
 
 def get_admin_service(request: Request) -> AdminService:
     """
-    AdminService instance'ını döndürür.
-    Kullanım: admin_service: AdminService = Depends(get_admin_service)
+    Returns the AdminService instance.
+    Usage: admin_service: AdminService = Depends(get_admin_service)
     """
     app_db = get_app_db(request)
     db_provider = get_db_provider(request)
@@ -76,9 +77,9 @@ async def ensure_owner(workspace_id: int,
     async with app_db.get_app_db() as db:
         ws = await db.get(Workspace, workspace_id)
         if not ws:
-            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
+            raise WorkspaceNotFoundError("Workspace not found")
         if ws.user_id != current_user.id:
-            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't own this workspace.")
+            raise WorkspaceAccessDeniedError("You don't own this workspace.")
         return ws
 
 
@@ -86,7 +87,7 @@ from notification import NotificationService
 
 def get_notification_service(request: Request) -> NotificationService:
     """
-    NotificationService instance'ını döndürür.
-    Kullanım: notification_service: NotificationService = Depends(get_notification_service)    
+    Returns the NotificationService instance.
+    Usage: notification_service: NotificationService = Depends(get_notification_service)    
     """
     return NotificationService()
\ No newline at end of file
diff --git a/web_api/entrypoint.sh b/web_api/entrypoint.sh
index 5a69086..c798812 100644
--- a/web_api/entrypoint.sh
+++ b/web_api/entrypoint.sh
@@ -1,7 +1,7 @@
 #!/bin/bash
 set -e
 
-# Veritabanı bağlantısını bekle (Retry mekanizması)
+# Wait for database connection (Retry mechanism)
 echo "Waiting for SQL Server to be ready..."
 max_retries=30
 count=0
@@ -21,5 +21,5 @@ if [ $count -eq $max_retries ]; then
     exit 1
 fi
 
-# Uygulamayı başlat
+# Start the application
 exec "$@"
diff --git a/web_api/middlewares/auth_middleware.py b/web_api/middlewares/auth_middleware.py
index dd3039b..af4b350 100644
--- a/web_api/middlewares/auth_middleware.py
+++ b/web_api/middlewares/auth_middleware.py
@@ -77,5 +77,16 @@ class AuthMiddleware(BaseHTTPMiddleware):
             )
             return response
         
-        response: StarletteResponse = await call_next(request)
-        return response
\ No newline at end of file
+        user_token = None
+        if user_id:
+            request.state.user_id = user_id
+            from common.logging_config import user_id_var
+            user_token = user_id_var.set(user_id)
+        
+        try:
+            response: StarletteResponse = await call_next(request)
+            return response
+        finally:
+            if user_token:
+                from common.logging_config import user_id_var
+                user_id_var.reset(user_token)
\ No newline at end of file
diff --git a/web_api/query_execution/__init__.py b/web_api/query_execution/__init__.py
index a16d457..fe0fc58 100644
--- a/web_api/query_execution/__init__.py
+++ b/web_api/query_execution/__init__.py
@@ -1,3 +1,4 @@
 from .services import QueryService
+from .exceptions import QueryExecutionError, QueryAnalysisRejectedError
 
-__all__ = ["QueryService"]
\ No newline at end of file
+__all__ = ["QueryService", "QueryExecutionError", "QueryAnalysisRejectedError"]
\ No newline at end of file
diff --git a/web_api/query_execution/router.py b/web_api/query_execution/router.py
index aa608b4..e64cb20 100644
--- a/web_api/query_execution/router.py
+++ b/web_api/query_execution/router.py
@@ -5,21 +5,19 @@ All routes are strictly typed and documented.
 """
 from fastapi import APIRouter, Depends, HTTPException, Request
 from typing import List, Any
-from slowapi import Limiter
-from slowapi.util import get_remote_address
+from common.limiter import limiter
 
 from query_execution import config
 from query_execution import schemas as query_models
 from query_execution.services import QueryService
 from authentication.services import get_current_user
-from dependencies import get_app_db, get_db_provider, get_query_service
-from app_database.app_database import AppDatabase
+from dependencies import get_db_provider, get_query_service
 from database_provider import DatabaseProvider
 from app_database.models import User
 
 router = APIRouter(prefix="/api")
 
-limiter = Limiter(key_func=get_remote_address)
+# Using centralized limiter
 
 
 @router.post("/execute_query", response_model=query_models.SQLResponse)
diff --git a/web_api/query_execution/services.py b/web_api/query_execution/services.py
index 05e6a8c..3ef2147 100644
--- a/web_api/query_execution/services.py
+++ b/web_api/query_execution/services.py
@@ -18,6 +18,12 @@ from app_database.models import User, QueryData, Workspace
 from query_execution.query_analyzer import QueryAnalyzer
 from notification import NotificationService
 
+import logging
+from common.exceptions import BaseServiceException
+from query_execution.exceptions import QueryExecutionError, QueryAnalysisRejectedError
+
+logger = logging.getLogger(__name__)
+
 class QueryService:
     """
     Query execution, security analysis, and logging service.
@@ -59,6 +65,7 @@ class QueryService:
         """
         log_id: int | None = None
         try:
+            logger.info(f"Initiating query execution on server '{server_name}', database '{database_name}'")
             log_id = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
             
             # Resolve target database technology from the database provider config
@@ -102,9 +109,9 @@ class QueryService:
                         workspace_id: int = workspace.id
                         await db_session.commit()
                         
-                    print(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
+                    logger.info(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
                 except Exception as save_exc:
-                    print(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
+                    logger.error(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
                 
                 try:
                     if self.notification_service:
@@ -119,13 +126,11 @@ class QueryService:
                             query=query
                         )
                 except Exception as notif_exc:
-                    print(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
+                    logger.error(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
                 
-                return {
-                    "response_type": "error",
-                    "data": [],
-                    "error": f"{error_msg}. Query saved to your workspaces and sent for admin approval."
-                }
+                raise QueryAnalysisRejectedError(
+                    message=f"{error_msg}. Query saved to your workspaces and sent for admin approval."
+                )
                 
             async with self.database_provider.get_session(
                 user=user,
@@ -167,21 +172,22 @@ class QueryService:
                 )
                 
                 if row_count > config.MAX_ROW_COUNT_WARNING:
-                    print(f"Warning: Query returned {row_count} rows")
+                    logger.warning(f"Query returned high row count: {row_count} rows")
+                
+                logger.info(f"Query executed successfully. Result: {message}")
                 return result_data
                 
+        except BaseServiceException:
+            # Re-raise already translated service exceptions
+            raise
         except Exception as e:
             error_msg: str = str(e)
-            print(f"Query execution error: {error_msg}")
+            logger.error(f"Query execution failed: {error_msg}")
             if log_id:
                 await self.app_db.update_log(
                     log_id=log_id,
                     successfull=False,
                     error=error_msg
                 )
-            return {
-                "response_type": "error",
-                "data": [],
-                "error": error_msg
-            }
+            raise QueryExecutionError(error_msg, original_exception=e)
  
\ No newline at end of file
diff --git a/web_api/tests/conftest.py b/web_api/tests/conftest.py
index 5d4f500..9ec068d 100644
--- a/web_api/tests/conftest.py
+++ b/web_api/tests/conftest.py
@@ -30,6 +30,10 @@ async def async_client():
     app.state.db_provider = DatabaseProvider()
     await app.state.db_provider.start_cache_loop()
     
+    # Disable rate limiter for testing to prevent 429 Too Many Requests
+    if hasattr(app.state, "limiter"):
+        app.state.limiter.enabled = False
+    
     transport = ASGITransport(app=app)
     async with AsyncClient(transport=transport, base_url="http://test") as client:
         yield client
diff --git a/web_api/workspaces/__init__.py b/web_api/workspaces/__init__.py
index fb4791a..a6e4802 100644
--- a/web_api/workspaces/__init__.py
+++ b/web_api/workspaces/__init__.py
@@ -2,3 +2,7 @@
 Workspaces Module
 Kullanıcı workspace (kaydedilmiş query) yönetimi
 """
+from .services import WorkspaceService
+from .exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError
+
+__all__ = ["WorkspaceService", "WorkspaceNotFoundError", "WorkspaceAccessDeniedError"]
diff --git a/web_api/workspaces/services.py b/web_api/workspaces/services.py
index 63f493d..5d72dda 100644
--- a/web_api/workspaces/services.py
+++ b/web_api/workspaces/services.py
@@ -14,6 +14,12 @@ from query_execution import config as query_config
 from database_provider import DatabaseProvider
 from app_database.models import User
 
+import logging
+from common.exceptions import BaseServiceException
+from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError
+
+logger = logging.getLogger(__name__)
+
 class WorkspaceService:
     """
     Workspace CRUD operations service
@@ -72,8 +78,8 @@ class WorkspaceService:
             return {"success": True, "workspace_id": workspace.id}
         except Exception as e:
             await db.rollback()
-            print(f"Error creating workspace: {e}")
-            return {"success": False, "error": str(e)}
+            logger.error(f"Error creating workspace: {e}")
+            raise BaseServiceException(f"Error creating workspace: {str(e)}", original_exception=e)
         
     async def get_workspace_by_id(self, db: AsyncSession, user_id: int):
         """
@@ -135,7 +141,7 @@ class WorkspaceService:
             workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
             workspace = workspace_result.scalars().first()
             if not workspace:
-                return False
+                raise WorkspaceNotFoundError("Workspace not found")
             
             query_id = workspace.query_id
             
@@ -149,10 +155,12 @@ class WorkspaceService:
             
             await db.commit()
             return True
+        except BaseServiceException:
+            raise
         except Exception as e:
             await db.rollback()
-            print(f"Error deleting workspace: {e}")
-            return False
+            logger.error(f"Error deleting workspace: {e}")
+            raise BaseServiceException(f"Error deleting workspace: {str(e)}", original_exception=e)
     
     async def update_workspace(self, db: AsyncSession, workspace_id: int, query: str = None, status: str = None):
         """
@@ -171,12 +179,12 @@ class WorkspaceService:
             workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
             workspace = workspace_result.scalars().first()
             if not workspace:
-                return False
+                raise WorkspaceNotFoundError("Workspace not found")
             
             query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
             query_data = query_result.scalars().first()
             if not query_data:
-                return False
+                raise WorkspaceNotFoundError("Query data not found for this workspace")
             
             if query:
                 query_data.query = query
@@ -184,10 +192,12 @@ class WorkspaceService:
                 query_data.status = status
             await db.commit()
             return True
+        except BaseServiceException:
+            raise
         except Exception as e:
             await db.rollback()
-            print(f"Error updating workspace: {e}")
-            return False
+            logger.error(f"Error updating workspace: {e}")
+            raise BaseServiceException(f"Error updating workspace: {str(e)}", original_exception=e)
     
     async def get_workspace_detail_by_id(self, db: AsyncSession, workspace_id: int, user_id: int):
         """
@@ -203,12 +213,16 @@ class WorkspaceService:
         """
         workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
         workspace = workspace_result.scalars().first()
-        if not workspace or workspace.user_id != user_id:
-            return None
+        if not workspace:
+            raise WorkspaceNotFoundError("Workspace not found")
+        if workspace.user_id != user_id:
+            raise WorkspaceAccessDeniedError("You do not own this workspace")
+            
         query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
         query_data = query_result.scalars().first()
         if not query_data:
-            return None
+            raise WorkspaceNotFoundError("Query data not found for this workspace")
+            
         return {
             "id": workspace.id,
             "name": workspace.name,
@@ -240,46 +254,55 @@ class WorkspaceService:
             workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
             workspace: Workspace | None = workspace_result.scalars().first()
             if not workspace:
-                return {"response_type": "error", "data": [], "error": "Workspace not found"}
+                raise WorkspaceNotFoundError("Workspace not found")
+
+            if workspace.user_id != current_user.id:
+                raise WorkspaceAccessDeniedError("You do not own this workspace")
 
             query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
             query_data: QueryData | None = query_result.scalars().first()
             if not query_data:
-                return {"response_type": "error", "data": [], "error": "Query data not found"}
+                raise WorkspaceNotFoundError("Query data not found for this workspace")
+                
             # enforce approval
             if not workspace.show_results or query_data.status != "approved_with_results":
-                return {"response_type": "error", "data": [], "error": "This workspace is not approved for execution"}
+                from query_execution.exceptions import QueryAnalysisRejectedError
+                raise QueryAnalysisRejectedError("This workspace is not approved for execution")
 
         log_id: int | None = None
         try:
+            logger.info(f"Executing approved workspace {workspace_id} on server '{query_data.servername}'")
             log_id = await self.app_db.create_log(user=current_user, query=query_data.query, machine_name=query_data.servername, approved_execution=True)
 
             async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
-                sql_query = text(query_data.query)
-                result = await session.execute(sql_query)
-                
-                row_count: int = 0
-                message: str = ""
-                result_data: list[dict[str, Any]] = []
-                
-                if result.returns_rows:
-                    rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
-                    row_count = len(rows)
-                    if row_count >= query_config.MAX_ROW_COUNT_LIMIT:
-                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
-                    else:
-                        message = f"{row_count} rows returned"
-                    result_data = [dict(row._mapping) for row in rows]
-                else:
-                    row_count = result.rowcount if result.rowcount is not None else 0
-                    message = f"{row_count} rows affected"
-                    result_data = []
+                  sql_query = text(query_data.query)
+                  result = await session.execute(sql_query)
+                  
+                  row_count: int = 0
+                  message: str = ""
+                  result_data: list[dict[str, Any]] = []
+                  
+                  if result.returns_rows:
+                      rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
+                      row_count = len(rows)
+                      if row_count >= query_config.MAX_ROW_COUNT_LIMIT:
+                          message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
+                      else:
+                          message = f"{row_count} rows returned"
+                      result_data = [dict(row._mapping) for row in rows]
+                  else:
+                      row_count = result.rowcount if result.rowcount is not None else 0
+                      message = f"{row_count} rows affected"
+                      result_data = []
 
             await self.app_db.update_log(log_id=log_id, successfull=True, row_count=row_count)
-
+            logger.info(f"Workspace {workspace_id} executed successfully. Result: {message}")
             return {"response_type": "data", "data": result_data, "message": message}
 
+        except BaseServiceException:
+            raise
         except Exception as e:
             if log_id:
                 await self.app_db.update_log(log_id=log_id, successfull=False, error=str(e))
-            return {"response_type": "error", "data": [], "error": str(e)}
\ No newline at end of file
+            from query_execution.exceptions import QueryExecutionError
+            raise QueryExecutionError(str(e), original_exception=e)
\ No newline at end of file

---

## Part 2: Newly Created Files (Full Contents)


### [NEW] web_api/authentication/exceptions.py
```python
"""
Authentication Exceptions
Custom exceptions for user authentication, registration, and session verification.
"""
from common.exceptions import BaseServiceException

class UserAlreadyExistsError(BaseServiceException):
    """Raised when registering a new user with an email that is already taken."""
    status_code = 400
    code = "USER_ALREADY_EXISTS"

class InvalidCredentialsError(BaseServiceException):
    """Raised when user login credentials verification fails."""
    status_code = 401
    code = "INVALID_CREDENTIALS"
```

### [NEW] web_api/common/exceptions.py
```python
"""
Common Exceptions Module
Contains the base service exception class for modular exception translation.
"""
from typing import Optional

class BaseServiceException(Exception):
    """
    Base exception class for all business/service layer errors.
    
    Attributes:
        message: Safe error message shown to the client.
        status_code: HTTP status code mapped to this exception.
        code: Enterprise error code string (e.g., WORKSPACE_NOT_FOUND).
        original_exception: Underlying infrastructure exception (e.g., SQLAlchemyError).
    """
    status_code: int = 500
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        self.message: str = message
        self.original_exception: Optional[Exception] = original_exception
        super().__init__(self.message)
```

### [NEW] web_api/common/logging_config.py
```python
"""
Logging Configuration Module
Configures structured logging with dynamic Trace ID and User ID tracking using contextvars.
"""
import logging
from contextvars import ContextVar
from typing import Any

# Context variables to hold Request Trace ID and User ID throughout the request lifecycle
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

class ContextFilter(logging.Filter):
    """
    logging.Filter that injects trace_id and user_id context variables into every log record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.user_id = user_id_var.get()
        return True

def setup_logging() -> None:
    """
    Initializes and configures the logging system with a custom formatter and context filters.
    """
    log_format: str = "%(asctime)s [%(levelname)s] [Trace: %(trace_id)s] [User: %(user_id)s] %(name)s: %(message)s"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicate logs in some environments
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Custom formatter
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # Inject ContextFilter
    context_filter = ContextFilter()
    console_handler.addFilter(context_filter)
    
    root_logger.addHandler(console_handler)
    
    # Suppress verbose loggers from libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

### [NEW] web_api/common/__init__.py
```python
from .exceptions import BaseServiceException
from .logging_config import setup_logging
from .limiter import limiter

__all__ = ["BaseServiceException", "setup_logging", "limiter"]

```

### [NEW] web_api/common/limiter.py
```python
"""
Rate Limiter Configuration Module
Defines a central, shared Limiter instance to be used across all routers.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Define a shared limiter instance
limiter: Limiter = Limiter(key_func=get_remote_address)
```

### [NEW] web_api/middlewares/trace_middleware.py
```python
"""
Trace Middleware Module
Generates a unique Trace ID for every request, logs request metrics, and exposes the ID in response headers.
"""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from fastapi import Request

from common.logging_config import trace_id_var

logger = logging.getLogger("web_api.trace")

class TraceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes a unique Trace ID (Request ID) for tracking and auditing.
    Logs request initiation, completion duration, and status code.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Resolve Trace ID (Check if client/gateway passed X-Request-ID, otherwise generate)
        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 2. Set Trace ID in contextvars for logging
        trace_token = trace_id_var.set(request_id)
        
        # 3. Log request initiation
        logger.info(f"Request started: {request.method} {request.url.path}")
        
        start_time: float = time.time()
        try:
            response: Response = await call_next(request)
            
            # 4. Measure and log request completion
            process_time: float = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
            )
            
            # 5. Expose Trace ID in response headers
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            process_time: float = (time.time() - start_time) * 1000
            logger.error(
                f"Request crashed: {request.method} {request.url.path} - "
                f"Error: {type(e).__name__} - Duration: {process_time:.2f}ms",
                exc_info=e
            )
            raise e
        finally:
            # 6. Reset contextvars to prevent memory leaks or context contamination
            trace_id_var.reset(trace_token)
```

### [NEW] web_api/query_execution/exceptions.py
```python
"""
Query Execution Exceptions
Custom exceptions for the query execution and security analysis service layer.
"""
from common.exceptions import BaseServiceException

class QueryExecutionError(BaseServiceException):
    """Raised when a SQL query execution fails inside the target database."""
    status_code = 400
    code = "QUERY_EXECUTION_FAILED"

class QueryAnalysisRejectedError(BaseServiceException):
    """Raised when a query fails the AST security analysis and is sent for admin approval."""
    status_code = 400
    code = "QUERY_REJECTED_BY_ANALYZER"
```

### [NEW] web_api/tests/integration/test_error_handling_and_trace.py
```python
"""
Integration tests for the centralized Exception Handling and Trace ID tracking system.
Verifies Trace ID headers, global exception routing, and error translation.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app import app
from app_database.models import Databases

@pytest.fixture
def mock_db_session():
    """
    Fixture that patches DatabaseProvider.get_session to return a mock session.
    """
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    
    @asynccontextmanager
    async def fake_get_session(user, servername, database_name):
        yield mock_session
        
    with patch("database_provider.DatabaseProvider.get_session", side_effect=fake_get_session):
        yield mock_session, mock_result

@pytest.mark.asyncio
async def test_trace_id_header_on_public_route(async_client: AsyncClient):
    """
    Test that even public endpoints (like /health) return the X-Request-ID trace header.
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

@pytest.mark.asyncio
async def test_query_execution_error_translation(async_client: AsyncClient, mock_db_session):
    """
    Test that database execution exceptions are wrapped into QueryExecutionError,
    caught by the global handler, and returned as a clean 400 Bad Request.
    """
    mock_session, mock_result = mock_db_session
    
    # 1. Inject mock database
    app_db = app.state.app_db
    async with app_db.get_app_db() as db:
        test_db = Databases(
            servername="trace-server",
            database_name="trace-db",
            technology="postgresql"
        )
        db.add(test_db)
        await db.commit()
    
    # Reload db_info in provider
    db_info = await app_db.get_db_info()
    app.state.db_provider.set_db_info(db_info)
    
    # 2. Register and login
    register_data = {
        "username": "traceuser",
        "email": "trace@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "trace@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 3. Configure mock session to raise a database execution exception (e.g. syntax error)
    mock_session.execute.side_effect = Exception("column 'non_existent' does not exist")
    
    # 4. Execute query
    query_payload = {
        "query": "SELECT non_existent FROM users",
        "servername": "trace-server",
        "database_name": "trace-db"
    }
    response = await async_client.post("/api/execute_query", json=query_payload)
    
    # Assert REST status is 400 (Bad Request) instead of 500 or 200 with error
    assert response.status_code == 400
    
    resp_data = response.json()
    assert resp_data["success"] is False
    assert resp_data["error_code"] == "QUERY_EXECUTION_FAILED"
    assert "column 'non_existent' does not exist" in resp_data["message"]
    assert "column 'non_existent' does not exist" in resp_data["error"]
    
    # Verify Trace ID matches the response header
    assert "X-Request-ID" in response.headers
    assert resp_data["trace_id"] == response.headers["X-Request-ID"]

@pytest.mark.asyncio
async def test_workspace_not_found_error_translation(async_client: AsyncClient):
    """
    Test that attempting to access a non-existent workspace raises WorkspaceNotFoundError
    which is translated by the global handler into a clean 404 Not Found.
    """
    # 1. Register and login
    register_data = {
        "username": "traceuser2",
        "email": "trace2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/register", json=register_data)
    
    login_data = {
        "email": "trace2@example.com",
        "password": "StrongPassword123!"
    }
    await async_client.post("/api/login", json=login_data)
    
    # 2. Get non-existent workspace (ID: 99999)
    response = await async_client.get("/api/get_workspace_by_id/99999")
    
    # Assert REST status is 404 (Not Found) instead of 400 or 500
    assert response.status_code == 404
    
    resp_data = response.json()
    assert resp_data["success"] is False
    assert resp_data["error_code"] == "WORKSPACE_NOT_FOUND"
    assert "Workspace not found" in resp_data["message"]
    
    # Verify Trace ID matches header
    assert "X-Request-ID" in response.headers
    assert resp_data["trace_id"] == response.headers["X-Request-ID"]
```

### [NEW] web_api/workspaces/exceptions.py
```python
"""
Workspaces Exceptions
Custom exceptions for the workspaces service layer.
"""
from common.exceptions import BaseServiceException

class WorkspaceNotFoundError(BaseServiceException):
    """Raised when a requested workspace is not found."""
    status_code = 404
    code = "WORKSPACE_NOT_FOUND"

class WorkspaceAccessDeniedError(BaseServiceException):
    """Raised when a user attempts to access a workspace they do not own."""
    status_code = 403
    code = "WORKSPACE_ACCESS_DENIED"
```

---

## Part 3: Modified Python (.py) and Shell (.sh) Files (Full Contents)


### [MODIFIED] web_api/admin/services.py
```python
"""
Admin Service Layer
Admin approval and management operations for risky queries
"""
from sqlalchemy.sql import select, text
from typing import Any, List, Dict
from app_database.models import QueryData, Workspace, User, Databases
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from .schemas import AdminApprovals
from query_execution import config

import logging
from common.exceptions import BaseServiceException
from workspaces.exceptions import WorkspaceNotFoundError

logger = logging.getLogger(__name__)

class BaseAdminService:
    """
    Base class for all admin services.
    Manages database connections for subclasses.
    """
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        self.app_db = app_db
        self.db_provider = db_provider

class AdminService(BaseAdminService):
    """
    Main Admin Service.
    
    Combines sub-services (Approval, DB Addition) to provide a unified interface.
    """
    
    def __init__(self, app_db: AppDatabase, db_provider: DatabaseProvider):
        # Establish connections by calling the Base class's __init__
        super().__init__(app_db, db_provider)
        
        # Initialize sub-services
        self.approval_service = AdminApprovalService(app_db, db_provider)
        self.db_addition_service = AdminDBAdditionService(app_db, db_provider)
        
        # Other services to be added in the future can go here
        # self.report_service = AdminReportService(app_db, db_provider)

    # --- Approval Service Delegations ---
    # We define the methods used in the router as wrappers here
    # So we don't have to change the router code.

    async def get_workspaces_for_approval(self):
        return await self.approval_service.get_workspaces_for_approval()

    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        return await self.approval_service.execute_for_preview(workspace_id, admin_user)

    async def reject_query_by_workspace_id(self, workspace_id: int):
        return await self.approval_service.reject_query_by_workspace_id(workspace_id)
            
    async def approve(self, workspace_id: int, show_results: bool):
        return await self.approval_service.approve(workspace_id, show_results)

class AdminApprovalService(BaseAdminService):
    """
    Sub-service handling admin approval operations.
    """

    async def get_workspaces_for_approval(self):
        """
        Retrieves workspaces waiting for admin approval.
        """
        result_list = []
        try:
            async with self.app_db.get_app_db() as db:
                results = await db.execute(select(QueryData).where(QueryData.status == "waiting_for_approval"))
                queries = results.scalars().all()
                if queries:
                    for query in queries:
                       
                        workspace_result = await db.execute(
                            select(Workspace).where(Workspace.query_id == query.id)
                        )
                        workspace = workspace_result.scalars().first()

                        user_result = await db.execute(select(User).where(User.id == query.user_id))
                        user = user_result.scalars().first()
                        
                        if workspace and user:
                            data = AdminApprovals(
                                user_id=query.user_id,
                                workspace_id=workspace.id,
                                username = user.username,
                                query= query.query,
                                database=query.database_name,
                                status= query.status,
                                risk_type=query.risk_type,
                                servername=query.servername
                            )

                            result_list.append(data)
            return result_list
        except  Exception as e:
            print(f"Error: {str(e)}")
            return []
        
    async def execute_for_preview(self, workspace_id: int, admin_user: User):
        """
        Executes and previews the query for the admin.
        """
        log_id = None
        
        async with self.app_db.get_app_db() as db:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                return {"success": False, "error": "Workspace not found"}
                    
            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                return {"success": False, "error": "Query data not found"}
                    
            user_result = await db.execute(select(User).where(User.id == admin_user.id))
            user = user_result.scalars().first()
            if not user:
                return {"success": False, "error": "User not found"}
            
            query_text = query_data.query
            servername = query_data.servername
            database_name = query_data.database_name
        
        try:
            log_id = await self.app_db.create_log(
                user=admin_user, 
                query=query_text, 
                machine_name=servername
            )
            
            async with self.db_provider.get_session(user, servername, database_name) as session:
                sql_query = text(query_text)
                result = await session.execute(sql_query)
                
                row_count: int = 0
                message: str | None = None
                result_data: list[dict[str, Any]] = []
                columns: list[str] = []
                
                if result.returns_rows:
                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                    row_count = len(rows)
                    result_data = [dict(row._mapping) for row in rows]
                    columns = list(result_data[0].keys()) if result_data else []
                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
                    else:
                        message = f"{row_count} rows returned"
                else:
                    row_count = result.rowcount if result.rowcount is not None else 0
                    message = f"{row_count} rows affected"
                    result_data = []
                    columns = []
            
            await self.app_db.update_log(
                log_id=log_id,
                successfull=True,
                row_count=row_count
            )

            return {
                "response_type": "data",
                "data": result_data,
                "columns": columns,
                "row_count": row_count,
                "message": message,
                "error": None
            }
        except Exception as e:
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=str(e)
                )

            print(f"Query preview failed: {e}")
            return {
                "response_type": "error",
                "data": [],
                "columns": [],
                "row_count": 0,
                "message": None,
                "error": str(e)
            }

    async def reject_query_by_workspace_id(self, workspace_id: int):
        """
        Rejects the query.
        """
        async with self.app_db.get_app_db() as db:
            try:
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace = workspace_result.scalars().first()
                if not workspace:
                    return {"success": False, "error": "Workspace not found"}
                    
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data = query_result.scalars().first()
                if not query_data:
                    return {"success": False, "error": "Query data not found"}
                
                query_data.status = "rejected"
                workspace.description = "Rejected by admin"
                
                await db.commit()
                return {"success": True}
                
            except Exception as e:
                await db.rollback()
                print(f"Error rejecting query: {e}")
                return {"success": False, "error": str(e)}
            
    async def approve(self, workspace_id: int, show_results: bool) -> dict[str, Any]:
        """
        Approves a query, enabling execution for the user.
        
        Args:
            workspace_id: The ID of the workspace containing the query.
            show_results: If True, the user can see execution results; otherwise, they cannot.
            
        Returns:
            dict[str, any]: A dictionary indicating success and the new query status.
        """
        async with self.app_db.get_app_db() as db:
            try:
                # 1. Fetch workspace by ID
                workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
                workspace: Workspace | None = workspace_result.scalars().first()
                if not workspace:
                    raise WorkspaceNotFoundError("Workspace not found")
                
                # 2. Fetch related QueryData
                query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
                query_data: QueryData | None = query_result.scalars().first()
                if not query_data:
                    raise WorkspaceNotFoundError("Query data not found for this workspace")
                
                # 3. Update status and description
                new_status: str = ""
                new_desc: str = ""
                if show_results:
                    new_status = "approved_with_results"
                    new_desc = "Approved by admin - User can execute"
                    workspace.show_results = True
                else:
                    new_status = "approved"
                    new_desc = "Approved by admin - User cannot execute"
                    workspace.show_results = False
                
                query_data.status = new_status
                workspace.description = new_desc
                
                await db.commit()
                
                logger.info(f"Query in workspace {workspace_id} approved by admin (Executable: {show_results})")
                return {
                    "success": True,
                    "status": new_status,
                    "message": f"Query approved successfully ({'executable' if show_results else 'not executable'})"
                }
            except BaseServiceException:
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Approval failed for workspace {workspace_id}: {e}")
                raise BaseServiceException(f"Approval failed: {str(e)}", original_exception=e)

class AdminDBAdditionService(BaseAdminService):
    """
    Service for adding new databases to the platform configuration.
    """
    async def add_database(self, servername: str, database_name: str, tech_name: str) -> dict[str, Any]:
        """
        Adds a new database server and database configuration to the application databases.
        
        Args:
            servername: The host/instance name of the SQL server.
            database_name: The name of the database.
            tech_name: The database technology/type (e.g., mssql, postgresql, mysql).
            
        Returns:
            dict[str, any]: A dictionary containing execution status and a message or error.
        """
        async with self.app_db.get_app_db() as db:
            try:
                # Check if it already exists
                existing = await db.execute(select(Databases).where(
                    Databases.servername == servername, 
                    Databases.database_name == database_name
                ))
                existing_db: Databases | None = existing.scalars().first()
                if existing_db:
                    raise BaseServiceException("Database already exists")

                database: Databases = Databases(servername=servername, database_name=database_name, technology=tech_name)
                db.add(database)
                await db.commit()
                logger.info(f"Database '{database_name}' on server '{servername}' successfully added by admin")
                return {"success": True, "message": "Database added successfully"}
            except BaseServiceException:
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Error adding database: {e}")
                raise BaseServiceException(f"Error adding database: {str(e)}", original_exception=e)
```

### [MODIFIED] web_api/app.py
```python
"""
WebQuery API - New Modular Architecture
Clean dependency injection with AppDatabase and DatabaseProvider
"""
import os
from dotenv import load_dotenv
import asyncio

# Load .env file (you can use .env.production for production)
env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file)

from common.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from common.exceptions import BaseServiceException
from middlewares.trace_middleware import TraceMiddleware
import logging
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from common.limiter import limiter
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app_database import AppDatabase
from database_provider import DatabaseProvider
from middlewares import AuthMiddleware

from slack_integration import SlackListener

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown lifecycle.
    """
    # Startup
    print("🚀 Application starting...")
    
    try:
        app.state.app_db = AppDatabase()
        # Real connection test
        async with app.state.app_db.app_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✓ AppDatabase connection successful")
        await app.state.app_db.create_tables()
        print("✓ Tables created/checked")
    except Exception as e:
        print(f"\n❌ FATAL: AppDatabase connection error!")
        print(f"   Error: {type(e).__name__}: {e}")
        print(f"   Please check the APP_DATABASE_URL environment variable")
        print(f"   Application cannot start!\n")
        await app.state.app_db.app_engine.dispose() if hasattr(app.state, 'app_db') else None
        raise SystemExit(1)
    
    try:
        app_db = app.state.app_db
        # Start Slack Listener (Socket Mode)
        app.state.slack_listener = SlackListener(app_db=app_db)
        slack_listener = app.state.slack_listener
        asyncio.create_task(slack_listener.start())

    except Exception as e:
        print(f"⚠️ Slack integration could not be started: {e}")
        print("   Slack features will be disabled, but the application will continue to run.")

    try:
        app.state.db_provider = DatabaseProvider()
        db_info = await app.state.app_db.get_db_info()
        app.state.db_provider.set_db_info(db_info)
        await app.state.db_provider.start_cache_loop()
        print("✓ DatabaseProvider ready, db_info loaded, and cache loop started")
    except Exception as e:
        print(f"\n❌ FATAL: DatabaseProvider initialization error!")
        print(f"   Error: {type(e).__name__}: {e}")
        print(f"   Please check the SQL_SERVER_NAMES environment variable and SQL Server connections")
        print(f"   Application cannot start!\n")
        # Cleanup
        await app.state.app_db.app_engine.dispose()
        raise SystemExit(1)

    print("All services started successfully\n")

    try:
        yield
    finally:
        print("\nApplication shutting down...")
        try:
            if hasattr(app.state, 'db_provider') and app.state.db_provider:
                await app.state.db_provider.close_engines()
                print("✓ DatabaseProvider connections closed")
        except Exception as e:
            print(f"DatabaseProvider shutdown error: {e}")
        try:
            if hasattr(app.state, 'app_db') and app.state.app_db:
                await app.state.app_db.app_engine.dispose()
                print("✓ AppDatabase connection closed")
        except Exception as e:
            print(f"AppDatabase shutdown error: {e}")
        print("Shutdown complete")

app = FastAPI(
    title="WebQuery API",
    description="Modular SQL Query Execution Platform",
    version="2.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(AuthMiddleware)
app.add_middleware(TraceMiddleware)
app.add_middleware(SlowAPIMiddleware)

cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "*")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")] if cors_origins_str else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(BaseServiceException)
async def service_exception_handler(request: Request, exc: BaseServiceException):
    logger = logging.getLogger("web_api.exception")
    if exc.original_exception:
        logger.error(
            f"Service Exception [{exc.code}] on {request.url.path}: {exc.message} - "
            f"Underlying Error: {type(exc.original_exception).__name__}: {exc.original_exception}",
            exc_info=exc.original_exception
        )
    else:
        logger.warning(f"Service Exception [{exc.code}] on {request.url.path}: {exc.message}")
    
    trace_id = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.code,
            "message": exc.message,
            "error": exc.message,  # Backward compatibility
            "trace_id": trace_id
        }
    )

from authentication.router import router as auth_router
app.include_router(auth_router, tags=["Authentication"])

from query_execution.router import router as query_router
app.include_router(query_router, tags=["Query Execution"])

from admin.router import router as admin_router
app.include_router(admin_router, tags=["Admin"])

from workspaces.router import router as workspace_router
app.include_router(workspace_router, tags=["Workspace"])

# from static_files.router import router as static_router
# app.include_router(static_router, tags=["Static Files"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_db": "connected" if getattr(app.state, 'app_db', None) else "disconnected",
        "db_provider": "connected" if getattr(app.state, 'db_provider', None) else "disconnected"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8080)),
        workers=int(os.getenv("WORKERS", 1)),
        reload=os.getenv("DEBUG", "True").lower() == "true"
    )```

### [MODIFIED] web_api/authentication/__init__.py
```python
from .exceptions import UserAlreadyExistsError, InvalidCredentialsError

__all__ = ["UserAlreadyExistsError", "InvalidCredentialsError"]
```

### [MODIFIED] web_api/authentication/router.py
```python
"""
Authentication Router Module
FastAPI router for user login, registration, logout, and self-information.
Strictly typed and documented.
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
import os
from typing import Any
from common.limiter import limiter

from authentication.exceptions import UserAlreadyExistsError

from authentication import config
from authentication import schemas
from authentication.services import create_access_token, get_current_user
from dependencies import get_app_db, get_db_provider
from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from app_database.models import User

router = APIRouter(prefix="/api")

# Using centralized limiter


@router.post("/login", response_model=schemas.Token)
@limiter.limit(config.RATE_LIMITER)
async def login(
    user: schemas.UserLogin,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, str]:
    """
    User login endpoint.
    Verifies credentials, creates JWT token, and writes login logs.
    
    Args:
        user: The user login credentials payload.
        response: The FastAPI response object (used to set auth cookies).
        request: The FastAPI request object (used for client IP logging).
        app_db: The application database manager instance.
        
    Returns:
        dict[str, str]: The access token response.
    """
    async with app_db.get_app_db() as db:
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        authenticated_user: User | None = result.scalars().first()
        
        if not authenticated_user or not authenticated_user.check_password(user.password):
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        user_id: int = int(authenticated_user.id)
        
        # Create JWT token
        user_to_login: dict[str, str] = {"sub": str(user_id)}
        token: str = create_access_token(user_to_login)
        
        response.set_cookie(
            key="access_token",
            value=token,
            secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
            samesite="strict",
            httponly=True,
            max_age=config.COOKIE_TOKEN_EXPIRE_MINUTES
        )
        
        client_ip: str = request.client.host if request.client else "unknown"
        await app_db.create_login_log(user_id=user_id, client_ip=client_ip)
        
        return {"access_token": token}


@router.post("/register")
@limiter.limit(config.RATE_LIMITER)
async def register(
    user: schemas.UserCreate,
    response: Response,
    request: Request,
    app_db: AppDatabase = Depends(get_app_db)
) -> dict[str, Any]:
    """
    New user registration endpoint.
    Registers a new user if the email is not already taken.
    
    Args:
        user: The user registration details payload.
        response: The FastAPI response object.
        request: The FastAPI request object.
        app_db: The application database manager instance.
        
    Returns:
        dict[str, any]: A dictionary indicating success or failure.
    """
    async with app_db.get_app_db() as db:
        from sqlalchemy.future import select
        
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user: User | None = result.scalars().first()
        
        if existing_user:
            raise UserAlreadyExistsError("Email already registered")
        
        new_user: User = User(
            username=user.username,
            email=user.email
        )
        try:
            new_user.set_password(user.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        db.add(new_user)
        try:
            await db.commit()
            await db.refresh(new_user)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")
        
        return {
            "success": True,
            "message": "Registration successful! Redirecting to login page..."
        }


@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: User = Depends(get_current_user)) -> schemas.User:
    """
    Returns current authenticated user information.
    
    Args:
        current_user: The authenticated user instance.
        
    Returns:
        schemas.User: The user details schema.
    """
    return schemas.User(
        username=current_user.username,
        is_admin=current_user.is_admin if current_user.is_admin is not None else False
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    app_db: AppDatabase = Depends(get_app_db),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, str]:
    """
    User logout endpoint.
    Clears auth cookie, updates logout logs, and closes user target database engines.
    
    Args:
        response: The FastAPI response object.
        current_user: The authenticated user instance.
        app_db: The application database manager instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, str]: A dictionary with success status.
    """
    # Clear token from cookie
    response.delete_cookie(
        key="access_token",
        secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
        samesite="strict",
        httponly=True
    )
    
    await app_db.update_login_log(user_id=current_user.id)
    await db_provider.close_user_engines(current_user.id)

    return {"message": "Successfully logged out"}```

### [MODIFIED] web_api/authentication/services.py
```python
"""
Authentication Service Layer
JWT token generation, verification, and user authorization operations.
"""
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Request
from sqlalchemy.future import select

from authentication import config
from app_database.models import User
from authentication.schemas import TokenData
from app_database.app_database import AppDatabase


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a new JWT access token.
    
    Args:
        data: Payload content (typically {"sub": user_id}).
        expires_delta: Token expiration duration (defaults to config.ACCESS_TOKEN_EXPIRE_MINUTES).
        
    Returns:
        str: Generated JWT token string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Validates a JWT token.
    
    Args:
        token: JWT token string.
        
    Returns:
        Optional[dict]: Decoded token payload if valid, otherwise None.
    """
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_payload(payload: dict) -> Optional[str]:
    """
    Extracts the user_id (sub) from the token payload.
    
    Args:
        payload: Decoded JWT token payload.
        
    Returns:
        Optional[str]: User ID string if present, otherwise None.
    """
    try:
        user_id = payload.get("sub")
        return user_id
    except Exception:
        return None


async def get_current_user(
    request: Request
) -> User:
    """
    Extracts JWT token from Request, validates it, and returns the User object.
    
    Args:
        request: FastAPI Request object.
        
    Returns:
        User: Authenticated user.
        
    Raises:
        HTTPException: If token is invalid or user is not found.
    """
    # Retrieve AppDatabase instance from request state to prevent circular imports
    app_db: AppDatabase = request.app.state.app_db

    # Retrieve token solely from cookies
    token = request.cookies.get("access_token")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(sub=user_id)
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise credentials_exception
    
    # Retrieve user from AppDatabase
    async with app_db.get_app_db() as db:
        result = await db.execute(select(User).filter(User.id == int(token_data.sub)))
        user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    
    return user
```

### [MODIFIED] web_api/database_provider/config.py
```python
"""
Database Provider Configuration
List of accessible SQL Server instances and connection string templates.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Retrieve comma-separated server list from environment, otherwise use default
_server_list = os.getenv("SQL_SERVER_NAMES", "localhost")
SERVER_NAMES: List[str] = [s.strip() for s in _server_list.split(",") if s.strip()]

# SQL Server authentication credentials
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Central service account credentials for executing queries on target databases
CENTRAL_DB_USER: str = os.getenv("CENTRAL_DB_USER", DB_USER)
CENTRAL_DB_PASSWORD: str = os.getenv("CENTRAL_DB_PASSWORD", DB_PASSWORD)

# Engine Cache Cleanup Interval (seconds)
# Default: 1800 seconds (30 minutes)
TIME_INTERVAL_FOR_CACHE = int(os.getenv("ENGINE_CACHE_TTL_SECONDS", "1800"))

# Technology to Driver mapping
TECHNOLOGY_DRIVER_MAP = {
    "mssql": "aioodbc",
    "mysql": "aiomysql",
    "postgresql": "asyncpg",
    "postgres": "asyncpg",  
}

def get_driver_for_technology(technology: str) -> str:
    """
    Returns the appropriate driver for a given database technology.
    
    Args:
        technology: Database technology (e.g., mssql, mysql, postgresql, etc.).
        
    Returns:
        str: Corresponding driver name (e.g., aioodbc, aiomysql, asyncpg).
        
    Example:
        >>> get_driver_for_technology("mssql")
        'aioodbc'
        >>> get_driver_for_technology("mysql")
        'aiomysql'
        >>> get_driver_for_technology("postgresql")
        'asyncpg'
    """
    tech = technology.lower().strip()
    return TECHNOLOGY_DRIVER_MAP.get(tech, "aioodbc")  # default: aioodbc


# Connection string builder functions
def create_connection_string(tech: str, driver: str, username: str, password: str, servername: str, database: str) -> str:
    """
    Generates a database connection string using centralized or custom credentials.
    Formats the string dynamically based on the technology.
    
    Args:
        tech: Database technology e.g., mssql, mysql, postgresql.
        driver: Database driver e.g., aioodbc, aiomysql, asyncpg.
        username: Database username.
        password: Database password.
        servername: Database server hostname or IP.
        database: Target database name.
        
    Returns:
        str: Formatted connection string.
    """
    tech = tech.lower()
    
    if tech == "mssql":
        # Microsoft SQL Server
        return (
            f"mssql+{driver}://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            "&connection timeout=30"
        )
    elif tech == "mysql":
        # MySQL
        return f"mysql+{driver}://{username}:{password}@{servername}/{database}"
    elif tech == "postgresql" or tech == "postgres":
        # PostgreSQL
        return f"postgresql+{driver}://{username}:{password}@{servername}/{database}"
    else:
        # Fallback to MSSQL format
        return (
            f"{tech}+{driver}://{username}:{password}@{servername}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
            "&connection timeout=30"
        )


def get_master_connection_string(server: str) -> str:
    """
    Generates a connection string for connecting to the master database.
    Used for administrative metadata retrieval (e.g., sys.databases query).
    
    Args:
        server: SQL Server instance name or address.
        
    Returns:
        str: Connection string for the master database.
        
    Note:
        DB_USER and DB_PASSWORD are fetched from the environment variables.
    """
    return (
        f"mssql+aioodbc://{DB_USER}:{DB_PASSWORD}@{server}/master"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
```

### [MODIFIED] web_api/database_provider/database.py
```python
"""
Database Provider Module
Manages database engines caching and session provisioning using centralized credentials.
All functions and classes are strictly typed.
"""
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import Dict, Any
import app_database.models as models
from database_provider.config import (
    create_connection_string, 
    get_driver_for_technology,
    CENTRAL_DB_USER,
    CENTRAL_DB_PASSWORD
)
from contextlib import asynccontextmanager
from .engine_cache import EngineCache

class DatabaseProvider:
    """
    Manages SQL Server database connections.
    """
    
    def __init__(self):
        """Initializes DatabaseProvider."""
        self.engine_cache: EngineCache = EngineCache()
        self.db_info: Dict[str, Dict[str, Any]] = {}
        # Format: {servername: {"databases": [list], "technology": str}}

    def set_db_info(self, info: Dict[str, Dict[str, Any]]) -> None:
        """
        Sets database configuration information.
        
        Args:
            info: Database configuration dictionary.
        """
        self.db_info = info
    
    @asynccontextmanager
    async def get_session(self, user: models.User, servername: str, database_name: str):
        """
        Provides user-specific async database session using centralized credentials.
        
        Args:
            user: User model.
            servername: Server instance name.
            database_name: Target database name.
            
        Yields:
            AsyncSession: SQLAlchemy async session.
        """
        
        # Server validation
        if servername not in self.db_info:
            raise ValueError(
                f"Server '{servername}' not found in database configuration. "
                f"Available servers: {list(self.db_info.keys())}. "
                f"Please add it to the Databases table."
            )
        
        server_info = self.db_info[servername]
        
        # Database validation
        available_databases = server_info.get("databases", [])
        if database_name not in available_databases:
            raise ValueError(
                f"Database '{database_name}' not found for server '{servername}'. "
                f"Available databases: {available_databases}. "
                f"Please add it to the Databases table."
            )
        
        # Get technology and driver
        tech = server_info.get("technology", "mssql")
        driver = get_driver_for_technology(tech)

        conn_str = create_connection_string(
            tech=tech,
            driver=driver,
            servername=servername,
            database=database_name,
            username=CENTRAL_DB_USER,
            password=CENTRAL_DB_PASSWORD,
        )
        
        engine = await self.engine_cache.get_engine(conn_str, owner_id=user.id)

        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def start_cache_loop(self) -> None:
        """
        Starts the background engine cache cleanup loop.
        Should be called during application startup.
        """
        await self.engine_cache.start_loop()

    async def close_engines(self) -> None:
        """
        Closes all engines for all users and releases resources.
        Should be called when the application shuts down.
        """
        await self.engine_cache.stop_loop()

    async def close_user_engines(self, user_id: int) -> None:
        """
        Closes all database engines for a specific user.
        Called when a user logs out.
        
        Args:
            user_id: The ID of the user whose engines should be closed.
        """
        await self.engine_cache.close_user_engines(user_id) 
    
    def get_db_info_db(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns database configuration information for all servers.
        
        Returns:
            Dict[str, Dict[str, Any]]: Configuration mapping of servers to their databases and technology.
        """
        return self.db_info```

### [MODIFIED] web_api/dependencies.py
```python
"""
Common Dependency Injection Functions
All routers use these functions to retrieve service instances from app.state.
"""
from fastapi import Request
from fastapi import Depends, HTTPException, status

from app_database.app_database import AppDatabase
from database_provider import DatabaseProvider
from authentication.services import get_current_user
from app_database.models import Workspace, User

from query_execution.services import QueryService
from workspaces.services import WorkspaceService
from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

def get_app_db(request: Request) -> AppDatabase:
    """
    Returns the AppDatabase instance.
    Usage: app_db: AppDatabase = Depends(get_app_db)
    """
    return request.app.state.app_db


def get_db_provider(request: Request) -> DatabaseProvider:
    """
    Returns the DatabaseProvider instance.
    Usage: db_provider: DatabaseProvider = Depends(get_db_provider)
    """
    return request.app.state.db_provider


# removed session cache and fernet dependencies as password caching is eliminated

def get_query_service(request: Request) -> QueryService:
    """
    Returns the QueryService instance.
    Usage: query_service: QueryService = Depends(get_query_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    notification_service = get_notification_service(request)
    return QueryService(database_provider=db_provider, app_db=app_db, notification_service=notification_service)


def get_workspace_service(request: Request) -> WorkspaceService:
    """
    Returns the WorkspaceService instance.
    Usage: workspace_service: WorkspaceService = Depends(get_workspace_service)
    """
    app_db = get_app_db(request)
    return WorkspaceService(app_db=app_db)

from admin.services import AdminService

def get_admin_service(request: Request) -> AdminService:
    """
    Returns the AdminService instance.
    Usage: admin_service: AdminService = Depends(get_admin_service)
    """
    app_db = get_app_db(request)
    db_provider = get_db_provider(request)
    return AdminService(app_db=app_db, db_provider=db_provider)


async def admin_required(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: ensures current_user is admin."""
    if not current_user or not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def ensure_owner(workspace_id: int,
                       current_user: User = Depends(get_current_user),
                       app_db: AppDatabase = Depends(get_app_db)) -> Workspace:
    """Dependency: ensures the current_user is the owner of the workspace. Returns the Workspace."""
    async with app_db.get_app_db() as db:
        ws = await db.get(Workspace, workspace_id)
        if not ws:
            raise WorkspaceNotFoundError("Workspace not found")
        if ws.user_id != current_user.id:
            raise WorkspaceAccessDeniedError("You don't own this workspace.")
        return ws


from notification import NotificationService

def get_notification_service(request: Request) -> NotificationService:
    """
    Returns the NotificationService instance.
    Usage: notification_service: NotificationService = Depends(get_notification_service)    
    """
    return NotificationService()```

### [MODIFIED] web_api/middlewares/auth_middleware.py
```python
"""
Authentication Middleware
Her HTTP request için JWT token doğrulama ve session kontrolü yapar
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from starlette.responses import RedirectResponse
from fastapi import Request
import os
from authentication.services import verify_token, get_user_id_from_payload
from fastapi.exceptions import HTTPException

class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT token validation middleware.
    
    For every request:
        1. Public endpoint check (login, register, health)
        2. Retrieves JWT token from access_token cookie
        3. Validates the token
        4. If invalid/missing, responds with 401 (for APIs) or redirects to /login (for web pages)
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> StarletteResponse:
        """
        Processes the request, checking authentication.
        
        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/endpoint handler.
        
        Returns:
            StarletteResponse: The HTTP response object.
        """
        skip_auth_paths: list[str] = [
            "/login", 
            "/register", 
            "/api/login", 
            "/api/register",
            "/health"
        ]
        
        if any(request.url.path.startswith(path) for path in skip_auth_paths):
            return await call_next(request)
        
        token: str | None = request.cookies.get("access_token")
        if not token:
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Token required"}',
                    status_code=401,
                    media_type="application/json"
                )
            return RedirectResponse(url="/login", status_code=302)
        try:
            payload: dict | None = verify_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            user_id: str | None = get_user_id_from_payload(payload=payload)
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            print(f"Auth verification failed: {e}")
            if request.url.path.startswith("/api/"):
                return StarletteResponse(
                    content='{"detail":"Invalid token"}',
                    status_code=401,
                    media_type="application/json"
                )
            response: RedirectResponse = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie(
                key="access_token",
                secure=os.getenv("COOKIE_SECURE", "False").lower() == "true",
                samesite="strict",
                httponly=True
            )
            return response
        
        user_token = None
        if user_id:
            request.state.user_id = user_id
            from common.logging_config import user_id_var
            user_token = user_id_var.set(user_id)
        
        try:
            response: StarletteResponse = await call_next(request)
            return response
        finally:
            if user_token:
                from common.logging_config import user_id_var
                user_id_var.reset(user_token)```

### [MODIFIED] web_api/query_execution/__init__.py
```python
from .services import QueryService
from .exceptions import QueryExecutionError, QueryAnalysisRejectedError

__all__ = ["QueryService", "QueryExecutionError", "QueryAnalysisRejectedError"]```

### [MODIFIED] web_api/query_execution/router.py
```python
"""
Query Execution Router Module
FastAPI router for single and multiple SQL query execution.
All routes are strictly typed and documented.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Any
from common.limiter import limiter

from query_execution import config
from query_execution import schemas as query_models
from query_execution.services import QueryService
from authentication.services import get_current_user
from dependencies import get_db_provider, get_query_service
from database_provider import DatabaseProvider
from app_database.models import User

router = APIRouter(prefix="/api")

# Using centralized limiter


@router.post("/execute_query", response_model=query_models.SQLResponse)
@limiter.limit(config.RATE_LIMITER)
async def execute_query(
    request: Request,
    query_request: query_models.SQLQuery,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> dict[str, Any]:
    """
    Executes a single SQL query via the query execution service.
    
    Args:
        request: The FastAPI request object.
        query_request: The SQL query execution request payload.
        current_user: The authenticated user instance.
        query_service: The query execution service instance.
        
    Returns:
        dict[str, Any]: The query execution results or error response.
    """
    result: dict[str, Any] = await query_service.execute_query(
        query=query_request.query,
        user=current_user,
        server_name=query_request.servername,
        database_name=query_request.database_name
    )
    return result


@router.post("/multiple_query", response_model=query_models.MultipleQueryResponse)
async def multiple_query(
    request: query_models.MultipleQueryRequest,
    current_user: User = Depends(get_current_user),
    query_service: QueryService = Depends(get_query_service)
) -> query_models.MultipleQueryResponse:
    """
    Executes multiple SQL queries sequentially.
    
    Args:
        request: The multiple SQL queries request payload.
        current_user: The authenticated user instance.
        query_service: The query execution service instance.
        
    Returns:
        query_models.MultipleQueryResponse: The list of results for each executed query.
    """
    if len(request.execution_info) > config.MULTIPLE_QUERY_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many queries. Maximum: {config.MULTIPLE_QUERY_COUNT}"
        )
    
    results: List[dict[str, Any]] = []
    
    for execution_info in request.execution_info:
        result: dict[str, Any] = await query_service.execute_query(
            query=execution_info.query,
            user=current_user,
            server_name=execution_info.servername,
            database_name=execution_info.database_name
        )
        results.append(result)
    
    return query_models.MultipleQueryResponse(results=results)


@router.get("/database_information", response_model=query_models.DatabaseInformationResponse)
async def get_database_information(
    current_user: User = Depends(get_current_user),
    db_provider: DatabaseProvider = Depends(get_db_provider)
) -> dict[str, Any]:
    """
    Returns the list of databases accessible to the user per server.
    
    Args:
        current_user: The authenticated user instance.
        db_provider: The database provider instance.
        
    Returns:
        dict[str, Any]: A mapping of servers to databases.
    """
    db_info: dict[str, Any] = db_provider.get_db_info_db()
    return {"db_info": db_info}
```

### [MODIFIED] web_api/query_execution/services.py
```python
"""
Query Execution Service Module
Contains the core QueryService responsible for analyzing, executing, and logging SQL queries.
Strictly typed and documented.
"""
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Dict, Any, List

import uuid

from query_execution import config
from database_provider import DatabaseProvider
from app_database.app_database import AppDatabase
from app_database.models import User, QueryData, Workspace

from query_execution.query_analyzer import QueryAnalyzer
from notification import NotificationService

import logging
from common.exceptions import BaseServiceException
from query_execution.exceptions import QueryExecutionError, QueryAnalysisRejectedError

logger = logging.getLogger(__name__)

class QueryService:
    """
    Query execution, security analysis, and logging service.
    Coordinates risk analysis and target database execution under strict auditing.
    """
    
    database_provider: DatabaseProvider
    app_db: AppDatabase
    analyzer: QueryAnalyzer
    notification_service: NotificationService

    def __init__(self, database_provider: DatabaseProvider, app_db: AppDatabase, notification_service: NotificationService) -> None:
        """
        Initializes the QueryService with required providers.
        
        Args:
            database_provider: The target database connections provider.
            app_db: The application metadata database manager.
            notification_service: The notifications service.
        """
        self.database_provider = database_provider
        self.app_db = app_db
        self.analyzer = QueryAnalyzer()
        self.notification_service = notification_service

    async def execute_query(self, query: str, user: User, server_name: str, database_name: str) -> Dict[str, Any]:
        """
        Analyzes, logs, and executes the SQL query against the target database.
        If the query is identified as risky, it is routed for admin approval.
        
        Args:
            query: The SQL query to analyze and execute.
            user: The authenticated user executing the query.
            server_name: The target SQL server instance name.
            database_name: The target database name.
            
        Returns:
            Dict[str, Any]: The execution results, rows, or error details.
        """
        log_id: int | None = None
        try:
            logger.info(f"Initiating query execution on server '{server_name}', database '{database_name}'")
            log_id = await self.app_db.create_log(user=user, query=query, machine_name=server_name)
            
            # Resolve target database technology from the database provider config
            server_info: Dict[str, Any] = self.database_provider.db_info.get(server_name, {})
            technology: str = server_info.get("technology", "mssql")
            
            query_analysis: Dict[str, Any] = self.analyzer.analyze(query, technology=technology)
            
            if not query_analysis["return"] and not user.is_admin:
                error_msg: str = f"Query rejected: {query_analysis['risk_type']}"
                await self.app_db.update_log(log_id=log_id, successfull=False, error=error_msg)
                
                try:
                    async with self.app_db.get_app_db() as db_session:
                        query_uuid: str = str(uuid.uuid4())
                        query_data: QueryData = QueryData(
                            user_id=user.id,
                            servername=server_name,
                            database_name=database_name,
                            query=query,
                            uuid=query_uuid,
                            status="waiting_for_approval",
                            risk_type=query_analysis.get('risk_type')
                        )
                        db_session.add(query_data)
                        await db_session.flush()
                        
                        query_data_id: int = query_data.id
                        
                        workspace_name: str = f"Pending: {query[:50]}..." if len(query) > 50 else f"Pending: {query}"
                        workspace: Workspace = Workspace(
                            user_id=user.id,
                            name=workspace_name,
                            description=f"Risk Type: {query_analysis.get('risk_type', 'UNKNOWN')} - Waiting for admin approval",
                            query_id=query_data_id,
                            show_results=None
                        )
                        db_session.add(workspace)
                        await db_session.flush()
                        
                        workspace_id: int = workspace.id
                        await db_session.commit()
                        
                    logger.info(f"Query saved for approval - Workspace ID: {workspace_id}, UUID: {query_uuid}")
                except Exception as save_exc:
                    logger.error(f"Failed to save query for approval: {type(save_exc).__name__}: {save_exc}")
                
                try:
                    if self.notification_service:
                        request_time: str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        await self.notification_service.send_approval_notification(
                            request_id=query_uuid,
                            username=getattr(user, 'username', str(getattr(user, 'id', 'unknown'))),
                            request_time=request_time,
                            database_name=database_name,
                            servername=server_name,
                            risk_type=query_analysis.get('risk_type', 'UNKNOWN'),
                            query=query
                        )
                except Exception as notif_exc:
                    logger.error(f"Notification send error: {type(notif_exc).__name__}: {notif_exc}")
                
                raise QueryAnalysisRejectedError(
                    message=f"{error_msg}. Query saved to your workspaces and sent for admin approval."
                )
                
            async with self.database_provider.get_session(
                user=user,
                servername=server_name,
                database_name=database_name
            ) as session:
                sql_query = text(query)
                result = await session.execute(sql_query)
                
                row_count: int = 0
                message: str = ""
                result_data: Dict[str, Any] = {}
                
                if result.returns_rows:
                    rows = result.fetchmany(size=config.MAX_ROW_COUNT_LIMIT)
                    row_count = len(rows)
                    if row_count >= config.MAX_ROW_COUNT_LIMIT:
                        message = f"Truncated to MAX_ROW_COUNT_LIMIT ({config.MAX_ROW_COUNT_LIMIT})"
                    else:
                        message = f"{row_count} rows returned"
                    result_data = {
                        "response_type": "data",
                        "data": [dict(row._mapping) for row in rows],
                        "message": message
                    }
                else:
                    row_count = result.rowcount if result.rowcount is not None else 0
                    message = f"{row_count} rows affected"
                    result_data = {
                        "response_type": "data",
                        "data": [],
                        "message": message
                    }
                
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=True,
                    row_count=row_count
                )
                
                if row_count > config.MAX_ROW_COUNT_WARNING:
                    logger.warning(f"Query returned high row count: {row_count} rows")
                
                logger.info(f"Query executed successfully. Result: {message}")
                return result_data
                
        except BaseServiceException:
            # Re-raise already translated service exceptions
            raise
        except Exception as e:
            error_msg: str = str(e)
            logger.error(f"Query execution failed: {error_msg}")
            if log_id:
                await self.app_db.update_log(
                    log_id=log_id,
                    successfull=False,
                    error=error_msg
                )
            raise QueryExecutionError(error_msg, original_exception=e)
 ```

### [MODIFIED] web_api/tests/conftest.py
```python
import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os
# Mock APP_DATABASE_URL before any app modules are imported
os.environ["APP_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Add the web_api directory to sys.path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app

# Mark all async tests to use asyncio automatically
pytestmark = pytest.mark.asyncio

import pytest_asyncio
from app_database import AppDatabase
from database_provider import DatabaseProvider

@pytest_asyncio.fixture
async def async_client():
    """
    Fixture for providing an asynchronous HTTP client that bypasses the actual network
    and directly calls the ASGI application.
    """
    # Manually setup state for testing
    app.state.app_db = AppDatabase()
    await app.state.app_db.create_tables()
    
    app.state.db_provider = DatabaseProvider()
    await app.state.db_provider.start_cache_loop()
    
    # Disable rate limiter for testing to prevent 429 Too Many Requests
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

### [MODIFIED] web_api/workspaces/__init__.py
```python
"""
Workspaces Module
Kullanıcı workspace (kaydedilmiş query) yönetimi
"""
from .services import WorkspaceService
from .exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

__all__ = ["WorkspaceService", "WorkspaceNotFoundError", "WorkspaceAccessDeniedError"]
```

### [MODIFIED] web_api/workspaces/services.py
```python
"""
Workspace Service Layer
User workspace (saved query) management operations
"""
from typing import Any, List, Dict
from app_database.models import QueryData, Workspace
from app_database.app_database import AppDatabase
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from .schemas import WorkspaceInfo, WorkspaceCreate
from sqlalchemy.sql import select
from sqlalchemy.sql import text
from query_execution import config as query_config
from database_provider import DatabaseProvider
from app_database.models import User

import logging
from common.exceptions import BaseServiceException
from workspaces.exceptions import WorkspaceNotFoundError, WorkspaceAccessDeniedError

logger = logging.getLogger(__name__)

class WorkspaceService:
    """
    Workspace CRUD operations service
    
    Manages users' operations of storing, editing, deleting,
    and listing queries in workspaces.
    
    Attributes:
        app_db: Application database instance
    """

    def __init__(self, app_db: AppDatabase):
        """
        Initializes WorkspaceService
        
        Args:
            app_db: AppDatabase instance
        """
        self.app_db = app_db

    async def create_workspace(self, db: AsyncSession, workspace_data: WorkspaceCreate, user_id: int):
        """
        Creates a new workspace.
        
        Args:
            db: Async database session
            workspace_data: Workspace creation schema
            user_id: ID of the user creating the workspace
        
        Returns:
            Dict: Result with workspace_id or error
        """
        try:
            new_query_data = QueryData(
                    user_id=user_id,
                    servername=workspace_data.servername,
                    database_name=workspace_data.database_name,
                    query=workspace_data.query,
                    uuid=str(uuid.uuid4()),
                    status="saved_in_workspace"
                )
            
            db.add(new_query_data)
            await db.flush()

            """Workspace creation operation"""
            workspace = Workspace(
                name=workspace_data.name,
                description=workspace_data.description,
                user_id=user_id,
                query_id=new_query_data.id
            )
            db.add(workspace)
            await db.commit()
            await db.refresh(workspace)
            return {"success": True, "workspace_id": workspace.id}
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating workspace: {e}")
            raise BaseServiceException(f"Error creating workspace: {str(e)}", original_exception=e)
        
    async def get_workspace_by_id(self, db: AsyncSession, user_id: int):
        """
        Retrieves all workspaces for the user.
        
        Args:
            db: Async database session
            user_id: ID of the user whose workspaces will be retrieved
        
        Returns:
            List[WorkspaceInfo]: List of workspaces (can be empty)
        """
        
        results = await db.execute(
            select(Workspace).where(Workspace.user_id == user_id)
        )
        workspaces = results.scalars().all()
        if not workspaces:
            return []

        query_ids = [ws.query_id for ws in workspaces]

        query_data_results = await db.execute(
            select(QueryData).where(QueryData.id.in_(query_ids))
        )
        query_data_map = {qd.id: qd for qd in query_data_results.scalars().all()}

        workspace_list = []
        for ws in workspaces:
            query_data = query_data_map.get(ws.query_id)
            if query_data:
                print(f"[DEBUG] Workspace {ws.id}: status={query_data.status}, show_results={getattr(ws, 'show_results', None)}")
                workspace_list.append(WorkspaceInfo(
                    id=ws.id,
                    name=ws.name,
                    description=ws.description,
                    query=query_data.query,
                    servername=query_data.servername,
                    database_name=query_data.database_name,
                    status=query_data.status,
                    show_results=getattr(ws, 'show_results', None),
                    owner_id=ws.user_id,
                    is_owner=True
                ))
        return workspace_list
    
    async def delete_workspace_by_id(self, workspace_id: int, db: AsyncSession):
        """
        Deletes workspace and related queryData.
        
        Args:
            workspace_id: ID of the workspace to delete
            db: Async database session
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                raise WorkspaceNotFoundError("Workspace not found")
            
            query_id = workspace.query_id
            
            await db.delete(workspace)
            
            if query_id:
                query_result = await db.execute(select(QueryData).where(QueryData.id == query_id))
                query_data = query_result.scalars().first()
                if query_data:
                    await db.delete(query_data)
            
            await db.commit()
            return True
        except BaseServiceException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting workspace: {e}")
            raise BaseServiceException(f"Error deleting workspace: {str(e)}", original_exception=e)
    
    async def update_workspace(self, db: AsyncSession, workspace_id: int, query: str = None, status: str = None):
        """
        Updates workspace query or status.
        
        Args:
            db: Async database session
            workspace_id: ID of the workspace to update
            query: New query (optional)
            status: New status (optional)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace = workspace_result.scalars().first()
            if not workspace:
                raise WorkspaceNotFoundError("Workspace not found")
            
            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data = query_result.scalars().first()
            if not query_data:
                raise WorkspaceNotFoundError("Query data not found for this workspace")
            
            if query:
                query_data.query = query
            if status:
                query_data.status = status
            await db.commit()
            return True
        except BaseServiceException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating workspace: {e}")
            raise BaseServiceException(f"Error updating workspace: {str(e)}", original_exception=e)
    
    async def get_workspace_detail_by_id(self, db: AsyncSession, workspace_id: int, user_id: int):
        """
        Retrieves details of a specific workspace.
        
        Args:
            db: Async database session
            workspace_id: ID of the workspace to retrieve details for
            user_id: ID of the requesting user (for authorization check)
        
        Returns:
            Dict | None: Workspace details or None
        """
        workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
        workspace = workspace_result.scalars().first()
        if not workspace:
            raise WorkspaceNotFoundError("Workspace not found")
        if workspace.user_id != user_id:
            raise WorkspaceAccessDeniedError("You do not own this workspace")
            
        query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
        query_data = query_result.scalars().first()
        if not query_data:
            raise WorkspaceNotFoundError("Query data not found for this workspace")
            
        return {
            "id": workspace.id,
            "name": workspace.name,
            "description": workspace.description,
            "query": query_data.query,
            "servername": query_data.servername,
            "database_name": query_data.database_name,
            "status": query_data.status,
            "show_results": getattr(workspace, 'show_results', None),
            "owner_id": workspace.user_id,
            "is_owner": True
        }

    async def execute_workspace(self, workspace_id: int, current_user: User, db_provider: DatabaseProvider) -> dict[str, Any]:
        """
        Executes a stored workspace query after enforcing approval rules.
        Uses centralized service account credentials, requiring no user password caching.

        Args:
            workspace_id: ID of the workspace to execute.
            current_user: The authenticated calling user instance.
            db_provider: The database connection provider.

        Returns:
            dict[str, Any]: A dictionary containing execution status and data or error details.
        """
        # Load workspace and query
        async with self.app_db.get_app_db() as db:
            workspace_result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
            workspace: Workspace | None = workspace_result.scalars().first()
            if not workspace:
                raise WorkspaceNotFoundError("Workspace not found")

            if workspace.user_id != current_user.id:
                raise WorkspaceAccessDeniedError("You do not own this workspace")

            query_result = await db.execute(select(QueryData).where(QueryData.id == workspace.query_id))
            query_data: QueryData | None = query_result.scalars().first()
            if not query_data:
                raise WorkspaceNotFoundError("Query data not found for this workspace")
                
            # enforce approval
            if not workspace.show_results or query_data.status != "approved_with_results":
                from query_execution.exceptions import QueryAnalysisRejectedError
                raise QueryAnalysisRejectedError("This workspace is not approved for execution")

        log_id: int | None = None
        try:
            logger.info(f"Executing approved workspace {workspace_id} on server '{query_data.servername}'")
            log_id = await self.app_db.create_log(user=current_user, query=query_data.query, machine_name=query_data.servername, approved_execution=True)

            async with db_provider.get_session(user=current_user, servername=query_data.servername, database_name=query_data.database_name) as session:
                  sql_query = text(query_data.query)
                  result = await session.execute(sql_query)
                  
                  row_count: int = 0
                  message: str = ""
                  result_data: list[dict[str, Any]] = []
                  
                  if result.returns_rows:
                      rows = result.fetchmany(size=query_config.MAX_ROW_COUNT_LIMIT)
                      row_count = len(rows)
                      if row_count >= query_config.MAX_ROW_COUNT_LIMIT:
                          message = f"Truncated to MAX_ROW_COUNT_LIMIT ({query_config.MAX_ROW_COUNT_LIMIT})"
                      else:
                          message = f"{row_count} rows returned"
                      result_data = [dict(row._mapping) for row in rows]
                  else:
                      row_count = result.rowcount if result.rowcount is not None else 0
                      message = f"{row_count} rows affected"
                      result_data = []

            await self.app_db.update_log(log_id=log_id, successfull=True, row_count=row_count)
            logger.info(f"Workspace {workspace_id} executed successfully. Result: {message}")
            return {"response_type": "data", "data": result_data, "message": message}

        except BaseServiceException:
            raise
        except Exception as e:
            if log_id:
                await self.app_db.update_log(log_id=log_id, successfull=False, error=str(e))
            from query_execution.exceptions import QueryExecutionError
            raise QueryExecutionError(str(e), original_exception=e)```

### [MODIFIED] web_api/app_database/config.py
```python
"""
Application Database Configuration

Application metadata database connection settings.
Used for user management, auditing logs, and workspace configuration storage.

Environment Variables:
    DB_USER: SQL Server username (default: "sa")
    DB_PASSWORD: SQL Server password (default: "")
    APP_DATABASE_URL: Full connection string (optional override)
"""
import os
from dotenv import load_dotenv

load_dotenv(".env.production")
load_dotenv()

db_user = os.getenv("DB_USER", "sa")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME", "dba_application_db")

DATABASE_URL = os.getenv(
    "APP_DATABASE_URL",
    (
        f"mssql+aioodbc://{db_user}:{db_password}@{db_host}/{db_name}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&TrustServerCertificate=yes"
        "&connection timeout=30"
    )
)```

### [MODIFIED] web_api/entrypoint.sh
```bash
#!/bin/bash
set -e

# Wait for database connection (Retry mechanism)
echo "Waiting for SQL Server to be ready..."
max_retries=30
count=0
while [ $count -lt $max_retries ]; do
    if python create_db.py; then
        echo "Database initialized successfully."
        break
    else
        echo "Database not ready yet. Retrying in 2 seconds... ($((count+1))/$max_retries)"
        sleep 2
        count=$((count+1))
    fi
done

if [ $count -eq $max_retries ]; then
    echo "Error: Could not connect to database after $max_retries attempts."
    exit 1
fi

# Start the application
exec "$@"
```

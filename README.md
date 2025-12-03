## WebQuery

Çoklu veritabanı desteği ile sorgu analizi ve güvenli yürütme özellikleri sunan FastAPI tabanlı bir uygulama. MSSQL, MySQL ve PostgreSQL veritabanlarına bağlanabilir. Kimlik doğrulama (JWT), hız sınırlama, çoklu sorgu yürütme ve risk analizi içerir.

## Özellikler
- **Çoklu Veritabanı Desteği**: MSSQL, MySQL, PostgreSQL
- **Gelişmiş Connection Pooling**: `EngineCache` ile sunucu kaynaklarını yormayan akıllı bağlantı yönetimi (LRU, TTL, Active Connection Check)
- **Risk Analizi ve Onay Mekanizması**: Tehlikeli sorgular için otomatik tespit ve Admin onay süreci
- **Workspace Yönetimi**: Sorguları kaydetme, düzenleme ve paylaşma
- JWT ile kullanıcı doğrulama ve oturum yönetimi
- Hız sınırlama (slowapi)
- Otomatik driver seçimi ve connection string yönetimi

## Mimari ve Teknolojiler
- **Backend**: FastAPI 0.116.x, Uvicorn
- **ORM**: SQLAlchemy 2.x (async)
- **Drivers**: 
  - MSSQL: `aioodbc` / `pyodbc`
  - MySQL: `aiomysql`
  - PostgreSQL: `asyncpg`
- **Güvenlik**: python-jose (JWT), cryptography (Fernet), bcrypt
- **Konfigürasyon**: python-dotenv

## Proje Yapısı
Modüler bir mimari benimsenmiştir:
- `app_database/`: Uygulama içi veritabanı (User, Log, Workspace) modelleri ve işlemleri
- `database_provider/`: Hedef veritabanlarına (MSSQL, MySQL, PG) bağlantı yönetimi (`EngineCache`)
- `query_execution/`: Sorgu çalıştırma, risk analizi (`QueryAnalyzer`) ve loglama
- `admin/`: Yönetici onay mekanizması ve işlemleri
- `workspaces/`: Kullanıcı çalışma alanları yönetimi
- `authentication/`: Login, register ve token işlemleri
- `middlewares/`: Auth ve rate limiting middleware'leri

## Gelişmiş Özellikler Detayı

### 1. Akıllı Engine Cache (Connection Management)
Uygulama, veritabanı bağlantılarını `EngineCache` sınıfı ile yönetir. Bu yapı, "Web Query Tool" senaryosu için özel olarak optimize edilmiştir:
- **Pool Size = 0**: Sunucuda boşta (idle) bağlantı tutulmaz. Her sorgu bittiğinde bağlantı kapatılır.
- **Max Overflow = 20**: Anlık yoğunlukta 20 eşzamanlı bağlantıya kadar izin verilir.
- **LRU Eviction**: Cache dolduğunda en az kullanılan engine silinir.
- **TTL Cleanup**: Belirli bir süre kullanılmayan engine'ler arka planda temizlenir.
- **Active Check**: Temizlik sırasında, o an sorgu çalıştıran engine'ler (`checkedout > 0`) korunur, işlem yarıda kesilmez.

### 2. Sorgu Risk Analizi (Query Analyzer)
Her sorgu çalıştırılmadan önce `QueryAnalyzer` tarafından taranır. Riskler 4 seviyede değerlendirilir:
1.  **SQL Injection**: `UNION SELECT`, `OR 1=1`, yorum satırları (`--`, `/*`) vb.
2.  **DDL (Yapısal Değişiklik)**: `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
3.  **Riskli DML**: `WHERE` koşulu olmayan `DELETE` veya `UPDATE` işlemleri.
4.  **Performans**: 3'ten fazla `JOIN`, `CROSS JOIN`, `LIKE '%...%'`, büyük `LIMIT` + `ORDER BY`.

**Onay Mekanizması**: Riskli bulunan sorgular (Admin değilse) doğrudan çalıştırılmaz. "Onay Bekliyor" durumuna alınır. Adminler bu sorguları inceleyip onaylayabilir veya reddedebilir.

### 3. Workspace Sistemi
Kullanıcılar sorgularını "Workspace" olarak kaydedebilir. Her workspace:
- Bir SQL sorgusu içerir.
- Sorgunun son çalışma durumu ve risk seviyesini tutar.
- Admin onayı gerekiyorsa durumunu takip eder.

## Gereksinimler

### Python ve Temel Bağımlılıklar
- Python 3.11+
- `requirements.txt` içindeki tüm paketler

### Veritabanı Driver'ları (Zorunlu)

Kullanmayı planladığınız veritabanı teknolojisine göre ilgili driver'ların sisteminizde kurulu olması **zorunludur**:

#### **MSSQL (Microsoft SQL Server)**
- **ODBC Driver 18 for SQL Server** (sistem seviyesinde kurulu olmalı)
- Windows: [Microsoft Download Center](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Linux: [Linux ODBC Driver Installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
- Python paketleri: `aioodbc`, `pyodbc` (requirements.txt'te mevcut)

#### **MySQL**
- **MySQL Client Libraries** (opsiyonel, bazı sistemlerde gerekebilir)
- Python paketleri: `aiomysql`, `PyMySQL` (requirements.txt'te mevcut)

#### **PostgreSQL**
- **PostgreSQL Client** (asyncpg için genellikle gerekli değil)
- Python paketi: `asyncpg` (requirements.txt'te mevcut)

### Veritabanı Erişimi
- İlgili veritabanı sunucusuna erişim (kullanıcı adı/şifre)
- Gerekli izinler (SELECT, INSERT vb.)

## Hızlı Başlangıç (Geliştirme)
1) Depoyu klonla
```powershell
git clone https://github.com/erdemdnmz2/WebQuery
cd WebQuery
```

2) Sanal ortam ve bağımlılıklar
```powershell
python -m venv venv
.\n+venv\Scripts\pip.exe install -r requirements.txt
```

3) Ortam dosyası
- `.env.example` dosyasını kopyalayıp değerleri düzenleyin:
```powershell
Copy-Item .env.example .env
```
- Bu dosyada tanımlı değişkenler: DB_USER, DB_PASSWORD, SQL_SERVER_NAMES, SECRET_KEY, JWT ayarları, rate limit ve sorgu limitleri (tam liste için `.env.example`’a bakın).

4) Çalıştırma (dev)
- Varsayılan olarak `.env` okunur; isterseniz özel dosya seçebilirsiniz:
```powershell
$env:ENV_FILE = ".env"          # veya ".env.staging" / ".env.production"
.
venv\Scripts\python.exe -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Production Çalıştırma (Önerilen Yol)
1) Kodu sunucuya kopyalayın (ENV dosyaları hariç)
2) Sunucuda `.env.production` oluşturun ve güvenli değerleri yazın
3) Sunucuda bağımlılıkları kurun ve uygulamayı başlatın

```powershell
python -m venv venv
.
venv\Scripts\pip.exe install -r requirements.txt

# Uygulamaya hangi .env dosyasını kullanacağını söyleyin
$env:ENV_FILE = ".env.production"
.
venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
```

> Not: Docker kullanacaksanız gizli bilgileri imajın içine koymayın. Konfigürasyonu runtime’da verin:
```powershell
docker run --env-file C:\path\to\.env.production -p 8000:8000 yourimage:tag
```

## Ortam Değişkenleri (dotenv)
- Uygulama başında `app.py` içinde şu mantık vardır:
  - `ENV_FILE` değişkeni set edilmişse o dosya yüklenir (örn: `.env.production`)
  - Aksi halde `.env` yüklenir
- Diğer modüller `os.getenv()` ile bu değerleri okur.

### Hangi dosyalar repo’ya girer?
- `.env.example` → EVET, commit’leyin (örnek ve dokümantasyon amaçlı)
- `.env`, `.env.production`, `.env.*` → HAYIR, gizli bilgiler; repo’ya eklemeyin

## CORS (Önemli)
Geliştirmede `*` kullanılabilir; production'da sadece izinli origin'leri tanımlayın.
Örnek (internal): `http://10.1.1.1:80`

## Çoklu Veritabanı Yapılandırması

### Desteklenen Veritabanı Tipleri
Uygulama şu veritabanı teknolojilerini destekler:
- **MSSQL** → Driver: `aioodbc`
- **MySQL** → Driver: `aiomysql`
- **PostgreSQL** → Driver: `asyncpg`

### Databases Tablosu Yapısı
Uygulama başlangıcında `Databases` tablosundan veritabanı bilgileri okunur:

```sql
CREATE TABLE Databases (
    id INT PRIMARY KEY IDENTITY(1,1),
    servername NVARCHAR(100) NOT NULL,      -- Sunucu adresi
    database_name NVARCHAR(100) NOT NULL,   -- Veritabanı adı
    technology NVARCHAR(100) NOT NULL       -- mssql, mysql, postgresql
);
```

### Örnek Kayıtlar
```sql
-- MSSQL Sunucu
INSERT INTO Databases (servername, database_name, technology)
VALUES ('localhost', 'Northwind', 'mssql'),
       ('localhost', 'AdventureWorks', 'mssql');

-- MySQL Sunucu
INSERT INTO Databases (servername, database_name, technology)
VALUES ('mysql-server-1', 'ecommerce', 'mysql'),
       ('mysql-server-1', 'analytics', 'mysql');

-- PostgreSQL Sunucu
INSERT INTO Databases (servername, database_name, technology)
VALUES ('postgres-server-1', 'production_db', 'postgresql'),
       ('postgres-server-1', 'staging_db', 'postgresql');
```

### Otomatik Driver Seçimi
Uygulama, `technology` alanına göre otomatik olarak doğru driver'ı seçer ve connection string oluşturur. Manuel konfigürasyona gerek yoktur.

## Veritabanı Notları

### MSSQL (SQL Server)
- SQL Authentication kullanılır: `.env` içinde `DB_USER` ve `DB_PASSWORD`.
- Uygulama DB'sinde user oluşturun ve uygun rol verin (kolay yol: `db_owner`).
- Diğer veri tabanlarında sadece okuma gerekiyorsa ilgili DB'de `CREATE USER ... FOR LOGIN ...; GRANT SELECT TO ...` yeterlidir.

### MySQL
- MySQL server'da kullanıcı oluşturun ve gerekli izinleri verin
- Örnek: `CREATE USER 'user'@'%' IDENTIFIED BY 'password'; GRANT SELECT ON db.* TO 'user'@'%';`

### PostgreSQL
- PostgreSQL'de kullanıcı ve izinleri ayarlayın
- Örnek: `CREATE USER myuser WITH PASSWORD 'mypass'; GRANT CONNECT ON DATABASE mydb TO myuser;`

## Sık Karşılaşılan Sorunlar

### Driver Sorunları
- **"ODBC Driver bulunamadı"** (MSSQL): 
  - Sunucuya "ODBC Driver 18 for SQL Server" kurun
  - Test: `odbcinst -j` (Linux) veya ODBC Data Sources (Windows)
  
- **"No module named 'aiomysql'"** (MySQL):
  - `pip install aiomysql PyMySQL` çalıştırın
  
- **"No module named 'asyncpg'"** (PostgreSQL):
  - `pip install asyncpg` çalıştırın

### Bağlantı Sorunları
- **"Login failed"**: 
  - `DB_USER/DB_PASSWORD` doğru mu?
  - İlgili DB'de USER bağlı mı?
  - `Databases` tablosunda kayıt var mı?
  
- **"Technology not supported"**:
  - `Databases` tablosunda `technology` alanı doğru mu? (mssql, mysql, postgresql)
  
- **"Connection timeout"**:
  - Sunucu erişilebilir mi?
  - Firewall kuralları doğru mu?

### Diğer Sorunlar
- **"CORS hatası"**: Production'da izinli origin eklediniz mi?
- **"Database not found"**: `Databases` tablosuna kayıt eklediniz mi?

## Lisans
Bu depo, iç kullanım amaçlıdır. Kurumsal politikalarınıza uygun olarak güncelleyiniz.

## WebQuery

SQL Server için geliştirilen, sorgu analizi ve güvenli yürütme özellikleri sunan FastAPI tabanlı bir uygulama. Kimlik doğrulama (JWT), hız sınırlama, çoklu sorgu yürütme ve risk analizi içerir.

## Özellikler
- JWT ile kullanıcı doğrulama ve oturum yönetimi
- Sorgu risk analizi (DDL, potansiyel tehlikeli ifadeler, performans sınırları)
- Çoklu sorgu desteği (tek istekte birden fazla sorgu)
- Hız sınırlama (slowapi)
- SQL Server’a SQL Authentication ile bağlanma (ODBC Driver 18)

## Mimari ve Teknolojiler
- FastAPI 0.116.x, Uvicorn
- SQLAlchemy 2.x (async) + aioodbc/pyodbc
- python-jose (JWT), cryptography (Fernet)
- python-dotenv ile ortam değişkenleri

## Gereksinimler
- Python 3.11+ (Windows önerilir)
- Microsoft ODBC Driver 18 for SQL Server (sunucuda kurulu olmalı)
- SQL Server’a erişim (kullanıcı adı/şifre)

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
Geliştirmede `*` kullanılabilir; production’da sadece izinli origin’leri tanımlayın.
Örnek (internal): `http://10.1.1.1:80`

## SQL Server Notları
- SQL Authentication kullanılır: `.env` içinde `DB_USER` ve `DB_PASSWORD`.
- Uygulama DB’sinde user oluşturun ve uygun rol verin (kolay yol: `db_owner`).
- Diğer veri tabanlarında sadece okuma gerekiyorsa ilgili DB’de `CREATE USER ... FOR LOGIN ...; GRANT SELECT TO ...` yeterlidir.

## Sık Karşılaşılan Sorunlar
- “ODBC Driver bulunamadı”: Sunucuya “ODBC Driver 18 for SQL Server” kurun.
- “Login failed”: `DB_USER/DB_PASSWORD` doğru mu, ilgili DB’de USER bağlı mı?
- “CORS hatası”: Production’da izinli origin eklediniz mi?

## Lisans
Bu depo, iç kullanım amaçlıdır. Kurumsal politikalarınıza uygun olarak güncelleyiniz.

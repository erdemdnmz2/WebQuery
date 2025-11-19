# 🚀 WebQuery Production Deployment Checklist

## ✅ ZORUNLU KONTROLLER

### 1. Environment Configuration (.env.production)
- [ ] `.env.production` dosyası oluşturuldu
- [ ] `SECRET_KEY` güçlü, rastgele bir key olarak değiştirildi (min 32 karakter)
- [ ] `DB_USER` production SQL Server kullanıcısı ayarlandı
- [ ] `DB_PASSWORD` güçlü bir şifre olarak ayarlandı
- [ ] `SQL_SERVER_NAMES` production server'lar listesi güncellendi
- [ ] `APP_DATABASE_URL` (varsa) production veritabanına işaret ediyor

### 2. Database Setup
- [ ] SQL Server'da `dba_application_db` veritabanı oluşturuldu
- [ ] Tüm tablolar oluşturuldu (User, actionLogging, loginLogging, queryData, Workspace)
- [ ] SQL Server Authentication aktif (Windows Authentication değil)
- [ ] ODBC Driver 18 for SQL Server yüklü
- [ ] DB kullanıcısının gerekli yetkileri var (CREATE, SELECT, INSERT, UPDATE, DELETE)
- [ ] Firewall'da SQL Server portları açık (varsayılan: 1433)

### 3. Security & CORS
- [ ] **ÖNEMLİ:** `app.py` içindeki CORS ayarları güncellendi
  ```python
  # ❌ GELİŞTİRME (herkese açık)
  allow_origins=["*"]
  allow_credentials=False
  
  # ✅ PRODUCTION (sadece frontend domain)
  allow_origins=["https://yourdomain.com"]
  allow_credentials=True
  ```
- [ ] Rate limit değerleri production için uygun (çok gevşek değil)
- [ ] Session timeout değerleri güvenli

### 4. Dependencies
- [ ] Python 3.11+ yüklü
- [ ] Virtual environment oluşturuldu
- [ ] `pip install -r requirements.txt` çalıştırıldı
- [ ] Tüm paketler başarıyla yüklendi

### 5. Application Test
- [ ] `python app.py` ile uygulama başlatıldı
- [ ] Startup sırasında hata yok:
  - ✓ AppDatabase bağlantısı başarılı
  - ✓ DatabaseProvider hazır ve db_info yüklendi
  - ✓ Fernet encryption hazır
  - ✓ Session cache hazır
- [ ] Health check çalışıyor: `GET http://localhost:8000/health`

### 6. API Endpoints Test
- [ ] `POST /api/register` - Yeni kullanıcı kaydı çalışıyor
- [ ] `POST /api/login` - Giriş ve JWT token alınıyor
- [ ] `GET /api/database_information` - Database listesi geliyor
- [ ] `POST /api/execute_query` - Query çalıştırma başarılı
- [ ] `GET /api/admin/queries_to_approve` - Admin approval çalışıyor (admin user ile)
- [ ] `POST /api/logout` - Çıkış işlemi başarılı

### 7. Frontend-Backend Integration
- [ ] Login sayfası `/login` açılıyor ve API'ye bağlanıyor
- [ ] Register sayfası `/register` açılıyor
- [ ] Ana sayfa `/` veya `/home` login sonrası açılıyor
- [ ] Query editor çalışıyor (Ace Editor yükleniyor)
- [ ] Workspace oluşturma ve listeleme çalışıyor
- [ ] Admin paneli `/admin` (admin user için) çalışıyor
- [ ] Logout işlemi cookie'yi siliyor

## ⚠️ KRİTİK GÜVENLİK SORUNLARI

### 🔴 CORS Ayarları (MUTLAKA DÜZELTİLMELİ!)
**Mevcut Durum:** `allow_origins=["*"]` - HERKESİN ERİŞİMİNE AÇIK!

**app.py dosyasında (satır ~102):**
```python
# MEVCUT (GELİŞTİRME İÇİN)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ❌ PRODUCTION'DA KULLANMAYIN!
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ÖNERİLEN (PRODUCTION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",  # Frontend domain
        "https://www.yourdomain.com"
    ],
    allow_credentials=True,  # Cookie için gerekli
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### Frontend API Çağrıları
**Mevcut Durum:** Tüm API çağrıları relative path kullanıyor (`/api/...`)
- ✅ Bu DOĞRU bir yaklaşım
- Frontend ve backend aynı domain'de serve edilmelidir
- Veya reverse proxy (nginx) kullanılmalıdır

## 📊 PRODUCTION DEPLOYMENT SENARYOLARI

### Senaryo 1: Tek Server (Basit)
```
├── Frontend + Backend (aynı sunucu)
│   ├── FastAPI (port 8000)
│   └── Static files (templates/)
├── SQL Server (aynı veya farklı sunucu)
```

**Adımlar:**
1. `.env.production` ayarla
2. CORS'u `allow_origins=["*"]` olarak bırak (aynı origin)
3. `uvicorn app:app --host 0.0.0.0 --port 8000` ile başlat
4. Firewall'da 8000 portunu aç

### Senaryo 2: Nginx Reverse Proxy (Önerilen)
```
[Client] → [Nginx :80/443] → [FastAPI :8000]
                ↓
           [SQL Server]
```

**Nginx Config:**
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Adımlar:**
1. CORS'u kaldır veya kısıtla (Nginx handle eder)
2. `uvicorn app:app --host 127.0.0.1 --port 8000`
3. SSL sertifikası ekle (Let's Encrypt)

### Senaryo 3: Ayrı Frontend (React/Next.js)
```
[Frontend :3000] → [Backend :8000] → [SQL Server]
```

**Adımlar:**
1. CORS'u frontend domain'e kısıtla
2. `allow_credentials=True` yap (cookie için)
3. Frontend'de BASE_URL ayarla

## 🔧 PRODUCTION BAŞLATMA KOMUTLARI

### Development Mode (Test için)
```bash
python app.py
```

### Production Mode (Önerilen)
```bash
# Gunicorn ile (Linux)
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Uvicorn direkt (Windows)
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4

# Systemd service olarak (Linux)
sudo systemctl start webquery
```

## 📝 DEPLOYMENT SONRASI TEST

### Manuel Test Checklist
```bash
# 1. Health Check
curl http://yourdomain.com/health

# 2. Register
curl -X POST http://yourdomain.com/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"Test123!"}'

# 3. Login
curl -X POST http://yourdomain.com/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Test123!"}' \
  -c cookies.txt

# 4. Database Info
curl http://yourdomain.com/api/database_information \
  -b cookies.txt

# 5. Execute Query
curl -X POST http://yourdomain.com/api/execute_query \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"servername":"localhost","database_name":"master","query":"SELECT 1"}'
```

## ⚡ PERFORMANS OPTİMİZASYONLARI

- [ ] SQL Server connection pool boyutu ayarlandı (app_database: 20, overflow: 30)
- [ ] Query result limit ayarlandı (MAX_ROW_COUNT_LIMIT=1000)
- [ ] Rate limiting aktif
- [ ] Static files için CDN kullanılıyor (Tailwind, React, Ace Editor)

## 🔍 MONİTÖRİNG & LOGGING

- [ ] Application log'ları kaydediliyor
- [ ] SQL query log'ları actionLogging tablosunda
- [ ] Login/logout log'ları loginLogging tablosunda
- [ ] Error log'ları izleniyor
- [ ] Health check endpoint monitör ediliyor

## 🆘 SORUN GİDERME

### "AppDatabase bağlantı hatası"
- SQL Server çalışıyor mu?
- DB_USER ve DB_PASSWORD doğru mu?
- Firewall SQL Server portunu engelliyor mu?
- ODBC Driver 18 yüklü mü?

### "DatabaseProvider başlatma hatası"
- SQL_SERVER_NAMES doğru mu?
- Server'lara erişim var mı?
- DB kullanıcısının master database'e erişimi var mı?

### "CORS hatası"
- allow_origins frontend domain'i içeriyor mu?
- allow_credentials=True mu? (cookie kullanımı için)
- Frontend aynı protocol kullanıyor mu? (http vs https)

### "Token geçersiz"
- SECRET_KEY tüm instance'larda aynı mı?
- Cookie SameSite ayarları doğru mu?
- Secure flag production'da true mu?

## 📚 EK KAYNAKLAR

- FastAPI Deployment: https://fastapi.tiangolo.com/deployment/
- Uvicorn Production: https://www.uvicorn.org/deployment/
- ODBC Driver: https://learn.microsoft.com/en-us/sql/connect/odbc/

---

**Son Güncelleme:** 2025-10-22
**Versiyon:** 2.0.0

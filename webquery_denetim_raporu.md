# WebQuery — Kapsamlı Kod, Akış ve Arayüz Denetimi

**Tarih:** 2026-08-29
**Dal:** `feature/security-hardening-implementation` (`1112a7f`)
**Kapsam:** `web_api/` (tüm modüller), `frontend/` (tüm sayfa ve bileşenler),
`docker-compose.yml`, `nginx.conf`, `.github/workflows/ci.yml`, `docs/`,
`webquery_implementasyon_sirasi.md` uyumu
**Amaç:** Uygulama sırasındaki adımların gerçekten ve doğru uygulanıp
uygulanmadığını, akışların/algoritmaların verimliliğini, best-practice uyumunu
ve frontend'de eksik arayüzleri objektif olarak tespit etmek.
**Not:** Bu rapor yalnızca bulgu kaydıdır; hiçbir kod değiştirilmemiştir.

---

## 0. Yöntem ve doğrulama kanıtları

Bulgular üç kaynaktan üretildi: (a) tüm üretim kodunun okunması, (b) yerel
çalıştırılabilir doğrulamalar, (c) `docs/` içindeki spec/ADR/inbox kayıtlarıyla
karşılaştırma.

Fiilen çalıştırılan komutlar ve gerçek sonuçları:

| Komut | Sonuç |
| --- | --- |
| `pytest` (`web_api/`) | **187 passed**, 1 warning, 110.14 s |
| `npm run typecheck` (`frontend/`) | Temiz, hata yok |
| `npm run build` (`frontend/`) | Başarılı, 2.94 s |
| `ruff check .` (`web_api/`) | **50 bulgu**: 24 BLE001, 8 DTZ005, 8 I001, 6 SIM117, 3 F821, 1 F401 |
| `npm run audit:api` | Tüm frontend çağrıları eşleşiyor; 2 rota arayüzsüz |
| `npm run audit:contrast` | Tüm kontrast hedefleri karşılanıyor |

**Sınır:** Hedef veritabanı (MSSQL/PostgreSQL/MySQL) davranışı gerçek sunucuya
karşı ölçülmedi; testler hedef oturumu mock'luyor. Hedef DB davranışına dair
bulgular bu nedenle "statik okuma + yerel repro" olarak işaretlenmiştir.

### Önem ölçeği

| İşaret | Anlamı |
| --- | --- |
| 🔴 **P0** | **Kesin değişmeli.** Güvenlik sınırını veya doğruluğu bozuyor; üretimde veri/erişim sonucu doğuruyor. |
| 🟠 **P1** | **Değişmeli.** Gerçek risk veya işlevsel boşluk, ama ya dar kapsamlı ya da geçici olarak yaşanabilir. |
| 🟡 **P2** | **Değişse iyi olur, acil değil.** Verimlilik, bakım, tutarlılık, doküman. |
| 🔵 **P3** | **Değişiklik gerekmiyor.** Doğru uygulanmış; kayıt amaçlı. |

---

## 1. 🔴 P0 — Kesin değişmeli

### P0-1 · Hedef veritabanı transaction'ı hiç commit edilmiyor

**Yer:** `web_api/database_provider/database.py:150-163`,
`web_api/query_execution/services.py:251-257`,
`web_api/workspaces/services.py:371-375`, `web_api/admin/services.py:407-409`
**Durum:** `docs/inbox/TARGET-TRANSACTION-COMMIT.md` içinde zaten kayıtlı
("en yüksek öncelik") — bu denetim kaydı **bağımsız olarak doğruluyor**.

`get_session` oturumu `autocommit=False` ile açıyor, engine'de
`isolation_level="AUTOCOMMIT"` yok ve kod tabanının tamamında hedef oturum
üzerinde tek bir `commit()` çağrısı yok:

```
grep -rn "commit()" --include="*.py" . → 8 sonuç, hepsi uygulama metadata DB'si
```

SQLAlchemy açık bir transaction'ı `close()` sırasında geri alır. Sonuç:
`INSERT`/`UPDATE`/`DELETE` çalışır, `rowcount` döner, audit `successfull=True`
yazar — sonra **rollback olur**. Kullanıcı yazdığını sanır, veri değişmemiştir.

Testler bu hatayı yakalayamıyor çünkü `tests/conftest.py` hedef oturumu
mock'luyor; `test_query_execution.py:175` `"3 rows affected"` iddiasını
mock'lanmış `rowcount` üzerinden doğruluyor.

**Etki:** `rw` ve `ddl` kademeleri fiilen işlevsiz. Adım 16'nın (`3.1`) tüm
yatırımı — ayrı hesaplar, kademe seçimi, `exceeds_mode` doğrulaması — yazma
yolunda hiç sonuç üretmiyor.

**Öneri:** Inbox kaydındaki iş kalemlerini uygula. Önce kırmızıya düşen bir
regresyon testi (gerçek sqlite/container hedefi ile), sonra `get_session`
içinde `tier != "ro"` için commit/rollback davranışı. Satırların oturum
kapanmadan okunduğuna dikkat et.

---

### P0-2 · Hedef DB kimlik bilgileri bağlantı dizesine URL-encode edilmeden yazılıyor

**Yer:** `web_api/database_provider/config.py:98-142` (`create_connection_string`),
`web_api/app_database/config.py:26-35`
**Durum:** **Yeni bulgu.** Hiçbir inbox/spec kaydında yok.

Kullanıcı adı ve parola f-string ile doğrudan URL'ye gömülüyor:

```python
return f"mssql+{driver}://{username}:{password}@{servername}/{database}?..."
```

`quote_plus` yok. Parolada `@`, `/`, `:`, `?`, `#` geçerse URL yanlış ayrışır.
Yerel repro (bu denetimde çalıştırıldı):

```
create_connection_string(tech='postgresql', driver='asyncpg',
    username='app_rw', password='P@ss/w0rd#1',
    servername='db.internal', database='sales')

URL:  postgresql+asyncpg://app_rw:P@ss/w0rd#1@db.internal/sales
make_url →  host = 'ss'   user = 'app_rw'   pass = 'P'   db = 'w0rd#1@db.internal/sales'
```

**Etki:** Bu güvenlik açısından yalnız "bağlantı kurulamaz" değil. Parola
`P` olarak, host `ss` olarak çözülüyor — yani **WebQuery, DBA'in verdiği
parolanın bir parçasını, admin'in hiç yazmadığı bir hosta gönderiyor.**
DNS ile ele geçirilebilir bir isim üretilebilirse credential dışarı sızar.

OQ-2026-002'nin kararı gereği parolaları **DBA yazıyor**; WebQuery üretmiyor.
Yani parola karakter kümesi WebQuery'nin kontrolünde değil — `@` içeren bir
kurumsal parola tamamen olağan.

**Öneri:** `sqlalchemy.engine.URL.create(...)` kullan (parça parça, kaçışı
kütüphaneye bırakarak) veya en azından `urllib.parse.quote_plus`. Aynı düzeltme
`app_database/config.py` içindeki varsayılan URL'ye de gerekli. Testte özel
karakterli parola vakası olmalı.

---

### P0-3 · Onaylanmış workspace'in SQL'i onay sonrası değiştirilebiliyor — onay bypass'ı

**Yer:** `web_api/workspaces/router.py:102-127`,
`web_api/workspaces/services.py:200-232`, `web_api/workspaces/schemas.py:52-61`
**Durum:** **Yeni bulgu.**

`PUT /api/workspaces/{id}` yalnız `ensure_owner` ile korunuyor. Gövde
`{query, status}` alıyor ve hiçbir durum makinesi doğrulaması yok:

```python
if query:  query_data.query = query
if status: query_data.status = status
```

İki ayrı sorun:

1. **Onay bypass'ı.** Kullanıcı zararsız bir riskli sorgu gönderir, admin
   `approve_with_results` ile onaylar (`show_results=True`,
   `status="approved_with_results"`). Kullanıcı sonra `PUT` ile SQL'i
   değiştirir. `execute_workspace` yalnız `show_results` ve `status` bakar
   (`workspaces/services.py:293-296`); yeni SQL için **analiz kapısı yeniden
   çalışmaz**. Rol kontrolü ve sert bloklar hâlâ geçerli, ama onay gerektiren
   sınıf (`ddl_pattern`, `risky_pattern`, `performance_risk`) tamamen atlanır.
   Bir WRITER, tek bir onayı sınırsız sayıda `WHERE`'siz `UPDATE`/`DELETE`'e
   çevirebilir.

2. **Onay penceresinde TOCTOU.** Sorgu `waiting_for_approval` iken sahibi SQL'i
   değiştirebilir. Admin `execute_for_preview` ile okuduğu SQL'i onaylarken,
   kayıtta başka bir SQL durabilir.

Frontend `isEditable(status)` ile düzenlemeyi kısıtlıyor — ama bu bir
istemci tarafı kısıtı; API doğrudan çağrılabilir.

**Öneri:** Üç kapı birden:
- `PUT` yalnız `saved_in_workspace` ve `rejected` durumlarında SQL değişikliğine
  izin versin; onaylı/beklemedeki kayıt için `409` dönsün.
- `status` istemciden hiç kabul edilmesin (durum geçişleri yalnız
  `approval.service.decide` ve çalıştırma akışının işi).
- SQL değişince `show_results` sıfırlansın ve durum `saved_in_workspace`'e
  düşsün.

---

### P0-4 · İstemci IP'si reverse proxy'nin IP'si — giriş kısıtlaması ve rate limit tüm platformu tek kovaya bağlıyor

**Yer:** `nginx.conf:16-22`, `web_api/app.py:246-250`,
`web_api/common/limiter.py:9`, `web_api/authentication/router.py:90`
**Durum:** **Yeni bulgu.** Adım 14'ün (`2.4`) doğrudan etkinliğini bozuyor.

nginx `X-Forwarded-For` ve `X-Real-IP` gönderiyor, ama uygulama tarafında bu
başlıkları okuyan hiçbir şey yok:

```
grep -rn "proxy_headers|ProxyHeaders|FORWARDED_ALLOW_IPS" web_api/ → 0 sonuç
```

Uvicorn'un kendi `ProxyHeadersMiddleware`'i varsayılan olarak yalnız
`127.0.0.1`'e güvenir; Docker ağında nginx konteynerinin IP'si bu değildir.
Dolayısıyla `request.client.host` **her istek için aynı** (nginx'in IP'si).

Üç somut sonuç:

| Mekanizma | Beklenen | Gerçekte |
| --- | --- | --- |
| `RedisLoginThrottle` IP anahtarı (`LOGIN_MAX_FAILURES=5`) | IP başına 5 başarısız giriş | **Tüm platformda toplam 5 başarısız giriş** → 15 dk boyunca herkes `429` |
| slowapi `get_remote_address` (`/api/login` `3/minute`) | Kullanıcı başına 3 giriş/dk | **Tüm platformda 3 giriş/dk** |
| Audit `client_ip` (`ActionLogging`, `AuditLog`, `LoginLogging`) | Saldırgan/aktör izi | Her kayıtta aynı sabit değer — denetim değeri sıfır |

İlk satır bir **self-DoS**: tek bir kullanıcının parolasını 5 kez yanlış
girmesi tüm şirketin girişini kilitler. OQ-2026-005'te bilinçli olarak
fail-closed seçildiği için Redis'e ulaşılabildiği hâlde bu kilit gerçekleşir.

**Öneri:** Uvicorn'u `--proxy-headers --forwarded-allow-ips=<nginx CIDR>` ile
çalıştır (veya `uvicorn.run(..., proxy_headers=True, forwarded_allow_ips=...)`).
Güvenilen proxy listesini ortam değişkeninden al; asla `*` kullanma. Ardından
`request.client.host` doğru değeri verir ve throttle/limiter/audit üçü birden
düzelir. Adım 14'ün kabul kriterlerine "proxy arkasında IP kovası ayrışıyor"
maddesi eklenmeli.

---

## 2. 🟠 P1 — Değişmeli

### P1-1 · `POST /api/multiple_query` rate limit'siz

**Yer:** `web_api/query_execution/router.py:58-93`

`execute_query` `@limiter.limit(config.RATE_LIMITER)` (varsayılan `10/minute`)
taşıyor; `multiple_query` **taşımıyor**. Endpoint istek başına
`MULTIPLE_QUERY_COUNT` (varsayılan 10) sorgu çalıştırıyor. Yani tek sorgu
uçtaki limiti sınırsız `multiple_query` çağrısıyla atlamak mümkün.

Ek olarak: `audit:api` çıktısına göre bu rotanın **hiç arayüzü yok**. Kullanılmayan
ve korumasız bir yürütme yüzeyi.

**Öneri:** Ya aynı limiter'ı ekle (tercihen istek başına sorgu sayısıyla
ağırlıklandırarak), ya da rotayı kaldır. Kaldırmak, `MULTIPLE_QUERY_COUNT`
konfigürasyonunu da sadeleştirir.

---

### P1-2 · `GET /api/admin/audit_log` veritabanı kapsamına göre daraltılmıyor

**Yer:** `web_api/admin/router.py:232-300`, `web_api/dependencies.py:104-124`

`admin_required` yalnız "**en az bir** veritabanında ADMIN mi" sorusunu
soruyor. Endpoint bundan sonra `AuditLog` tablosunun tamamını döndürüyor:
diğer veritabanlarının erişim değişiklikleri, OWNER işlemleri, tüm kullanıcıların
login/logout kayıtları, tüm masking delta'ları.

Modülün geri kalanı bu hatayı yapmıyor — `discover_schema`,
`get_all_masking_rules`, `save_masking_rules`, `associate_user_to_database`
hepsi hedef `database_id` üzerinde ADMIN kontrolü tekrarlıyor. Audit endpoint'i
bu desende tek istisna.

**Öneri:** Sorguyu çağıranın ADMIN olduğu `database_id` kümesine daralt;
`target_type = database` olmayan platform seviyesi kayıtları (OWNER işlemleri,
login) yalnız `is_platform_owner` için aç. Alternatif olarak endpoint'i tümüyle
OWNER'a taşı — ama o zaman DB ADMIN'in kendi veritabanının onay geçmişini
göreceği bir yüzey kalmıyor.

---

### P1-3 · `GET /api/masking_rules` erişim kontrolü yapmıyor

**Yer:** `web_api/query_execution/router.py:162-172`,
`web_api/query_execution/services.py:330-343`

`get_active_masking_rules(db_uuid)` yalnız UUID ile `Databases`'i buluyor ve
maskelenen kolon adlarını döndürüyor. Çağıranın o veritabanına
`UserDatabaseAssociation` sahibi olup olmadığı **hiç kontrol edilmiyor**.

Herhangi bir kimliği doğrulanmış kullanıcı, elindeki bir UUID ile erişimi
olmayan bir veritabanının hassas kolon adlarını (`salary`, `tckn`, `iban` ...)
listeleyebilir. Şema keşfi için kullanışlı bir bilgi.

**Öneri:** `execute_query`'deki association kontrolünün aynısını uygula; yoksa
`403`. Zaten `database_information` bu daraltmayı doğru yapıyor.

---

### P1-4 · MSSQL'de statement timeout muhtemelen uygulanmıyor

**Yer:** `web_api/database_provider/config.py:44-49`
**İlgili:** ADR-0007 "Accepted Risks" bölümünde bu riski açıkça kabul ediyor.

```python
if tech == "mssql":
    # aioodbc/pyodbc applies this as the statement execution timeout.
    return {"timeout": timeout_seconds}
```

Yorum yanlış. pyodbc'de `connect(timeout=...)` `SQL_ATTR_LOGIN_TIMEOUT`'a,
yani **giriş** zaman aşımına karşılık gelir. Sorgu zaman aşımı ayrı bir şeydir:
bağlantı nesnesi üzerindeki `Connection.timeout` özniteliği.

Bu doğruysa, Adım 6'nın (`0.3`) getirisi projenin **birincil teknolojisinde**
yok: PostgreSQL'de `command_timeout` + `statement_timeout` var, MySQL'de
`SET SESSION max_execution_time` var, MSSQL'de hiçbir şey yok.

**Öneri:** Gerçek bir MSSQL'e karşı `WAITFOR DELAY '00:10:00'` ile ölç. Doğrulanırsa
SQLAlchemy `connect` event'iyle `dbapi_connection.timeout = QUERY_TIMEOUT_SECONDS`
ata. ADR-0007'nin "Accepted Risks" maddesi ölçüm sonucuna göre güncellensin.
Ayrıca not: MySQL'in `max_execution_time`'ı yalnız salt-okuma `SELECT` için
geçerlidir; `rw` kademesindeki DML orada da korumasız.

---

### P1-5 · Sonuç kümesi tamamen belleğe alınıyor; satır limiti yalnız cevabı kırpıyor

**Yer:** `web_api/query_execution/services.py:264`,
`web_api/workspaces/services.py:382`, `web_api/admin/services.py:417`
**İlgili:** Adım 22 (`4.6`) bunu "opsiyonel, yük artarsa" olarak sınıflandırıyor.

SQLAlchemy'nin async katmanı `session.execute()` sonucunu **ön-belleğe alır**;
`fetchmany(1000)` ancak ondan sonra çalışır. Yani 8 milyon satırlık bir `SELECT`
tamamen uygulama belleğine gelir, sonra 1000 satırı döndürülür.

Bunu üç şey birleştirdiğinde risk "opsiyonel"in üstüne çıkıyor:
- `QUERY_TIMEOUT_SECONDS` varsayılanı 300 sn — okumaya bol zaman var,
- MSSQL'de o timeout muhtemelen hiç uygulanmıyor (P1-4),
- `performance_risk` varsayılan olarak **bloklamıyor** (`PERFORMANCE_BLOCKS=false`).

Yani `SELECT * FROM buyuk_tablo` bir onay kapısına takılmadan, zaman aşımına
uğramadan, worker'ın belleğini tüketebilir. Tek bir kullanıcı process'i
düşürebilir.

**Öneri:** Adım 22'yi "opsiyonel"den çıkar. `returns_rows` yolunda
`session.stream()` kullan, limitte döngüyü kır; DML yolu `execute()` ile kalsın
(inbox'taki `MULTI-RESULT-SET-REPORTING` ile birlikte değerlendirilmeli).

---

### P1-6 · bcrypt (rounds=14) event loop'u bloke ediyor

**Yer:** `web_api/app_database/models.py:125,138`,
`web_api/authentication/router.py:99-110`

`bcrypt.gensalt(rounds=14)` ≈ 1–2 sn CPU. `check_password` ve `set_password`
senkron; async endpoint'in içinden doğrudan çağrılıyorlar. Bu süre boyunca
**tüm worker** durur — o anki her istek, her sorgu, her audit yazımı bekler.

Kanıt: 187 testin 110 saniye sürmesinin ana kalemi budur.

`login` üstelik bu işi `async with app_db.get_app_db() as db:` bloğunun içinde
yapıyor; bir app-DB bağlantısı da saniyelerce tutuluyor.

Rounds=14 tercihi sağlamdır ve **değiştirilmemeli**; sorun onun nerede
çalıştığı.

**Öneri:** `await anyio.to_thread.run_sync(...)` ile thread'e taşı. Ayrıca
kullanıcı bulunamadığında da sabit süreli bir dummy hash doğrulaması yap
(zamanlama yan kanalı; şu an kullanıcı yok → anında `400`, kullanıcı var →
1,5 sn sonra `400`, yani e-posta enumerasyonu zamanlamadan okunabilir).
DB oturumunu hash doğrulamasından önce kapat.

---

### P1-7 · Kullanıcıya veritabanı erişimi verecek arayüz yok

**Yer:** `frontend/services/api.ts:268-273` (`associateUser`),
`frontend/pages/Admin.tsx` (yalnız `approvals`/`masking`/`owner` sekmeleri)

`api.associateUser` tanımlı ama **hiçbir bileşen çağırmıyor**:

```
grep -rn "associateUser" frontend/ → yalnız services/api.ts:268 (tanım)
```

Sonuç, uçtan uca akışta bir kopukluk:

| Rol | UI'dan yapabildiği | Yapamadığı |
| --- | --- | --- |
| OWNER | Kullanıcı aktive/pasif, DB ekle, DB ADMIN ata/kaldır | Kullanıcıya READER/WRITER/DDL veremez |
| DB ADMIN | Onay ver/reddet, maskeleme kuralı | Kullanıcıya READER/WRITER/DDL veremez, kullanıcı listesini bile göremez |

Yani bir kullanıcı kaydolup OWNER tarafından aktive edildikten sonra
**arayüzden hiçbir veritabanına erişemez**; erişim ancak doğrudan API çağrısı
veya elle SQL ile verilebilir. Bu, Adım 16 ve Adım 20'nin yönetişim modelini
üretimde kullanılamaz kılıyor.

Ek olarak DB ADMIN'in kullanacağı bir "kullanıcı listele" ucu da yok:
`/api/owner/users` OWNER'a kapalı. Yani `user_id` bilinemiyor.

`npm run audit:api` bunu yakalamıyor çünkü betik `services/api.ts`'teki tanımı
"frontend çağrısı" sayıyor; bileşenlerden çağrılıp çağrılmadığına bakmıyor.

**Öneri:** Yönetim paneline "Erişimler" sekmesi ekle (veritabanı seç → kullanıcı
listesi → rol ata/değiştir). Backend'de DB ADMIN'in görebileceği, kapsamı dar
bir kullanıcı listeleme ucu gerekiyor. `audit:api` betiğine "tanımlı ama
çağrılmayan istemci fonksiyonu" kontrolü eklenmeli.

---

### P1-8 · Erişim iptali (revoke) akışı hiç yok

**Yer:** `web_api/common/audit_actions.py:5-7`, `web_api/admin/`
**Durum:** `docs/inbox/AUDIT-ACTION-FOLLOW-UPS.md` içinde kayıtlı.

`AuditAction.REVOKE_DATABASE_ACCESS` tanımlı, hiçbir yerde kullanılmıyor —
çünkü bir kullanıcının veritabanı erişimini **kaldıran endpoint yok**.
`associate_user_to_database` yalnız rol değiştirebiliyor; boş rol gönderimi
`"Invalid role"` ile reddediliyor.

İşten ayrılan bir çalışanın hedef veritabanı erişimini kaldırmanın tek yolu,
kullanıcıyı OWNER üzerinden tamamen devre dışı bırakmak. Tek bir veritabanından
erişim çekmek mümkün değil.

**Öneri:** `DELETE /api/admin/databases/{id}/users/{user_id}` ekle; aynı
transaction'da `REVOKE_DATABASE_ACCESS` audit'i yaz (inbox kaydındaki alan
listesiyle). ADMIN rolüne dokunmasın — o OWNER'ın işi.

---

### P1-9 · Şifre değiştirme akışı yok

**Yer:** `web_api/common/audit_actions.py:14` (`PASSWORD_CHANGED`, kullanılmıyor)

12 karakter + büyük harf + rakam politikası var, bcrypt rounds=14 var, ama
kullanıcının şifresini değiştirebileceği bir endpoint veya ekran yok. Şifre
sıfırlama da yok. Sızmış bir şifreyi değiştirmenin uygulama içi yolu bulunmuyor.

`PASSWORD_CHANGED` audit action'ının tanımlı olması, bunun planlanıp
uygulanmadığını gösteriyor.

**Öneri:** `POST /api/me/password` (eski şifre + yeni şifre), aynı transaction'da
`PASSWORD_CHANGED` audit'i ve `revoke_user_sessions` ile diğer oturumların
iptali. Frontend'de hesap menüsüne bağla.

---

### P1-10 · Hedef DB kaydı güncellenemiyor/silinemiyor — credential rotasyonu imkânsız

**Yer:** `web_api/owner/router.py` (yalnız `POST` ve `GET`)
**Durum:** `docs/inbox/DATABASE-REGISTRATION-LIFECYCLE.md` içinde kayıtlı.

DBA hedef sunucuda `app_rw` şifresini değiştirdiğinde WebQuery'de karşılığını
güncellemenin yolu yok. Yanlış yazılan bir sunucu adı düzeltilemiyor, kullanımdan
kalkan bir veritabanı kaydı silinemiyor. `AuditAction.REMOVE_DATABASE` tanımlı
ama kullanılmıyor.

OQ-2026-002 kararı gereği parolaları DBA yönetiyor; rotasyon o modelin doğal
parçası. Rotasyon yolu olmayan bir credential modeli, ilk rotasyonda
veritabanını erişilemez bırakır.

**Öneri:** Inbox kaydını uygula. `close_database_engines(db_uuid)` zaten var —
güncelleme sonrası cache'i geçersiz kılmak için doğru kanca hazır.

---

### P1-11 · `EncryptedText` çözemediği değeri sessizce ham döndürüyor

**Yer:** `web_api/app_database/models.py:78-88`

```python
except Exception:
    # Fallback to returning raw value if decryption fails (legacy plaintext)
    return value
```

`QUERY_ENCRYPTION_KEY` değiştiğinde (rotasyon, yanlış deploy, ortam karışması)
bu blok **şifreli metni parola olarak** üst katmana verir. Sonuç: hedef DB'ye
`gAAAAAB...` ile bağlanma denemesi, anlaşılmaz bir kimlik doğrulama hatası ve
hiçbir yerde "anahtar yanlış" sinyali yok. Aynı şey `ActionLogging.query` ve
`QueryData.query` için de geçerli — audit kaydı okunamaz hâle gelir ve bunu
kimse fark etmez.

Ayrıca `_fernet` sınıf düzeyinde tek örnek olarak cache'leniyor; `MultiFernet`
kullanılmadığı için **anahtar rotasyonu için geçiş dönemi yok**.

**Öneri:** Legacy düz metin ihtimalini bir kez migration ile kapat, sonra
fallback'i kaldır ve çözme hatasını yükselt (veya en azından `logger.error`
ile görünür kıl). Rotasyon için `MultiFernet` ve `QUERY_ENCRYPTION_KEYS`
(çoğul, virgüllü) desteği ekle.

---

### P1-12 · Dağıtım yapılandırması üretim için sertleştirilmemiş

**Yer:** `docker-compose.yml`, `web_api/Dockerfile`, `web_api/app.py:240-250`,
`nginx.conf`

Tek tek küçük, birlikte ciddi:

| Bulgu | Yer | Sonuç |
| --- | --- | --- |
| `DEBUG` varsayılanı `"True"` → `uvicorn.run(reload=True)` | `app.py:249` | Üretimde `DEBUG` set edilmezse auto-reload açık; `workers` ayarı yok sayılır |
| Konteyner `root` olarak çalışıyor (`USER` yok) | `Dockerfile` | Konteyner kaçışında ayrıcalık |
| `DB_USER:-sa` varsayılanı | `docker-compose.yml:11` | Adım 4'te (`0.4`) koddan kaldırılan `sa` varsayılanı compose'da duruyor |
| `MSSQL_SA_PASSWORD=${DB_PASSWORD}` | `docker-compose.yml:37` | Uygulama DB parolası = `sa` parolası |
| `./web_api:/app` bind mount | `docker-compose.yml:19` | Üretim imajının içeriği host'tan eziliyor; imaj değişmezliği yok |
| `1433:1433` host'a açık | `docker-compose.yml:38-39` | Veritabanı doğrudan erişilebilir |
| nginx'te TLS, güvenlik başlıkları, rate limit yok | `nginx.conf` | `COOKIE_SECURE` varsayılanı da `False`; oturum çerezi düz HTTP'de |

**Öneri:** `DEBUG` varsayılanını `"false"` yap. Dockerfile'a non-root `USER`.
Compose'dan `sa` varsayılanını, bind mount'u ve 1433 publish'ini kaldır.
nginx'e TLS + HSTS + `X-Content-Type-Options` + `X-Frame-Options` +
`Content-Security-Policy` ekle; `COOKIE_SECURE=true` zorunlu hâle gelsin
(`config_guard`'a taşınabilir).

---

### P1-13 · `create_db.py` bootstrap'ı: işlevsiz retry, `sa`, string interpolation, `db_owner`

**Yer:** `web_api/create_db.py`, `web_api/entrypoint.sh:6-18`

`entrypoint.sh` "veritabanı hazır mı" beklemesini `if python create_db.py`
başarısına bağlıyor. Ama `create_db.py` tüm istisnaları yakalayıp
`logger.warning` ile yutuyor ve **her zaman 0 ile çıkıyor**. Yani retry döngüsü
ilk turda "başarılı" der, SQL Server ayakta olmasa bile; hemen ardından
`alembic upgrade head` çalışır ve patlar. 30 denemelik bekleme mekanizması
fiilen yok.

Aynı dosyada üç ek konu:
- `sa` ile bağlanıyor ve uygulama kullanıcısına `db_owner` veriyor,
- `CREATE LOGIN {target_user} WITH PASSWORD = '{target_password}'` — parola ve
  kullanıcı adı f-string ile SQL'e gömülü (ortam değişkeninden SQL injection),
- `CREATE DATABASE {target_db}` aynı şekilde.

**Öneri:** Bekleme mantığını `create_db.py`'den ayır (basit bir `SELECT 1`
denemesi, gerçekten exit code döndüren). Bootstrap'ı üretim entrypoint'inden
tamamen çıkarıp yalnız geliştirme profiline bırakmak en temizi. Kalırsa
tanımlayıcılar için `sqlalchemy.sql.quoted_name`/whitelist doğrulaması ve
`db_owner` yerine dar rol seti.

---

## 3. 🟡 P2 — Değişse iyi olur, acil değil

### P2-1 · `QUERY_REJECTED_BY_ANALYZER` iki farklı şey için kullanılıyor → yanlış arayüz mesajı

**Yer:** `web_api/query_execution/services.py:126,133`,
`frontend/lib/execution.ts:75`, `frontend/pages/Studio.tsx:208-212`

`QueryAnalysisRejectedError` üç durumda fırlatılıyor:
1. Veritabanına erişim yetkisi yok,
2. Rol bu ifadeyi çalıştıramaz,
3. Analizci reddetti → **onaya gönderildi**.

Frontend yalnız hata koduna bakıyor (`error.code === QUERY_SENT_FOR_APPROVAL`)
ve üçünde de "**Sorgu onaya gönderildi**" toast'ı gösterip bekleme durumu
çiziyor. İlk iki durumda hiçbir onay talebi oluşturulmamıştır; kullanıcı
olmayan bir onayı bekler.

**Öneri:** Yetki reddi için ayrı bir exception/kod (`QUERY_ROLE_DENIED`,
`DATABASE_ACCESS_DENIED`). `QUERY_REJECTED_BY_ANALYZER` yalnız gerçekten
onaya düşen yol için kalsın.

---

### P2-2 · Sorgu başına 3–4 kez sqlglot parse

**Yer:** `web_api/query_execution/services.py:117,135,146`,
`web_api/workspaces/services.py:337,346,352`

Tek bir çalıştırma için aynı SQL şu sırayla ayrıştırılıyor:
`check_permissions_match_role` → `required_tier` → `analyze`. Workspace yolunda
`hard_block_reason` bir `analyze` daha çağırıyor: **4 parse**.

Doğruluk sorunu değil, ama sqlglot ayrıştırması ucuz değil ve tümü aynı
event loop'ta senkron çalışıyor.

**Öneri:** Bir kez `sqlglot.parse` yap, `statements` listesini üç kontrole de
geçir. `QueryAnalyzer`'a `analyze_parsed(statements)` gibi bir iç yüzey yeter;
dış API korunabilir.

---

### P2-3 · Kimlik doğrulama başına 3 app-DB sorgusu, biri tamamen gereksiz

**Yer:** `web_api/middlewares/auth_middleware.py:74-97`,
`web_api/authentication/services.py:113-133`

Her kimliği doğrulanmış istek için:

| # | Sorgu | Nerede |
| --- | --- | --- |
| 1 | `session_alive` | AuthMiddleware |
| 2 | `SELECT User` | AuthMiddleware |
| 3 | `session_alive` (**tekrar**) | `get_current_user` bağımlılığı |

Middleware kullanıcıyı `request.state.authenticated_user`'a koyuyor ve
bağımlılık onu tekrar kullanıyor — ama `session_alive` yeniden çağrılıyor.
Aynı istek içinde aynı cevap.

**Öneri:** Middleware oturum doğrulamasının sonucunu da `request.state`'e
yazsın; bağımlılık varsa onu kullansın (izole test yolu için mevcut fallback
korunur). Bu, isteklerin üçte birlik DB yükünü kaldırır.

---

### P2-4 · N+1 sorgu desenleri

| Yer | Desen |
| --- | --- |
| `admin/services.py:302-349` `get_workspaces_for_approval` | Bekleyen her sorgu için 4 ayrı `SELECT` (Databases, association, Workspace, User) |
| `admin/services.py:135-158` `list_databases` | Zaten join'lenmiş association'ı her satır için tekrar sorguluyor |
| `owner/services.py:139-163` `list_database_admins` | Tüm association'ları çekip Python'da `is_admin` ile eliyor |
| `workspaces/services.py:130-133` | Tüm `Databases` tablosunu çekip bellekte map kuruyor |

Hiçbiri hatalı değil; hepsi kayıt sayısıyla doğrusal ek sorgu üretiyor.
Onay kuyruğu 50 kayda çıktığında `get_workspaces_for_approval` 200'den fazla
sorgu atar.

**Öneri:** Tek `join` + `selectinload` ile yeniden yaz; `is_admin` filtresini
SQL'e taşımak zor (virgüllü rol dizesi) ama en azından `role LIKE '%ADMIN%'`
ön-filtresi + Python doğrulaması kombinasyonu kullanılabilir.

---

### P2-5 · `discover_schema` her çağrıda tüm hedef DB credential'larını yeniden yüklüyor

**Yer:** `web_api/admin/services.py:170-172`

```python
db_info = await self.app_db.get_db_info()
self.db_provider.set_db_info(db_info)
```

Her şema tarama isteği, kayıtlı **tüm** veritabanlarının şifrelerini
veritabanından çekip Fernet ile çözüyor ve global provider durumunu baştan
kuruyor. Tek bir veritabanına bakmak için gereksiz; ayrıca eşzamanlı isteklerde
paylaşılan sözlüğü yeniden yazıyor.

**Öneri:** Katalog yenilemesini yalnız kayıt değiştiğinde yap (OWNER
`add_database` zaten doğru yerde yapıyor). `discover_schema` mevcut katalogla
çalışsın.

---

### P2-6 · Maskeleme kuralı `table_name` ve `masking_type` alanlarını yok sayıyor

**Yer:** `web_api/common/security.py:26-62`,
`web_api/query_execution/services.py:139-144`

Kural `(table_name, column_name, masking_type)` olarak saklanıyor, arayüzde
tablo tablo seçiliyor, audit'te tablo adıyla birlikte kaydediliyor — ama
uygulanırken yalnız `column_name` bir kümeye atılıyor:

```python
masking_cols.add(rule.column_name.lower())
```

Sonuç:
- `Customers.email` için tanımlanan kural, `Suppliers.email` sonuçlarını da
  maskeler (**aşırı maskeleme**, sessiz veri kaybı),
- `masking_type` hiçbir yerde okunmuyor; her şey `"********"`.

Arayüz, motorun uygulamadığı bir ayrıntı seviyesi vaat ediyor.

**Öneri:** Ya enforcement'ı tablo farkındalığına taşı (sonuç kümesinde tablo
bilgisi olmadığı için kolay değil — sorgu AST'sinden çıkarılmalı), ya da
kararı belgeleyip UI'ı kolon bazına indir ve `masking_type`'ı kaldır. İkisinden
biri seçilmeli; mevcut hâl kullanıcıya yanlış bilgi veriyor.

---

### P2-7 · Kırpma tespitinde bir-fazla hatası

**Yer:** `query_execution/services.py:265-268`, `workspaces/services.py:383-386`,
`admin/services.py:418-423`

`fetchmany(size=LIMIT)` en fazla `LIMIT` satır döndürür; kod
`if row_count >= LIMIT` ile kırpıldığını varsayıyor. Sonuç kümesi **tam olarak**
`LIMIT` satırsa, kullanıcıya yanlışlıkla "kırpıldı" denir ve frontend
"İlk 1000 satır (kırpıldı)" gösterir.

**Öneri:** `fetchmany(size=LIMIT + 1)` çek, `len(rows) > LIMIT` ise kırp ve
işaretle.

---

### P2-8 · `save_masking_rules` yetki hatasını genel hataya çeviriyor

**Yer:** `web_api/admin/services.py:220-277`

Tüm gövde `except Exception: return False` ile sarılı. ADMIN olmayan bir
kullanıcı için fırlatılan `BaseServiceException` de, veritabanı hatası da,
`MaskingRulesAuditDetails` içindeki `ValueError` (aynı tablo+kolon iki kez
gönderilirse) de aynı `400 "Failed to save masking rules"` mesajına dönüşüyor.
Kullanıcı neyi düzelteceğini bilemiyor, operatör de logdan ayırt edemiyor.

**Öneri:** `BaseServiceException`'ı yeniden fırlat; yalnız beklenmeyen hataları
yakala. Yinelenen kural için ayrı, anlaşılır bir mesaj.

---

### P2-9 · `EngineCache`: aktif engine tahliyesi ve ölümcül temizlik döngüsü

**Yer:** `web_api/database_provider/engine_cache.py:58-67,131-155`

- `_evict_lru` boşta engine yoksa `min(idle or entries, ...)` ile **aktif** bir
  engine'i seçip `dispose()` ediyor. 100 engine sınırına ulaşıldığında devam
  eden bir sorgunun havuzu kapatılabilir.
- `_loop` yalnız `asyncio.CancelledError` yakalıyor. `dispose()` veya başka bir
  adım beklenmedik bir istisna fırlatırsa `while` döngüsünden çıkılır, task
  sessizce ölür ve **TTL temizliği bir daha hiç çalışmaz** — bunu gösteren bir
  log da yok.

**Öneri:** Tahliye edilecek boşta engine yoksa yeni engine oluşturmayı reddet
(veya bekle), aktif olanı disposelama. `_loop`'ta `except Exception:
logger.exception(...)` ile döngüyü ayakta tut.

---

### P2-10 · `X-Request-ID` doğrulanmadan kabul ediliyor

**Yer:** `web_api/middlewares/trace_middleware.py:24`

İstemcinin gönderdiği başlık olduğu gibi `request.state.request_id` oluyor,
oradan da `AuditLog.trace_id` (`String(36)`) ve response header'a gidiyor.
36 karakterden uzun bir değer audit yazımını veritabanı hatasıyla düşürebilir;
istemci ayrıca kendi izini başkasının izleriyle karıştırabilir.

**Öneri:** Gelen değeri UUID formatına göre doğrula; uymuyorsa yeni UUID üret
(istemcinin değerini ayrı bir alanda taşımak istenirse `X-Correlation-ID`).

---

### P2-11 · Zaman damgaları tutarsız: 8 yerde naive local time

**Yer:** ruff `DTZ005` × 8 — `app_database/app_database.py`, `common/audit.py`,
`approval/service.py`

`sessions.py` ve `owner/services.py` bilinçli olarak `datetime.now(UTC).replace(tzinfo=None)`
kullanıyor (naive UTC). Ama `create_log`, `update_log`, `update_approval_status`,
`create_login_log`, `log_in` düz `datetime.now()` yani **sunucunun yerel saati**
kullanıyor. Aynı tabloda iki farklı zaman ekseni.

Sonuç: audit sıralaması ve süre hesapları (`login_duration_ms`,
`ExecutionDurationMS`) DST geçişinde veya farklı TZ'li bir replica'da yanlış
olur; negatif süre bile üretilebilir.

**Öneri:** Tek bir `_db_now()` yardımcısını (`sessions.py`'dekinin aynısı)
ortak yere taşı ve her yazımda onu kullan.

---

### P2-12 · Ölü kod ve ölü şema — Adım 17 (`4.5`) tamamlanmamış

| Öğe | Yer | Durum |
| --- | --- | --- |
| `static_files/router.py` | tüm dosya | `app.py`'de yorum satırı; import edilse **NameError** (ruff F821 × 3); referans verdiği `templates/*.html` yok |
| `create_access_token` | `authentication/services.py:22` | Hiç çağrılmıyor; yerini `sessions.mint_access` aldı |
| `BlacklistedToken` + `blacklist_token` + `is_token_blacklisted` | `models.py:294`, `app_database.py:310-330` | `mint_access` `jti` üretmediği için tablo hiç yazılmıyor, kontrol hiç çalışmıyor. Adım 7 (`0.5`) sonrası mekanizma tamamen atıl |
| `generate_secure_credentials` | `common/security.py:10` | Hiç çağrılmıyor (OQ-2026-002 ile WebQuery artık hesap üretmiyor) |
| `Databases.db_username` / `db_password` | `models.py:246-247` | Üretim kodunda hiç okunmuyor/yazılmıyor |
| `passlib`, `Jinja2` | `requirements.txt` | Kullanılmıyor (bcrypt doğrudan, template yok) |
| `AuditAction.USER_CREATED` | `audit_actions.py:11` | Çağrı noktası yok |
| `unused import User` | `sessions.py:11` | ruff F401 |
| `CONFIRMATION_SECRET` | uygulama sırası kontrol listesi | Hiçbir yerde yok — DML teyidi ertelendiği için beklenen, ama kontrol listesi güncellenmeli |

**Öneri:** Tek bir temizlik commit'i. `BlacklistedToken` için karar gerekiyor:
ya `mint_access` `jti` üretip mekanizmayı yeniden bağla, ya tabloyu ve kodu
migration ile kaldır. İkisinin arasında kalmak en kötüsü.

---

### P2-13 · Refresh token yeniden kullanımı yalnız tek oturumu iptal ediyor

**Yer:** `web_api/authentication/sessions.py:122-133`

Yeniden kullanım tespit edildiğinde yalnız `prev_refresh_hash` eşleşen tek
`UserSession` satırı iptal ediliyor. Yaygın pratik, çalınmış bir token
tespitinde **tüm oturum ailesini** (veya kullanıcının tüm oturumlarını) iptal
etmektir; `revoke_user_sessions` fonksiyonu zaten var ve kullanılmıyor.

**Öneri:** Yeniden kullanım tespitinde `revoke_user_sessions(user_id, "reuse")`
çağır ve `SESSION_REVOKED` audit'i yaz.

---

### P2-14 · `/api/refresh` rate limit'siz; `/api/register` e-posta enumerasyonuna açık

**Yer:** `web_api/authentication/router.py:166-205`, `:209-262`

- `/api/refresh` hem `skip_auth_paths` içinde hem limiter'sız. Geçersiz token
  denemeleri sınırsız; her deneme 1–2 DB sorgusu.
- `/api/register` var olan e-posta için `UserAlreadyExistsError` (409/400),
  olmayan için başarı döndürüyor. Alan adı allowlist'i saldırı yüzeyini
  daraltıyor ama kurum içi e-posta doğrulaması yapılabiliyor.

**Öneri:** `/api/refresh`'e limiter ekle. `register` her iki durumda da aynı
"başvurunuz alındı" mesajını dönsün (aktivasyon zaten OWNER'da).

---

### P2-15 · Bağımlılıklar güncel değil ve CI'da taranmıyor

| Paket | Sürüm | Not |
| --- | --- | --- |
| `aiohttp` | 3.9.5 | Sonraki sürümlerde giderilmiş bilinen açıklar var (request smuggling, static route traversal). Slack Bolt üzerinden dolaylı kullanılıyor |
| `xlsx` (SheetJS) | 0.18.5 (frontend) | npm'deki bu sürüm için bilinen prototype-pollution / ReDoS kayıtları var; upstream npm'i terk etti |
| `httpx` | 0.24.1 | 2023 sürümü, iki majör geride |
| `python-jose` | 3.5.0 | Bilinen CVE'ler kapalı ama proje fiilen bakımsız; PyJWT tavsiye ediliyor |

CI'da `pip-audit`/`npm audit`/Dependabot yok; "Secret leak scan" adımı var ama
bağımlılık taraması yok.

**Öneri:** CI'ya `pip-audit` ve `npm audit --audit-level=high` ekle (önce
informational). `xlsx` için `exceljs` gibi bakımlı bir alternatif değerlendir.

---

### P2-16 · CI kapsamı dar

**Yer:** `.github/workflows/ci.yml`
**İlgili:** ADR-0002 bunu bilinçli bir ara durum olarak kaydediyor.

- `ruff check` `continue-on-error: true` — 50 bulgu birikmiş durumda,
  aralarında gerçek bir hata (F821 × 3) var,
- Frontend için hiçbir job yok: `npm run typecheck`, `npm run build`,
  `audit:api`, `audit:contrast` CI'da çalışmıyor (hepsi yerelde geçiyor),
- Testler yalnız SQLite'a karşı; MSSQL'e özgü davranış (NVARCHAR, DATETIME2,
  `UNIQUEIDENTIFIER`, timeout) hiç doğrulanmıyor.

**Öneri:** Frontend job'ı ekle (ucuz ve şu an yeşil). Ruff'ı önce yalnız
`F` kuralları için merge gate yap, sonra genişlet. MSSQL servis konteynerli
bir nightly job değerlendir.

---

### P2-17 · `pool_pre_ping=False` her iki engine'de de kapalı

**Yer:** `database_provider/engine_cache.py:110`, `app_database/app_database.py:44`

Veritabanı yeniden başladığında veya güvenlik duvarı boşta bağlantıyı
düşürdüğünde havuzdaki bayat bağlantılar ilk kullanımda hata verir.
`pool_recycle` (1800/3600 sn) bunu kısmen azaltıyor ama garanti etmiyor.
Hedef engine'lerde TTL temizliği de var; asıl risk uygulama DB'sinde.

**Öneri:** En azından uygulama engine'inde `pool_pre_ping=True`. Maliyeti
bağlantı başına bir `SELECT 1`.

---

### P2-18 · Riskli sorgunun tam SQL metni Slack'e gönderiliyor

**Yer:** `web_api/notification/services.py:19-37`,
`web_api/query_execution/services.py:236-245`

Onaya düşen sorgunun tamamı (literal değerler dâhil — TCKN, IBAN, e-posta
filtreleri) Slack webhook'una gidiyor. Uygulama içinde `EncryptedText` ile
şifreleyip audit'te maskeleme uygulanan veri, Slack kanalında düz metin duruyor.

Bu bilinçli bir tasarım olabilir (onaylayanın sorguyu görmesi gerekiyor), ama
hiçbir spec/ADR'de bu veri çıkışı kaydedilmemiş.

**Öneri:** Kararı bir ADR'ye yaz. En azından bir uzunluk sınırı ve
"tam sorguyu WebQuery'de görüntüle" bağlantısı seçeneğini değerlendir.

---

### P2-19 · Doküman kayması: README ve ADR-0003

**README.md** birkaç yerde artık doğru olmayan bir sistemi anlatıyor:

| README ifadesi | Gerçek |
| --- | --- |
| "Centralized Service Account Architecture", "No User-Stored Credentials" | ADR-0005 ile veritabanı ve kademe başına ayrı hedef DB hesapları kullanılıyor |
| `pool_size=0`, "up to 20 concurrent" | `_POOL_BY_TIER`: ro 10/20, rw 5/10, ddl 1/2 |
| "more than 3 JOINs" | `MAX_JOINS` varsayılanı **8** |
| Roller: `READER`, `WRITER`, `ADMIN` | `DDL` rolü ve platform `OWNER` eksik |
| "Stateless JWT Authorization" | ADR-0008 ile sunucu tarafı `UserSessions` + rotasyonlu refresh |
| "AES-256 encryption" | Fernet = AES-128-CBC + HMAC-SHA256 |
| SQL injection: "UNION SELECT, OR 1=1, inline comments" | Gerçek kontrol: `exp.Command` içinde `EXEC`/`EXECUTE AS` + ayrıştırılamayan sorgu |
| Redis zorunluluğu, OWNER bootstrap | Hiç geçmiyor |

**ADR-0003 yok.** `docs/open-questions.md` OQ-2026-001'in cevabını
`docs/adr/ADR-0003-engine-cache-lifecycle.md` dosyasına kaydettiğini söylüyor;
dosya mevcut değil. Ayrıca o cevap (`pool_size=50, max_overflow=100`) Adım 16
ile geçersizleşmiş ama OQ girişi güncellenmemiş.

**Öneri:** README'yi mevcut mimariye göre yeniden yaz (bu, yeni katılan biri
için güvenlik modelini yanlış anlatan tek doküman). ADR-0003'ü ya yaz ya da
OQ-2026-001'i `Superseded` işaretleyip doğru kayda yönlendir.

---

### P2-20 · Küçük ama gerçek pürüzler

| # | Bulgu | Yer |
| --- | --- | --- |
| a | `skip_auth_paths` `startswith` ile eşleşiyor; `/login...` ile başlayan yeni bir rota sessizce kimlik doğrulamasız olur | `middlewares/auth_middleware.py:41-53` |
| b | `UserDatabaseAssociation` hem `role` hem `is_admin` tutuyor; yetki kararları yalnız `role`'ü okuyor → iki alanın ayrışması sessiz kalır | `models.py:262-268` |
| c | `QueryData`→`Databases` bağı `(servername, database_name)` ham metin çifti; `database_id` FK yok | inbox `DATABASE-EXTERNAL-IDENTIFIER-UUID.md` |
| d | `ExecutionDurationMS` "sorgu süresi" değil, log oluşturmadan güncellemeye kadar geçen süre (analiz + onay yolu dâhil); hata durumunda hiç yazılmıyor | `app_database.py:180-186` |
| e | `execute_for_preview` hata yolunda ham `str(exc)` döndürüyor; `scrub` uygulanmıyor (admin yüzeyi olsa da diğer üç yolla tutarsız) | `admin/services.py:462-472` |
| f | Slack listener `asyncio.create_task` sonucu saklanmıyor; task referansı GC'ye açık | `app.py:104-108` |
| g | `admin/services.py` `discover_schema` yetkisizde `{}` döndürüyor (403 yerine); istemci "şema boş" ile "yetkiniz yok"u ayıramıyor | `admin/services.py:161-168` |
| h | `get_workspace_by_id` router'ı, servise istek sahibinin değil workspace sahibinin `user_id`'sini geçiriyor; içteki kontrol totoloji (güvenlik açığı değil, `ensure_owner` zaten koruyor — ama yanıltıcı) | `workspaces/router.py:129-152` |
| i | `MaskingRule` üzerinde `(database_id, table_name, column_name)` unique kısıtı yok | `models.py:270-278` |
| j | `AuditLog` "append-only" olarak belgeleniyor ama veritabanı düzeyinde bunu zorlayan bir kısıt/izin/trigger yok — yalnız test seviyesinde | `models.py:315-334` |
| k | `exceeds_mode` rolleri alfabetik geziyor; hata mesajında en yüksek aşılan kademe yerine ilki raporlanabilir | `common/roles.py:118-123` |
| l | `check_explain` regex'i sorgu metnine bakıyor; string literal içindeki `EXPLAIN ... ANALYZE` yanlış pozitif üretir | `query_analyzer.py:60,180` |

---

## 4. 🔵 P3 — Değişiklik gerekmiyor

Bu maddeler denetimde incelendi ve **doğru uygulanmış** bulundu. Kayıt amaçlı
listeleniyor; aksiyon gerekmiyor.

- **Onay yarışı (Adım 10, `1.2`).** `approval/service.py:128-146` durum geçişini
  `UPDATE ... WHERE status = 'waiting_for_approval'` ile koşullu yapıyor ve
  `rowcount != 1` ise `ApprovalConflictError` fırlatıyor. Kontrol ve yazma tek
  cümlede; yarış gerçekten kapalı.
- **Web/Slack onay birleştirmesi (Adım 11, `1.3`).** Tek `decide()` fonksiyonu
  her iki taşıma için yetkilendirme, geçiş, bağımlı yazımlar ve audit'i sahipleniyor.
  Slack tarafında ADMIN kontrolü ve "kendi sorgunu onaylayamazsın" kuralı var.
- **Slack kimlik doğrulaması.** `_resolve_approver` silinmiş hesap, bot,
  misafir, e-postasız profil ve eşleşmeyen kullanıcı vakalarının hepsini
  kapatıyor. Titiz.
- **Analizci sert blok sınırı (Adım 19, `3.2`).** `HARD_BLOCKED_RISKS` hiçbir
  rolün atlayamayacağı sınıfı doğru tanımlıyor; `hard_block_reason` hem admin
  önizlemesinde hem onaylı workspace tekrarında ikinci kapıyı kapatıyor.
  `_function_names` tırnaklı çağrıyı da yakalıyor — atlanması kolay bir ayrıntı.
- **`EXPLAIN ANALYZE` özel işlemi.** sqlglot'un opak `Command` üretmesi
  nedeniyle parse öncesi regex kullanılması doğru karar; gerekçesi kodda yazılı.
- **Kademe/rol kesişimi (OQ-2026-008).** `effective_mode` kullanıcıya kaydın
  modunu değil, kendi etkin yetkisini gösteriyor; `exceeds_mode` de kayıtta
  olmayan kademenin verilmesini `400` ile engelliyor. Karar ile kod birebir uyumlu.
- **`config_guard` fail-closed (Adım 3, `0.1`).** Eksik/varsayılan değerlerde
  `SystemExit(1)`; Fernet anahtarı gerçekten doğrulanıyor; ayrıcalıklı
  `CENTRAL_DB_USER` uyarılıyor.
- **`schema_guard` (Adım 20 öncesi).** `create_all()` ile bootstrap edilmiş eski
  kurulumların eksik index/kısıtlarını başlangıçta yakalayıp fail-closed
  davranması, sessiz bozulmayı önleyen iyi bir karar.
- **Hata temizleme (Adım 5, `0.2`).** `common/errors.py` ikili yaklaşımı
  (`redact_passwords` loga, `scrub` istemciye) OQ-2026-003/004 kararlarıyla
  birebir örtüşüyor. Kullanıcının düzeltebileceği hataların geçirilmesi doğru
  denge.
- **Maskeleme dürüstlüğü (SPEC-0012).** `masked_columns` "istenen" değil
  "gerçekten maskelenen" kolonları döndürüyor; admin bypass'ında boş kalıyor.
  Frontend de bunu doğru okuyor.
- **OWNER yönetişimi (Adım 20, `3.4.4`).** `ensure_active_owner` başlangıçta
  fail-closed; son aktif OWNER devre dışı bırakılamıyor; son DB ADMIN
  kaldırılamıyor; kendi hesabını devre dışı bırakma engelli; OWNER olmak sorgu
  yetkisi vermiyor. OQ-2026-011 kararı eksiksiz uygulanmış.
- **OWNER bootstrap.** Yalnız sunucu tarafı CLI; mevcut kullanıcının parolasını
  değiştirmiyor; `with_for_update` ile yarışa kapalı; audit yazıyor.
- **Redis giriş kısıtlaması (Adım 14, `2.4`).** Lua script'i Redis `TIME`
  kullanıyor (saat kayması yok), anahtarlar hash'li, `LoginThrottleUnavailable`
  fail-closed 503'e çevriliyor. OQ-2026-005/006 kararlarıyla uyumlu.
  *(Tek sorun kovanın anahtarı — bkz. P0-4; mekanizmanın kendisi doğru.)*
- **Oturum/refresh mimarisi (Adım 15, `2.3`).** Rotasyon, `prev_refresh_hash`
  grace penceresi (sekme yarışı için), `with_for_update`, cookie path
  daraltması ve legacy cookie temizliği — hepsi düşünülmüş.
- **Frontend tasarım sistemi.** Token'lar, kontrast denetimi (otomatik betik),
  `capability.ts`'teki "mod ≠ yetenek" ayrımı, `execution.ts`'teki tek noktadan
  mesaj ayrıştırma. Tip güvenliği tam; `typecheck` ve `build` temiz.
- **API sözleşme denetim betiği.** `scripts/api-contract-audit.mjs` frontend
  çağrılarını backend rotalarıyla eşleştiriyor ve arayüzsüz rotaları raporluyor —
  çoğu projede olmayan bir disiplin.
- **Alembic'e geçiş (Adım 1, `4.1`).** 9 revizyon, baseline + drift onarımı
  dâhil; `create_all()` üretim yolundan çıkarılmış; `entrypoint.sh` sırası doğru.
- **`print()` temizliği (Adım 21, `4.3`).** Üretim kodunda tek `print` kalmamış;
  `set_db_info` artık içerik değil özet logluyor.

---

## 5. Uygulama sırası (`webquery_implementasyon_sirasi.md`) uyum tablosu

| Adım | Madde | Durum | Not |
| --- | --- | --- | --- |
| 1 | `4.1` Alembic | ✅ | 9 revizyon; baseline + drift onarımı |
| 2 | `4.2` CI | ◐ | Var; ruff gate değil, frontend job yok (P2-16) |
| 3 | `0.1` config_guard | ✅ | `CONFIRMATION_SECRET` DML teyidiyle birlikte ertelendi |
| 4 | `0.4` `sa` varsayılanı | ◐ | Kodda kaldırılmış, `docker-compose.yml`'de duruyor (P1-12) |
| 5 | `0.2` Hata temizleme | ✅ | Admin önizleme yolu hariç (P2-20e) |
| 6 | `0.3` Sorgu zaman aşımı | ◐ | MSSQL'de muhtemelen etkisiz (P1-4) |
| 7 | `0.5` Blacklist temizliği | ◐ | Mekanizma atıl kaldı, tablo/kod duruyor (P2-12) |
| 8 | `4.4` `common/roles.py` | ✅ | Tek kaynak; `max_tier`/`granted_tier`/`effective_mode` ayrımı net |
| 9 | `1.1` AuditLog | ◐ | Altyapı tam; 4 action'ın çağrı noktası yok (P1-8, P1-9) |
| 10 | `1.2` Onay yarışı | ✅ | Koşullu UPDATE + conflict hatası |
| 11 | `1.3` Web/Slack birleştirme | ✅ | Tek `decide()`; Slack'te ADMIN aranıyor |
| 12 | `2.1` Kullanıcı devre dışı | ✅ | Middleware'de her istekte kontrol + oturum iptali |
| 13 | `2.2` Kaydı kapat | ✅ | Alan adı allowlist + aktivasyon bekleme |
| 14 | `2.4` Giriş kısıtlaması | ◐ | Mekanizma doğru, IP anahtarı proxy arkasında bozuk (P0-4) |
| 15 | `2.3` Refresh token | ✅ | Yeniden kullanımda aile iptali eksik (P2-13) |
| 16 | `3.1` Kademe credential | ◐ | Uygulandı; **yazma yolu commit edilmiyor** (P0-1), legacy fallback açık, rotasyon yok (P1-10) |
| 17 | `4.5` Ölü kod | ❌ | Büyük ölçüde yapılmamış (P2-12) |
| 18 | `3.3` sqlglot | ✅ | 30.14.0 |
| 19 | `3.2` Analizci sertleştirme | ✅ | Beş alt maddenin beşi de uygulanmış |
| 20 | `3.4` Hiyerarşi / DML / platform rolü | ◐ | OWNER tamamlandı; DML teyidi OQ-2026-010 ile bilinçli ertelendi (inbox) |
| 21 | `4.3` `print()` → logging | ✅ | Temiz |
| 22 | `4.6` Streaming | ❌ | Ertelendi — ama "opsiyonel" sınıfı yeniden değerlendirilmeli (P1-5) |

---

## 6. Frontend eksik arayüz envanteri

| Eksik yüzey | Backend hazır mı? | Etki | Öncelik |
| --- | --- | --- | --- |
| Kullanıcıya DB erişimi/rol verme | Evet (`POST /api/admin/associate_user`) | Aktive edilen kullanıcı hiçbir veritabanına erişemiyor | 🟠 P1-7 |
| Kullanıcı listesi (DB ADMIN için) | Hayır — yalnız OWNER ucu var | `user_id` bilinemiyor | 🟠 P1-7 |
| Erişim iptali | Hayır | İşten ayrılan için tek yol hesabı tamamen kapatmak | 🟠 P1-8 |
| Şifre değiştirme | Hayır | Sızmış şifre değiştirilemiyor | 🟠 P1-9 |
| Hedef DB güncelle/sil | Hayır | Credential rotasyonu imkânsız | 🟠 P1-10 |
| Audit log görüntüleyici | Evet (`GET /api/admin/audit_log`) | Denetim kaydı yalnız API'den okunabiliyor | 🟡 |
| Aktif oturumları görme/iptal | Kısmen (`revoke_user_sessions` var, uç yok) | Kullanıcı kendi oturumlarını yönetemiyor | 🟡 |
| Çoklu sorgu (`/api/multiple_query`) | Evet | Arayüzsüz, korumasız uç | 🟡 (P1-1 ile birlikte kaldırılabilir) |
| Workspace paylaşımı | Hayır (`owner_id`/`is_owner` alanları var, hep `true`) | Sözleşmede yer tutuyor, işlev yok | 🔵 |

---

## 7. Önerilen çalışma sırası

1. **P0-1** hedef transaction commit'i — inbox kaydı zaten hazır; regresyon
   testiyle birlikte.
2. **P0-2** bağlantı dizesi kaçışı — tek dosya, düşük risk, yüksek getiri.
3. **P0-4** proxy header — tek satırlık konfigürasyon; üç mekanizmayı birden
   düzeltiyor.
4. **P0-3** workspace durum makinesi — onay modelinin bütünlüğü buna bağlı.
5. **P1-3**, **P1-2**, **P1-1** — üç yetkilendirme/limit boşluğu, hepsi küçük.
6. **P1-7 + P1-8** erişim yönetimi (backend ucu + arayüz) — ürünü fiilen
   kullanılabilir yapan parça.
7. **P1-4** MSSQL timeout ölçümü, ardından **P1-5** streaming — birlikte
   değerlendirilmeli.
8. **P1-6** bcrypt'i thread'e taşı.
9. **P1-11 / P1-12 / P1-13** dağıtım sertleştirmesi tek bir turda.
10. **P2** kalemleri; **P2-12** (ölü kod) ve **P2-19** (README) en ucuz ikisi.

---

## 8. Genel değerlendirme

Mimari sağlam ve tutarlı: modül deseni her domainde aynı, tip anotasyonları
kapsamlı, DI temiz, kararların gerekçeleri kodun içine yazılmış, spec/ADR/inbox
disiplini çoğu projede görülmeyen düzeyde. Adım 19'daki analizci sertleştirmesi
ve Adım 20'deki OWNER yönetişimi özellikle iyi uygulanmış — kenar vakalar
(tırnaklı fonksiyon adı, son OWNER, son DB ADMIN, sekme yarışı) tek tek
düşünülmüş.

Kritik bulguların ortak noktası mimari değil, **yol sonu doğrulaması**:
kademeli credential mimarisi kuruldu ama yazma yolu commit edilmiyor;
giriş kısıtlaması doğru yazıldı ama IP kovası proxy arkasında ayrışmıyor;
onay akışı atomik yapıldı ama onaylanan metin sonradan değiştirilebiliyor;
erişim modeli tasarlandı ama erişimi verecek ekran yok. Dördü de "kod yanlış"
değil, "zincirin son halkası bağlanmamış" tipinde.

Sayısal özet: **4 P0**, **13 P1**, **20 P2 başlığı**, **19 doğrulanmış P3**.
P0'ların üçü ve P1'lerin çoğu tek dosyalık, dar kapsamlı düzeltmeler.

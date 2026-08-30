# Oturum Kaydı: Rol bazlı hedef DB credential'ları ve şema bütünlüğü

**Tarih:** 2026-08-28
**Branch:** `feature/security-hardening-implementation`
**Aralık:** `af30b98..aedfe32` — 3 commit, 46 dosya, +2493 / −333
**Durum:** Uygulandı, doğrulandı, push edildi

> Bu klasördeki diğer kayıtlar `HANDOFF-TEMPLATE.yaml` biçimindedir. Bu dosya
> bilinçli olarak anlatı biçiminde yazılmıştır: amacı devir teslim değil,
> 46 dosyalık diff'i inceleyecek kişiye her değişikliğin **neden** yapıldığını
> anlatmaktır. Karar kayıtları ilgili spec ve ADR'lerdedir; burası onları
> tekrar etmez, aralarındaki bağı kurar.

---

## 1. Özet

İki bağımsız iş yapıldı, üçüncü commit ikisinin ortaya çıkardığı belgeleri
kaydetti.

| Commit | Konu | Dosya |
| --- | --- | --- |
| `7056eb3` | Rol bazlı hedef DB credential'ları + etkin yetki rozeti | 35 |
| `bf23d8d` | Şema bütünlüğü guard'ı + drift onarımı | 8 |
| `aedfe32` | `.env.example` ve iki inbox notu | 3 |

İkinci iş birincinin yan ürünü olarak ortaya çıktı: geliştirme ortamı Docker
ile ayağa kaldırılırken uygulama açılmadı, kök neden araştırılınca Alembic
baseline'ının koşullu davranışının kalıcı bir şema boşluğu bıraktığı görüldü.

---

## 2. Commit `7056eb3` — Rol bazlı credential'lar ve etkin yetki rozeti

### 2.1 Neden

Runtime sorgu bağlantıları tüm hedef veritabanları ve tüm roller için tek bir
`CENTRAL_DB_USER` hesabını kullanıyordu. Uygulama katmanındaki rol kontrolü
atlanırsa, bağlantının arkasında hedef DB seviyesinde ikinci bir yetki sınırı
yoktu. Karar `OQ-2026-002`'de verildi, `ADR-0005` ve `SPEC-0002`'ye kaydedildi.

Bu commit iki katmanı içeriyor: credential modelinin kendisi (branch'te
başlamış olan iş) ve bu modelin arayüzde nasıl göründüğü (bu oturumda eklendi).

### 2.2 Veri modeli ve migration

**`web_api/app_database/models.py`** — `Databases` tablosuna altı kolon:
`username_ro/rw/ddl` ve `password_ro/rw/ddl`. Şifreler `EncryptedText`
(Fernet) ile saklanıyor. Eski `db_username`/`db_password` kolonları
kaldırılmadı; mevcut kurulumların geçişi tamamlanana kadar duruyor ve yeni
kayıtlar bunları hiç doldurmuyor.

**`migrations/versions/d7e9f0a1b2c3_add_target_db_tier_credentials.py`** —
altı kolonu ekliyor. Guard'lı: kolon zaten varsa atlıyor.

### 2.3 Kayıt akışı: bağlantı modu

`OQ-2026-007`'nin cevabı gereği admin yalnız üç hiyerarşik moddan birini
seçebiliyor: `ro`, `ro + rw`, `ro + rw + ddl`. `rw` veya `ddl` kendinden düşük
kademe olmadan tek başına tanımlanamıyor.

**`web_api/admin/schemas.py`** — `DatabaseAddRequest`'e `connection_mode` ve
altı credential alanı. `model_validator`, seçilen modun gerektirdiği her
kademe için kullanıcı adı **ve** şifreyi zorunlu tutuyor; seçilmeyen kademede
değer gönderilmesini de reddediyor. İkinci kural olmadan form, kaydedilmeyecek
bir credential'ı sessizce yutardı.

**`web_api/admin/services.py`** — `add_database` artık credential üretmiyor
(`generate_secure_credentials` çağrısı kaldırıldı); DBA'in sağladığı değerleri
kaydediyor. Cevaptan `db_username`/`db_password` çıkarıldı, yalnız `db_uuid`
dönüyor.

**`frontend/components/app/admin/MaskingTab.tsx`** — form bağlantı modu
seçici (`SegmentedControl`) ve moda göre görünen credential alanları kazandı.

**`frontend/components/app/admin/CredentialsDialog.tsx` — silindi.** Bu diyalog
WebQuery'nin ürettiği credential'ları admin'e bir kez gösteriyordu. Artık
credential üretilmediği için gösterilecek bir şey yok.

### 2.4 Çalışma zamanı: kademe seçimi

**`web_api/query_execution/query_analyzer.py`** — yeni `required_tier()`,
sorguyu `ro` / `rw` / `ddl` olarak sınıflandırıyor. Ayrıştırılamayan ifade
`ddl` alıyor, böylece çağıran güvenli tarafta fail-closed davranabiliyor. Bu
bir yetkilendirme kararı değil, yalnız hangi hesapla bağlanılacağının tespiti.

`check_role_permission` içinde ayrıca `DDL` rolü tanınır hale getirildi;
önceden DDL yalnız `ADMIN`'e bağlıydı.

**`web_api/database_provider/database.py`** — `get_session(..., tier="ro")`.
`_credentials_for()` ilgili kademeyi çözüyor; kademe tanımlı değilse `None`
dönüyor ve çağıran hata veriyor. Hiç kademe credential'ı olmayan (henüz
geçirilmemiş) kayıtlar için `ro`/`rw` isteklerinde merkezi hesaba geri dönüş
korunuyor — bu geçiş dönemine özel ve yorumda böyle işaretli.

`close_user_engines` artık no-op. Eskiden bir kullanıcının çıkışı, aynı hedef
veritabanını paylaşan başka bir kullanıcının aktif havuzunu da kapatıyordu;
havuzlar kullanıcıya değil hedef veritabanına ait.

**`web_api/database_provider/engine_cache.py`** — en büyük tek dosya
değişikliği (220 satır). Cache artık iki seviyeli: hedef DB uuid'si → kademe →
havuz. Böylece `ro` ve `rw` engine'leri birbirine karışmıyor.

Ek olarak her havuz `credential_fingerprint` taşıyor. Credential değişirse
parmak izi tutmaz, eski havuz `dispose` edilip yenisi kurulur. Bu olmadan
credential rotasyonu sessizce etkisiz kalırdı: eski bağlantı çalışmaya devam
eder, yenisi hiç denenmezdi.

Havuz boyutları kademe başına ayrıştırıldı: `ro` 10/20, `rw` 5/10, `ddl` 1/2.
**Bu, `OQ-2026-001`'in kayıtlı cevabıyla çelişiyor** — ayrıntı §5.2'de.

`close_database_engines(db_uuid)` eklendi: bir hedef veritabanının tüm kademe
havuzlarını kapatıyor. Kayıt güncelleme/silme akışı yazıldığında gerekli olacak
(bkz. `docs/inbox/DATABASE-REGISTRATION-LIFECYCLE.md`).

**`web_api/query_execution/services.py`**, **`web_api/workspaces/services.py`**,
**`web_api/admin/services.py`** — üç çağrı noktası da `required_tier` hesaplayıp
`get_session`'a geçiriyor.

### 2.5 Arayüz: tek veritabanı, etkin yetki rozeti

Bu bölüm bu oturumda eklendi. Sorun şuydu: `get_db_info` kademe credential'ları
taşıyor ve kademelerin arayüzde ayrı veritabanı gibi görünme riski vardı.

**Karar (`OQ-2026-008`):** hedef veritabanı arayüzde **tek kayıt**. Kullanıcı
kademe seçmiyor; kademeyi backend sorgudan türetiyor. Kullanıcı yalnız bir
yetki rozeti görüyor.

**`web_api/common/roles.py`** — dört yardımcı eklendi:

| Fonksiyon | İşi |
| --- | --- |
| `mode_from_credentials` | Hangi kademelerin saklandığından bağlantı modunu türetir |
| `granted_tier` | Rolün ulaşabileceği en yüksek kademe (`max_tier`'dan farkı: `ADMIN`'i `ddl` sayar, çünkü `check_role_permission` öyle davranıyor) |
| `effective_mode` | Kaydın modu ∩ kullanıcının rolü — ikisinden düşüğü |
| `exceeds_mode` | Rolün gerektirdiği ama kaydın sağlamadığı kademe |

**`web_api/app_database/app_database.py`** — `get_db_info` her veritabanı için
`connection_mode` de döndürüyor. Docstring'i güncellendi; eskisi hâlâ
"databases: [database_names]" diyordu, oysa uzun süredir sözlük döndürüyordu.

**`web_api/database_provider/database.py`** — `set_db_info` public kataloğa
`connection_mode`'u da koyuyor. Kritik ayrım korunuyor: `db_info` (API'ye
giden, credential'sız) ile `db_by_uuid` (runtime, credential'lı) ayrı.

**`web_api/query_execution/router.py`** — `/api/database_information` her kayıt
için `capability` döndürüyor. Association satırından `role` de okunuyor; bu
satır zaten çekiliyordu, yani **ek sorgu maliyeti yok**. Kaydın ham modu
response'a girmiyor.

Neden ham mod değil de kesişim: `ro_rw` bir veritabanı `READER` rolündeki
kullanıcıya "yazma" yeteneği vaat ederdi ve sorgu çalıştırıldığında rol
kontrolü reddederdi. `frontend/DESIGN.md` §9 aynı ilkeyi maskeleme rozeti için
zaten koyuyor: rozet niyetten değil, gerçekleşecek davranıştan beslenir.

**`frontend/lib/capability.ts`** (yeni) — etiketler tek yerde. İki ayrı harita
var ve bu bilinçli: `CONNECTION_MODE` admin yüzeyi için ("bu kayıt ne sunuyor"),
`CAPABILITY` editör için ("sen ne yapabilirsin"). Aynı enum iki farklı şey
anlatıyor; tek haritada birleştirmek ikisini karıştırırdı.

**`frontend/types.ts`, `frontend/lib/targets.ts`, `frontend/pages/Studio.tsx`** —
`capability` alanı tip zincirinden geçirildi; Studio hem seçicide hem seçili
hedefin yanında rozet gösteriyor (tooltip'li).

### 2.6 Yetki verme doğrulaması

**`web_api/admin/services.py` + `exceptions.py`** — `associate_user_to_database`
artık hedef veritabanında credential'ı tanımlı olmayan bir kademeyi gerektiren
rolü `400 ROLE_NOT_SUPPORTED_BY_DATABASE` ile reddediyor.

Neden gerekli: aksi halde yetki verme başarılı olur, o kademedeki her sorgu
sonradan fail-closed düşer ve hiçbir şey hatayı yetki verme anına geri bağlamaz.
Kullanıcıya "veritabanı bozuk" gibi görünür, oysa kayıt eksik.

`ADMIN` muaf: yönetişim rolü ve `add_database` onu her modda kaydı oluşturan
kişiye veriyor. Hiç kademe credential'ı olmayan eski kayıtlar da muaf.

### 2.7 Testler

| Dosya | Kapsam |
| --- | --- |
| `tests/unit/test_roles.py` | 8 yeni test — mod türetme, `ADMIN`→`ddl` farkı, kesişim, kaydın sağlamadığını aşmama |
| `tests/unit/test_database_add_request.py` | Bağlantı modu doğrulaması |
| `tests/integration/test_database_capability.py` | 5 test — rozet daraltması, credential'ın response'a sızmadığı, grant reddi ve kabulü |
| `tests/unit/test_engine_cache.py` | Kademe ayrımı, credential parmak izi |
| `tests/unit/test_database_provider_uuid.py` | Public kataloğun credential taşımadığı |

`test_advanced_security.py` şifreleme testi `db_password` yerine `password_ro`
üzerinden çalışacak şekilde güncellendi. Diğer entegrasyon testlerindeki
değişiklikler `get_session` imzasına `tier` eklenmesinin mekanik sonucu.

---

## 3. Commit `bf23d8d` — Şema bütünlüğü guard'ı ve drift onarımı

### 3.1 Kök neden

`ADR-0001` şema yönetimini Alembic'e taşıdı. Baseline revizyonu
(`5d2a9a282ea1`), Alembic'ten önce `Base.metadata.create_all()` ile kurulmuş
kurulumlarda tabloları yeniden oluşturmaya çalışıp patlamasın diye erken
dönüyor:

```python
if expected_tables.issubset(existing_tables):
    return
```

Guard doğru; tabloların yeniden oluşturulmasını engelliyor. Ancak baseline
yalnız tablo oluşturmuyor — **index'leri ve unique kısıtlarını da o oluşturuyor.**
Erken dönüş bunları da atlıyor ve sonraki hiçbir revizyon geri gelip
tamamlamıyor. Sonuç: çalışan ama sessizce eksik bir şema.

Projenin kendi geliştirme veritabanında ölçülen eksikler:

| Eksik | Sonucu |
| --- | --- |
| `uq_server_database` | Aynı `(servername, database_name)` çiftinin iki kez kaydedilmesine karşı tek gerçek garanti |
| `ix_Databases_uuid` | Her sorgu çalıştırması hedefi uuid ile çözüyor |
| `ix_ActionLogging_trace_id` | Slack onay akışının arama anahtarı |
| `ix_ActionLogging_database_id`, `ix_ActionLogging_approval_status` | Audit ve onay listelemeleri |
| `Databases.uuid` nullable | NULL uuid'li satır her API yüzeyinden erişilemez |
| `ActionLogging.approval_status` nullable | Denetim izinde anlamsız boşluk |

Ortak özellikleri: hata nedeninden çok uzakta görünür. Veritabanı aylarca
sorunsuz çalışır, sonra bir gün iki admin aynı hedefi kaydeder.

### 3.2 Üç parça

**`web_api/common/schema_contract.py`** (yeni, 194 satır) — 31 index, 3 unique
kısıt, 35 NOT NULL kolonun düz veri listesi ve `missing_objects(inspector)`.

Neden elle yazıldı: migration'lar model sınıflarını import etmiyor (baseline'daki
yorum bunu açıkça söylüyor — şema, migration'ın kendi tarifidir). Bu, listenin
modellerden sapması riskini doğuruyor; risk testle kapatıldı (§3.3).

**`migrations/versions/e4b1c7a09d52_repair_schema_drift.py`** (yeni, 180 satır) —
eksik olanı oluşturuyor. Migration'larla kurulmuş bir veritabanında hiçbir şey
yapmıyor. Üç adım, bu sırayla: NOT NULL onarımları → unique kısıtlar → index'ler.

NOT NULL onarımı yalnız değeri tartışmasız olan iki kolonu kapsıyor:
`Databases.uuid` (satır başına yeni kimlik; NULL uuid'yi hiçbir şey referans
edemez) ve `ActionLogging.approval_status` (model varsayılanı `AUTO_APPROVED`).
Diğer boşluklar guard'a bırakılıyor, çünkü değer uydurmak satırın ne anlama
geldiğini tahmin etmek olurdu.

Yinelenen kayıt yüzünden unique kısıt oluşturulamıyorsa migration **hata
veriyor**. Atlayıp başarı bildirmek, garantisi olmayan bir veritabanını
garantili gibi göstermek olurdu.

**`web_api/common/schema_guard.py`** (yeni) + **`web_api/app.py`** —
`verify_schema`, `entrypoint.sh` içindeki `alembic upgrade head` çalıştıktan
sonra, veritabanı bağlantısı doğrulanır doğrulanmaz çalışıyor. Eksik varsa
listesini yazıp `SystemExit(1)`.

`app.py`'deki çağrı mevcut `except Exception` bloğunun içinde ama `SystemExit`
bir `BaseException` olduğu için yakalanmadan geçiyor — yorumda bu belirtildi.

### 3.3 Sözleşme modellerden sapamıyor

`tests/unit/test_schema_contract.py`, listenin `Base.metadata` ile birebir aynı
olduğunu üç yönden doğruluyor (index, unique, NOT NULL). Modele index eklenip
sözleşmeye eklenmezse test kırılıyor. DRY'lik bağımlılıkla değil testle
sağlanıyor; migration'ların model-bağımsız kalması böyle korunuyor.

`tests/unit/test_schema_guard.py` guard'ın gerçekten durdurduğunu doğruluyor:
düşürülmüş index, kaldırılmış unique kısıt, nullable bırakılmış kolon.

### 3.4 Gerçek MSSQL'de çıkan iki davranış

Bunlar SQLite testlerinde görünmedi, yalnız gerçek veritabanında çalıştırınca
çıktı ve ikisi de koda yansıdı:

1. **MSSQL diyalekti `get_unique_constraints()` implemente etmiyor** —
   `NotImplementedError` fırlatıyor. Kısıtları `get_indexes()` üzerinden unique
   index olarak bildiriyor (`UQ__Users__AB6E6164...`). Kontrol ikisini de
   okuyor ve **isim yerine kolon kümesiyle** eşleştiriyor, çünkü adsız
   tanımlanan kısıtların adını veritabanı üretiyor.

2. **Hata 5074** — indexi olan kolon `ALTER COLUMN` edilemiyor. Onarım bağımlı
   index'leri düşürüp değişiklikten sonra yeniden oluşturuyor. Unique index'e
   rastlarsa hata veriyor: MSSQL'de bu bir unique kısıtın fiziksel biçimi
   olabilir, `DROP INDEX` onu kaldıramaz.

### 3.5 Gerçek ortamda doğrulama

Guard ilk açılışta **4 eksik** buldu ve uygulamayı durdurdu. Onarım revizyonu
üçünü kapattı; guard kalan `ActionLogging.approval_status`'u yakaladı, o da
onarıma eklendi. Sonuç: `EKSIK: yok`, `Şema doğrulandı: tüm index ve kısıtlar
mevcut`, `RestartCount=0`. Veri kaybı olmadı.

---

## 4. Commit `aedfe32` — `.env.example` ve inbox notları

**`.env.example`** — `QUERY_ENCRYPTION_KEY` bu dosyada **hiç yoktu**. Bu, bir
kök nedendi: `.env.example`'dan kopyalanan her kurulum config guard'ında
duruyordu. Kendi bölümüyle eklendi (değer boş).

Açıklamaya iki uyarı yazıldı, çünkü ikisi de pratikte yaşandı:
- Format `SECRET_KEY` ile aynı değil. `openssl rand -hex 32` çıktısı (64
  karakter hex) burada çalışmıyor; Fernet anahtarı 32 baytın base64url hâli,
  44 karakter, `=` ile biter.
- Anahtar değişirse eski kayıtlar çözülemez. `EncryptedText.process_result_value`
  çözemediği değeri hata fırlatmadan ham ciphertext olarak döndürüyor, yani
  uygulama çökmüyor ama o alanlar okunamıyor.

`SECRET_KEY` açıklaması da guard'ın gerçek kuralını söyleyecek şekilde
düzeltildi (en az 32 karakter; dosyadaki örnek değer reddediliyor).

**`docs/inbox/DATABASE-REGISTRATION-LIFECYCLE.md`** (yeni) — kayıtlı bir hedef
veritabanı eklendikten sonra güncellenemiyor ve silinemiyor. Credential
rotasyonu bu yüzden imkânsız: kayıt silinemediği için yeniden de eklenemiyor
(`add_database` `(servername, database_name)` çiftini benzersiz kabul ediyor).
Karar gerektiren dört nokta kayıtlı: silme sert mi yumuşak mı, kimlik alanları
değişebilir mi, mod daraltılırsa mevcut yetkiler ne olur, kısmi credential
güncellemesi.

**`docs/inbox/DATABASE-EXTERNAL-IDENTIFIER-UUID.md`** — bu oturumdan önce
yazılmıştı, takipsiz duruyordu; commit'lendi.

---

## 5. Doğrulama ve açık kalan konular

### 5.1 Çalıştırılan komutlar

| Komut | Sonuç |
| --- | --- |
| `pytest` (`web_api/` içinden) | **148 passed** |
| `npx tsc --noEmit` (`frontend/`) | temiz |
| `npm run build` (`frontend/`) | başarılı |
| `ruff check .` (`web_api/`) | 46 hata — hepsi dokunulmamış dosyalarda, §5.3 |
| Docker stack | `Application startup complete`, `RestartCount=0`, frontend 200 / API 401 |

Rozet davranışı gerçek stack üzerinde tarayıcıyla da doğrulandı: `ro_rw` bir
veritabanı `READER` kullanıcıya "Salt-okuma", `ro_rw_ddl` bir veritabanı
`WRITER` kullanıcıya "Okuma + yazma" gösterdi; `WRITER` yetkisi verildikten
sonra aynı liste rozeti güncelledi.

### 5.2 Kapatılmayan: engine havuzu ayarı `OQ-2026-001` ile çelişiyor

`OQ-2026-001`'in kayıtlı cevabı: *"Mevcut kod kaynak doğrudur; `EngineCache`
içindeki `pool_size=50` ve `max_overflow=100` ayarları belgelenmelidir"* ve
kaydedildiği yer `docs/adr/ADR-0003-engine-cache-lifecycle.md`.

İki sorun var:

1. **`ADR-0003` dosyası `docs/adr/` altında yok.** ADR numaraları 0001, 0002,
   0004… diye devam ediyor; 0003 eksik.
2. **Bu branch ayarları değiştirdi.** `engine_cache.py` artık kademe başına
   ayrı havuz kullanıyor: `ro` 10/20, `rw` 5/10, `ddl` 1/2. Yani 50/100 artık
   kod gerçeği değil.

`README.md:26` ise üçüncü bir değer iddia ediyor: *"It sets `pool_size=0` to
release idle server-side connections immediately."*

Üç kaynak üç farklı şey söylüyor. Kademe başına ayrım savunulabilir bir
tasarım — en yüksek yetkili hesabın en küçük havuza sahip olması mantıklı —
ama karar hiçbir yerde yazılı değil. Yeni bir ADR yazılıp `OQ-2026-001`
`Superseded` yapılmalı.

### 5.3 Kapatılmayan: 46 ruff hatası

Hepsi bu branch'te dokunulmamış dosyalarda, yani `HEAD`'den geliyor.
Dağılım: 25 `BLE001` (blind except), 8 `DTZ005` (tz'siz `datetime.now`),
6 `SIM117`, 3 `I001`, 1 `F401`, **3 `F821`**.

`F821` olanlar ciddi: `static_files/router.py:13,17,21` içinde
`get_current_user` tanımsız — bu dosya çalışma zamanında `NameError`
verebilir. Bu oturumda eklenen dosyaların hepsi `All checks passed`.

### 5.4 Kapatılmayan: kaybolan şifreleme anahtarı

Geliştirme veritabanındaki 3 workspace sorgusu ve 1 eski `db_password` eski
bir `QUERY_ENCRYPTION_KEY` ile şifrelenmişti. Anahtar `.env`'den kaybolmuş;
yenisi üretildiği için bu değerler artık çözülemiyor ve `gAAAAAB...` olarak
görünüyor. Uygulama çalışıyor. Eski anahtar bulunursa geri konarak
kurtarılabilir.

### 5.5 Kaydedilen kararlar

| Karar | Nerede |
| --- | --- |
| Rol bazlı credential modeli | `SPEC-0002`, `ADR-0005`, `OQ-2026-002` |
| Geçerli bağlantı modu kombinasyonları | `SPEC-0002` BR-06, `OQ-2026-007` |
| Tek kayıt + etkin yetki rozeti; grant kademe sınırı | `SPEC-0002` BR-07/08/09, `ADR-0005`, `OQ-2026-008` |
| Şema bütünlüğü guard'ı ve drift onarımı | `SPEC-0018`, `ADR-0015` |

### 5.6 Önerilen sıradaki adımlar

1. `ADR-0003` boşluğunu ve havuz ayarı çelişkisini kapatan ADR (§5.2).
2. `static_files/router.py` içindeki `F821` (§5.3).
3. `docs/inbox/DATABASE-REGISTRATION-LIFECYCLE.md` — dört açık soru sorulup
   kayıt güncelleme/silme akışı yazılmalı; `close_database_engines` bunun için
   hazır bekliyor.

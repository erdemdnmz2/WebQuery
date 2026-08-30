# Hedef veritabanı dış tanımlayıcısının UUID'ye taşınması

**Durum:** Inbox / uygulanacak iş
**Kaydedildi:** 2026-08-28
**Kapsam:** `web_api/admin/`, `web_api/workspaces/`, `web_api/app_database/models.py`,
`frontend/services/api.ts`, `frontend/types.ts`, `frontend/components/app/admin/`

Bu kayıt, kayıtlı hedef veritabanlarının API yüzeyinde hangi kimlikle
adreslendiği sorununu takip eder. Karar verilip uygulanana kadar mevcut davranış
korunur; bu dosya yalnızca sorunun, hedef durumun ve iş kalemlerinin kaydıdır.

## Sorun

Aynı varlığın (`Databases` satırı) dışarıya iki farklı kimliği veriliyor ve
üçüncü bir yerde de ham metin adı fiilen birincil anahtar gibi kullanılıyor:

| Yüzey | Kullanılan kimlik | Yer |
| --- | --- | --- |
| Kullanıcı API'si | `uuid` | `web_api/query_execution/router.py:130`, `web_api/query_execution/schemas.py` |
| Workspace API'si | `uuid` | `web_api/workspaces/schemas.py` |
| Admin API'si | integer PK `id` | `web_api/admin/router.py:163-186`, `:188`, `:200`, `:220`, `UserAssociationRequest.database_id` |
| `add_database` cevabı | `uuid` | `web_api/admin/router.py:153-157` |
| `QueryData` → `Databases` bağı | `(servername, database_name)` ham metin çifti | `web_api/admin/services.py:407-412`, `web_api/workspaces/services.py:138-140`, `:259-262`, `:307-314` |

Bunun üç somut sonucu var:

1. **Sözleşme kendi içinde tutarsız.** `POST /api/admin/add_database` cevabında
   `db_uuid` dönüyor (`frontend/types.ts` → `CreatedDatabase`) ama frontend bu
   değeri hiçbir admin çağrısında kullanamıyor; masking ve şema uçları integer
   `id` bekliyor. Ekleme sonrası listeyi yeniden çekip `id` bulmak zorunda.
2. **Integer PK dışarı sızıyor.** Sıralı ve tahmin edilebilir bir iç anahtar
   admin istemcisine veriliyor. Bugün bu bir zafiyet **değil** — her admin ucu
   `UserDatabaseAssociation` + `is_admin` kontrolü yapıyor
   (`web_api/admin/services.py:155-176`, `:180-191`, `:730-740`) — ama iç
   anahtarın dış yüzeyde görünmesi gereksiz ve tutarsız.
3. **Ham ad kimlik olarak kullanılıyor.** `QueryData` tablosunda hedef
   veritabanına FK yok; eşleşme `(servername, database_name)` metin çiftiyle
   yapılıyor. Bu, listedeki en kırılgan madde — ayrıntısı aşağıda.

## Kapsam dışı: ham adın gösterilmesi

`servername` ve `database_name` alanlarının admin cevaplarında yer alması
**doğru davranıştır ve değiştirilmeyecektir**:

- Admin bu değerleri zaten kendisi giriyor (`DatabaseAddRequest`).
- Masking kuralları hedef veritabanının gerçek tablo/kolon adları üzerinde
  tanımlanıyor; `discover_schema` gerçek isimlerle dönüyor.
- Admin'den veritabanı adını gizlemenin güvenlik kazancı yok, maliyeti
  kullanılamaz bir arayüz.

Bu iş kalemi **gösterilen veriyi değil, adreslemede kullanılan kimliği**
değiştirir.

## Hedef durum

- `Databases.uuid` sistemin tek dış tanımlayıcısı olur; integer `id` yalnız
  veritabanı içi ilişkilerde (FK'ler, audit `target_id`) kalır.
- Admin uçları `uuid` ile adreslenir, kullanıcı ve workspace yüzeyleriyle aynı
  kimliği paylaşır.
- `QueryData` hedef veritabanına gerçek bir FK ile bağlanır; ham ad kolonları
  yalnız tarihsel görüntüleme verisi olarak kalır.

## İş kalemleri

Sırasıyla uygulanmalı; her adım kendi başına teslim edilebilir.

### 1. Önkoşul: `Databases.uuid` üzerine UNIQUE constraint

`web_api/app_database/models.py:241` içinde `uuid` şu an
`nullable=False, index=True` — **unique değil**. Dış tanımlayıcı olacaksa
benzersizlik veritabanı seviyesinde garanti edilmeli.

- `UniqueConstraint("uuid", name="uq_databases_uuid")` ekle.
- Alembic migration yaz; migration öncesi mevcut veride çift `uuid` olup
  olmadığını kontrol eden bir adım koy.
- Bu adım tek başına geriye dönük uyumlu; API sözleşmesini değiştirmez.

### 2. Admin API'sinin dış tanımlayıcısını UUID'ye çevir

Backend:

- `DatabaseResponseSchema.id: int` → `uuid: str`
  (`web_api/admin/schemas.py`).
- Path parametreleri: `/api/admin/databases/{database_id}/discover_schema` ve
  `/api/admin/databases/{database_id}/masking_rules` (GET ve POST) →
  `{db_uuid}` (`web_api/admin/router.py:188-240`).
- `UserAssociationRequest.database_id: int` → `db_uuid: str`.
- Servis imzaları: `AdminService.discover_schema`, `get_all_masking_rules`,
  `save_masking_rules`, `associate_user_to_database` uuid alacak; içeride
  `Databases` satırını uuid ile çözüp yetki kontrolünü yine `db_entry.id`
  üzerinden yapmaya devam edecek.
- Bilinmeyen uuid için `404`, yetkisiz erişim için mevcut hata davranışı
  korunacak. Var olmayan uuid ile yetkisiz uuid arasındaki cevap farkının
  bilgi sızdırmadığını kontrol et.

Frontend:

- `RegisteredDatabase.id: number` → `uuid: string` (`frontend/types.ts:103-108`).
- `api.discoverSchema`, `api.databaseMaskingRules`, `api.saveMaskingRules`
  imzaları `databaseId: number` → `dbUuid: string`
  (`frontend/services/api.ts:270-278`).
- `api.associateUser` payload'ı `database_id` → `db_uuid`
  (`frontend/services/api.ts:279-283`). Bu fonksiyonun şu an çağıran bir
  bileşeni yok; değişim maliyeti düşük.
- `MaskingTab.tsx:96-97`, `:162`, `:330-332` — `database.id` yerine
  `database.uuid`; React `key` ve seçili kayıt karşılaştırması dahil.
- `CreatedDatabase.db_uuid` artık doğrudan kullanılabilir hale gelir: ekleme
  sonrası listeyi yeniden çekmeden yeni veritabanını seçili yapmak mümkün olur.

### 3. Audit `target_id` kararı

`AuditLog` kayıtları hedef veritabanı için integer `database.id` yazıyor
(`web_api/admin/services.py:597`, `:305`). Audit iç kayıt olduğu için integer
kalabilir, ancak `GET /api/admin/audit_log?target_id=` filtresi dışarıya açık.
UI elinde uuid tutarken bu filtrenin ne kabul edeceğine karar verilmeli:

- **A:** `target_id` integer kalır, UI filtrelemeden önce uuid → id çevirir.
- **B:** Veritabanı hedefli audit kayıtları uuid yazar; geçmiş kayıtlar integer
  kaldığı için filtre iki formatı da kabul eder.

Karar spec'e yazılmalı; sessizce seçilmemeli.

### 4. `QueryData` → `Databases` bağının FK'ye taşınması

**Bu madde listedeki en yüksek değerli iştir ve 2. maddeden bağımsız olarak da
yapılabilir.**

Mevcut durumda `QueryData` hedef veritabanına FK ile bağlı değil
(`web_api/app_database/models.py:183-198`); eşleşme her seferinde
`(servername, database_name)` metin çiftiyle yapılıyor. Bunun sonuçları:

- Bir veritabanının adı veya sunucusu değişirse ilgili tüm workspace'ler
  sessizce öksüz kalır. `web_api/workspaces/services.py:140` ve `:262` bu
  durumda `db_uuid = ""` döndürür — hata değil, boş değer.
- `QueryData.servername` ve `QueryData.database_name` `String(50)` iken
  `Databases.servername` ve `Databases.database_name` `String(100)`. 50
  karakteri aşan bir ad `QueryData` tarafında kırpılır ve eşleşme hiçbir zaman
  tutmaz.
- Her workspace listelemesi tüm `Databases` tablosunu çekip bellekte map kuruyor
  (`web_api/workspaces/services.py:138-140`).

Yapılacak:

- `QueryData.database_id = Column(Integer, ForeignKey("Databases.id"), nullable=True)`
  ekle (yeni kayıtlar için doldur, eskiler için geriye dönük backfill).
- Backfill migration: mevcut satırları `(servername, database_name)` ile eşle;
  eşleşmeyen satırları raporla, sessizce atlama.
- Çözümleme noktalarını FK'ye taşı: `web_api/admin/services.py:407-412`,
  `web_api/workspaces/services.py:138-140`, `:259-262`, `:307-314`.
- Ham ad kolonları silinmez; sorgunun çalıştığı andaki hedefi gösteren tarihsel
  kayıt olarak kalır.
- Backfill tamamlanıp doğrulandıktan sonra ayrı bir adımda `nullable=False`
  yapılabilir.

## Riskler ve dikkat noktaları

- **Kırıcı API değişikliği.** 2. madde admin sözleşmesini değiştirir; frontend
  ile aynı sürümde teslim edilmeli.
- **Mevcut branch'e karıştırma.** `feature/security-hardening-implementation`
  branch'i role-based credential çalışması ve kendi migration'ını taşıyor. Bu
  iş ayrı branch'te yapılmalı; aksi halde inceleme yüzeyi gereksiz büyür.
- **Test yüzeyi.** Etkilenen dosyalar: `web_api/tests/integration/test_admin_api.py`,
  `test_admin_auth.py`, `test_advanced_security.py`,
  `web_api/tests/unit/test_audit_log.py`, `test_database_provider_uuid.py`.
- **MSSQL `UNIQUEIDENTIFIER` tipi.** ORM `uuid.UUID` nesnesi döndürüyor, istek
  gövdesinden string geliyor. `DatabaseProvider.set_db_info` bunu `str()` ile
  normalize ediyor (`web_api/database_provider/database.py:54`). Yeni
  karşılaştırma noktalarında aynı normalizasyon unutulmamalı.

## Teslim kontrolü

Bu iş uygulanmaya başlandığında:

- Önce `docs/open-questions.md` içine dış tanımlayıcı kararı (integer PK mı,
  uuid mi) `Open` statüsüyle eklenir ve kullanıcıya sorulur.
- Karar sonrası `docs/specs/` altında API sözleşmesi değişikliğini tarif eden
  bir spec yazılır (`SPEC-TEMPLATE.md` esas alınır).
- Kalıcı bir mimari tercih olduğu için `docs/adr/` altında ADR açılır
  (`ADR-TEMPLATE.md` esas alınır); audit `target_id` kararı da burada kayda
  geçer.
- Her madde için normal ve hata yolu testleri eklenir; yetki kontrolünün uuid'ye
  geçişte zayıflamadığı ayrıca test edilir.
- Backend testleri `web_api/` dizininden `pytest` ile çalıştırılır.
- Frontend için `frontend/` dizininden `npm run build` çalıştırılır.

# Hedef veritabanı kaydının yaşam döngüsü: güncelleme ve silme

**Durum:** Kapandı (2026-08-30). Dört iş kaleminin hepsi uygulandı:
`PATCH`/`DELETE /api/owner/databases/{id}`, yumuşak silme ve audit
action'ları. Yürürlükteki sözleşme
`docs/specs/SPEC-0027-target-database-lifecycle.md` ve
`docs/adr/ADR-0021-target-database-soft-delete.md` içinde; bu dosya
sorunun ve alınan kararların kaydı olarak duruyor.
**Kapanmadan önceki durum:** Inbox / uygulanacak iş
**Kaydedildi:** 2026-08-28
**Kapsam:** `web_api/admin/router.py`, `web_api/admin/services.py`,
`web_api/admin/schemas.py`, `web_api/database_provider/`,
`frontend/components/app/admin/MaskingTab.tsx`, `frontend/services/api.ts`

Bu kayıt, kayıtlı bir hedef veritabanının **eklendikten sonra** yönetilememesi
sorununu takip eder. Karar verilip uygulanana kadar mevcut davranış korunur;
bu dosya yalnızca sorunun, hedef durumun ve iş kalemlerinin kaydıdır.

## Sorun

Admin API'si hedef veritabanı kaydı için yalnızca **ekleme** ve **okuma**
sağlıyor. Kayıt bir kez oluştuktan sonra üzerinde hiçbir işlem yapılamıyor:

| İşlem | Uç nokta | Durum |
| --- | --- | --- |
| Ekle | `POST /api/admin/add_database` | Var (`web_api/admin/router.py:127`) |
| Listele | `GET /api/admin/databases` | Var (`web_api/admin/router.py:163`) |
| Şema tara | `GET /api/admin/databases/{id}/discover_schema` | Var |
| Masking kuralları | `.../masking_rules` GET + POST | Var |
| **Güncelle** | — | **Yok** |
| **Sil** | — | **Yok** |

Bunun somut sonuçları:

1. **Credential rotasyonu imkânsız.** DBA hedef sunucuda `app_rw` şifresini
   değiştirdiğinde WebQuery'de karşılığını güncellemenin yolu yok. Kayıt
   silinemediği için yeniden de eklenemez: `add_database`
   `(servername, database_name)` çiftini benzersiz kabul edip
   `DatabaseAlreadyExistsError` fırlatıyor (`web_api/admin/services.py:571-576`).
   Tek çıkış yolu veritabanına elle müdahale.
2. **Bağlantı modu genişletilemiyor.** `ro` olarak kaydedilmiş bir veritabanına
   sonradan `rw` hesabı eklenemiyor. SPEC-0002 BR-09 gereği bu kayıttaki bir
   kullanıcıya `WRITER` yetkisi de verilemediği için, kayıt kalıcı olarak
   salt-okuma kalıyor.
3. **Yanlış kayıt kalıcı.** Sunucu adı hatalı girilmiş bir kayıt sistemde
   kalıyor ve kullanıcı listelerinde görünmeye devam ediyor.

## Neden şimdi yapılmadı

`feature/security-hardening-implementation` branch'i rol bazlı credential
çalışmasını taşıyor. Silme ve güncelleme **yeni API yüzeyidir** ve kendi
güvenlik kararlarını gerektirir (aşağıdaki açık sorulara bakınız); mevcut
branch'e eklenmesi inceleme yüzeyini gereksiz büyütür.

## Hedef durum

- Admin, kayıtlı bir hedef veritabanının credential'larını ve bağlantı modunu
  güncelleyebilir.
- Admin, artık kullanılmayan bir kaydı, bağlı verinin ne olacağı açıkça
  tanımlanmış bir kuralla kaldırabilir.
- Her iki işlem de audit'e yazılır ve önbellekteki bağlantı havuzlarını
  geçersiz kılar.

## Karar gerektiren noktalar

Uygulamadan **önce** `docs/open-questions.md` içine `Open` statüsüyle eklenip
kullanıcıya sorulmalı. Sessizce seçilmemeli.

### S1: Silme sert mi, yumuşak mı?

`Databases.id` üç yerden FK ile referans alınıyor:

| Tablo | Kolon | Nullable | Yer |
| --- | --- | --- | --- |
| `ActionLogging` | `database_id` | evet | `web_api/app_database/models.py:167` |
| `UserDatabaseAssociation` | `database_id` | hayır (PK parçası) | `:255` |
| `MaskingRule` | `database_id` | hayır | `:266` |

Ayrıca `QueryData` hedef veritabanına FK ile bağlı **değil**; eşleşme
`(servername, database_name)` metin çiftiyle yapılıyor (bkz.
`DATABASE-EXTERNAL-IDENTIFIER-UUID.md`, 4. madde). Sert silmede bu satırlar
sessizce öksüz kalır.

- **A — Yumuşak silme (`is_active = False`).** Audit ve sorgu geçmişi bozulmaz.
  Listeleme uçlarının ve `get_db_info`'nun pasif kayıtları dışlaması gerekir;
  `add_database`'in benzersizlik kontrolünün pasif kaydı nasıl sayacağına da
  karar verilmeli.
- **B — Sert silme + cascade.** `MaskingRule` ve `UserDatabaseAssociation`
  satırları silinir, `ActionLogging.database_id` `NULL`'a çekilir. Denetim izi
  hangi veritabanına ait olduğunu kaybeder.

Audit gerekliliği olan bir üründe A varsayılan tercih gibi görünüyor, ancak
karar kullanıcıya ait.

### S2: Güncelleme kimliği değiştirebilir mi?

`servername` ve `database_name` değişirse `QueryData` metin eşleşmesi kopar ve
mevcut workspace'ler `db_uuid = ""` döndürmeye başlar
(`web_api/workspaces/services.py:140`, `:262`). Güncelleme yalnız credential ve
bağlantı moduyla mı sınırlı olmalı, yoksa kimlik alanları da değişebilmeli mi?

### S3: Bağlantı modu daraltılırsa mevcut yetkiler ne olur?

`ro + rw` bir kayıt `ro`'ya çekilirse, o veritabanında `WRITER` yetkisi olan
kullanıcıların association'ları SPEC-0002 BR-09 ile çelişir hale gelir. İstek
reddedilmeli mi, yetkiler otomatik düşürülmeli mi, yoksa admin'e liste
gösterilip onay mı istenmeli?

### S4: Kısmi credential güncellemesi

Admin yalnız `rw` şifresini değiştirmek istediğinde tüm kademeleri yeniden
girmek zorunda mı kalmalı? Kısmi güncelleme (`PATCH`) izin verilirse,
gönderilmeyen alanın "değiştirme" mi "temizle" mi anlamına geldiği şemada
açıkça ayrılmalı — `None` iki anlama gelemez.

## İş kalemleri

Kararlar alındıktan sonra sırasıyla uygulanmalı.

### 1. Spec ve ADR

- SPEC-0002'ye kayıt yaşam döngüsü bölümü eklenir veya ayrı bir spec açılır.
- Silme semantiği kalıcı bir veri modeli kararı olduğu için ADR gerekir
  (`docs/adr/ADR-TEMPLATE.md`). ADR-0005'in "Credential rotasyonu için ileride
  ayrı bir operasyonel akış tasarlanmalıdır" sonucu bu işle kapanır.

### 2. Güncelleme ucu

- `PUT` veya `PATCH /api/admin/databases/{id}` + `DatabaseUpdateRequest`.
  Doğrulama `DatabaseAddRequest.validate_credentials_for_mode` ile aynı
  hiyerarşik kuralı paylaşmalı (`web_api/admin/schemas.py:86-113`) — kural iki
  yerde ayrı yazılmamalı.
- Şifre alanı boş bırakıldığında mevcut değerin korunması (S4 kararına bağlı).
- Kayıt değiştikten sonra **önbellek geçersiz kılınmalı**: `DatabaseProvider`
  üzerinde `close_database_engines(db_uuid)` zaten var
  (`web_api/database_provider/database.py:163`,
  `web_api/database_provider/engine_cache.py:169`). Bu çağrılmazsa eski
  credential ile açılmış havuzlar kullanılmaya devam eder — sessiz ve teşhisi
  zor bir hata.
- Ardından `set_db_info` yeniden yüklenmeli (`add_database` bunu zaten yapıyor,
  `web_api/admin/services.py:603-605`).

### 3. Silme ucu

- `DELETE /api/admin/databases/{id}`, S1 kararına göre yumuşak veya sert.
- Bağlı kayıtların ne olacağı testle sabitlenmeli; sessiz öksüz satır kalmamalı.
- Silme sonrası `close_database_engines` + `set_db_info` yenilemesi.

### 4. Audit

- `AuditAction` içine kayıt güncelleme ve silme eylemleri eklenir
  (`web_api/common/audit_actions.py`). Mevcut ekleme eylemiyle aynı desende.
- Credential değeri audit detayına **yazılmaz**; yalnız hangi kademelerin
  değiştiği kaydedilir. SPEC-0002 §7 bu kısıtı zaten koyuyor.

### 5. Frontend

- `MaskingTab.tsx` içindeki kayıt listesine satır bazlı düzenle/sil işlemleri.
  Kayıt formu ve güncelleme formu aynı doğrulama mantığını paylaşmalı; şu an
  form durumu ve `disabled` koşulu bileşenin içinde satır içi duruyor
  (`frontend/components/app/admin/MaskingTab.tsx:118-145`, `:290-300`).
- Silme yıkıcı bir işlem olduğu için onay diyaloğu gerekir; `Dialog` bileşeni
  mevcut. Bağlı masking kuralı ve yetki sayısı onay ekranında gösterilmeli.
- `api.ts` içine `updateDatabase` ve `deleteDatabase`.

## Riskler ve dikkat noktaları

- **Önbellek tutarlılığı en büyük risk.** Credential güncellenip havuz
  kapatılmazsa hata sessizdir: eski bağlantı çalışmaya devam eder, yenisi
  hiç denenmez. Bu davranış testle sabitlenmeli.
- **Yetki kontrolü.** Yeni uçlar mevcut admin desenini izlemeli:
  `UserDatabaseAssociation` + `is_admin` kontrolü, o veritabanı için
  (`web_api/admin/services.py:155-176`). Global admin varsayımı yapılmamalı.
- **Kimlik değişikliği.** Bu iş `DATABASE-EXTERNAL-IDENTIFIER-UUID.md` ile
  aynı uçları değiştiriyor. İkisi aynı anda yapılırsa çakışır; önce kimlik
  işinin bitirilmesi tercih edilmeli, aksi halde güncelleme/silme uçları önce
  integer `id` ile yazılıp sonra tekrar değiştirilecek.
- **Test yüzeyi.** `web_api/tests/integration/test_admin_api.py`,
  `test_database_capability.py`, `web_api/tests/unit/test_engine_cache.py`.

## Teslim kontrolü

- S1–S4 `docs/open-questions.md` içine `Open` olarak eklenip soruldu mu?
- Spec ve ADR yazıldı mı?
- Her uç için normal, yetkisiz ve bulunamadı yolları test edildi mi?
- Credential güncellemesinden sonra eski havuzun kullanılmadığı test edildi mi?
- Backend testleri `web_api/` dizininden `pytest` ile çalıştırıldı mı?
- Frontend için `frontend/` dizininden `npm run build` çalıştırıldı mı?

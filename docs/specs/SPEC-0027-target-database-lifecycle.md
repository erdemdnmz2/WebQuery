# Mini-Spec: Hedef veritabanı kaydının yaşam döngüsü

## 1. Spec Kartı

- Özellik: Kayıtlı hedef veritabanlarının güncellenmesi, kimlik değişikliği,
  bağlantı modu daraltması ve yumuşak silme
- Durum: Implemented
- Versiyon: 2026-08-30
- Tarih: 2026-08-30
- Sahip: WebQuery platform ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Bir hedef veritabanı kaydedildikten sonra **hiçbir şekilde değiştirilemiyor
ve kaldırılamıyordu**. Somut sonucu: hedef DB'nin DBA'i bir parolayı
döndürdüğünde WebQuery'nin kaydını güncellemenin tek yolu metadata
veritabanını elle düzenlemekti. Yani credential rotasyonu, güvenlik
uygulamasının kendisi tarafından imkânsız kılınıyordu.

### Başarı Sinyali

- OWNER, bir kaydın herhangi bir kademesinin parolasını, diğer kademelerin
  parolalarını yeniden girmek zorunda kalmadan döndürebilir.
- Rotasyondan hemen sonra çalışan bir sorgu yeni credential'ı kullanır.
- Bir kayıt kaldırıldığında hiçbir audit satırı, sorgu geçmişi ya da kayıtlı
  workspace öksüz kalmaz.
- Sunucu/veritabanı adı değiştiğinde kayıtlı workspace'ler çalışmaya devam
  eder.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `PATCH /api/owner/databases/{id}` — kısmi güncelleme.
- `DELETE /api/owner/databases/{id}` — yumuşak silme (emeklilik).
- `Databases.is_active` / `retired_at` / `retired_by` sütunları
  (migration `b2c3d4e5f6a7`).
- Emekli bir `(servername, database_name)` çiftinin yeniden kaydedilmesinde
  mevcut satırın yeniden etkinleştirilmesi.
- Kimlik değişikliğinde eşleşen `QueryData` satırlarının aynı transaction
  içinde taşınması.
- Bağlantı modu daraltmasının, çakışan yetki varken reddedilmesi.
- Listeleme ve çalıştırma yollarının emekli kaydı doğru ele alması.

### Kapsam Dışı

- `QueryData` ↔ `Databases` bağının metin çiftinden yabancı anahtara
  taşınması. Bu ayrı bir iş olarak izleniyor
  (`docs/inbox/DATABASE-EXTERNAL-IDENTIFIER-UUID.md`); bu spec mevcut metin
  eşleşmesiyle çalışır ve onun kırılganlığını açıkça telafi eder.
- Emekli bir kaydın kalıcı olarak silinmesi (hard delete). Desteklenmiyor.

## 4. Sözleşme

### `PATCH /api/owner/databases/{database_id}`

Yetki: platform OWNER.

Gövde (`OwnerDatabaseUpdate`, `extra="forbid"`, en az bir alan zorunlu):

```json
{
  "servername": "string | null",
  "database_name": "string | null",
  "connection_mode": "ro | ro_rw | ro_rw_ddl | null",
  "username_ro": "string | null", "password_ro": "string | null",
  "username_rw": "string | null", "password_rw": "string | null",
  "username_ddl": "string | null", "password_ddl": "string | null"
}
```

Yanıtlar:

| Durum | Anlamı |
| --- | --- |
| `200` | Güncellendi |
| `404` | Kayıt yok veya emekli |
| `409` | Bağlantı modu daraltması mevcut yetkilerle çakışıyor; gövdede çakışan kullanıcı/rol listesi döner |
| `409` | Yeni kimlik (`servername`, `database_name`) başka bir kayıtta kullanılıyor |
| `422` | Bilinmeyen alan veya boş gövde |

### `DELETE /api/owner/databases/{database_id}`

Yetki: platform OWNER. Kaydı emekliye ayırır (`is_active=False`), hiçbir
veriyi silmez, `AuditAction.REMOVE_DATABASE` yazar. Zaten emekli bir kayıt
için `404` döner.

## 5. İş Kuralları

### BR-01: Silme yumuşaktır (OQ-2026-016)

`Databases.id` üç tablodan referans alınıyor ve `QueryData` hedefe
`(servername, database_name)` metin çiftiyle bağlı. Sert silme, audit ve
sorgu geçmişini öksüz bırakır. `DELETE` yalnız `is_active=False`,
`retired_at`, `retired_by` yazar.

### BR-02: Emekli kayıt çalışma zamanında yoktur

`get_db_info()` yalnız `is_active=True` kayıtları döndürür, dolayısıyla
emekli bir kayıt runtime kataloğunda yer almaz ve her çalıştırma yolu ona
karşı fail-closed davranır. Listeleme uçları ve workspace çözümlemesi de
emekli kaydı canlı bir hedefmiş gibi göstermez: `db_uuid` boş döner.

### BR-03: Yeniden kayıt, emekli satırı diriltir

Aynı `(servername, database_name)` için yeni bir kayıt isteği geldiğinde
emekli satır yeniden etkinleştirilir (`is_active=True`, `retired_at=None`,
`retired_by=None`) ve credential'ları güncellenir. Yeni bir satır
oluşturulmaz; böylece geçmiş kayıtlar bağlı kalır.

### BR-04: Kimlik değişebilir, `QueryData` onunla taşınır (OQ-2026-017)

`servername` veya `database_name` değişirse, eski çifti taşıyan tüm
`QueryData` satırları **aynı transaction içinde** yeni çifte taşınır.
Taşınmazsa mevcut workspace'ler `db_uuid=""` döndürür ve çalıştırılamaz
hâle gelir.

### BR-05: Kimlik çakışması reddedilir

Yeni kimlik başka bir kayıtta kullanılıyorsa istek `409` ile reddedilir.
Kontrol, atamadan **önce** yapılır: yeni adı önce yazmak, autoflush'ın
unique kısıta çarpmasına ve bu ucun kendi cevabı yerine bir sürücü
`IntegrityError`'ının yüzeye çıkmasına yol açardı.

### BR-06: Mod daraltması sessizce yetki düşürmez (OQ-2026-018)

`ro_rw` bir kayıt `ro`'ya çekilmek istendiğinde, o veritabanında `WRITER`
(veya `ro_rw_ddl` → `ro_rw` için `DDL`) yetkisi olan kullanıcılar varsa
istek `409` ile reddedilir ve çakışan kullanıcı/rol listesi yanıtta döner.
Admin önce yetkileri düşürür, sonra modu daraltır. Otomatik düşürme,
admin'in fark etmediği bir yetki kaybı üretirdi.

`ADMIN` bu kontrolden muaftır: kayıt yönetim rolüdür ve `add_database` onu
kademe bağımsız olarak verir.

### BR-07: Güncelleme `PATCH` semantiğindedir (OQ-2026-019)

Gönderilmeyen alan değişmez. WebQuery saklanan parolaları hiçbir listeleme
ucunda geri döndürmediğinden (SPEC-0002 §7), tam gövde semantiği admin'i tek
bir parolayı döndürmek için DBA'den diğer tüm parolaları istemeye zorlardı.
Bir kademeyi tamamen kaldırmak, `connection_mode` daraltmasıyla yapılır —
böylece eksik alan tek anlama gelir.

### BR-08: Rotasyon havuzları geçersiz kılar

Bir kaydın credential'ı değiştiğinde o veritabanının engine'leri kapatılır.
Aksi hâlde cache'teki engine TTL'i dolana kadar eski parolayla bağlanmaya
devam eder ve rotasyon sessizce etkisiz kalır.

### BR-09: Credential değerleri denetim kaydına yazılmaz

`UPDATE_DATABASE` audit satırı, **hangi kademelerin** değiştiğini kaydeder;
neye değiştiğini değil (SPEC-0002 §7).

## 6. Acceptance Criteria

- AC-01: Given `ro_rw` modunda bir kayıt, when yalnız `password_rw`
  gönderilir, then diğer kademelerin credential'ları değişmez ve audit
  satırı `updated_tiers=["rw"]` yazar.
- AC-02: Given bir credential güncellemesi, when işlem tamamlanır, then o
  veritabanının cache'lenmiş engine'leri kapatılmıştır.
- AC-03: Given `ro_rw` bir kayıt ve o veritabanında `WRITER` rolü olan bir
  kullanıcı, when `connection_mode` `ro`'ya çekilmek istenir, then `409`
  döner ve yanıt o kullanıcıyı listeler; kayıt değişmez.
- AC-04: Given aynı kayıt ve `WRITER` yetkisinin `READER`'a düşürülmesi,
  when mod `ro`'ya çekilir, then istek başarılı olur ve `rw` credential'ları
  temizlenir.
- AC-05: Given bir kayıt ve ona bağlı bir workspace, when `servername`
  değiştirilir, then workspace hâlâ geçerli bir `db_uuid` döndürür.
- AC-06: Given başka bir kayıtta kullanılan bir `(servername,
  database_name)` çifti, when kimlik o çifte değiştirilmek istenir, then
  `409` döner ve hiçbir `QueryData` satırı taşınmaz.
- AC-07: Given aktif bir kayıt, when `DELETE` çağrılır, then `is_active`
  `False` olur, `retired_at`/`retired_by` dolar, hiçbir satır silinmez ve
  `REMOVE_DATABASE` audit satırı yazılır.
- AC-08: Given emekli bir kayıt, when `GET /api/database_information`
  çağrılır, then kayıt listede yer almaz.
- AC-09: Given emekli bir kayda bağlı bir workspace, when çalıştırılmak
  istenir, then istek reddedilir.
- AC-10: Given emekli bir kayıt, when aynı `(servername, database_name)`
  yeniden kaydedilir, then mevcut satır yeniden etkinleşir ve `id`
  değişmez.
- AC-11: Given OWNER olmayan bir kullanıcı, when bu uçlar çağrılır, then
  `403` döner.

Testler: `web_api/tests/integration/test_database_lifecycle.py`,
`web_api/tests/integration/test_owner_governance.py`,
`web_api/tests/unit/test_roles.py` (`exceeds_mode`).

## 7. Teknik ve Güvenlik Kısıtları

- Kayıt satırı `with_for_update()` ile kilitlenir; eşzamanlı iki güncelleme
  birbirinin üstüne yazamaz.
- Kimlik değişikliği ve `QueryData` taşıması tek transaction'dadır: ikisi
  birlikte olur ya da hiçbiri olmaz.
- Bu uçların tamamı platform OWNER yetkisi ister (ADR-0017).
- `exceeds_mode`, aşılan **en yüksek** kademeyi döndürür; çakışma listesi
  admin'in gerçekten kaldırması gereken yetkiyi göstermek zorundadır.

## 8. Open Questions

- OQ-2026-016: Yanıtlandı — yumuşak silme.
- OQ-2026-017: Yanıtlandı — kimlik değişebilir, `QueryData` taşınır.
- OQ-2026-018: Yanıtlandı — mod daraltması `409` ile reddedilir.
- OQ-2026-019: Yanıtlandı — `PATCH` semantiği.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (ADR-0021)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

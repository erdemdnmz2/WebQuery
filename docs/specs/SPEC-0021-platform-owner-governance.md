# SPEC-0021: Kalıcı Platform OWNER Yönetişimi

## 1. Spec Kartı

- Özellik: Kalıcı OWNER rolü ve platform yönetim modülü
- Durum: Implemented
- Versiyon: 1.0.0
- Tarih: 2026-08-29
- Sahip: WebQuery

## 2. Amaç ve Başarı Sinyali

### Amaç

Platform kapsamlı kullanıcı yaşam döngüsü, hedef veritabanı kaydı ve ilk DB
ADMIN atamasını herhangi bir veritabanının `ADMIN` rolünden ve deployment
ortam değişkeninden ayırarak kalıcı, denetlenebilir bir OWNER sınırına taşımak.

### Başarı Sinyali

- Veritabanı ADMIN'i platform kullanıcısı etkinleştiremez/devre dışı bırakamaz
  ve hedef veritabanı kaydedemez.
- OWNER platform yönetim API ve arayüzünü kullanabilir; OWNER olmayan kullanıcı
  aynı endpoint'lerden `403` alır.
- İlk OWNER yalnız sunucu tarafı bootstrap komutuyla oluşturulur veya mevcut
  kullanıcıya verilir.
- Yeni hedef veritabanı ve ilk DB ADMIN ataması aynı transaction'da oluşur.
- OWNER olmak tek başına sorgu çalıştırma veya sorgu onaylama yetkisi vermez.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `Users.is_platform_owner` kalıcı alanı ve Alembic migration'ı.
- En az bir aktif OWNER bulunmasını doğrulayan startup guard.
- Mevcut kullanıcıyı OWNER yapan veya ilk kullanıcıyı güvenli parola istemiyle
  oluşturan sunucu tarafı bootstrap komutu.
- Ayrı `owner/` backend domain modülü, `/api/owner/*` endpoint'leri ve OWNER
  dependency'si.
- Kullanıcı listeleme, etkinleştirme/devre dışı bırakma.
- Hedef veritabanı kaydıyla birlikte zorunlu ilk DB ADMIN ataması.
- Bir hedef veritabanına ek DB ADMIN atama ve DB ADMIN yetkisini geri alma.
- `/api/me` ve yönetim arayüzünde OWNER görünürlüğü.
- Tüm OWNER durum değişikliklerinin audit edilmesi.

### Kapsam Dışı

- Etkilenecek satır sayısını önceden hesaplama veya genel yıkıcı DML teyidi.
- OWNER'ın başka bir kullanıcıya uygulama API/UI üzerinden OWNER yetkisi
  vermesi; OWNER değişikliği yalnız bootstrap CLI ile yapılır.
- OWNER'a otomatik `READER`, `WRITER`, `DDL` veya DB `ADMIN` yetkisi verilmesi.
- OWNER'ın DB sorgularını görmesi, önizlemesi ya da onaylaması.
- Hedef veritabanı kaydını silme/soft-delete yaşam döngüsü.
- Break-glass erişimi ve harici kimlik sağlayıcı/broker entegrasyonu.

## 4. Sözleşme

### Kullanıcı oturum bilgisi

`GET /api/me` şu platform alanını döndürür:

```json
{
  "username": "kurucu",
  "is_admin": false,
  "is_platform_owner": true
}
```

`is_admin`, DB kapsamlı ilişkilerden türetilmeye devam eder.

### OWNER API

- `GET /api/owner/users`: tüm kullanıcıların durum ve OWNER bilgisini listeler.
- `POST /api/owner/users/{user_id}/enable`: kullanıcıyı etkinleştirir.
- `POST /api/owner/users/{user_id}/disable`: kullanıcıyı devre dışı bırakır ve
  aktif oturumlarını iptal eder.
- `GET /api/owner/databases`: credential taşımayan hedef DB kayıtlarını listeler.
- `POST /api/owner/databases`: hedef DB'yi ve `initial_admin_user_id` ile ilk
  aktif DB ADMIN'ini aynı transaction'da oluşturur.
- `GET /api/owner/database-admins`: tüm DB ADMIN atamalarını listeler.
- `POST /api/owner/databases/{database_id}/admins/{user_id}`: aktif kullanıcıya
  DB ADMIN yönetişim rolü ekler.
- `DELETE /api/owner/databases/{database_id}/admins/{user_id}`: ADMIN rolünü
  kaldırır; son DB ADMIN kaldırılamaz.

Eski platform endpoint'leri (`/api/admin/add_database`, `/api/admin/users*`)
OWNER sözleşmesiyle değiştirilir. DB kapsamlı `/api/admin/*` onay, maskeleme ve
veri rolü (`READER`/`WRITER`/`DDL`) atama endpoint'leri DB ADMIN'e ait kalır;
bu eski yüzey `ADMIN` rolünü veremez veya mevcut `ADMIN` rolünü silemez.

### Bootstrap

```text
python -m scripts.bootstrap_owner --email owner@company.com
```

Kullanıcı varsa aktif OWNER yapılır. Kullanıcı yoksa komut `--username` ister
ve parolayı terminalde görünmeden iki kez sorarak aktif OWNER hesabını
oluşturur. Komut migration'dan sonra çalışır ve işlemi audit kaydına yazar.
Runtime yetkilendirmesinde `PLATFORM_ADMINS` kullanılmaz.

## 5. İş Kuralları

### BR-01: OWNER ve DB ADMIN farklı kapsamdır

OWNER platform kimliklerini ve DB yöneticilerini yönetir. DB ADMIN yalnız
ilişkili olduğu hedef veritabanında sorgu onayı, maskeleme ve kullanıcı erişimi
yönetir; yeni DB ADMIN atayamaz veya ADMIN yönetişim rolünü kaldıramaz.

### BR-02: OWNER veri yeteneği vermez

`is_platform_owner=true`, `UserDatabaseAssociation` oluşturmaz. OWNER sorgu
çalıştırmak veya onaylamak istiyorsa ilgili DB için ayrıca açık rol almalıdır.

### BR-03: İlk DB ADMIN atomiktir

Yeni hedef DB kaydı aktif bir `initial_admin_user_id` olmadan kabul edilmez.
DB kaydı, ADMIN ilişkisi ve audit satırları tek transaction'da commit edilir.

### BR-04: Yönetici ataması mevcut veri rollerini korur

Bir kullanıcıya DB ADMIN eklenirken mevcut `READER`/`WRITER`/`DDL` rol kümesi
silinmez. ADMIN geri alınırken de veri rolleri korunur; hiçbir rol kalmazsa
ilişki silinir.

### BR-05: Yönetişim sahipsiz bırakılamaz

Son aktif platform OWNER devre dışı bırakılamaz. Bir hedef veritabanındaki son
DB ADMIN'in ADMIN rolü geri alınamaz. OWNER kendi hesabını API üzerinden
devre dışı bırakamaz.

### BR-06: OWNER yükseltmesi yalnız sunucu tarafıdır

Uygulama API veya arayüzü OWNER verme/geri alma endpoint'i sunmaz. Bootstrap
komutu fiziksel/operasyonel sunucu erişimini güven kökü kabul eder.

### BR-07: Admin risk sınırı korunur

DB ADMIN yalnız `sql_injection_risk` ve `blocked_operation` sert bloklarında
durdurulur. Değerlendirilebilir risk bypass'ı log/audit edilir. Satır sayımı ve
yıkıcı DML teyidi bu sürümde uygulanmaz.

## 6. Acceptance Criteria

- AC-01: Given migration uygulanmış veritabanı, when şema incelenir, then
  `Users.is_platform_owner` NOT NULL, varsayılan false ve indexli olur.
- AC-02: Given sıfır aktif OWNER, when production startup doğrulaması çalışır,
  then uygulama fail-closed durur ve bootstrap komutunu gösterir.
- AC-03: Given mevcut aktif kullanıcı, when bootstrap CLI kullanıcıyı OWNER
  yapar, then alan true olur ve `owner_granted` audit kaydı yazılır.
- AC-04: Given DB ADMIN ama OWNER olmayan kullanıcı, when `/api/owner/*`
  çağrılır, then `403` döner.
- AC-05: Given OWNER ama DB ilişkisi olmayan kullanıcı, when `/api/me` çağrılır,
  then `is_platform_owner=true`, `is_admin=false` döner ve sorgu/onay endpoint'i
  yetki kazanmaz.
- AC-06: Given OWNER ve aktif ilk admin, when hedef DB eklenir, then DB, ilk
  ADMIN ilişkisi ve audit kayıtları aynı transaction'da oluşur.
- AC-07: Given pasif kullanıcı, when ilk/ek DB ADMIN yapılmak istenir, then
  istek reddedilir ve ilişki yazılmaz.
- AC-08: Given son aktif OWNER veya hedef DB'nin son ADMIN'i, when yetkisi
  dolaylı olarak kaldırılmak istenir, then işlem reddedilir.
- AC-09: Given OWNER kullanıcıyı devre dışı bırakır, when işlem commit olur,
  then oturumlar iptal edilir ve `user_disabled` audit kaydı yazılır.
- AC-10: Given OWNER arayüzü, when kullanıcı ve DB durumları yüklenir, then
  yükleniyor/boş/hata/dolu durumları gösterilir; OWNER olmayan kullanıcıya
  OWNER kontrolleri render edilmez.
- AC-11: Given admin değerlendirilebilir riskli sorgu çalıştırır, when analiz
  tamamlanır, then mevcut bypass korunur; sert blok sorgusu yine reddedilir.
- AC-12: Given bu sürüm, when `UPDATE`/`DELETE` çalıştırılır, then ek satır
  sayımı veya genel teyit API/UI akışı oluşmaz.

## 7. Teknik ve Güvenlik Kısıtları

- Migration hem SQLite hem MSSQL ile uyumlu ve tekrar çalıştırmaya dayanıklı
  olmalıdır.
- OWNER ve DB ADMIN grant/revoke audit kayıtları aynı iş transaction'ında
  yazılmalıdır.
- Owner kullanıcı listesi parola, token veya credential içermez.
- Hedef DB liste yanıtı credential değerlerini içermez.
- Bootstrap parolayı argüman, log veya shell history üzerinden kabul etmez;
  yalnız `getpass` ile okur.
- Frontend doğrudan `fetch` kullanmaz; tüm çağrılar `services/api.ts` üzerinden
  geçer ve tasarım sistemi primitive'lerini kullanır.

## 8. Open Questions

- Yok. OQ-2026-009, OQ-2026-010 ve OQ-2026-011 cevaplandı.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

# Mini-Spec: Audit log altyapısı ve güvenlik olayı entegrasyonları

## 1. Spec Kartı

- Özellik: Append-only genel audit altyapısı ve güvenlik olayı entegrasyonları
- Durum: Implemented
- Versiyon: 2026-08-24
- Tarih: 2026-08-24
- Sahip: WebQuery

## 2. Amaç ve Başarı Sinyali

### Amaç

Sorgu yürütme kayıtlarından ayrı olarak yetkilendirme, yapılandırma ve kimlik
olaylarını kaydetmek için güvenli ve genişletilebilir bir veri temeli sağlamak.

### Başarı Sinyali

- Alembic `upgrade head`, yeni ve önceden oluşturulmuş şemalarda `AuditLog`
  tablosunu güvenle kurar.
- Yetki, yapılandırma, query kararı ve kimlik olayları aynı iş transaction'ında
  veya açıkça bağımsız audit transaction'ında kaydedilir.
- Admin, doğrulanmış filtrelerle audit kayıtlarını okuyabilir.
- Slack kararları yalnız veritabanı değişikliği ve audit satırı commit edildikten
  sonra başarı olarak bildirilir.
- Audit action değerleri kalıcı veri sözleşmesi olarak testle korunur.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `AuditLog` ORM modeli ve Alembic migration'ı.
- Kalıcı action/target sözlüğü ile `log_in` ve `log_standalone` yardımcıları.
- Model, migration, yardımcı ve uygulama entegrasyon testleri.
- `save_masking_rules` için table/column bazlı ekleme-kaldırma delta details'i.
- Database access grant/role change, database ekleme, web ve Slack query
  approve/reject, query preview, register, login/login-failed, logout ve tekil
  session revoke çağrı noktaları.
- Admin-only, filtrelenebilir `GET /api/admin/audit_log` endpoint'i.

### Kapsam Dışı

- Henüz uygulama endpoint'i olmayan revoke/remove/enable/disable/password-change
  iş akışları.
- Audit kayıtlarını güncelleyen veya silen API.

## 4. Sözleşme

`AuditLog` satırı actor, action, target, JSON details, client IP ve trace ID
alanlarını taşır. `log_in(session, ...)` caller session'a ekler ve commit etmez.
`log_standalone(...)` yalnız state-changing olmayan eylemler için kendi
transaction'ında kayıt yazar.

`save_masking_rules`, `UPDATE_MASKING_RULES` action'ı ile hedef veritabanına
bir delta yazar. Details yalnız `added_rules` ve `removed_rules` listelerini
taşır; aynı `(table_name, column_name)` anahtarındaki özellik değişimi, eski
kuralın kaldırılması ve yeni kuralın eklenmesi olarak yazılır.

`GET /api/admin/audit_log` yalnız `admin_required` kullanıcılara açıktır.
`action` ve `target_type` değerleri kalıcı sözlüklere göre doğrulanır;
`target_id` string karşılaştırmasıyla filtrelenir; `limit` 1 ile 1000
arasındadır. Sonuçlar `AuditLog.id DESC` sırasındadır.

## 5. İş Kuralları

### BR-01: Append-only kayıt

`AuditLog` için update/delete işlevi sağlanmaz. Düzeltme gerektiğinde yeni
bir audit satırı yazılır.

### BR-02: Transaction bütünlüğü

`STATE_CHANGING` içindeki action'lar `log_in(session, ...)` ile aynı
transaction'a eklenir. Helper commit etmez ve hatayı yutmaz.

### BR-03: Kalıcı action değerleri

`AuditAction` string değerleri geçmiş audit verisinin sözleşmesidir; mevcut
değerler değiştirilemez veya silinemez.

### BR-04: Masking delta semantiği

Değişmeyen masking kuralları audit details'e yazılmaz. Aynı table/column
anahtarında `masking_type` veya `is_active` değişirse details eski kuralı
`removed_rules`, yeni kuralı `added_rules` içinde taşır. Aynı anahtar iki kez
gönderilirse kayıt reddedilir ve hiçbir değişiklik/audit satırı commit edilmez.

### BR-05: Kaynak IP bütünlüğü

HTTP üzerinden başlayan audit olaylarında `client_ip`, doğrudan
`request.client.host` değerinden alınır. Doğrulanmamış proxy header'ları kaynak
olarak kullanılmaz.

### BR-06: Slack karar bütünlüğü

Slack approve/reject olayı, `QueryData` üzerindeki server/database bilgisiyle
kayıtlı `Databases.id` değerini çözer ve audit details'e bu kimliği yazar.
Kayıt bulunamazsa query durumu değiştirilmez. Kullanıcıya başarı mesajı yalnız
query durumu, workspace ve audit satırı birlikte commit edildikten sonra verilir.

### BR-07: Audit okuma yetkisi ve doğrulama

Audit endpoint'i admin olmayan kullanıcıya veri döndürmez. Bilinmeyen action
veya target type boş sonuç gibi davranmaz; HTTP 400 ile reddedilir.

## 6. Acceptance Criteria

- AC-01: Given boş bir uygulama veritabanı, when `alembic upgrade head`
  çalışır, then `AuditLog` ve gerekli indeksler oluşur.
- AC-02: Given eski bir şema `AuditLog` tablosunu zaten içerir, when migration
  çalışır, then migration hata vermez.
- AC-03: Given state-changing bir action, when `log_in` çağrılır, then kayıt
  caller transaction'ına eklenir ve helper transaction'ı commit etmez.
- AC-04: Given action sözlüğü, when test çalışır, then önceden tanımlı action
  stringleri değiştirilmiş veya silinmişse test başarısız olur.
- AC-05: Given mevcut `a`, `b`, `c` masking kuralları, when yalnız `c`
  kaldırılarak kayıt edilir, then `UPDATE_MASKING_RULES` details'i yalnız `c`
  için bir `removed_rules` girdisi içerir.
- AC-06: Given aynı table/column anahtarında bir masking kuralı değişir, when
  kayıt edilir, then details eski kuralı kaldırılmış, yenisini eklenmiş olarak
  temsil eder; tam önce/sonra koleksiyonlarını tekrar saklamaz.
- AC-07: Given aynı masking kuralları tekrar gönderilir, when kayıt edilir,
  then kural seti korunur ve audit satırı yazılmaz.
- AC-08: Given yeni database access veya rol değişikliği, when admin işlemi
  commit eder, then uygun grant/change-role audit satırı aynı transaction'da
  actor, target, details ve doğrudan client IP ile yazılır.
- AC-09: Given web approve/reject kararı, when işlem commit eder, then query ve
  audit satırı aynı transaction'da güncellenir.
- AC-10: Given Slack approve/reject kararı, when registry database bulunur,
  then details gerçek database ID taşır ve başarı cevabı commit sonrasında
  gönderilir; registry kaydı yoksa hiçbir durum değişikliği commit edilmez.
- AC-11: Given register, login, login-failed veya logout, when olay gerçekleşir,
  then action'a uygun actor/target/details ve doğrudan client IP kaydedilir.
- AC-12: Given admin audit endpoint'i, when geçerli filtreler gönderilir, then
  en yeni kayıtlar önce döner; bilinmeyen action/target HTTP 400, sınır dışı
  limit HTTP 422 ve admin olmayan kullanıcı HTTP 403 alır.

## 7. Teknik ve Güvenlik Kısıtları

- `details` alanına parola, access/refresh token, connection string veya ham
  SQL yazılmayacaktır.
- Migration hem SQLite hem MSSQL ile uyumlu SQLAlchemy tipleri kullanır.
- Masking details yalnız table adı, column adı, masking türü ve aktiflik
  durumunu taşıyabilir.
- Slack `database_id` alanı nullable yapılarak veri kalitesi düşürülemez; gerçek
  registry kimliği çözülmelidir.

## 8. Yeni bir action eklenirken

`AuditAction` genişletildiğinde uyulacak kısıtlar. (2026-08-30'da kapatılan
`docs/inbox/AUDIT-ACTION-FOLLOW-UPS.md` kaydından buraya taşındı; o kaydın tüm
maddeleri tamamlanmıştı ve `AuditAction` içindeki her action'ın artık en az bir
üretim çağrı noktası var.)

- Spec ve ADR'deki action kapsamını güncelle.
- State-changing action için aynı transaction'da `log_in` kullan.
- Details modeli ekle veya mevcut modeli genişlet
  (`web_api/common/audit_details.py`); bilinmeyen alanları reddet.
- Credential, parola ve connection string details'e girmez.
- Normal ve rollback/error path testleri ekle.
- `tests/unit/test_audit_log.py` içindeki `FROZEN_ACTIONS` sözlüğünü güncelle;
  bu sözlük action değerlerinin sessizce değişmesini engelliyor.
- Backend testlerini `web_api/` dizininden çalıştır.

## 9. Open Questions

- Yok.

## 10. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu/güncellendi
- [x] Doğrulama komutları çalıştırıldı ve sonuçları teslimde raporlandı

# Mini-Spec: Audit log altyapısı

## 1. Spec Kartı

- Özellik: Append-only genel audit altyapısı ve masking-rule delta kaydı
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
- Masking-rule kaydı yalnız değişen kuralları içeren bir audit satırı üretir.
- Audit action değerleri kalıcı veri sözleşmesi olarak testle korunur.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `AuditLog` ORM modeli ve Alembic migration'ı.
- Kalıcı action/target sözlüğü ile `log_in` ve `log_standalone` yardımcıları.
- Model, migration ve yardımcı davranışlarına yönelik unit testleri.
- `save_masking_rules` için table/column bazlı ekleme-kaldırma delta details'i.

### Kapsam Dışı

- Masking-rules dışındaki admin, auth, web veya Slack action çağrı noktalarına
  audit eklemek.
- Audit log görüntüleme API'si.
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

## 7. Teknik ve Güvenlik Kısıtları

- `details` alanına parola, access/refresh token, connection string veya ham
  SQL yazılmayacaktır; action entegrasyonları sonraki kapsamda bunu doğrular.
- Migration hem SQLite hem MSSQL ile uyumlu SQLAlchemy tipleri kullanır.
- Details yalnız table adı, column adı, masking türü ve aktiflik durumunu
  taşıyabilir; credential, token, connection string veya ham SQL içeremez.
- Masking dışındaki action'lar entegrasyon tamamlanana kadar audit edilmez.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [x] Doğrulama komutları çalıştırıldı ve sonuçları teslimde raporlandı

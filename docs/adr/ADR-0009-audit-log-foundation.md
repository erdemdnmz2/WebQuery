# ADR-0009: Transaction-bound append-only audit log altyapısı

## Status

Accepted

## Context

`ActionLogging` sorgu çalıştırma olaylarına özeldir; yetki, yapılandırma ve
kimlik değişiklikleri için ortak bir veri modeli sunmaz. State değişikliği ve
audit kaydı ayrı transaction'larda yazılırsa, değişiklik kayıtsız kalabilir
veya gerçekleşmeyen olay kaydedilebilir.

## Decision

Genel denetim kayıtları `AuditLog` tablosunda tutulacaktır. Kalıcı action ve
target sözlüğü Python `StrEnum` değerleriyle yönetilir. State-changing action
çağrıları caller transaction'ına `log_in` ile eklenir; bu helper commit etmez
ve hata yutmaz. State-changing olmayan olaylar için `log_standalone` bağımsız
transaction kullanabilir ve audit yazma hatasını loglar.

Audit kayıtları admin-only `GET /api/admin/audit_log` endpoint'i üzerinden
okunur. Action ve target filtreleri kalıcı sözlüğe göre doğrulanır; böylece
yazım hatası boş audit izi olarak yorumlanamaz. HTTP kaynaklı audit olaylarında
IP yalnız doğrudan request peer bilgisinden alınır.

Slack query kararlarında details içindeki `database_id` nullable yapılmaz.
Handler, `QueryData` server/database anahtarıyla registry kaydını aynı session
içinde çözer. Query durumu, workspace ve audit satırı commit edilmeden Slack'e
başarı cevabı verilmez.

Masking-rule kaydı için details tam önce/sonra rule-set kopyaları yerine
table/column anahtarına göre deterministik ekleme-kaldırma deltası olacaktır.
Bir kuralın `masking_type` veya `is_active` değeri değişirse audit, eski
değerin kaldırılıp yeni değerin eklendiğini kaydeder. Bu yaklaşım hem delta
anlamını korur hem de değişmeyen kuralları tekrarlamaz.

## Rejected Alternatives

### 1. Her olay için ayrı, action'a özgü tablo

Sorgulama ve saklama kurallarını dağıtır; ortak actor, trace ve hedef
bağlamlarının tutarsızlaşmasına neden olur.

### 2. Tüm audit kayıtlarını bağımsız transaction'da yazmak

Uygulaması daha basittir ancak state değişikliği ile denetim kaydını atomik
olmaktan çıkarır.

### 3. Masking-rule setinin tam önce/sonra kopyalarını saklamak

Bir olayı tek başına yeniden oluşturmayı kolaylaştırır; ancak değişmeyen
kuralları her kayıtta tekrarlar ve küçük bir değişikliğin denetim izini
gereksiz biçimde büyütür.

### 4. Slack audit details içinde nullable database ID kullanmak

Handler değişikliğini küçültür ancak güvenlik kararının hangi kayıtlı database
üzerinde verildiğini belirsiz bırakır. Registry kimliği çözülemezse kararın da
commit edilmemesi tercih edilmiştir.

### 5. Slack başarı cevabını database commit'inden önce göndermek

Arayüzü daha hızlı günceller ancak audit veya state write başarısız olduğunda
kullanıcıya gerçekte uygulanmamış bir kararın başarıyla uygulandığını söyler.
Slack acknowledgement hemen yapılır; kullanıcıya görünür sonuç commit sonrasına
bırakılır.

## Consequences

- Yetki ve yapılandırma action'ları için ortak, append-only veri modeli oluşur.
- Her yeni state-changing action mevcut transaction'ına `log_in` eklemelidir.
- Migration deploy edilmeden audit helper'ı çağırılmamalıdır.
- Admin audit endpoint'i sözlük doğrulaması ve 1000 kayıt üst sınırı uygular.
- HTTP çağrı noktaları request peer bilgisini service katmanına taşır.
- Slack registry çözümü veya audit insert'i başarısız olursa karar rollback olur
  ve kullanıcı başarı yerine hata cevabı görür.
- Masking-rule güncellemeleri delta olarak sorgulanır; bir kuralın güncel
  setini bulmak için audit yerine `MaskingRules` tablosu kaynak doğrusu kalır.

## Accepted Risks

- Endpoint'i olmayan revoke/remove/enable/disable/password-change action'ları
  çağrı noktaları eklenene kadar audit coverage dışında kalır.

## References

- Spec: `docs/specs/SPEC-0006-audit-log-foundation.md`
- Supersedes / Superseded by: Yok

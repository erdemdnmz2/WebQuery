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

## Consequences

- Yetki ve yapılandırma action'ları için ortak, append-only veri modeli oluşur.
- Her yeni state-changing action mevcut transaction'ına `log_in` eklemelidir.
- Migration deploy edilmeden audit helper'ı çağırılmamalıdır.
- Masking-rule güncellemeleri delta olarak sorgulanır; bir kuralın güncel
  setini bulmak için audit yerine `MaskingRules` tablosu kaynak doğrusu kalır.

## Accepted Risks

- Masking dışındaki action çağrı noktaları entegrasyon yapılana kadar audit
  coverage dışında kalır.

## References

- Spec: `docs/specs/SPEC-0006-audit-log-foundation.md`
- Supersedes / Superseded by: Yok

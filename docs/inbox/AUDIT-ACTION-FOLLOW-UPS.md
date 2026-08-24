# Audit action takip listesi

**Durum:** Inbox / uygulanacak iş

Bu kayıt, `AuditLog` altyapısı eklendikten sonra uygulamada henüz çağrı noktası
olmayan action'ları takip eder. Bir iş akışı eklendiğinde ilgili audit adımı da
aynı değişiklikte tamamlanmalıdır.

## Tamamlanan çağrı noktaları

- Database access grant ve role change
- Database ekleme
- Masking-rule delta güncellemesi
- Web ve Slack query approve/reject
- Query preview
- Register, başarılı/başarısız login ve logout
- Tekil session revoke

## Uygulanacak action'lar

### Database access revoke

İş akışı eklendiğinde:

- `AuditAction.REVOKE_DATABASE_ACCESS` ile aynı transaction'da `log_in` çağır.
- Target: erişimi kaldırılan kullanıcı.
- Details: `database_id`, önceki rol ve `operation="revoke"`.
- Association silinmesi başarısız olursa audit satırının da rollback olduğunu
  test et.

### Database remove

İş akışı eklendiğinde:

- `AuditAction.REMOVE_DATABASE` ile aynı transaction'da audit yaz.
- Target: silinen veritabanı.
- Details yalnız server, database adı ve teknoloji içersin.
- Credential, parola veya connection string details'e yazılmasın.

### User disable / enable

İş akışı eklendiğinde:

- `USER_DISABLED` veya `USER_ENABLED` action'ı ile audit yaz.
- Target: durumu değişen kullanıcı; actor işlemi yapan admin.
- Session'lar iptal edilirse her iptal için `SESSION_REVOKED` kaydı veya
  anlaşılır toplu iptal details'i üret.
- Disabled kullanıcının login/refresh erişiminin reddedildiğini test et.

### Password change

İş akışı eklendiğinde:

- `PASSWORD_CHANGED` action'ı ile aynı transaction'da audit yaz.
- Details yalnız `event="password_changed"` ve güvenli kaynak bilgisini
  içersin; eski/yeni parola, hash, token veya reset kodu kesinlikle yazılmasın.
- Gerekliyse session iptalleri ayrıca auditlensin.

### Bulk session revoke

`revoke_user_sessions` çağıran bir akış eklendiğinde:

- Kaç aktif session'ın iptal edildiğini ve nedenini secrets içermeyen details
  alanında kaydet.
- Session değişikliği ile audit satırlarının aynı transaction'da olduğunu test et.

## Teslim kontrolü

Her madde tamamlanırken:

- Spec ve ADR'deki action kapsamını güncelle.
- State-changing action için aynı transaction'da `log_in` kullan.
- Details modeli ekle veya mevcut modeli genişlet; unknown alanları reddet.
- Normal ve rollback/error path testleri ekle.
- İlgili backend testlerini `web_api/` dizininden çalıştır.

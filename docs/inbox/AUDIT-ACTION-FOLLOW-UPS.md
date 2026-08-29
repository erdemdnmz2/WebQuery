# Audit action takip listesi

**Durum:** Kapandı (2026-08-30)

Bu kayıt, `AuditLog` altyapısı eklendikten sonra uygulamada henüz çağrı noktası
olmayan action'ları takip ediyordu. **Listedeki beş maddenin hepsi tamamlandı;**
`AuditAction` içindeki her action'ın artık en az bir üretim çağrı noktası var.
Dosya, hangi maddenin nerede kapandığının kaydı olarak duruyor ve yeni bir
action eklenmedikçe silinebilir.

## Tamamlanan çağrı noktaları

- Database access grant ve role change
- Database ekleme
- Masking-rule delta güncellemesi
- Web ve Slack query approve/reject
- Query preview
- Register, başarılı/başarısız login ve logout
- Tekil session revoke
- Admin-only, doğrulanmış filtreli audit log görüntüleme endpoint'i

## Kapanan maddeler (2026-08-30 denetim düzeltmesi)

| Madde | Action | Çağrı noktası | Kaynak |
| --- | --- | --- | --- |
| Database access revoke | `REVOKE_DATABASE_ACCESS` | `admin/services.py` — `DELETE /api/admin/databases/{id}/users/{user_id}` | P1-8 |
| Database remove | `REMOVE_DATABASE` | `owner/services.py` — `retire_database`, yumuşak silme | P1-10 |
| User disable / enable | `USER_DISABLED`, `USER_ENABLED` | `owner/services.py` | Adım 20 (OWNER governance) |
| Password change | `PASSWORD_CHANGED` | `authentication/router.py` — `POST /api/me/password` | P1-9 |
| Bulk session revoke | `SESSION_REVOKED` | `authentication/sessions.py` — refresh reuse tespitinde kullanıcının tüm oturumları | P2-13 |

Her biri bu dosyanın öngördüğü kısıtlara uyuyor: state-changing action'lar
çağıranın transaction'ında `log_in` ile yazılıyor, details modelleri
`common/audit_details.py` içinde tanımlı ve bilinmeyen alanları reddediyor,
credential/parola/connection string details'e girmiyor. Toplu oturum iptali
her satır için ayrı kayıt yerine sayıyı taşıyan tek bir `SESSION_REVOKED`
satırı yazıyor — bu dosyanın izin verdiği iki seçenekten "anlaşılır toplu
iptal details'i" olanı.

`USER_CREATED` action'ı bu turda **kaldırıldı**: hiç çağrı noktası yoktu ve
kayıt olma akışının gerçekten yazdığı action `USER_REGISTERED`. Bkz.
`docs/specs/SPEC-0025-dead-code-removal.md`.

## Yeni bir action eklenirse

- Spec ve ADR'deki action kapsamını güncelle.
- State-changing action için aynı transaction'da `log_in` kullan.
- Details modeli ekle veya mevcut modeli genişlet; unknown alanları reddet.
- Normal ve rollback/error path testleri ekle.
- `tests/unit/test_audit_log.py` içindeki `FROZEN_ACTIONS` sözlüğünü güncelle;
  bu sözlük action değerlerinin sessizce değişmesini engelliyor.
- İlgili backend testlerini `web_api/` dizininden çalıştır.

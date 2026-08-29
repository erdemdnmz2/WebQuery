# SPEC-0015: Kullanıcı Hesabını Devre Dışı Bırakma

## 1. Spec Kartı

- Özellik: Kullanıcı devre dışı bırakma
- Durum: Implemented
- Versiyon: 1.1.0
- Tarih: 2026-08-25
- Sahip: WebQuery

## 2. Amaç ve Başarı Sinyali

### Amaç

Bir platform OWNER, kullanıcı satırını silmeden hesabı devre dışı bırakabilmeli ve
devre dışı bırakılan kullanıcının mevcut access/refresh oturumları hemen
geçersizleşmelidir.

### Başarı Sinyali

- Devre dışı bırakılan kullanıcı bir sonraki korumalı isteğinde 401 alır.
- Kullanıcı yeni login veya refresh oturumu oluşturamaz.
- İşlem, hedef kullanıcı ve işlemi yapan admin ile audit edilir.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `Users` yaşam döngüsü kolonları.
- OWNER-only kullanıcı disable endpoint’i.
- Middleware ve authentication dependency katmanlarında aktiflik kontrolü.
- Mevcut kullanıcı oturumlarının iptali.
- Login, refresh ve korumalı isteklerde pasif kullanıcı reddi.
- Audit kaydı ve migration.

### Kapsam Dışı

- Kullanıcıyı yeniden etkinleştiren endpoint.
- Kullanıcı silme veya anonimleştirme.
- Kayıt endpoint’inin kapatılması.
- Kullanıcı yönetimi UI’ı.

## 4. Sözleşme

### Endpoint

`POST /api/owner/users/{user_id}/disable`

Başarılı yanıt:

```json
{"success": true, "message": "Kullanıcı devre dışı bırakıldı."}
```

Hata davranışı:

- Hedef kullanıcı yoksa `404`.
- OWNER kendi hesabını kapatmaya çalışırsa `400`.
- Pasif kullanıcı için işlem idempotent olarak başarılı kabul edilir.

## 5. İş Kuralları

### BR-01: Soft disable

Disable işlemi kullanıcı satırını silmez; `is_active` değerini `false` yapar,
`disabled_at` ve `disabled_by` alanlarını doldurur.

### BR-02: Anında erişim kesme

Korumalı istekte middleware kullanıcıyı veritabanından bulur. Kullanıcı yoksa
veya `is_active` false ise istek 401 ile durdurulur.

### BR-03: Oturum iptali

Disable işlemi hedef kullanıcının aktif `UserSessions` kayıtlarını revoke eder.

### BR-04: Kimlik doğrulama noktaları

Login ve refresh, middleware muafiyetleri nedeniyle kendi `is_active`
kontrollerini korur. `get_current_user`, middleware state’i yoksa bağımsız
çalışabilmek için kullanıcı ve aktiflik kontrolünü yine yapar.

### BR-05: Kendi hesabını kapatma yasağı

Admin kendi hesabını devre dışı bırakamaz.

### BR-06: Audit

Başarılı disable işlemi `user_disabled` action’ı ile hedef kullanıcıyı,
işlemi yapan admin’i, IP adresini ve trace ID’yi kaydeder.

## 6. Acceptance Criteria

- AC-01: Given aktif bir admin ve aktif bir hedef kullanıcı, when admin disable endpoint’ini çağırır, then kullanıcı pasif olur ve 200 döner.
- AC-02: Given devre dışı bir kullanıcının geçerli access token’ı, when korumalı endpoint çağrılır, then 401 döner.
- AC-03: Given devre dışı bir kullanıcı, when login veya refresh çağrılır, then yeni oturum/token üretilmez ve 401/400 döner.
- AC-04: Given hedef kullanıcının aktif session’ları, when disable tamamlanır, then session’ların `revoked_at` alanı doldurulur.
- AC-05: Given admin kendi user ID’sini gönderir, when disable çağrılır, then 400 döner ve hesap değişmez.
- AC-06: Given normal bir kullanıcı, when admin disable endpoint’ini çağırır, then 403 döner.
- AC-07: Given başarılı disable, when audit log sorgulanır, then `user_disabled` kaydı admin, hedef kullanıcı, IP ve trace bilgilerini içerir.
- AC-08: Given zaten pasif bir kullanıcı, when disable tekrar çağrılır, then işlem güvenli ve idempotent biçimde tamamlanır.

## 7. Teknik ve Güvenlik Kısıtları

- Şema değişikliği Alembic migration ile yapılır; startup sırasında `create_all()` kullanılmaz.
- Middleware’in bulduğu `User` nesnesi `request.state.authenticated_user` ile dependency katmanına aktarılır; aynı istek için gereksiz ikinci kullanıcı sorgusu yapılmaz.
- `/api/login` ve `/api/refresh` middleware’den muaf olduğu için aktiflik kontrolü bu akışlarda ayrıca korunur.
- İstemciye pasif kullanıcı için hassas hesap durumu gereksiz yere açıklanmaz.
- Disable ve session revoke aynı uygulama veritabanı transaction’ında tamamlanır.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi
- [x] Doğrulama komutları çalıştırıldı

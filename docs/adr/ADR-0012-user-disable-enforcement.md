# ADR-0012: Kullanıcı Devre Dışı Bırakma ve İstek Başında Aktiflik Kontrolü

## Status

Accepted

## Context

WebQuery mevcut access token’ı olan bir kullanıcının hesabını silmeden erişimini
kesmelidir. `AuthMiddleware` JWT içinden user ID’yi zaten çıkarıyor; ancak
mevcut akışta kullanıcıyı veritabanından yükleyip `is_active` kontrolü yapmıyor.
`get_current_user` ise korumalı endpoint’lerde kullanıcıyı ayrıca yüklüyor.
Hesap kapatma sırasında access token’ların süresini beklemek ve refresh
session’larını açık bırakmak güvenlik açığı oluşturur.

## Decision

`Users` tablosuna kullanıcı yaşam döngüsü alanları eklenir. Platform yetki
sınırı ADR-0017 ile kalıcılaştırıldıktan sonra disable işlemi OWNER-only
`POST /api/owner/users/{user_id}/disable` endpoint’inden sunulur.

Kimlik doğrulama akışı şu şekilde uygulanır:

1. Middleware token, blacklist ve session doğrulamasından sonra kullanıcıyı
   veritabanından yükler.
2. Kullanıcı bulunamazsa veya `is_active` false ise istek 401 ile durdurulur.
3. Yüklenen kullanıcı `request.state.authenticated_user` içine yazılır.
4. `get_current_user` bu state’i kullanır; state yoksa bağımsız fallback sorgusu
   yapar ve yine aktiflik kontrolü uygular.
5. Login ve refresh middleware’den muaf oldukları için kendi aktiflik
   kontrollerini uygular.

Disable işlemi kullanıcıyı silmez; `is_active=false`, `disabled_at` ve
`disabled_by` alanlarını günceller, tüm aktif `UserSessions` kayıtlarını iptal
eder ve `user_disabled` audit kaydını aynı transaction içinde yazar.

## Rejected Alternatives

### 1. Yalnızca access token süresinin dolmasını beklemek

Token geçerli kaldığı sürece devre dışı kullanıcı erişebilir. Offboarding için
yeterli değildir.

### 2. Yalnızca `get_current_user` içinde kullanıcıyı kontrol etmek

Dependency kullanan endpoint’leri korur; ancak middleware’in koruduğu ve
dependency kullanmayan akışlarda tek tip istek başı kontrolü sağlamaz.

### 3. Middleware ve dependency’de kullanıcıyı iki kez sorgulamak

Doğru sonucu verir ancak her korumalı istekte gereksiz ek veritabanı sorgusu
oluşturur. Middleware state’i bu tekrarın önüne geçer.

## Consequences

- Devre dışı bırakma access token TTL’sini beklemeden etkili olur.
- Her korumalı istekte kullanıcı yaşam döngüsü için bir merkezi DB okuması
  yapılır; mevcut session kontrolü ile birlikte bu maliyet kabul edilir.
- `request.state` aktarımı middleware ve authentication dependency arasında
  ortak sözleşme hâline gelir.
- Migration mevcut kullanıcıları aktif olarak backfill etmelidir.
- Yeniden etkinleştirme bu ADR’nin kapsamında değildir.

## Accepted Risks

- Disable ile aynı anda başlamış, middleware kontrolünü geçmiş bir in-flight
  istek tamamlanabilir; sonraki istekler engellenir.
- `/api/login` ve `/api/refresh` middleware’den muaf olduğundan bu endpoint’lerde
  duplicate aktiflik kontrolleri korunur.

## References

- Spec: `docs/specs/SPEC-0015-user-lifecycle-disable.md`
- Related ADR: `docs/adr/ADR-0008-access-refresh-session-auth.md`
- Authorization boundary: `docs/adr/ADR-0017-persisted-platform-owner-boundary.md`

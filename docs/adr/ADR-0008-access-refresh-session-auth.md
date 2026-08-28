# ADR-0008: Access/Refresh Token ile Sunucu Tarafı Oturumlar

## Durum

Accepted

## Karar

Kısa ömürlü JWT access token ve veritabanında hash'i tutulan, opak ve rotasyonlu
refresh token kullanılacak. `UserSessions` oturumun yaşam döngüsünü, iptalini,
refresh rotasyonunu ve tekrar kullanım tespitini yönetecek.

## Gerekçe

Tek ve 24 saatlik access token çalındığında uzun süre kullanılabiliyordu. Access
token'ı stateless ve kısa tutmak her istekte veritabanı yükünü azaltır; refresh
token'ı sunucu tarafında tutmak ise logout, hesap kapatma ve acil tüm oturumları
iptal etme davranışlarını mümkün kılar. Ham refresh token yerine SHA-256 özeti
tutulması veritabanı sızıntısında token'ın doğrudan kullanılmasını engeller.

## Güvenlik ve İşletim Notları

- Access ve refresh tokenlar yalnızca `HttpOnly`, `SameSite=Strict` cookie'lerde
  taşınır; login yanıt gövdesi token içermez.
- Refresh token cookie'si `/api/refresh` path'iyle sınırlandırılır; böylece
  normal API çağrılarında tarayıcı refresh tokenı göndermez.
- Daha önce `/api` path'iyle oluşturulmuş aynı adlı cookie, path değişimi cookie
  kimliğini değiştirdiği için login ve refresh yanıtlarında ayrıca silinir.
- Rotasyon, çalınmış eski refresh token'ın tekrar kullanımını tespit eder.
- Mevcut `BlacklistedTokens` mekanizması geçiş ve geriye dönük uyumluluk için
  korunur; yeni session'lar ayrıca `revoked_at` ile iptal edilir.
- `SECRET_KEY`, refresh TTL ve cookie güvenlik ayarları ortam değişkenlerinden
  gelir.

## Sonuçlar

Her korumalı access isteği session durumunu sorgular. Bu, eski blacklist-only
akışına göre ek bir merkezi veritabanı okumasıdır; karşılığında logout ve hesap
devre dışı bırakma etkisi access token TTL'sini beklemeden uygulanır.

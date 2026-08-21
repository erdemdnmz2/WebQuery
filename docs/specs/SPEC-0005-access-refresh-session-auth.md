# SPEC-0005: Kısa Access Token ve Rotasyonlu Refresh Token

## Durum

Accepted

## Amaç

JWT access token çalınırsa geçerlilik penceresini kısaltmak ve refresh token
üzerinden sunucu tarafı oturum iptali sağlamak.

## Davranış

1. Login, 20 dakikalık JWT access token ve 12 saatlik opak refresh token üretir.
2. Refresh token'ın kendisi değil SHA-256 özeti `UserSessions` tablosunda tutulur.
3. Her refresh isteği refresh token'ı rotasyona uğratır; önceki token yeniden
   kullanılırsa ilgili oturum iptal edilir. Eşzamanlı sekmeler için 30 saniyelik
   grace penceresi uygulanır.
4. Access token `sid` taşır. Her korumalı istekte oturumun aktif, doğru kullanıcıya
   ait ve süresi geçmemiş olduğu doğrulanır.
5. Logout ilgili oturumu iptal eder, cookie'leri siler ve eski access token'lar
   için mevcut JTI blacklist kaydını geriye dönük uyumluluk amacıyla korur.
6. Refresh sırasında kullanıcının hâlâ aktif olduğu yeniden doğrulanır.

## Kabul Kriterleri

- Login sonrası `access_token` ve `refresh_token` cookie'leri oluşur.
- Access token varsayılan olarak 20 dakikadan uzun yaşamaz.
- Geçerli refresh token `/api/refresh` ile yeni access ve refresh cookie'leri üretir.
- Logout sonrası access token ile korumalı endpoint'e erişim 401 döner.
- Geçersiz, süresi dolmuş veya iptal edilmiş refresh token 401 döner.
- Refresh token tekrar kullanımı oturumu iptal eder.
- Refresh token ham değeri veritabanında tutulmaz.

## Kapsam Dışı

Refresh token'ın cookie dışı istemci taşıma biçimleri ve çoklu bölge dağıtık
kilitleme bu değişikliğin kapsamı dışındadır.

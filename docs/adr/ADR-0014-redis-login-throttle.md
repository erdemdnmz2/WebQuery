# ADR-0014: Redis tabanlı dağıtık login throttle

## Status

Accepted

## Context

Adım 14, başarısız login denemelerini kullanıcı hesabı ve IP bazında
sınırlamalıdır. Process-local bellek birden çok Uvicorn worker'ında ortak
değildir; container yeniden başladığında sayaçlar da kaybolur. WebQuery Docker
Compose altyapısında Redis hizmeti zaten bulunmaktadır.

Belirleyici kriter, worker sayısından bağımsız olarak login güvenlik
sözleşmesinin aynı kalmasıdır.

## Decision

Redis, `POST /api/login` throttle için tüm runtime ortamlarında zorunlu ortak
backend olacaktır. Uygulama startup'ta Redis'e ping atar; erişilemezse başlamaz.
Runtime Redis arızasında login fail-closed olarak `503` döner.

Kullanıcı hesabı ve IP sayaçları Redis sorted set'lerinde ayrı tutulur. Kayan
pencere temizliği, sayımı ve kayıt ekleme Redis Lua script'leri ile her anahtar
için atomik gerçekleştirilir. Anahtar parçaları SHA-256 ile türetilir; ham
e-posta ve IP Redis anahtarına yazılmaz.

Başarılı giriş kullanıcı hesabı sayacını temizler, IP sayacını temizlemez.
Mevcut SlowAPI IP limiter'ı ek yerel savunma katmanı olarak kalır; dağıtık
garantinin kaynağı değildir.

## Rejected Alternatives

### 1. Worker sayısına göre in-memory veya Redis backend seçmek

Tek worker geliştirme ortamında daha az altyapı gerektirir. Ancak deployment
topolojisi login güvenlik davranışını değiştirir; restartta sayaçlar kaybolur ve
ileride container replica'ları eklendiğinde kolayca yanlış yapılandırılır.

### 2. Sayaçları uygulama veritabanında tutmak

Mevcut altyapıyı kullanır. Ancak yüksek frekanslı login denemeleri için gereksiz
veritabanı yazma ve kilit yarışları üretir; kayan pencere atomikliği Redis kadar
doğal değildir.

## Consequences

- Redis erişilebilirliği login erişilebilirliği için kritik hâle gelir.
- Docker Compose Redis health check içermeli ve uygulamaya Redis URL'i vermelidir.
- Testler Redis istemcisini test doubles ile izole eder; production davranışı
  startup ve hata testleriyle doğrulanır.
- Genel uygulama cache'i bu ADR'nin kapsamı dışındadır, fakat ileride aynı Redis
  altyapısını kullanabilir.

## Accepted Risks

- Tek Redis instance'ı login için tek hata noktasıdır. Fail-closed kararı bunu
  bilinçli olarak kabul eder; production'da uygun izleme ve yüksek erişilebilir
  Redis değerlendirilmelidir.

## References

- Spec: `docs/specs/SPEC-0017-redis-login-throttle.md`
- Supersedes / Superseded by: Yok

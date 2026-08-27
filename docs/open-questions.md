# Open Questions

This is the project-wide decision queue. Every AI session must ask every item
with status `Open` before doing task work; see `AGENTS.md`.

### OQ-2026-001: Hedef veritabanı engine pool ayarının kaynak doğrusu hangisi?

- Status: Answered
- Raised: 2026-08-20
- Scope: `web_api/database_provider/engine_cache.py`, engine-cache ADR ve performans dokümantasyonu
- Question: Hedef DB engine'leri için amaçlanan ayar `pool_size=0, max_overflow=20` mi (README), yoksa `pool_size=50, max_overflow=100` mü (mevcut `EngineCache` kodu)?
- Why it matters: Bağlantı yaşam döngüsü, kaynak tüketimi ve ölçekleme kararını iki ayar zıt biçimde etkiler; ADR ve spec'in doğru davranışı tarif etmesi gerekir.
- Answer: Mevcut kod kaynak doğrudur; `EngineCache` içindeki `pool_size=50` ve `max_overflow=100` ayarları belgelenmelidir.
- Recorded in: `docs/adr/ADR-0003-engine-cache-lifecycle.md`

### OQ-2026-002: Hedef DB sorgu bağlantısında hangi kimlik bilgisi modeli amaçlanıyor?

- Status: Answered
- Raised: 2026-08-20
- Scope: merkezi erişim ve credential ADR'si; `web_api/database_provider/database.py` ve admin DB kayıt akışı
- Question: Runtime sorgu bağlantılarında yalnızca `CENTRAL_DB_USER/CENTRAL_DB_PASSWORD` mı kullanılmalı (mevcut `DatabaseProvider`), yoksa admin kaydında üretilip şifrelenen veritabanı başına `db_username/db_password` mı kullanılmalı?
- Why it matters: İki modelin yetki sınırı, credential rotasyonu, erişim izolasyonu ve veri modelindeki alanların anlamı farklıdır. Bu karar bilinmeden merkezi erişim ADR'si doğru yazılamaz.
- Answer: Veritabanı başına ve role göre ayrı hedef DB kimlik bilgileri kullanılacak. Hedef veritabanının DBA'i `ro` ve `rw` hesaplarını, gerekirse `ddl` hesabını, hedef sunucuda manuel oluşturur. Admin bu gerçek kullanıcı adı/şifreleri WebQuery'ye girer; WebQuery şifreleri kendi veritabanında `EncryptedText` ile saklar ve sorgu kademesine göre ilgili hesapla bağlanır. WebQuery hedef DB hesaplarını oluşturmaz ve `CREATE LOGIN`/`GRANT` yetkisi taşımaz.
- Recorded in: `docs/specs/SPEC-0002-role-based-target-database-credentials.md`, `docs/adr/ADR-0005-role-based-target-database-credentials.md`

### OQ-2026-003: Ham veritabanı hata temizlemenin kapsamı nedir?

- Status: Answered
- Raised: 2026-08-21
- Scope: `0.2` ham veritabanı hata temizleme; sorgu, workspace ve diğer API hata akışları
- Question: Temizleme yalnızca sorgu/workspace çalıştırma akışlarında mı uygulanmalı, yoksa istemciye dönen tüm ham veritabanı hatalarını mı kapsamalı?
- Why it matters: Dar kapsam mevcut adımın riskini sınırlar; geniş kapsam kayıt, admin ve diğer endpoint'lerdeki aynı bilgi sızıntılarını da kapatır ancak daha geniş API davranışı değişikliği ve test alanı doğurur.
- Answer: Yalnızca sorgu ve workspace çalıştırma akışlarında uygulanacak. Kayıt/login, admin ve diğer endpoint'lerin hata davranışı bu adımın kapsamı dışında kalacak.
- Recorded in: `docs/specs/SPEC-0003-target-database-error-sanitization.md`, `docs/adr/ADR-0006-target-database-error-sanitization.md`

### OQ-2026-004: Ham veritabanı hataları log ve audit kaydında nasıl saklanmalı?

- Status: Answered
- Raised: 2026-08-21
- Scope: `0.2` ham veritabanı hata temizleme; uygulama logları ve `QueryData`/audit hata alanları
- Question: Ham hata log ve audit kaydına olduğu gibi mi yazılmalı, yoksa bu kayıtlara yazılmadan önce bağlantı bilgileri/parolalar da temizlenmeli mi?
- Why it matters: Ham kayıt teşhisi kolaylaştırır ancak veritabanı sürücüsü bağlantı dizesi veya parola döndürürse hassas veri sızıntısı yaratabilir; önceden temizleme güvenliği artırır ancak bazı teşhis ayrıntılarını kaybettirir.
- Answer: Log ve audit kayıtlarında bağlantı bilgileri korunabilir; olası parola değerleri kaydedilmeden önce maskelenmelidir. İstemciye dönen mesajda bağlantı bilgileri de temizlenmelidir.
- Recorded in: `docs/specs/SPEC-0003-target-database-error-sanitization.md`, `docs/adr/ADR-0006-target-database-error-sanitization.md`

### OQ-2026-005: Redis tabanlı giriş kısıtlayıcısı kullanılamazsa login nasıl davranmalı?

- Status: Answered
- Raised: 2026-08-26
- Scope: Adım 14 Redis tabanlı kullanıcı ve IP giriş kısıtlaması; `/api/login` hata sözleşmesi ve operasyonel izleme
- Question: Redis erişilemez veya zaman aşımına uğrarsa giriş isteği `503` ile reddedilerek fail-closed mu davranmalı, yoksa giriş Redis throttling'i atlanarak mevcut IP limiter ile devam mı etmeli?
- Why it matters: Fail-closed parola saldırısı ve bcrypt kaynak tüketimine karşı korumayı sürdürür ancak Redis arızası login erişimini keser; fail-open erişilebilirliği korur ancak Redis arızasında kullanıcı bazlı dağıtık korumayı kaldırır.
- Answer: Fail-closed. Redis tabanlı throttle aktifken Redis erişilemezse `/api/login` bcrypt veya veritabanı doğrulamasına geçmeden `503 Service Unavailable` dönecek.
- Recorded in: `docs/specs/SPEC-0017-redis-login-throttle.md`, `docs/adr/ADR-0014-redis-login-throttle.md`

### OQ-2026-006: Login throttle cache backend'i deployment topolojisine göre nasıl seçilmeli?

- Status: Answered
- Raised: 2026-08-26
- Scope: Adım 14 Redis tabanlı giriş kısıtlaması; Docker Compose ve production deployment yapılandırması
- Question: Cache backend'i açık bir `LOGIN_THROTTLE_BACKEND=memory|redis` ayarı ve startup doğrulamasıyla mı seçilmeli, yoksa uygulama yalnızca worker sayısını okuyup backend'i otomatik mi seçmeli?
- Why it matters: Worker sayısı tek başına toplam process sayısını göstermez; birden fazla application replica'sı birer worker ile çalışabilir. Otomatik seçim bu topolojide yanlışlıkla process-local throttle'a düşebilir; açık ayar ise deployment konfigürasyonunun doğru yönetilmesini gerektirir.
- Answer: Login throttle için Redis, worker sayısından bağımsız sabit runtime bağımlılığı olacak. Memory backend ve worker sayısına göre otomatik backend seçimi uygulanmayacak.
- Recorded in: `docs/specs/SPEC-0017-redis-login-throttle.md`, `docs/adr/ADR-0014-redis-login-throttle.md`

## Entry Format

Add new items in this format. Keep resolved entries for decision history, but
change their status so they are not asked again.

```md
### OQ-YYYY-NNN: Short question

- Status: Open | Answered | Deferred | Superseded
- Raised: YYYY-MM-DD
- Scope: feature, module, or decision affected
- Question: The exact decision the user must make
- Why it matters: Consequence of each valid answer
- Answer: Leave blank while open; record the user's answer once received
- Recorded in: Spec/ADR path, once applicable
```

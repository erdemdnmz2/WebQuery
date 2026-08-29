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

### OQ-2026-007: Hedef DB ekleme ekranı hangi credential kademesi kombinasyonlarını desteklemeli?

- Status: Answered
- Raised: 2026-08-28
- Scope: Adım 16 (`3.1`), `Databases` credential alanları, admin "Veritabanı Ekle" API/UI sözleşmesi ve runtime fail-closed davranışı
- Question: Admin, hedef veritabanını yalnızca `ro`; `ro` + `rw`; veya `ro` + `rw` + `ddl` olarak mı kaydedebilmeli? `rw` ya da `ddl` hesaplarının `ro` olmadan tek başına tanımlanmasına izin verilecek mi?
- Why it matters: Seçim, formdaki zorunlu alanları, API doğrulamasını, hangi sorguların destekleneceğini ve eksik kademelerdeki fail-closed hata sözleşmesini kalıcı olarak belirler. `rw` tek başına izin verilirse salt-okuma sorgularının daha yüksek yetkili hesapla çalışması veya hiç çalışmaması için ayrıca net bir kural gerekir.
- Answer: Admin yalnızca üç bağlantı modundan birini seçebilir: `ro` (salt-okuma), `ro + rw` (okuma ve yazma) veya `ro + rw + ddl` (gelişmiş/DDL). `rw` ve `ddl` tek başına tanımlanamaz.
- Recorded in: `docs/specs/SPEC-0002-role-based-target-database-credentials.md`, `docs/adr/ADR-0005-role-based-target-database-credentials.md`

### OQ-2026-008: Sorgu ekranında hedef DB credential'ları kullanıcıya nasıl gösterilmeli?

- Status: Answered
- Raised: 2026-08-28
- Scope: `GET /api/database_information`, `DatabaseProvider.set_db_info`, Studio veritabanı seçici, SPEC-0002 §7
- Question: Sorgu çalıştıran son kullanıcıya, seçtiği hedef veritabanı için yalnız bağlantı modu/yetki rozeti mi (`RO`, `RO + RW`, `RO + RW + DDL`) gösterilmeli; yoksa kademe kullanıcı adları da (`app_ro`, `app_rw`) gösterilmeli mi?
- Why it matters: Bağlantı modu tek başına türetilmiş, hassas olmayan bir yetenek bilgisidir ve mevcut spec ile çelişmez. Kullanıcı adlarının response'a eklenmesi ise SPEC-0002 §7 ve ADR-0005'in "credential değerleri listeleme endpoint'lerine yazılmaz" kısıtını değiştirir; hedef DB hesap adları saldırgan için keşif bilgisi olduğundan spec ve ADR'nin güncellenmesi gerekir. Şifreler her iki durumda da response'a girmez.
- Answer: SQL editöründe yalnız yetki rozeti gösterilecek; credential değeri gönderilmeyecek. Rozet, kaydın bağlantı modu değil, kullanıcının o veritabanındaki **etkin yetkisi** olacak (mod ∩ kullanıcı rolü), böylece çalıştırıldığında reddedilecek bir yetenek vaat edilmez. Admin ekranı ayrı bir yüzeydir: kaydın hangi kademeleri sağladığını ve yönetim işlemlerini gösterir. Ek karar: admin, veritabanında tanımlı olmayan bir kademeyi kullanıcıya yetki olarak veremez; istek `400` ile reddedilir.
- Recorded in: `docs/specs/SPEC-0002-role-based-target-database-credentials.md`, `docs/adr/ADR-0005-role-based-target-database-credentials.md`

### OQ-2026-009: Admin sorguları hangi engellere takılmalı?

- Status: Answered
- Raised: 2026-08-28
- Scope: Adım 19 (`3.2.5`) admin bypass daraltması, Adım 20 (`3.4`) yıkıcı DML
  teyidi; `web_api/query_execution/services.py`, `HARD_BLOCKED_RISKS`
- Question: Veritabanı admin'i şu an yalnız `sql_injection_risk` ve
  `blocked_operation` risklerinde durduruluyor; `ddl_pattern`, `risky_pattern`
  ve `performance_risk` için onay gerekliliğini atlayıp sorguyu çalıştırıyor
  (atlama loglanıyor). Bu sınır doğru mu, yoksa admin'in de durdurulması
  gereken başka risk sınıfları var mı?
- Why it matters: Sınır iki yönde de bedelli. Genişletmek admin'i kendi hedef
  veritabanı hesabına yönlendirir ve o an WebQuery'nin audit kaydında hiçbir iz
  kalmaz. Daraltmak ise analizciyi bir rol için fiilen devre dışı bırakır.
  ADR-0016 mevcut sınırı bilinçli bir **ara durum** olarak kaydetti; Adım 20'de
  yıkıcı DML teyidi geldiğinde ölçüt kişiye bakmayacağı için bu istisnanın
  tamamen kalkması planlanıyor. Karar, Adım 20'nin kapsamını belirler.
- Answer: Admin yalnız `sql_injection_risk` ve `blocked_operation` sert
  bloklarında durdurulacak. `ddl_pattern`, `risky_pattern` ve
  `performance_risk` için mevcut admin bypass'ı korunacak; atlama log ve audit
  kaydında görünmeye devam edecek.
- Recorded in: `docs/adr/ADR-0016-analyzer-block-boundary.md`,
  `docs/specs/SPEC-0021-platform-owner-governance.md`

### OQ-2026-010: Satır sayımı ertelenirken yıkıcı DML teyidi nasıl davranmalı?

- Status: Answered
- Raised: 2026-08-29
- Scope: Adım 20 (`3.4`), `UPDATE`/`DELETE` sorgu akışı, backend API ve Studio
  teyit arayüzü
- Question: Etkilenecek satır sayısını önceden hesaplama ertelenirken
  `UPDATE`/`DELETE` için sorguya bağlı kısa ömürlü genel bir kullanıcı teyidi
  yine de uygulanmalı mı, yoksa yıkıcı DML teyidinin tamamı mı ertelenmeli?
- Why it matters: Genel teyit yanlışlıkla çalıştırmayı azaltır ancak kullanıcıya
  gerçek etki alanını göstermez ve kolayca alışkanlıkla onaylanan bir kapıya
  dönüşebilir. Teyidin tamamını ertelemek mevcut davranışı korur; buna karşılık
  satır sayımı gelene kadar ek insan-hatası bariyeri sağlamaz.
- Answer: Yıkıcı DML teyidinin tamamı ertelenecek. Satır sayımı olmadan genel
  bir `UPDATE`/`DELETE` teyidi uygulanmayacak; mevcut yetki, sert blok, audit ve
  admin bypass davranışı korunacak.
- Recorded in: `docs/specs/SPEC-0021-platform-owner-governance.md`

### OQ-2026-011: Platform yetkisi allowlist mi kalmalı, gerçek OWNER rolü mü olmalı?

- Status: Answered
- Raised: 2026-08-29
- Scope: Adım 20 (`3.4.4`), kullanıcı modeli, migration, platform yönetimi API
  ve arayüzü
- Question: Mevcut `PLATFORM_ADMINS` ortam değişkeni allowlist'i korunarak
  yalnız eksik platform yetki kontrolleri mi tamamlanmalı, yoksa şimdi kalıcı
  `is_platform_owner` veri modeli, ilk OWNER bootstrap komutu ve OWNER yönetim
  sözleşmesi mi uygulanmalı?
- Why it matters: Allowlist basit ve mevcut deployment sözleşmesiyle uyumludur
  ancak yetki değişiklikleri deploy gerektirir. Kalıcı OWNER rolü denetlenebilir
  ve uygulama içinden yönetilebilir; buna karşılık migration, bootstrap,
  self-escalation koruması ve daha geniş API/UI sözleşmesi gerektirir.
- Answer: Kalıcı `is_platform_owner` veri modeli ve ayrı OWNER modülü şimdi
  uygulanacak. İlk OWNER mevcut bir kullanıcıya yalnız sunucu tarafı bootstrap
  komutuyla verilecek; OWNER kullanıcı aktivasyonu, hedef veritabanı kaydı ve
  veritabanı ADMIN atamalarını yönetecek. OWNER olmak kendiliğinden sorgu
  çalıştırma (`ro`/`rw`/`ddl`) yetkisi vermeyecek.
- Recorded in: `docs/specs/SPEC-0021-platform-owner-governance.md`,
  `docs/adr/ADR-0017-persisted-platform-owner-boundary.md`

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

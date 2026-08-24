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

- Status: Deferred
- Raised: 2026-08-20
- Scope: merkezi erişim ve credential ADR'si; `web_api/database_provider/database.py` ve admin DB kayıt akışı
- Question: Runtime sorgu bağlantılarında yalnızca `CENTRAL_DB_USER/CENTRAL_DB_PASSWORD` mı kullanılmalı (mevcut `DatabaseProvider`), yoksa admin kaydında üretilip şifrelenen veritabanı başına `db_username/db_password` mı kullanılmalı?
- Why it matters: İki modelin yetki sınırı, credential rotasyonu, erişim izolasyonu ve veri modelindeki alanların anlamı farklıdır. Bu karar bilinmeden merkezi erişim ADR'si doğru yazılamaz.
- Answer: Karar daha sonra verilecek.
- Recorded in: User deferred the decision on 2026-08-24.

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

# ADR-0011: Onay kararları tek bir ortak servis üzerinden verilir

## Status

Accepted

## Context

Web ve Slack approval yolları önce `QueryData.status` değerini okuyup daha sonra
ORM nesnesini değiştirerek commit ediyor. İki yönetici aynı kaydı eşzamanlı
okuduğunda ikisi de `waiting_for_approval` görebiliyor ve son commit önceki
kararı sessizce ezebiliyor.

Bu değişiklikte belirleyici kriter veri bütünlüğüdür: bekleyen bir sorgu için
yalnızca ilk kararın uygulanması ve kaybeden kararın görünür bir çakışma olarak
raporlanması gerekir.

## Decision

Yeni `approval.service.decide()` fonksiyonu web ve Slack kararlarının tek iş
kuralı kaynağıdır. Yetki doğrulama, self-approval savunması, red gerekçesi,
koşullu durum geçişi, workspace/action log/audit güncellemeleri burada tek bir
transaction içinde yapılır.

Durum geçişi `QueryData.id` ile mevcut durumunu birlikte filtreleyen koşullu bir
SQLAlchemy `UPDATE` ifadesiyle yapılır:

```sql
UPDATE QueryData
SET status = :new_status
WHERE id = :query_id
  AND status = 'waiting_for_approval'
```

`rowcount == 1` başarı, başka bir sonuç ise çakışma olarak kabul edilir ve
`APPROVAL_CONFLICT` / HTTP 409 döndürülür. Web ve Slack yalnızca aktörü, karar
türünü ve transport'a özgü kullanıcı yanıtını sağlar.

## Rejected Alternatives

### 1. Python tarafında önce `SELECT`, sonra `if`, sonra `UPDATE`

Okuma ile yazma arasında yarış penceresi bıraktığı için iki istek de kontrolü
geçebilir. Bu nedenle TOCTOU problemi devam eder.

### 2. `SELECT ... FOR UPDATE`

Doğru transaction kapsamıyla çalışabilir; ancak kilit davranışı ve sözdizimi
desteklenen veritabanına göre değişir. Bu akışta tek koşullu `UPDATE` daha az
round-trip ve daha küçük bir stale-nesne yüzeyi sağlar.

### 3. Web ve Slack için ayrı karar implementasyonları

İki yüzeyin kendi koşullu `UPDATE` ve audit mantığını tutması kısa vadede küçük
bir diff üretir; ancak davranışların zamanla ayrışmasına ve bir yüzeydeki
güvenlik düzeltmesinin diğerinde unutulmasına yol açar.

## Consequences

- İlk kararın kazanması veritabanı tarafından garanti edilir.
- Web ve Slack karar politikası tek bir fonksiyonda tutulur.
- Kaybeden istek kullanıcıya açık bir çakışma döndürür; istemci yenileme mesajı
  gösterebilir.
- Red gerekçesi ve karar metadatası `QueryData` üzerine Alembic migration'ıyla
  eklenir.
- `rowcount` davranışı SQL Server sürücüsü ve `NOCOUNT` ayarlarıyla üretimde
  doğrulanmalıdır.
- Her iki transport yolu aynı davranışı korumak zorundadır.

## Accepted Risks

- SQLite testleri gerçek üretim satır kilidi davranışını tam olarak temsil etmez;
  üretim motorunda eşzamanlılık testi ayrıca yapılmalıdır.
- Bu ADR yeni bir audit event tablosu veya migration altyapısı tanımlamaz.

## References

- Spec: `docs/specs/SPEC-0013-approval-concurrency.md`
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 10 (`1.2`)
- Supersedes / Superseded by: yok

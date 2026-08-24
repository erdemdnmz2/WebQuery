# ADR-0011: Onay kararlarında koşullu UPDATE kullanılır

## Status

Proposed

## Context

Web ve Slack approval yolları önce `QueryData.status` değerini okuyup daha sonra
ORM nesnesini değiştirerek commit ediyor. İki yönetici aynı kaydı eşzamanlı
okuduğunda ikisi de `waiting_for_approval` görebiliyor ve son commit önceki
kararı sessizce ezebiliyor.

Bu değişiklikte belirleyici kriter veri bütünlüğüdür: bekleyen bir sorgu için
yalnızca ilk kararın uygulanması ve kaybeden kararın görünür bir çakışma olarak
raporlanması gerekir.

## Decision

Onay ve red geçişleri `QueryData.id` ile mevcut durumunu birlikte filtreleyen
koşullu bir SQLAlchemy `UPDATE` ifadesiyle yapılır:

```sql
UPDATE QueryData
SET status = :new_status
WHERE id = :query_id
  AND status = 'waiting_for_approval'
```

`rowcount == 1` başarı, başka bir sonuç ise çakışma olarak kabul edilir ve
`APPROVAL_CONFLICT` / HTTP 409 döndürülür. Workspace ve ActionLogging yan
etkileri aynı transaction içinde tutulur. Aynı kural Slack yolunda da uygulanır.

## Rejected Alternatives

### 1. Python tarafında önce `SELECT`, sonra `if`, sonra `UPDATE`

Okuma ile yazma arasında yarış penceresi bıraktığı için iki istek de kontrolü
geçebilir. Bu nedenle TOCTOU problemi devam eder.

### 2. `SELECT ... FOR UPDATE`

Doğru transaction kapsamıyla çalışabilir; ancak kilit davranışı ve sözdizimi
desteklenen veritabanına göre değişir. Bu akışta tek koşullu `UPDATE` daha az
round-trip ve daha küçük bir stale-nesne yüzeyi sağlar.

## Consequences

- İlk kararın kazanması veritabanı tarafından garanti edilir.
- Kaybeden istek kullanıcıya açık bir çakışma döndürür; istemci yenileme mesajı
  gösterebilir.
- `rowcount` davranışı SQL Server sürücüsü ve `NOCOUNT` ayarlarıyla üretimde
  doğrulanmalıdır.
- Her iki transport yolu aynı davranışı korumak zorundadır.

## Accepted Risks

- SQLite testleri gerçek üretim satır kilidi davranışını tam olarak temsil etmez;
  üretim motorunda eşzamanlılık testi ayrıca yapılmalıdır.
- Bu ADR yeni bir audit event tablosu veya migration altyapısı tanımlamaz.

## References

- Spec: `docs/specs/SPEC-0012-approval-concurrency.md`
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 10 (`1.2`)
- Supersedes / Superseded by: yok

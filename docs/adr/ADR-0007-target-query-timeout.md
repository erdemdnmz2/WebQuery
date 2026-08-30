# ADR-0007: Hedef sorgularda teknolojiye uygun timeout kullanımı

## Status

Accepted

## Context

Hedef veritabanı sorgularında mevcut `pool_timeout` yalnızca connection pool'dan
bağlantı alma süresini, bağlantı dizesindeki `connection timeout` ise ilk
bağlantı kurma süresini sınırlar. Bunların hiçbiri bir SQL statement'ının ne
kadar çalışabileceğini sınırlamaz. Pahalı bir sorgu bu nedenle bağlantıları ve
async worker'ları uzun süre tüketebilir.

## Decision

Hedef sorgular için merkezi `QUERY_TIMEOUT_SECONDS` ayarı kullanılacak ve
varsayılan 300 saniye olacaktır. Timeout, SQL metni değiştirilmeden SQLAlchemy
engine/session katmanına uygulanacaktır:

- MSSQL: driver `timeout` argümanı.
- PostgreSQL: asyncpg `command_timeout`, ayrıca server-side
  `statement_timeout` ve idle transaction timeout.
- MySQL: bağlantı sonrası `SET SESSION max_execution_time`.

`EngineCache.get_engine()` teknolojiye uygun `connect_args` alır ve bunu
`create_async_engine()` çağrısına aktarır.

## Rejected Alternatives

### 1. SQL sorgusuna `LIMIT` veya `TOP` eklemek

Bu, sorgunun hesaplama maliyetini veya DML işlemlerini doğru şekilde
sınırlamaz; ayrıca kullanıcı SQL'ini değiştirir ve farklı motorlarda uyumluluk
sorunları doğurur.

### 2. Yalnızca `pool_timeout` kullanmak

Bu ayar sorgu süresini değil, pool'dan bağlantı bekleme süresini sınırlar.

### 3. Yalnızca istemci tarafı timeout kullanmak

İstemci bağlantıyı kesebilse de bazı motorlarda sunucu tarafındaki statement'ın
sonlandırılması garanti edilmez. Desteklenen motorlarda server-side sınır da
kullanılmalıdır.

## Consequences

- Uzun süren hedef sorgular kontrollü biçimde kesilir.
- Timeout davranışı veritabanı driver'ına göre farklı teknik mekanizmalarla
  uygulanır.
- Engine cache mevcut olduğundan timeout değeri cache yaşam döngüsü boyunca
  sabittir; konfigürasyon değişikliği için engine'lerin yeniden oluşturulması
  gerekir.
- Gerçek MSSQL/PostgreSQL/MySQL sunucularında timeout entegrasyon testi ayrıca
  yapılmalıdır.

## Accepted Risks

- MSSQL tarafında uygulanan driver timeout'unun sunucu statement'ını her
  durumda server-side bir ayar kadar kesin sonlandırdığı varsayılmaz; üretim
  ortamında gerçek sorgu testi ve bağlantı temizliği izlenmelidir.

## References

- Spec: `docs/specs/SPEC-0004-target-query-timeout.md`
- Supersedes / Superseded by: Yok

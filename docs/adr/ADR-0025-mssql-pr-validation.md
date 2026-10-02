# Trade-off Tablosu

Senaryo: WebQuery metadata veritabanı MSSQL'dir, fakat mevcut otomatik suite
yalnız SQLite üzerinde çalışır. Migration ve kritik metadata akışlarının gerçek
SQL Server'da ne sıklıkta doğrulanacağı seçilmelidir.

Baştan tahmininizce en belirleyici kriter: MSSQL'e özgü migration veya veri
tipi hatasının birleştirilmeden önce yakalanması.

| Kriter | 1. Her PR'da seçilmiş MSSQL smoke | 2. Yalnız nightly MSSQL | 3. Yalnız SQLite/static derleme |
| --- | --- | --- | --- |
| Hata yakalama gecikmesi | Birleştirmeden önce | Bir sonraki gece veya sonrası | Üretime kadar kaçabilir |
| CI süresi | Orta; dar test seçimi | Düşük PR maliyeti | Düşük |
| MSSQL güveni | Migration + kritik akış kanıtı | Gecikmeli kanıt | Gerçek çalışma kanıtı yok |
| Operasyonel karmaşıklık | ODBC ve servis konteyneri | Aynı, daha seyrek kullanılır | Düşük ama risk yüksek |

## Karar

Seçilen alternatif: 1. Her PR'da seçilmiş MSSQL smoke.

Gerekçe: Metadata veritabanı birincil MSSQL ortamıdır; migration veya tip
farkının merge sonrasında bulunması kabul edilemez. Tam suite'i ikinci kez
çalıştırmak yerine migration, schema guard ve yüksek etkili metadata akışları
çalıştırılır.

# ADR-0025: Her PR'da geçici MSSQL doğrulaması

## Status

Accepted (2026-09-24)

## Context

SQLite unit/integration testleri hızlıdır ancak `UNIQUEIDENTIFIER`,
`DATETIME2`, `NVARCHAR`, SQL Server introspection ve migration DDL davranışını
kanıtlamaz. Özellikle yeni migration'lar MSSQL'e hiç uygulanmadan teslim
edilmiştir.

## Decision

CI, GitHub-hosted Ubuntu runner üzerinde geçici SQL Server 2022 servis
konteyneri başlatacaktır. Job, ODBC Driver 18'i yükler; yalnız `webquery_ci`
adlı boş veritabanını sıfırlayan korumalı smoke test ile Alembic head'i uygular
ve schema guard/tip kontrolünü çalıştırır. Ardından login/session,
OWNER/DB ADMIN, audit, database lifecycle ve query execution için seçilmiş
entegrasyon testlerini MSSQL metadata veritabanına karşı koşturur.

## Rejected Alternatives

### 1. Yalnız nightly MSSQL

PR CI süresini düşürür, fakat merge edilen kırık migration'ın fark edilmesini
bir gün geciktirir ve geri alma maliyetini artırır.

### 2. Yalnız SQLite ve MSSQL SQL derlemesi

Hızlıdır fakat gerçek ODBC bağlantısı, DDL yürütümü ve inspector davranışını
kanıtlamaz.

## Consequences

- CI süresine bir SQL Server servis job'ı eklenir; job 20 dakika ile sınırlıdır.
- Test reseti yalnız sentinel ve sabit geçici DB adıyla güvenli hale getirilir.
- Staging backup/restore tatbikatı hâlâ canlıya benzer, yetkili ortamda
  yapılacak operasyonel bir süreçtir.

## Accepted Risks

- CI service image etiketi SQL Server 2022 sürüm hattında güncellenebilir;
  uygulamanın desteklediği ana sürüm değişmez. Deployment image pinleme bu
  kararın değil, ertelenmiş deployment paketinin kapsamındadır.
- Geçici CI parolası workflow içinde görünürdür; yalnız disposable SQL Server
  konteynerine aittir ve herhangi bir deployment sırrı değildir.

## References

- Spec: `docs/specs/SPEC-0030-mssql-migration-validation.md`
- Supersedes / Superseded by: Yok

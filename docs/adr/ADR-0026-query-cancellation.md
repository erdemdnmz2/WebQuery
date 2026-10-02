# Trade-off Tablosu

Senaryo: Hedef SQL'i kullanıcı isteğiyle durdurma, çok worker ve tier hesapları.
Belirleyici kriter: yalnız doğru sorguyu gerçek hedefte durdurmak.

| Kriter | Redis sinyali + hedef sürücü | Process-local task.cancel | DBA KILL oturumu |
| --- | --- | --- | --- |
| Farklı worker | Desteklenir | Desteklenmez | Ek registry gerekir |
| MSSQL'de çalışan SQL | SQLCancel | Thread'deki SQL sürebilir | Durdurur |
| Yetki | Mevcut tier hesabı | Mevcut tier hesabı | Ayrı yüksek yetki |
| Havuz yarışları | Seal + watcher cleanup | Sürücüye bağımlı | Yanlış oturum riski |

## Karar

Redis sinyali + hedef sürücü iptali.

# ADR-0026: Kullanıcıya ait hedef sorgunun iptali

## Status

Proposed

## Context

Tarayıcı isteğini veya aioodbc coroutine'ini iptal etmek SQL Server'daki
çalışmayı durdurma garantisi vermez. İptal HTTP isteği başka worker'a gidebilir.

## Decision

Mevcut Redis'te authenticated user/execution UUID ile kapsanan TTL'li durum
saklanır. Execution context yalnız hedef session'a driver iptal callback'i
bağlar. MSSQL cursor.cancel ayrı thread'de çağrılır; PostgreSQL/MySQL için
aynı tier hesabıyla kısa ömürlü ayrı kontrol bağlantısı kullanılır. İstemciden
oturum ID'si alınmaz. Commit öncesi seal iptal kabulünü atomik kapatır;
watcher sonlanmadan hedef bağlantı havuza dönmez. Metadata/audit işlemleri
iptal edilmez. Var olan Redis altyapısı yeniden kullanılır.

## Rejected Alternatives

### 1. Yalnız AbortController / task.cancel

Tarayıcı beklemesini keser; MSSQL executor thread'indeki SQL devam edebilir.

### 2. MSSQL KILL ile privileged kontrol hesabı

DBA yetkisi ve yeni credential sınırı gerektirir; tier izolasyonuyla uyuşmaz.

## Consequences

- Her aktif iptal edilebilir sorgu Redis durumunu kısa aralıkla okur.
- Execution ID'siz eski API çağrıları ek Redis trafiği oluşturmaz.
- İptal isteği kabulü ile SQL'in sonlanması ayrı durumlardır.
- Commit sonrası ve DB'nin otomatik commit ettiği değişiklikler geri alınamaz.

## Accepted Risks

- Hedef veya Redis arızasında iptal anında tamamlanamayabilir. Ekran sonuç
  isteğini takip eder; iptal tamamlanmış gibi göstermez. Hedef timeout korunur.
- Sürücü/DB davranışı gerçek hedef servis testleriyle ayrıca kanıtlanmalıdır.
- MSSQL cursor erişimi SQLAlchemy/aioodbc adapter iç yapısına bağlıdır;
  sürücü güncellemesinde gerçek MSSQL iptal testi zorunlu regresyon kapısıdır.

## References

- Spec: `docs/specs/SPEC-0031-query-cancellation.md`
- Supersedes / Superseded by: Yok
- [pyodbc cursor.cancel, ayrı thread sözleşmesi](https://github.com/mkleehammer/pyodbc/blob/master/src/pyodbc.pyi)
- [PostgreSQL pg_cancel_backend yetki sınırı](https://www.postgresql.org/docs/17/functions-admin.html)
- [MySQL KILL QUERY ve aynı hesap sınırı](https://dev.mysql.com/doc/refman/8.0/en/kill.html)

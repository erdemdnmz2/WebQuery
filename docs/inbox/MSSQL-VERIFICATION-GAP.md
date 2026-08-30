# Testler ve migration'lar hiç MSSQL'e karşı çalışmadı

**Durum:** Inbox / uygulanacak iş
**Kaydedildi:** 2026-08-30
**Kapsam:** `web_api/tests/`, `web_api/migrations/versions/`,
`.github/workflows/ci.yml`
**Kaynak:** `webquery_denetim_raporu.md` P2-16; `docs/adr/ADR-0002` 2026-08-30
güncellemesi
**Kardeş kayıt:** `CI-SIGNAL-AND-VERIFICATION-GAPS.md` — aynı "CI'nın
doğrulamadığı davranış" sınıfının frontend ve tarama-sinyali tarafı

WebQuery'nin birincil hedefi ve varsayılan metadata veritabanı MSSQL. Tüm
otomatik doğrulama ise SQLite'a karşı çalışıyor
(`sqlite+aiosqlite:///:memory:`). Bu, projenin kendi bilinen boşluğu; bu kayıt
onu ve 2026-08-30 düzeltmesiyle **büyüyen** kısmını takip eder.

## Doğrulanmayan davranış

| Alan | SQLite'ta | MSSQL'de |
| --- | --- | --- |
| `AppNVarChar` / `AppText` | düz `String`/`Text` | `NVARCHAR`, `TEXT` — uzunluk ve collation davranışı farklı |
| `AppDateTime` | `DATETIME` | `DATETIME2(7)` — hassasiyet farkı; süre hesaplarını etkiler |
| `AppUUID` | `String(36)` | `UNIQUEIDENTIFIER` — ORM `uuid.UUID` nesnesi döndürür, string değil |
| Statement timeout | yok | pyodbc `Connection.timeout` (ADR-0007, P1-4 düzeltmesi) |
| Satır değerli `IN` | destekleniyor | **desteklenmiyor** |
| Unique kısıt ihlali | `IntegrityError` | farklı hata sınıfı ve mesaj |

Satır değerli `IN` maddesi teorik değil: `workspaces/services.py` içindeki
workspace listeleme sorgusu bu yüzden `tuple_(...).in_(...)` yerine iki ayrı
`IN` kullanıyor. Karar doğru ama SQLite bunu hiçbir zaman doğrulayamaz —
yanlış yazılsaydı testler yine yeşil olurdu.

## Migration'lar

2026-08-30 düzeltmesi üç migration ekledi ve **hiçbiri MSSQL'de
çalıştırılmadı**:

| Revizyon | Ne yapıyor | Risk |
| --- | --- | --- |
| `a1b2c3d4e5f6` | `BlacklistedTokens` tablosunu düşürür; `MaskingRule` üzerine `(database_id, table_name, column_name)` unique kısıtı ekler | Tablo düşürme geri alınamaz. Unique kısıt, mevcut veride çift kayıt varsa başarısız olur — MSSQL'in hata davranışı SQLite'ınkinden farklı |
| `b2c3d4e5f6a7` | `Databases` tablosuna `is_active`, `retired_at`, `retired_by` ekler | `server_default` ile `NOT NULL` sütun ekleme MSSQL'de tablo kilidi alır; büyük tabloda süre alır |
| `e4b1c7a09d52` | (mevcut) şema kayması onarımı, bu turda düzenlendi | — |

Bunlar `tests/unit/test_baseline_migration.py` tarafından SQLite'a karşı
sınandı; bu, revizyon zincirinin tutarlılığını doğrular, MSSQL'de
çalışacaklarını değil.

## Yapılacak

### 1. Deploy öncesi provası (acil, tek seferlik)

Bir staging MSSQL örneğine üretim şemasının kopyasını al ve
`alembic upgrade head` çalıştır. Özellikle:

- `a1b2c3d4e5f6`'nın unique kısıt adımı: önce
  `SELECT database_id, table_name, column_name, COUNT(*) FROM MaskingRules
  GROUP BY 1,2,3 HAVING COUNT(*) > 1` ile çift kayıt olup olmadığına bak.
- Migration süresi ve kilit davranışı ölç.
- `common/schema_guard.py`'nin açılış doğrulamasının geçtiğini gör.

Bu madde CI işinden bağımsız ve ondan önce yapılmalı.

### 2. MSSQL servis konteynerli CI job'ı (kalıcı çözüm)

GitHub Actions `services:` bloğuyla `mcr.microsoft.com/mssql/server:2022-latest`
ayağa kaldırılıp entegrasyon testlerinin bir alt kümesi ona karşı
çalıştırılabilir. Dikkat noktaları:

- Konteynerin hazır olmasını beklemek gerekir; `web_api/wait_for_db.py`
  zaten bunun için var ve doğru çıkış kodu döndürüyor.
- Tüm suite'i iki kez çalıştırmak CI süresini ikiye katlar. Muhtemelen doğru
  kapsam: migration'lar + tip davranışına dokunan entegrasyon testleri, tüm
  birim testleri değil.
- Nightly mi her PR'da mı olacağı ayrı bir karar. Denetim nightly öneriyor.

Bu, ADR-0002'nin kapsamını genişletir; uygulanırsa ADR güncellenmeli.

## Neden bu turda yapılmadı

Denetim düzeltmesi zaten 116 dosya ve 15 commit'ti. MSSQL'li bir CI job'ı
kendi başına bir altyapı işi: servis konteyneri, hazırlık bekleme, test
kapsamı seçimi ve süre bütçesi kararı içeriyor. ADR-0002'nin güncellemesinde
kabul edilen risk olarak kaydedildi ve README'nin "Testing" bölümünde
kullanıcıya görünür bir boşluk olarak yazıldı — gizlenmedi, ertelendi.

## Teslim kontrolü

- 1. madde için: `alembic upgrade head` çıktısı, şema doğrulamasının sonucu ve
  ölçülen süre handoff'a yazılır.
- 2. madde için: ADR-0002 güncellenir, CI job'ının hangi testleri kapsadığı
  ve neden o alt kümenin seçildiği kaydedilir.

# Mini-Spec: Gerçek MSSQL migration ve kritik akış doğrulaması

## 1. Spec Kartı

- Özellik: MSSQL migration validation
- Durum: Implemented — yerel gerçek MSSQL ve 4143c92 GitHub Actions koşusu geçti
- Versiyon: 2026-09-24
- Tarih: 2026-09-24
- Sahip: WebQuery engineering

## 2. Amaç ve Başarı Sinyali

### Amaç

SQLite testlerinin kapsamadığı gerçek SQL Server DDL, tip, introspection ve
uygulama metadata davranışını her PR'da doğrulamak.

### Başarı Sinyali

- Boş bir MSSQL veritabanına `alembic upgrade head` uygulanır.
- Alembic head, şema sözleşmesi, `UNIQUEIDENTIFIER` ve `NVARCHAR` garantileri
  gerçek MSSQL introspection'ı ile doğrulanır.
- Login/session, OWNER/DB ADMIN, audit, hedef veritabanı yaşam döngüsü ve
  sorgu audit yazımı için seçilmiş entegrasyon testleri MSSQL'de geçer.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- GitHub Actions üzerinde geçici SQL Server 2022 servis konteyneri.
- Boş CI veritabanının güvenli biçimde yeniden oluşturulması ve migration
  zincirinin çalıştırılması.
- Şema guard, migration head ve MSSQL'e özgü tip smoke testleri.
- Kritik metadata akışlarını kapsayan seçilmiş mevcut entegrasyon testleri.

### Kapsam Dışı

- Üretim veya müşteri veritabanına CI erişimi.
- Gerçek müşteri backup'ının restore edilmesi; bu yalnız yetkili staging
  ortamında runbook ile yapılır.
- Hedef müşteri veritabanlarında sorgu çalıştırma performans/tuning testi.

## 4. Sözleşme

- `MSSQL_TEST_URL`, yalnız CI'ın geçici `webquery_ci` veritabanını gösterebilir.
- MSSQL destructive hazırlık testi, `MSSQL_CI=1` ve `webquery_ci` veritabanı
  adı olmadan çalışmayı reddeder.
- Uygulama metadata bağlantısı için `mssql+aioodbc` URL'si kullanılır; Alembic
  bunu mevcut sözleşme gereği `mssql+pyodbc`'ye çevirir.

## 5. İş Kuralları

### BR-01: Migration gerçek boş MSSQL üzerinde başlar

Her MSSQL CI çalışması, yalnız geçici `webquery_ci` veritabanını silip yeniden
oluşturur ve şema kurulumunu yalnız Alembic ile yapar.

### BR-02: Runtime testleri migration kanıtını ikame etmez

Runtime entegrasyon testleri MSSQL davranışını sınar; migration testinin
Alembic head ve `verify_schema()` kontrolleri ayrıca başarıyla tamamlanmalıdır.

### BR-03: CI müşteri verisine dokunmaz

CI yalnız kendine ait geçici SQL Server servis konteynerini kullanır. Başka bir
veritabanı adı veya CI sentinel'ı yoksa reset işlemi hata verir.

## 6. Acceptance Criteria

- AC-01: Given boş `webquery_ci`, when migration smoke testi çalışırsa, then
  `alembic upgrade head` başarıyla biter ve version tablosu güncel head'i taşır.
- AC-02: Given migrate edilmiş MSSQL şeması, when schema guard çalışırsa, then
  eksik index, unique veya NOT NULL garantisi raporlamaz.
- AC-03: Given migrate edilmiş MSSQL şeması, when inspector tipleri okunursa,
  then `QueryData.uuid` `UNIQUEIDENTIFIER`, `Workspaces.name` ve
  `Workspaces.description` `NVARCHAR` olur.
- AC-04: Given MSSQL CI job'ı, when seçilmiş login, RBAC, audit, database
  lifecycle ve query execution testleri çalışırsa, then tamamı geçer.
- AC-05: Given yanlış/eksik CI koruması veya `webquery_ci` dışında bir isim,
  when destructive test hazırlığı çağrılırsa, then reset işlemi reddedilir.

## 7. Teknik ve Güvenlik Kısıtları

- CI parolası yalnız geçici servis konteyneri içindir; üretim sırrı değildir.
- ODBC Driver 18 ile TLS sertifika doğrulama istisnası yalnız localhost CI
  konteyneri URL'sinde `TrustServerCertificate=yes` olarak uygulanır.
- Job başına en fazla 20 dakika; tüm SQLite paketi MSSQL'de ikinci kez
  çalıştırılmaz.

## 8. Open Questions

Yok.

## 9. Done Kontrolü

- [x] Migration/smoke testi eklendi
- [x] Seçilmiş MSSQL entegrasyon akışları eklendi
- [x] CI servis konteyneri ve ODBC kurulumu eklendi
- [x] Staging backup/restore runbook'u eklendi
- [x] Yerel doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı
- [x] GitHub Actions'ta gerçek MSSQL servis koşusu görüldü (run 37053373074, commit 4143c92)

### 2026-10-02 doğrulama ve regresyon düzeltmeleri

- Gerçek SQL Server 2022 / ODBC Driver 18 ile boş `webquery_ci` üzerine tüm
  migration zinciri, güncel head, schema guard, UNIQUEIDENTIFIER ve NVARCHAR
  kontrolleri geçti. Ortam mevcut uygulamadan ayrı geçici Docker servisleridir.
- ODBC kurulumunda ikinci, Signed-By'sız apt kaynağı oluşturma kaldırıldı;
  Microsoft'un canonical `packages-microsoft-prod.deb` kurulumu kullanılıyor.
- Migration subprocess URL'si parolayı gizleyen `str(URL)` yerine yalnız
  process ortamına açık URL taşır; URL loglanmaz. Alembic ConfigParser'da `%`
  kaçışları korunur; public migration CLI için regresyon testi eklendi.
- MSSQL'in desteklemediği unique-constraint reflection yerine unique backing
  index fallback'i kullanılır. Aktif kayıt/OWNER filtrelerinde MSSQL'de
  geçersiz `IS 1` yerine portable boolean equality kullanılır; yetki ve
  emeklilik kuralları değişmez.
- Mevcut test verileri geçerli UUID ve JSON string UUID kullanacak şekilde
  düzeltildi. Test-only ODBC ikinci havuzu kapatıldı; SQLAlchemy havuzları
  açık kalır, geçici hedef hesabı test sonunda temizlenebilir.
- Sorgu iptali ve ona ait Redis/test seçimi `feat/query-cancellation` branchine
  ayrıldı. `security-validation-hardening` branchi yalnız bağımlılık güvenliği,
  MSSQL migration doğrulaması ve bunları destekleyen uyumluluk/regresyon
  düzeltmelerini içerir. Feature branch bu ortak tabanı devralır; ayrıca gerçek
  Redis servisini ve `tests/mssql/test_target_cancellation.py` ile
  `tests/integration/test_query_cancellation_api.py` CI seçimini içerir.

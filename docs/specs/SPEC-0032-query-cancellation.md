# SPEC-0032: Hedef veritabanındaki sorguyu iptal etme — mevcut uygulama kaydı

## 1. Spec Kartı

- Özellik: Query cancellation
- Durum: Implemented; gerçek MSSQL ve Redis doğrulandı
- Versiyon: 2026-10-02
- Tarih: 2026-10-02
- Sahip: WebQuery engineering

## 2. Amaç ve Başarı Sinyali

### Amaç

Kullanıcı çalışan sorgusunu hedef veritabanında durdurabilsin.

### Başarı Sinyali

İptal isteği hedef sürücüye ulaşır; sonuç isteği sorgu sonlanıp transaction
temizlendikten sonra `QUERY_CANCELLED` döner ve audit başarısız/iptal kaydı taşır.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- Studio, RunWorkspace ve hedefte sorgu çalıştıran yönetici önizlemesi.
- Yalnız çalıştıran kullanıcının kendi execution UUID'sini iptal etmesi.
- MSSQL, PostgreSQL ve MySQL için hedef bağlantının sorgusunu durdurma.

### Kapsam Dışı

- Navbar'da çalışan sorgular listesi (inbox'a kaydedildi).
- Yeni form/dialog iptal butonları; mevcut Vazgeç butonları korunur.
- Başka kullanıcıların sorgularını veya sunucu oturumlarını yönetme.

## 4. Sözleşme

Mevcut execute_query, execute_workspace ve execute_for_preview istekleri
opsiyonel `execution_id: UUID` kabul eder. Eski istemciler çalışmaya devam eder.
Frontend her çalıştırma için yeni UUID üretir.

`POST /api/query_executions/{execution_id}/cancel` kimlik doğrulamalıdır.
İptal rotası mevcut query execution rate-limit ayarını kullanır (`429`).
Yanıt `202 {status: "cancelling"}` yalnız isteğin kabul edildiğini bildirir.
Başkasının/olmayan execution'ı `404`, bitmiş/commit aşamasındaki execution
`409`, Redis erişilemezliği `503` döner. İptal edilen özgün çalıştırma isteği
`409 QUERY_CANCELLED` döner. İptal tamamlandı bildirimi bu yanıttan üretilir.

## 5. İş Kuralları

### BR-01: Sahiplik

İptal anahtarı authenticated user ID ve execution UUID ile kapsanır. İstemci
DB oturum ID'si, credential, SQL veya başka kullanıcı ID'si gönderemez.

### BR-02: Gerçek hedef iptali

MSSQL SQLCancel; PostgreSQL pg_cancel_backend; MySQL KILL QUERY kullanır.
Kontrol bağlantısı mevcut seçilmiş tier hesabını kullanır. MSSQL KILL veya
yeni DBA/processadmin yetkisi talep edilmez.

### BR-03: Transaction ve yarış

İptal sinyali SQL başlarken veya çalışırken kabul edilir. Commit öncesi atomik
seal işlemi iptal ile commit yarışını kapatır. İptal kabul edilmişse rollback;
seal geçmişse yeni iptal isteği reddedilir. İptal worker'ı hedef bağlantı
havuza dönmeden tamamlanır. DDL'nin DB'ye özgü otomatik commit'i ve SQL
içindeki açık COMMIT gibi daha önce commitlenmiş değişiklikler geri alınamaz.

### BR-04: Tasarım ve doğru geri bildirim

Mevcut secondary Button, tema token'ları ve Türkçe `İptal et` etiketi kullanılır.
Buton yalnız sorgu çalışırken görünür. Kabul sonrası `İptal ediliyor…` durumu
gösterilir; sorgu sonucu gelene kadar çalıştırma kilidi kalkmaz. İptal bir hata
veya onay bekleme durumu gibi gösterilmez. İptal isteği hatası ekran içinde
gösterilir; özgün sorgu takibi devam eder. Çift çalıştırma engellenir.

## 6. Acceptance Criteria

- AC-01: Given çalışan hedef SQL, when sahibi iptal isterse, then yalnız o
  SQL için sürücü iptali çağrılır ve özgün istek QUERY_CANCELLED döner.
- AC-02: Given başka kullanıcı UUID'si, when iptal isterse, then 404 ve hedef
  iptal çağrısı yoktur.
- AC-03: Given iptal kabul edilmiş yazma, when hedef blok sonlanırsa, then
  rollback yapılır, commit yapılmaz ve audit QUERY_CANCELLED taşır.
- AC-04: Given tamamlanmış/seal edilmiş çalışma, when iptal istenirse, then
  404/409; yeni veya havuza dönmüş bağlantıya iptal uygulanmaz.
- AC-05: Given farklı worker registry'leri, when iptal istenirse, then Redis
  sinyali çalıştıran worker tarafından görülür; TTL ve cleanup kaynak bırakmaz.
- AC-06: Given üç sorgu yüzeyi, when sorgu çalışırsa, then temalı İptal et
  görünür; sonuç gelmeden bekleme kalkmaz; başka yüzeylere buton eklenmez.
- AC-07: Given execution_id'siz eski istek, then mevcut davranış korunur.

## 7. Teknik ve Güvenlik Kısıtları

- Mevcut audit, masking, onay, risk ve credential tier denetimleri korunur.
- SQLCancel yalnız mevcut hedef cursor'a, kontrol SQL'i yalnız backend'de
  yakalanan tam sayı oturum ID'sine uygulanır.
- Redis yalnız execution durumu taşır; SQL ve secret içermez.
- İptal hedef SQL'in sonucunu bekler; tarayıcı AbortController kullanılmaz.

## 8. Open Questions

OQ-2026-022 yanıtlandı. Branch taşıması yeni davranış kararı içermez.

### SPEC-0031 ile ilişki

Bu belge 4143c92'deki uygulamayı kaydeder; önceki
`SPEC-0031-live-query-cancellation.md`, `ADR-0026-live-query-cancellation.md`
ve `PLAN-0031-live-query-cancellation.md` taslağının tamamlandığı anlamına gelmez.
2026-10-02 branch taşıması sırasında önceki belgeler ve OQ-2026-021 kararı
korundu; bunlar superseded/accepted olarak değiştirilmedi.

Mevcut API body UUID kullanır, state GET ucu yoktur ve Redis polling uygular.
Önceki taslak header UUID, state GET, local-first cancel ve Pub/Sub/batch routing
önerir. Özellikle OQ-2026-021'in tüm yeni sorgular için fail-closed ve Redis
arızasında mevcut local handle iptali şartları mevcut uygulamayla tam karşılanmaz:
ID'siz eski çağrılar registry'yi atlar, cancel ise Redis'e bağımlıdır.
Bu farkları gidermek branch taşımasının kapsamı dışındadır; önceki kullanıcı
kararını değiştirme veya bu taslağın tamamlandığını ilan etme yetkisi verilmedi.
Gerçek PostgreSQL/MySQL doğrulaması da halen eksiktir.

## 9. Done Kontrolü

- [x] Acceptance criteria testleri eklendi; gerçek MSSQL/Redis iptal ve rollback kanıtı alındı
- [x] Güvenlik/değişiklik incelemesi
- [x] ADR-0027 (Proposed uygulama kaydı; önceki ADR-0026'yı supersede etmez)
- [x] Backend pytest ve frontend doğrulamaları; handoff

### Test eşlemesi ve doğrulama sınırı

- AC-01/04/05/07: `tests/unit/test_query_cancellation.py`; MSSQL cursor
  iptali ayrı thread'de, PostgreSQL/MySQL aynı hesapla kontrollü oturum ID'si,
  farklı registry/worker, seal ve eski API davranışı.
- AC-02/03: `tests/integration/test_query_cancellation_api.py`; gerçek auth
  middleware üzerinden sahiplik, üç yürütme rotasında bekleme/409 ve audit.
- AC-01/03/04/05: `tests/mssql/test_target_cancellation.py`; gerçek WAITFOR'un
  5 saniye içinde kesilmesi, ayrı Redis istemcisinden iptal, yazmanın rollback'i
  ve aynı tek bağlantılı havuzun tekrar kullanımı. Ek HTTP testi gerçek
  DatabaseProvider, hedefte yalnız SELECT/UPDATE yetkili hesap (sysadmin ve
  processadmin değil), kilitte bekleyen iki yazmalı batch, QUERY_CANCELLED audit
  ve sonraki API sorgusuyla rollback/bağlantı tekrar kullanımını doğrular.
- AC-06: Sentetik API sunucusuyla tarayıcı kontrolü: üç yüzey, light/dark,
  Enter ile iptal, 202 sonrası bekleme, 503 sonrası hata/yeniden deneme ve
  sonuçtan sonra butonun kaldırılması. Frontend otomatik test runner'ı yok;
  bu kontrol bir frontend unit-test sonucu değildir.
- Docker'da mevcut uygulamadan ayrı, host portu açmayan geçici SQL Server 2022
  ve Redis 7.2 servisleriyle gerçek hedef doğrulaması yapıldı. Test imajında
  Python 3.11 ve güncel requirements pin'leri kullanıldı. Müşteri/mevcut
  uygulama veritabanına dokunulmadı. PostgreSQL/MySQL gerçek servis testi
  yapılmadı; bu sürücüler için kanıt unit testleriyle sınırlı.
- CI'de Redis servisi ve gerçek iptal testleri eklendi. ODBC apt Signed-By
  çakışması, URL parola aktarımı/percent escaping, MSSQL unique introspection
  ve boolean filtre hataları düzeltildi (SPEC-0030). GitHub Actions sonucu
  ayrıca doğrulanmalıdır; yerel sonuç uzaktaki CI'nin yeşil olduğu iddiası değildir.
- Son test sayıları ve çalıştırılan komutlar:
  `docs/handoffs/2026-10-02-query-cancellation.yaml`.

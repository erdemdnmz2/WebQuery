# PLAN-0031: Canlı sorgu iptali implementasyon planı

- Durum: Taslak; tüm plan uygulanmadı. Mevcut farklı uygulama 2026-10-02'de bu branche taşındı.
- Tarih: 2026-09-30
- Branch: `feat/query-cancellation`
- Spec: [SPEC-0031](../specs/SPEC-0031-live-query-cancellation.md)
- Mimari: [ADR-0026](../adr/ADR-0026-live-query-cancellation.md)
- İzolasyon: `59cd62a1a6ecb8c93c2acf44e59e5862ff56d971` commit'inden ayrı
  worktree. Ana checkout'taki commit edilmemiş değişiklikler dahil edilmedi.

## 0. Karar kapısı

### 2026-10-02 branch taşıması

`security-validation-hardening` üzerindeki 4143c92 iptal uygulaması bu branche
ayrıldı. Mevcut uygulama ve test sınırı
[SPEC-0032](../specs/SPEC-0032-query-cancellation.md) ve
[ADR-0027](../adr/ADR-0027-query-cancellation.md) içinde kayıtlıdır.
Bu planın header/state API, local-first cancel, Pub/Sub/batch reconciliation,
Redis arızasında local iptal, ID'siz yeni sorgular için fail-closed ve gerçek
üç-driver doğrulaması maddeleri henüz tümüyle karşılanmaz.
OQ-2026-021 kararı korunur. Taşıma işi bu farkları çözmez, taslağı kabul etmez
ve planı tamamlanmış hale getirmez.

OQ-2026-021, 2026-10-01 tarihinde cevaplandı ve spec/ADR'ye kaydedildi: Redis
registry erişilemezse yeni sorgular hedef DB'ye başlamadan 503 ile reddedilir;
local-only fallback yoktur. API taslağını
gözden geçirin: optional X-Execution-ID, GET state, POST cancel, ortak domain
error kodları. Ready for implementation olmadan runtime kodunu değiştirmeyin.
Mevcut unrelated dokümanlar bu branch'e taşınmaz. Kullanıcı 2026-10-01 tarihinde
tasarım belgelerinin commit edilip branch'in publish edilmesini istedi; merge yoktur.

## Modül, sınıf ve DI tasarımı

Özelliğin domain sahibi mevcut `query_execution/` modülüdür. Aşağıdaki sınıf
ve imzalar önerilen uygulama tasarımıdır; henüz runtime kodu değildir. Driver
spike'ı adaptör binding ayrıntılarını doğrular.

| Dosya | Eklenecek tip | Sorumluluk ve scope |
| --- | --- | --- |
| `query_execution/executions.py` | `ExecutionState`, `ExecutionSnapshot` | Durum enum'u ve güvenli metadata; canlı driver referansı taşımaz |
| `query_execution/executions.py` | `ExecutionHandle` | Her çalıştırma için actor, ID, generation, cancel event, kilit ve canlı driver binding |
| `query_execution/executions.py` | `ExecutionRegistry` | Worker başına tek yerel handle registry'si |
| `query_execution/execution_registry_store.py` | `ExecutionRegistryStore` Protocol, `RedisExecutionRegistryStore` | Atomik claim, ownership, state/CAS, flag, publish/subscribe ve retention; worker başına tek store |
| `query_execution/config.py` | `ExecutionSettings` | Redis namespace, bounded timeout, reconciliation ve retention ayarları |
| `query_execution/cancellation.py` | `CancellationAdapter` Protocol | Binding, iptal sinyali, sonuç sınıflandırma ve kontrol cleanup sözleşmesi |
| `query_execution/cancellation_adapters/mssql.py` | `MssqlCancellationAdapter` | Ayrı bounded cancel executor'ı ve cursor iptali |
| `query_execution/cancellation_adapters/postgresql.py` | `PostgresqlCancellationAdapter` | Kontrollü statement/fetch task cancellation |
| `query_execution/cancellation_adapters/mysql.py` | `MysqlCancellationAdapter` | Aynı hedef/kademe credential'ıyla ayrı kontrol bağlantısı üzerinden KILL QUERY |
| `query_execution/execution_coordinator.py` | `ExecutionCoordinator` | Registration scope, local/remote cancel, snapshot, terminal finalization ve subscriber/reconciliation task'ları |
| `database_provider/execution_hooks.py` | `TargetExecutionHooks` Protocol | Session açılışı, commit bariyeri ve pool release öncesi cleanup için dar sözleşme |

`ExecutionHandle`, `TargetExecutionHooks` sözleşmesini yapısal olarak uygular.
`DatabaseProvider` coordinator veya Redis store import etmez. Hook sözleşmesi
provider modülünde dependency-free kalır: mevcut `query_execution/__init__.py`
servisleri import ettiği için provider'dan query domain'ine ters import döngü
yaratabilir. Driver adaptörlerinin SQLAlchemy erişimi dar ve test edilmiş seam'de
kalır; session init sırasında gelen cancel de kullanıcı SQL'ini engeller.

### Mevcut sınıflardaki entegrasyon

- `QueryService(..., execution_coordinator)` ve
  `WorkspaceService(app_db, execution_coordinator)` aynı process singleton'ını
  alır. Workspace'in mevcut method-level `db_provider` parametresi korunabilir.
- `AdminService(..., execution_coordinator)` bu nesneyi yalnız execution yapan
  `AdminApprovalService` constructor'ına aktarır; kullanıcı yetki servisine
  cancellation bağımlılığı eklenmez.
- `run_statement(..., execution=handle)` mevcut fonksiyon olarak genişler;
  bind/execute/stream/fetch/close sınırlarını handle ve seçilen adaptörle yönetir.
- `DatabaseProvider.get_session(..., execution_hooks=handle)` bağlantı,
  transaction, rollback/commit ve close sahibi olarak kalır. Cleanup bitmeden
  pool release olmaz. MySQL kontrol bağlantısı ayrı kapasiteyle provider içinde
  edinilir; credential resolution çoğaltılmaz ve dolu query pool'una bağımlı olmaz.
- `query_execution/execution_router.py` yeni state/cancel uçlarını barındırır;
  `schemas.py` ve `exceptions.py` mevcut domain içinde genişletilir. Router'lar
  authenticated actor'ı coordinator'a verir; coordinator sahipliği tekrar denetler.
- `dependencies.py`: `AppContext` coordinator'ı constructor'dan alır, üç
  servise dağıtır; `get_execution_coordinator()` kontrol router'larına aynı
  instance'ı döndürür. Request başına coordinator/Redis client oluşturulmaz.

### Lifespan oluşturma sırası ve sahiplik

1. Mevcut config doğrulaması, login throttle, AppDatabase/schema/OWNER ve
   DatabaseProvider/cache başlangıcı tamamlanır; Slack yaşam döngüsü korunur.
2. Lifespan içinde yeni `worker_id` UUID ve `ExecutionSettings` oluşturulur.
3. Yerel `ExecutionRegistry`, ardından `RedisExecutionRegistryStore` kurulur.
   Mevcut `REDIS_URL` kullanılır; execution client/pool ve namespace'i login
   throttle'ın private client'ından ayrıdır.
4. Üç adaptör ve teknolojiye göre seçilen adaptör mapping'i oluşturulur.
   Adaptörler kendi kontrol kaynaklarını lifecycle içinde başlatır; canlı
   cursor/task binding'i bu aşamada oluşturulmaz.
5. Registry, store ve adaptör mapping'i ile `ExecutionCoordinator` oluşturulur.
6. Coordinator `AppContext`'e aktarılır; context mevcut servisleri aynı
   coordinator ile oluşturur. Context yalnız composition yapar, async task başlatmaz.
7. Coordinator'ın subscriber/reconciliation kaynakları `await start()` ile
   başlatılır; startup'ta edinilen kaynaklar hata halinde de kapatılır. Ardından
   lifespan `yield` ile request kabulüne geçer.

Lifespan shutdown önce coordinator'ın yeni registration kabulünü kapatır.
Aktif driver/kontrol işi ve gerekli cleanup tamamlanmadan kontrol kaynakları
ve hedef bağlantıları kapatılmaz. Subscriber/reconciliation, adaptör kontrol
kaynakları ve execution Redis client'ı kapatıldıktan sonra mevcut provider/DB
cleanup sürer. Yeni kaynakların kapanışı idempotent ve bounded olur; bu genel
bir drain/crash recovery ürünü değildir.

### Tek çalıştırmanın sırası

Auth/yetki/risk preflight → coordinator registration → Redis atomik claim
doğrulaması → yerel handle'ın hazırlanması → provider session acquisition/init
→ adaptör binding → statement ve fetch → commit bariyeri (write) → commit veya
rollback → kontrol cleanup ve güvenli pool release → doğrulanmış terminal state
→ final audit/response. Claim doğrulanamazsa acquisition öncesi 503'tür.
Registration sırasında ownership/claim yarışları test edilir; hazırlıkta kabul
edilen iptal niyeti binding öncesinde korunur.

Test DI'sında aynı constructor sözleşmeleri kullanılır: `ExecutionRegistryStore`
ve adaptör test double'ları enjekte edilir. Redis ve gerçek driver testlerinde
gerçek kaynaklar kullanılır; production için memory-only fallback eklenmez.

## 1. Üç gerçek driver için cancellation spike

Önce gerçek cancellation erişimini kanıtlayın; UI veya generic cursor API'si
varsayımıyla başlamayın. Mevcut pin'leri kullanın; sırf kolaylık için upgrade yok.

| Hedef | Kanıtlanacak mekanizma | Kritik sınır |
| --- | --- | --- |
| MSSQL | Çalışan pyodbc cursor.cancel, ayrı bounded kontrol executor'ı | Cursor execute başlamadan bind edilir; query thread arkasına cancel kuyruğa girmez |
| PostgreSQL | asyncpg in-flight statement/fetch task cancel -> protocol cancel | SQLAlchemy cleanup ve connection reuse gerçek DB ile doğrulanır |
| MySQL | Canlı connection ID + ayrı aynı-kademe kontrol bağlantısında KILL QUERY | Query pool doygunken kapasite var; session geç iptal sırasında yeniden kullanılmaz |

Kontrol için hedef DB hesabına geniş KILL/DBA yetkisi vermeyin. Driver seam'i
SQLAlchemy adaptation sınırında dar bir modülde tutun. Bir sürücü mekanizması
kanıtlanamıyorsa o sürücü için destek varmış gibi davranmayın; ADR/spec güncelleyin.

Çıktı: Uzun statement'ın server'da durduğu, cancelled exception/normal completion
yarışının sınıflandırıldığı ve aynı pool'da sonraki sorgunun çalıştığı testler.
Fake cursor testleri gerçek driver testlerinin yerine geçmez (AC-04/07/14).

## 2. Yerel execution yaşam döngüsü

Önerilen modüller: `web_api/query_execution/executions.py` (registry/handle),
`cancellation.py` (adaptör sözleşmesi), `cancellation_adapters/` (driver kodu).
İsimler taslaktır; ayrı process veya bağlantı manager'ı oluşturmayın.

- `app.py` lifespan ve `dependencies.py` AppContext'e process UUID ve registry
  ekleyin. Fork öncesi global UUID üretmeyin; singleton scope process'tir.
- `execution_id`, authenticated user ID, state, cancel Event ve driver binding
  içeren handle. Hazırlıkta cancel niyeti kaybolmaz; terminal transition idempotent.
- Task/cursor lifetime, cancel kontrol işinin bitmesi ve pool release birlikte
  yönetilir. Bounded driver cleanup başarısızlığında bağlantı invalidate edilir.
- Aynı handle üzerinde cancel/commit bariyeri; committing sonrası too-late.
- `runner.py` ortak statement/fetch yürütme noktasıdır. `DatabaseProvider.get_session`
  transaction sahibidir; sadece execute içine registry koymak commit/fetch
  yarışlarını çözmez. Normal preflight kapıları servislerde kalır.

Çıktı: Unit testler preparing-cancel, binding yarışı, duplicate cancel,
completion-wins, late signal ve commit bariyeri için geçer (AC-01/05/06/07).

## 3. Redis routing ve mesaj kaybı

Önerilen modül: `web_api/query_execution/execution_registry_store.py`.
Mevcut Redis konfigürasyonunu kullanın; login-throttle key/iş mantığına dokunmayın.

- Atomik execution claim ve kullanıcı/worker ownership; deployment namespace.
- Local-first cancel için kullanıcı denetimi yerel handle'dan; remote için
  tek-ID lookup + atomik flag/CAS. Önce flag, sonra per-worker publish.
- Subscriber yalnız yerel registry'deki execution/version ile eşleşen mesajı
  işler. Reconnect + bounded batch reconciliation kendi aktif ID'lerine bakar.
- Local cancel Redis down olsa da driver'a ulaşır; metadata update hatası bu
  gerçeği örtmez. Remote kabul Redis flag güvenle yazılmadıysa 503 olur.
- Terminal TTL taslak 5 dakika; aktif execution expire edilmez. Eski worker'ın
  kaydı restart'ta otomatik devralınmaz. Stale key riski belgelenir ve ölçülür.
- Yeni iş kabulünde atomik registry claim'i bounded timeout ile doğrulanır;
  Redis erişim/claim timeout veya hatasında hedef connection acquisition ve
  kullanıcı SQL'ine geçilmeden `503 EXECUTION_REGISTRY_UNAVAILABLE` döner.
  Local-only fallback eklenmez. Üç execution yüzeyinde bu sınırı test edin.

Çıktı: Gerçek Redis ve iki bağımsız process ile routing, duplicate/delayed message,
missed publish/reconnect, runtime outage ve retention testleri (AC-02/08/12/13).

## 4. Üç servis, transaction ve audit entegrasyonu

- `query_execution/services.py`, `workspaces/services.py` ve `admin/services.py`
  preflight sonrası aynı execution scope'u kullanır. Owner, sorguyu o anda
  çalıştıran kullanıcıdır; workspace author ID'si cancellation owner değildir.
- Claim/binding öncesi pending cancel ve exception/finally cleanup yollarını
  kapsayın. Init SQL/connection bekleyişinde kullanıcı SQL'i başlamamalıdır.
- Ad-hoc başarı audit'ini session context çıkışına/commit sonrasına taşıyın;
  workspace/preview akışlarıyla tutarlı finalization kullanın. Commit hatasının
  successful audit bıraktığı regression test ekleyin.
- Kullanıcı iptali, timeout, normal driver hatası ve uncertain commit ayrılır.
  `CancelledError` kontrol akışı broad `Exception` catch'te kaybolmaz; servis
  cancellation ile request/server shutdown cancellation birbirine karıştırılmaz.
- Mevcut audit altyapısına execution/trace korelasyonu ve cancel olaylarını
  ekleyin; password redaction/error scrub korunur. Audit teslim hatası hedef
  commit'i geri aldı iddiasına dönüşmez; iki datastore atomikliği vaat edilmez.

Çıktı: Transactional DML rollback, commit barrier, commit failure/audit,
masking/risk/tier ve üç yüzey regresyon testleri (AC-06/10/11).

## 5. API sözleşmesi

- Üç execution router'ına UUID header aktarımı; schemas'a additive ID/status.
- Yeni execution state/cancel router ve servis; authentication, only-own,
  404 non-enumeration, rate limit ve Redis timeout.
- Cancel domain hata kodlarını üç mevcut router'ın genel error mapping'inden
  koruyun; OpenAPI dokümantasyonu/snapshot testlerini güncelleyin.
- Registry arızasının `503 EXECUTION_REGISTRY_UNAVAILABLE` kodunu üç execution
  router'ında koruyun; hedef SQL'in başlamadığı bu hata, başlamış işin
  `EXECUTION_OUTCOME_UNKNOWN` sonucundan ayrı gösterilir.
- Early cancel, duplicate claim, already terminal, remote unavailable ve
  invalid UUID örneklerini kontrat testiyle sabitleyin.

Çıktı: GET/POST authorization ve response schema testleri; owner/admin preview
ayrımı; sorgu sonucu endpoint'leri polling-job API'ye dönüşmez (AC-03/05/09/11/13).

## 6. UI

Önce `frontend/DESIGN.md` okuyun. `frontend/services/api.ts`, `lib/execution.ts`
ve types'a execution kimliği/state/cancel desteği ekleyin. Studio.tsx,
RunWorkspace.tsx ve admin ReviewDialog.tsx aynı cancellation contract'ını kullanır.

- Request başlamadan UUID, execution'a özel state ve Durdur düğmesi.
- Registration öncesi Durdur niyetini saklama; orijinal isteğin terminal olduğu
  anda retry/polling'i durdurma. Race'de eski request yeni UI run state'ini ezmez.
- 202 yalnız pending; confirmed cancel ayrı feedback, unknown ayrı uyarı.
  Bounded polling/backoff, unmount cleanup ve keyboard/aria-live erişilebilirlik.
- Registry unavailable 503'te sorgunun başlamadığı gösterilir; bu execution
  için pending cancel/retry/polling bitirilir.
- Browser AbortController'ı hedef DB cancel kanıtı saymayın. Workspace approval
  statüsünü execution cancellation statüsüne çevirmeyin.

Çıktı: Üç ekranda normal result, cancel, cancel-too-late ve Redis/owner failure
senaryoları doğrulanır (AC-05/09/11). Frontend'de committed test command yok;
manuel kontrolü automated test gibi raporlamayın.

## Test haritası ve doğrulama

| Kriterler | Önerilen test yeri |
| --- | --- |
| AC-01, AC-05, AC-06, AC-07 | Yeni `tests/unit/test_execution_registry.py`, mevcut `test_query_runner.py` |
| AC-02, AC-08, AC-12, AC-13 | Yeni Redis/two-process integration testleri |
| AC-03, AC-11 | `tests/integration/test_query_execution.py`, `test_workspaces.py`, `test_admin_api.py` |
| AC-04, AC-07, AC-14 | Üç gerçek driver için yeni cancellation integration suite |
| AC-06, AC-10 | `tests/integration/test_target_transaction.py` + gerçek hedef DB transaction testleri |
| AC-05, AC-09, AC-11 | UI build/typecheck + raporlanmış manuel üç-ekran senaryoları |

Uygulama aşamasında backend environment ile `web_api/` içinden:

```sh
python -m pytest tests/unit/test_query_runner.py tests/integration/test_target_transaction.py tests/integration/test_query_execution.py tests/integration/test_workspaces.py tests/integration/test_admin_api.py
python -m pytest
```

Yeni test dosyaları da ilk targeted komuta eklenecek. Gerçek Redis/DB suite
komutu fixture'lar yazılınca handoff'a kaydedilecek; server yoksa skip gerçek
driver desteğinin geçtiği anlamına gelmez. Credential'ları log/docs'a yazmayın.

Frontend değişikliklerinde `frontend/` içinden `npm run build` ve
`npm run typecheck`. Sonrasında SQL execution/auth/connection/audit değişimleri
için change-review skill/playbook ve AC bazlı güvenlik incelemesi gerekir.

## Teslim ve rollout

- OQ-2026-021 cevabı kaydedildi. ADR acceptance, gerçek üç driver cancellation kanıtı ve AC test
  sonuçları olmadan “tamamlandı” denmez.
- Operasyon sinyalleri: active handles, cancel accepted/confirmed/unconfirmed,
  signal-to-observed-stop süresi, Redis routing/reconciliation hatası, control
  capacity ve cleanup/invalidation hatası. SQL veya credential metric label olmaz.
- Handoff gerçek komut/sonuç, driver/server sürümü ve kalan riskleri içerir.
  Mevcut commit edilmemiş değişiklikleri taşımayın. Tasarım belgelerinin push'u
  2026-10-01 kullanıcı talebiyle yetkilendirildi; merge yapılmaz.

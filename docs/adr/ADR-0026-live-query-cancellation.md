# Trade-off Tablosu

Senaryo: WebQuery, aynı veya başka process'e düşen bir HTTP isteğiyle çalışan
MSSQL, PostgreSQL ve MySQL sorgularını durdurabilmeli. Tek worker'da düşük
ek maliyet, çok worker/replica'da doğru yürütücüye yönlendirme isteniyor.

En belirleyici kriter: Doğru canlı sorguya güvenli biçimde ulaşmak; iptal
sinyalini göndermek ile sorgunun gerçekten durmasını birbirine karıştırmamak.

| Kriter | 1. Yalnız yerel registry | 2. Yerel handle + Redis yönlendirme | 3. Metadata DB + merkezi job manager |
| --- | --- | --- | --- |
| Performans | Yerel dictionary erişimi | Yerelde hızlı yol; uzakta Redis + mesaj | Ek SQL lookup ve job koordinasyonu |
| Kompleksite | Düşük | Orta; yaşam döngüsü ve mesaj kaybı yönetilir | Yüksek; kuyruk/scheduler modeli gerekir |
| Ölçeklenebilirlik | Başka process'e ulaşamaz | Worker ve replica sayısından bağımsız | Mümkün; mevcut request modeli değişir |
| Bakım | Basit, fakat çok worker için yetersiz | Ortak registry ve sürücü adaptörleri | Merkezi orchestration katmanı |
| Maliyet | Ek servis yok | Mevcut Redis; execution başına küçük metadata | DB yükü ve yeni yönetim bileşeni |
| Doğru hedef ve doğrulama | Yalnız kendi handle'ı | Handle sahibinde kalır; sonuç sahibi tarafından doğrulanır | Canlı sürücü handle'ı yine yürütücüde gerekir |

## Karar

Seçilen alternatif: **2. Yerel handle + Redis yönlendirme**.

Kullanıcıyla üzerinde anlaşılan yön budur. OQ-2026-021, 2026-10-01 tarihinde
yeni sorgular için fail-closed 503 olarak cevaplandı. Ayrıntılı API taslağı ve
gerçek sürücü doğrulaması tamamlanmadan uygulama hazır kabul edilmez.

# ADR-0026: Canlı sorgu iptali için yerel handle ve Redis yönlendirme

## Status

Proposed — 2026-09-30. Mimari yön görüşmede seçildi; bu belge henüz uygulanmadı.

## Context

`query_execution/runner.py` ad-hoc, workspace ve admin preview akışlarında
ortak yürütme noktasıdır. `DatabaseProvider.get_session()` bağlantı,
rollback/commit ve close yönetir. Engine cache bağlantı havuzunu yönetir;
execution ID'den canlı cursor'a erişim sağlamaz. Process bellekleri paylaşılmaz.

Timeout, kullanıcının istediği anda iptal yerine geçmez. DB-API bütün
sürücüler için ortak bir `cursor.cancel()` sözleşmesi tanımlamaz. Ayrıca bir
Python task'ını durdurmak her sürücüde sunucudaki SQL'in durduğunu kanıtlamaz.

Redis zaten login throttle için runtime bağımlılığıdır. Yalnız iptal
yönlendirmesi için ikinci bir metadata SQL sorgusu veya yeni execution tablosu
eklemek istenmiyor. Mevcut authentication ve audit DB işlemleri korunur.

## Decision

1. FastAPI lifespan içinde, fork sonrasında her process için bir UUID
   `worker_id` oluşturulur. PID tek başına kimlik değildir; restart yeni UUID
   üretir. Hiçbir worker başka worker'ın Python nesnesine erişmez.
2. Process-local `ExecutionRegistry`, `execution_id -> ExecutionHandle` ve
   doğrulanmış kullanıcı kimliğini tutar. Bu bir bağlantı pool'u değildir.
   Handle, iptal niyeti, sürücü adaptörü ve ilgili canlı bağlantı/cursor/task
   referanslarını taşır. SQL bitmeden ve cleanup tamamlanmadan kaynak başka
   execution'a verilmez.
3. Redis'te deployment'a özel namespace altında execution ID, owner worker,
   kullanıcı ID, durum, cancel flag ve yarış güvenliği için generation/version
   bilgisi tutulur. Ham SQL, sonuç, parola, bağlantı dizesi ve cursor tutulmaz.
   UUID ve sahiplik atomik claim edilir; client kullanıcı/worker kimliği seçemez.
4. Cancel yerel registry'de aranır. Yerel hit'te mevcut authentication sonrası
   handle sahibi doğrulanır ve adaptöre doğrudan gidilir; ek execution SQL
   lookup veya Redis roundtrip'i, canlı sorguyu iptal etmenin önkoşulu olmaz.
   Uzaktaki execution için Redis owner lookup, kullanıcı kontrolü, atomik cancel
   flag ve owner kanalına bildirim kullanılır.
5. Redis Pub/Sub tek başına teslim garantisi değildir. Remote cancel flag
   publish'ten önce kaydedilir. Subscriber reconnect'te ve kısa, batch edilmiş
   bir reconciliation döngüsünde worker yalnız kendi aktif execution ID'lerini
   kontrol eder. Mesajdaki execution/version yerel handle ile doğrulanır;
   duplicate ve gecikmiş mesaj idempotent işlenir. Bu döngü lease/heartbeat
   değildir; worker liveness iddiasında bulunmaz.
6. Ortak handle sürücüye özgü adaptör çağırır. MSSQL'de `pyodbc.Cursor.cancel()`
   ayrı ve sorgu executor'ına takılmayan kontrol yolundan çağrılır. PostgreSQL'de
   asyncpg'nin protocol cancel mekanizmasını tetikleyen kontrollü statement/fetch
   task cancellation kullanılır. MySQL'de aynı hedef kademe hesabıyla ayrı
   kontrol bağlantısından `KILL QUERY connection_id` gönderilir. SQLAlchemy
   entegrasyonu gerçek sürücü testleriyle kanıtlanır; hayali ortak cursor API'si
   veya sürücünün private alanlarına dayalı garanti verilmez.
7. Driver işi, fetch, cancellation ve transaction cleanup birlikte yönetilir.
   İptal isteğinin kabul edilmesi `cancelled` değildir. Owner runner sonucu
   sınıflandırır. Commit başlamadan atomik bir commit bariyeri vardır;
   `committing` sonrası cancel reddedilir. Commit sonucu belirsizse
   `outcome_unknown` gösterilir; başarı veya rollback uydurulmaz.
8. V1'de lease, heartbeat, otomatik crash recovery, tekrar yürütme veya
   approved-job queue yoktur. Redis kaydı, sahibi ölmüş işi durduramaz. Aktif
   kaydın TTL ile sessizce kaybolmasına izin verilmez; terminal kayıt kısa
   retention sonrası silinebilir. TTL temizliktir, durma kanıtı değildir.
9. Redis execution registry erişilemezse **yeni sorgular** fail-closed davranır.
   Normal preflight sonrasında atomik claim bounded timeout içinde doğrulanmadan
   hedef connection acquisition ve kullanıcı SQL'i başlamaz; execution ucu
   `503 EXECUTION_REGISTRY_UNAVAILABLE` döner. Local-only fallback uygulanmaz.
   Bu, OQ-2026-021'e kullanıcının 2026-10-01 tarihinde verdiği karardır.
   Daha önce başlamış execution'ın yerel handle iptali Redis'e bağlı değildir;
   remote flag kaydedilemezse cancel 503 döner, kabul edildi iddiası üretilmez.

## Rejected Alternatives

### 1. Yalnız in-memory registry veya worker sayısına göre otomatik seçim

Tek process için yeterlidir. Fakat birer worker'lı iki replica da dağıtık
topolojidir; iptal isteği başka process'e düşebilir. Worker sayısı Redis'i
devreden çıkarmak için güvenilir deployment ölçütü değildir. Yerel hızlı yol
tek worker maliyetini azaltır; ayrıca memory-only ürün modu eklenmez.

### 2. Redis'e cursor/engine/PID koyup uzaktan nesneyi iptal etmek

Canlı nesne serialize edilerek kullanılabilir bir remote handle olmaz. PID,
container ve restart'larda tekrar kullanılabilir. Sürücüye erişen iptal işlemi
gerçek kaynak sahibinde kalır; Redis yalnız adresleme ve iptal niyeti taşır.

### 3. Sadece Pub/Sub veya sadece HTTP bağlantısını kapatmak

Pub/Sub mesajı kaybolabilir. Fetch abort ise browser bekleyişini bitirir;
sunucudaki statement'ın durmasını garanti etmez. Kalıcı cancel flag ve owner
tarafından doğrulanmış terminal sonuç gerekir.

### 4. Lease + merkezi manager + kalıcı job queue

Crash recovery için anlamlıdır; yalnız canlı sorgu iptali ihtiyacının kapsamını
aşar. `QueryData` bir workspace/onay kaydıdır, execution/job kaydı değildir.
Onay verildiği anda otomatik iş çalıştırma bu ADR ile eklenmez.

## Consequences

- Redis registry arızası yeni sorguları hedef DB'ye başlamadan 503 ile durdurur;
  çok-worker adreslenebilirliğini korumak için sorgu erişilebilirliği azalır.
- Aynı process'te routing lookup beklemeden cancel; diğer process'lerde bir
  owner lookup ve bildirim. O(1) anahtar erişimi uçtan uca iptal süresi garantisi
  değildir; ağ, sürücü ve rollback gecikmesi vardır.
- ID ve ortak yaşam döngüsü gelecekte execution yönetimini genişletmeyi
  kolaylaştırır; şu anda kalıcı geçmiş veya crash sonrası doğru final durum yoktur.
- MySQL kontrol kapasitesi sorgu pool'u doluyken de kullanılabilmelidir.
  Genel DBA yetkisi verilmez; hesabın kendi session'ını durdurabilmesi doğrulanır.
- SQL Server'da geniş `KILL` yetkileri gerekmez. Cancel executor'ı bounded
  olmalı, event loop'u veya statement'ın beklediği thread'i kilitlememelidir.
- Ad-hoc akışındaki başarı audit'i bugün session context çıkışından önce
  yazılıyor. Başarıyı commit doğrulamasından sonra kaydetme planın parçasıdır.
- Uygulama ve UI; iptal isteniyor, iptal edildi, tamamlandı ve sonucu belirsiz
  durumlarını ayırt eder. Kullanıcı yalnız kendi execution'ını durdurabilir.

## Accepted Risks

- Redis registry erişilemediğinde yeni sorgular çalıştırılamaz. Local-only
  fallback çok-worker cancellation sözleşmesini zayıflatacağı için seçilmedi.
- Lease olmadığı için worker ölümü otomatik saptanmaz. Stale aktif kayıtlar
  kalabilir; Redis büyümesi izlenir, cleanup ayrı operasyonel iş olur. Canlı
  sorguyu etkilemeden stale olduğunu kanıtlayamayan cleanup kör silme yapmaz.
- İptal bir rollback garantisi değildir: önceden commit edilmiş iş,
  nontransactional işlem veya DDL etkisi kalabilir. Rollback uzun sürebilir.
- Sürücü davranışı versiyona bağlıdır. Mevcut pin'lerle gerçek üç DB testi
  geçmeden destekleniyor iddiası veya tüm sürücüleri kapsayan rollout yapılmaz.
- Redis ve audit DB arasında distributed transaction yoktur. Sinyal kabulü,
  engine sonucu ve audit teslim hatası ayrı olaylar olarak raporlanır.

## References

- Spec: [SPEC-0031](../specs/SPEC-0031-live-query-cancellation.md)
- Plan: [PLAN-0031](../plans/PLAN-0031-live-query-cancellation.md)
- [Open questions](../open-questions.md): OQ-2026-021
- [Engine lifecycle](ADR-0003-engine-cache-lifecycle.md)
- [Credential tiers](ADR-0005-role-based-target-database-credentials.md)
- [Redis login dependency](ADR-0014-redis-login-throttle.md)
- [PEP 249](https://peps.python.org/pep-0249/)
- [Redis Pub/Sub delivery semantics](https://redis.io/docs/latest/develop/pubsub/)
- [pyodbc 5.2.0 cursor API](https://github.com/mkleehammer/pyodbc/blob/5.2.0/src/pyodbc.pyi)
- [ODBC SQLCancel semantics](https://learn.microsoft.com/en-us/sql/odbc/reference/syntax/sqlcancel-function?view=sql-server-ver17)
- [asyncpg 0.30.0 protocol](https://github.com/MagicStack/asyncpg/blob/v0.30.0/asyncpg/protocol/protocol.pyx)
- [aiomysql 0.3.2 connection](https://github.com/aio-libs/aiomysql/blob/v0.3.2/aiomysql/connection.py)
- [MySQL KILL QUERY semantics](https://dev.mysql.com/doc/refman/8.4/en/kill.html)
- Supersedes / Superseded by: Yok.

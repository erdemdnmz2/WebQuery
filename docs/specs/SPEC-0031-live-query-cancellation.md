# Mini-Spec: Çalışan sorguyu kullanıcı isteğiyle iptal etme

## 1. Spec Kartı

- Özellik: Live query cancellation
- Durum: Draft
- Versiyon: 2026-10-01
- Tarih: 2026-09-30
- Sahip: WebQuery
- ADR: [ADR-0026](../adr/ADR-0026-live-query-cancellation.md)
- Plan: [PLAN-0031](../plans/PLAN-0031-live-query-cancellation.md)

## 2. Amaç ve Başarı Sinyali

### Amaç

Kullanıcı devam eden kendi sorgusunu durdurabilsin; isteğin başka worker'a
düşmesi buna engel olmasın. UI yalnız HTTP bekleyişini kesmesin, gerçek hedef
DB cancellation mekanizmasını kullansın ve doğrulanmayan sonucu başarılı
iptal olarak göstermesin.

### Başarı Sinyali

- Üç hedef DB'de uzun statement'ın sunucuda durduğu ve ardından kaynakların
  güvenle kullanılabildiği gerçek sürücü testiyle gösterilir.
- İki worker testinde B'ye gelen cancel A'nın canlı execution'ına ulaşır.
- Başkasının execution'ı etkilenmez; geç sinyal pooled bağlantıda yeni sorguya
  uygulanmaz. Mevcut timeout, authorization, risk analizi ve masking korunur.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- Ad-hoc query, workspace execution ve admin preview.
- Execution başına benzersiz UUID, yerel registry ve ortak handle yaşam döngüsü.
- Redis routing, cancel flag, bildirim ve kaçırılan mesaj reconciliation'ı.
- MSSQL, PostgreSQL ve MySQL adaptörleri; kullanıcıya durum ve Durdur kontrolü.

### Kapsam Dışı

- Başkasının sorgusunu admin/OWNER olarak durdurma yetkisi.
- Lease, worker heartbeat, crash recovery, restart sonrası yeniden çalıştırma.
- Job queue, merkezi manager, onaylı işleri otomatik çalıştırma ve kalıcı
  execution geçmişi. Yeni metadata tablosu veya migration.
- Genel graceful-shutdown/drain ürünü. Eklenen subscriber/executor kaynaklarının
  mevcut lifespan içinde güvenli başlatılması ve kapanması yine gereklidir.
- Commit edilmiş veya nontransactional değişiklikleri geri alma garantisi.

## 4. Sözleşme

Aşağıdaki API/UI ayrıntıları önerilen taslaktır; uygulanmış sözleşme değildir.

### Execution kimliği ve mevcut uçlar

Mevcut senkron sonuç uçları korunur:

- `POST /api/execute_query`
- `POST /api/execute_workspace/{workspace_id}`
- `POST /api/admin/execute_for_preview/{workspace_id}`

İstemci isteğe optional `X-Execution-ID: <UUID>` header'ı ekleyebilir. Yeni UI
her çalıştırma için `crypto.randomUUID()` üretir; sonuç dönmeden ID'yi bilir.
Header yoksa server ID üretir. Geçersiz header `422`; claim edilmiş ID ile
ikinci execution `409` verir ve hedef SQL başlamaz. Claim, normal auth/yetki/risk
kapıları geçtikten sonra fakat connection acquisition ve kullanıcı SQL'inden
önce yapılır. ID, workspace ID veya request trace ID değildir. Cross-origin
konfigürasyonu varsa header CORS allowlist'ine eklenir.

Başarılı sonuçların mevcut alanları korunur; `execution_id` ve
`execution_status` eklenir. Mevcut preflight hata sözleşmeleri değişmez.
Normal preflight kapıları geçildikten sonra Redis registry claim'i bounded
timeout içinde doğrulanamazsa üç execution ucu da HTTP `503`,
`detail.code="EXECUTION_REGISTRY_UNAVAILABLE"` ve güvenli bir mesaj döner.
Hedef connection acquisition ve kullanıcı SQL'i başlamaz; local-only fallback
yapılmaz. Bu hata, SQL başlamışken oluşan belirsiz sonuç hatasından ayrıdır.
Doğrulanmış cancellation için üç uçta ortak domain hatası önerilir:
HTTP `409`, `detail.code="QUERY_CANCELLED"`, `detail.execution_id` ve güvenli
bir mesaj. Belirsiz target sonucu HTTP `503`, `detail.code="EXECUTION_OUTCOME_UNKNOWN"`
olur. Router'ların mevcut genel hata çevirileri bu iki kodu kaybetmemelidir.

### Kontrol uçları

`GET /api/executions/{execution_id}` authenticated kullanıcıya yalnız kendi
execution metadata'sını verir. Örnek alanlar: `execution_id`, `status`,
`cancel_requested`, `outcome_confirmed`. Owner worker ID, hedef session ID,
SQL, sonuç ve credential istemciye verilmez. Kayıt tek başına worker'ın canlı
olduğunu kanıtlamaz; aktif snapshot'ın `outcome_confirmed` değeri false'dur.

`POST /api/executions/{execution_id}/cancel` aynı authenticated executor'a aittir.

| Sonuç | HTTP | Anlam |
| --- | --- | --- |
| İptal niyeti kabul edildi veya zaten bekliyor | 202 | Henüz durdu garantisi yok |
| Owner tarafından daha önce cancelled doğrulandı | 200 | Idempotent terminal cevap |
| Başarı/başarısızlık terminal oldu veya commit başladı | 409 | Artık iptal edilebilir aktif statement yok |
| Bilinmeyen ID veya başka kullanıcıya ait ID | 404 | Sahiplik/varlık sızdırılmaz |
| Remote flag güvenle kaydedilemiyor/yönlendirme bozuk | 503 | Kabul edildi iddiası yok; retry yapılabilir |

UUID tek başına yetki değildir. Kontrol uçları rate-limit edilir; remote Redis
işlemlerine bounded timeout uygulanır. Standart auth oturum kontrolleri korunur.

Kayıt olmadan gelen cancel yeni key oluşturmaz. UI erken Durdur niyetini
saklar, orijinal istek sürerken kısa bounded/backoff durum kontrolleriyle
kayıt oluştuğunda cancel yollar. Orijinal istek preflight'ta reddedilir veya
biterse tekrar deneme biter. `404` hiçbir zaman “iptal edildi” sayılmaz.

### Durumlar ve UI

Normal yol: `preparing -> running -> committing (write) -> succeeded`.
İptal yolu: `preparing/running -> cancel_requested -> cancelling -> cancelled`.
Driver hata yolu `failed`; doğrulanamayan hedef sonuç `outcome_unknown`.
`cancel_requested` ile tamamlanma yarışında zaten bitmiş sonuç kazanabilir;
cancel flag'in true olması terminal sonucun cancelled olmasını zorlamaz.

UI Durdur tıklamasında “İptal isteniyor” gösterir; 202'yi terminal saymaz.
Doğrulanmış cancelled, başarı/boş sonuçtan ve genel SQL hatasından ayrılır.
Belirsiz durumda kullanıcıya durmanın doğrulanamadığı bildirilir. Stop düğmesi
yalnız ilgili execution'ı kontrol eder. Browser fetch abort backend cancel
yerine geçmez; workspace onay durumu execution durumuyla değiştirilmez.

## 5. İş Kuralları

### BR-01: Tek execution, tek sahip

ID atomik claim edilir; kullanıcı kimliği authenticated principal'dan, worker
kimliği process lifespan'dan gelir. Client ID routing ipucudur, yetki değildir.

### BR-02: Kaynak sahipte kalır

Cursor/task/session referansları yalnız owning process'tedir. Registration
önce, driver binding sonra yapılır; binding öncesi cancel niyeti SQL başlamasını
engeller. Registry ancak driver işi ve cleanup bittikten sonra bırakılır.

### BR-03: Yerel hızlı yol ve remote teslim

Yerel cancel routing için ek metadata DB/Redis lookup beklemez. Remote cancel
owner'ı Redis'ten bulur, flag'i atomik yazar, sonra bildirir. Reconciliation
kaçırılan bildirimleri idempotent toparlar. Mesaj handler'ı worker/execution
generation'ını tekrar doğrular; dışarıdan verilen PID/session ID'yi kullanmaz.

### BR-04: Sinyal doğrulanmış sonuç değildir

Owner runner canceled driver sonucunu ve cleanup'ı gözler. İptal talebinden
sonra normal başarı, normal hata veya belirsizlik çıkabilir. Hedef SQL'in
durduğu doğrulanmadan terminal cancelled yoktur. Sahibi yanıt vermeyen kayıt
aktif snapshot olarak görünse de UI durma veya liveness garantisi vermez.

### BR-05: Commit ve connection reuse güvenliği

Cancel kabulü ve commit başlangıcı aynı yerel senkronizasyon bariyerini kullanır.
Commit başladıysa geç iptal reddedilir. Cancel kontrol işi bitmeden bağlantı
pool'a dönmez; timeout/cleanup başarısızlığında güvenle invalidation gerekir.
Statement sürerken paralel rastgele rollback/close başlatılmaz. Başarı audit'i
yalnız gerekli target commit tamamlandıktan sonra yazılır.

### BR-06: Mevcut güvenlik kapıları korunur

Execution/cancel kontrolü authentication, analyzer, hedef kademe, audit,
masking ve trace zincirini atlamaz. Admin preview actor'ı admin'dir; workspace
sahibine başkasının preview'ını iptal yetkisi verilmez. OWNER otomatik ek yetki
almaz. Başkasının ID'sine erişim 404'tür.

### BR-07: Timeout ve user cancel ayrıdır

Mevcut timeout korunur; timeout SQL hataları otomatik user-cancel sayılmaz.
User cancellation normal driver hatasından ayrı kodlanır. Audit/structured
log'da actor, execution ID, trace ID, cancel kabulü ve nihai sonuç ilişkilendirilir.
Yeni cancellation audit olayları mevcut logging altyapısıyla uygulanır; sırf
routing için DB sorgusu veya yeni execution tablosu eklenmez.

### BR-08: Metadata retention ve arıza sınırı

Aktif kayıtta çalışmayı unutturan kısa TTL kullanılmaz. Terminal retention için
taslak başlangıç değeri 5 dakikadır; süre dolunca kontrol uçları 404 dönebilir.
Client aynı ID'yi tekrar kullanmaz; retention sonrası exactly-once garanti yoktur.
Worker ölümü sonrası stale kayıt otomatik retry veya doğrulanmış failed/cancelled
anlamına gelmez. OQ-2026-021'in 2026-10-01 cevabına göre runtime Redis registry
erişilemezse yeni execution fail-closed davranır: atomik claim doğrulanmadan
hedef bağlantı edinilmez ve kullanıcı SQL'i başlamaz; istek
`503 EXECUTION_REGISTRY_UNAVAILABLE` ile reddedilir. Local-only fallback yoktur.
Arızadan önce başlamış execution'ın yerel handle iptali çalışmaya devam eder;
remote flag güvenle kaydedilemiyorsa cancel ucu 503 döner. Bu arıza tek başına
çalışan sorgunun cancelled veya outcome_unknown olduğunu göstermez.

## 6. Acceptance Criteria

- AC-01: Aynı worker'daki kendi uzun sorgusuna cancel geldiğinde yerel handle
  çağrılır; routing için ek metadata SQL veya Redis lookup gerekmez (BR-02/03).
- AC-02: A yürütürken cancel B'ye düştüğünde owner flag/bildirim yoluyla gerçek
  sorgu durur; duplicate cancel yalnız aynı execution'ı etkiler (BR-01/03).
- AC-03: İkinci authenticated kullanıcı ID'yi bilse dahi GET/POST 404 döner,
  hiçbir handle veya flag etkilenmez; eksik auth mevcut 401'i korur (BR-06).
- AC-04: MSSQL/PostgreSQL/MySQL gerçek sürücü testleri uzun SQL'in hedef DB'de
  durduğunu doğrular; salt Python task/fetch abort yeterli kabul edilmez (BR-04).
- AC-05: Cancel connection acquisition/binding öncesi kabul edildiyse kullanıcı
  SQL'i başlamaz; kayıt öncesi 404 UI'da pending intent'i kaybettirmez (BR-02).
- AC-06: Cancel ile doğal tamamlanma yarışırsa tek tutarlı terminal sonuç
  üretilir; commit bariyeri sonrasında cancel 409'dur (BR-04/05).
- AC-07: İptal/cleanup bittikten sonra pool'da aynı bağlantıyı kullanan sonraki
  sorgu normal çalışır; gecikmiş mesaj/kontrol komutu ona uygulanmaz (BR-05).
- AC-08: Pub/Sub bildirimi kaçırılıp bağlantı geri geldiğinde aktif execution
  flag'i reconciliation ile alınır; at-most-once mesaj kaybı niyeti silmez (BR-03).
- AC-09: Cancel 202'de UI bekler; doğrulanmış sonuçta iptal gösterir. Owner
  yanıt vermiyorsa başarı uydurmaz ve polling sonsuza dek sürmez (BR-04).
- AC-10: Transactional DML cancel testinde commit oluşmaz ve rollback doğrulanır;
  commit/bağlantı belirsizliği cancelled değil unknown olur. Başarı audit'i
  commit başarısızlığına rağmen successful yazılmaz (BR-05/07).
- AC-11: Üç execution yüzeyi ID ve cancel hatası sözleşmesini korur; mevcut
  timeout, maskelenmiş sonuç, row limit, trace ve permission testleri geçer (BR-06/07).
- AC-12: Aktif uzun execution TTL yüzünden görünmez olmaz; terminal kayıt
  retention sonrası kaybolabilir. Crash kaydı yeni worker'a devredilmez (BR-08).
- AC-13: Preflight'tan geçen yeni sorguda Redis registry erişilemez veya claim
  timeout/hatası oluşursa üç execution ucu da 503 ve
  `EXECUTION_REGISTRY_UNAVAILABLE` döner; hedef connection acquisition ve
  kullanıcı SQL'i çağrılmaz, local-only fallback yapılmaz. Arızadan önce
  başlayan yerel handle cancel edilebilir; remote başarısız kabul yanlış
  202/cancelled üretmez (BR-03/08).
- AC-14: MySQL query pool'u doluyken kontrol bağlantısı erişilebilir kalır;
  cancel path event loop'u bloke etmez ve genel DBA yetkisi gerektirmez (BR-03/05/06).

## 7. Teknik ve Güvenlik Kısıtları

- MSSQL: aioodbc 0.5.0 / pyodbc 5.2.0 canlı cursor cancel; PostgreSQL: asyncpg
  0.30.0 kontrollü task/protocol cancel; MySQL: aiomysql 0.3.2 ayrı bağlantıda
  KILL QUERY. Pin değişirse driver contract testleri yeniden koşulur.
- Registration, terminal update ve batch reconciliation dışında row başına
  Redis çağrısı yapılmaz. State güncellemeleri CAS/version ile terminal sonucu
  overwrite etmez; Redis gecikmesi yerel driver cancel'i bloke etmez.
- Reconciliation aralığı, remote kontrol timeout'ları ve polling bütçesi
  konfigurasyonla bounded olur; düşük gecikme hedefi rollback süresi garantisi değildir.
- Redis kullanıcılarca erişilebilir kontrol API'si değildir. Deployment namespace,
  ACL ve güvenli ağ korunur; credential/result/SQL cache'e yazılmaz.
- Yeni UI mevcut component/token'ları, keyboard erişimi ve aria-live durum
  bildirimini kullanır; dialog Escape davranışı yeni cancel shortcut ile bozulmaz.

## 8. Open Questions

Aktif açık soru yok. OQ-2026-021, kullanıcı tarafından 2026-10-01 tarihinde
cevaplandı: yeni sorgular Redis registry arızasında hedef DB'ye başlamadan
503 ile reddedilir; local-only fallback yoktur. Karar
[open-questions.md](../open-questions.md) ve ADR-0026'da kayıtlıdır.
API ayrıntıları hâlâ taslaktır; spec'in Draft durumu bu nedenle korunur.

## 9. Done Kontrolü

- [ ] Acceptance criteria için test eklendi veya güncellendi
- [ ] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Proposed ADR oluşturuldu
- [x] OQ-2026-021 cevaplandı ve spec/ADR'ye kaydedildi
- [ ] API taslağı onaylandı
- [ ] Runtime doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

Bu teslim yalnız tasarım belgeleridir; runtime kabul kriterleri henüz tamamlanmadı.

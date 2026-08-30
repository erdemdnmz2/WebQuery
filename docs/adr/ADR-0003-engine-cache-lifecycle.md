# Trade-off Tablosu

Senaryo: WebQuery, kayıtlı her hedef veritabanına SQLAlchemy engine'i üzerinden
bağlanıyor. Engine'ler süreç ömrü boyunca yaşayan bir cache'te tutuluyor.
Karar: bu engine'lerin havuz boyutu, ne zaman tahliye edilecekleri ve çalışan
bir sorgunun ortasında tahliye edilmelerinin nasıl engelleneceği.

Baştan tahminimizce en belirleyici kriter: çalışan bir sorgunun altından
bağlantının çekilmemesi. Yanlış boyutlandırılmış bir havuz yavaşlık üretir;
aktif bir engine'in tahliyesi ise veri kaybı ve yarım kalmış transaction
üretir.

| Kriter | 1. İstek başına engine | 2. Sınırsız kalıcı cache | 3. LRU + TTL'li sınırlı cache (seçilen) |
| --- | --- | --- | --- |
| Performans | Kötü: her sorguda TCP + TLS + login | En iyi | İyi: sıcak hedefler havuzda kalır |
| Kompleksite | En düşük | Düşük | Orta: tahliye, TTL döngüsü, aktiflik kontrolü |
| Ölçeklenebilirlik | Hedef sunucuda bağlantı fırtınası | Kayıt sayısıyla sınırsız bellek/bağlantı | Sınırlı ve öngörülebilir |
| Bakım | Yok | Yok | Arka plan görevi izlenmeli |
| Maliyet | Hedef DB'de yüksek login maliyeti | Boşta duran bağlantılar hedef DB kotasını yer | Boşta duran engine TTL ile kapanır |
| **Çalışan sorgunun korunması** | Konu dışı | Konu dışı | Açıkça ele alınmalı — kararın asıl yükü burada |

## Karar

Seçilen alternatif: **3. LRU + TTL'li sınırlı cache.**

Gerekçe: Alternatif 1, hedef veritabanına sorgu başına bir login maliyeti
bindirir ve MSSQL'de bu maliyet sorgunun kendisinden büyük olabilir. Alternatif
2, kayıtlı veritabanı sayısı büyüdükçe hedef sunucuların bağlantı kotasını
sessizce tüketir. Seçilen alternatif ikisinin arasında durur; bedeli, aktif
engine'in korunmasının açıkça kodlanması gerektiğidir.

# ADR-0003: Hedef veritabanı engine cache yaşam döngüsü

## Status

Accepted (2026-08-20). Havuz boyutlandırması 2026-08-28'de ADR-0005 ile
değiştirildi; aşağıdaki "Havuz boyutları" bölümü güncel değeri taşır.

## Context

`database_provider/engine_cache.py`, hedef veritabanı engine'lerini süreç
ömrü boyunca bir sözlükte tutuyor. Bu ADR yazılana kadar üç şey belgesizdi:

1. **Havuz boyutu.** OQ-2026-001 bu soruyu sordu: README `pool_size=0,
   max_overflow=20` diyordu, kod `pool_size=50, max_overflow=100`
   kullanıyordu. Kullanıcı "mevcut kod kaynak doğrudur" cevabını verdi ve
   cevabı bu dosyaya kaydedeceğini söyledi — ama dosya hiç yazılmadı
   (denetim bulgusu P2-19).
2. **Tahliye politikası.** Cache dolduğunda hangi engine'in kapatılacağı.
3. **Arka plan temizliğinin dayanıklılığı.** TTL döngüsünün beklenmedik bir
   hatada ne yapacağı.

2026-08-28'de ADR-0005 (kademe başına hedef DB hesapları) tabloyu değiştirdi:
artık bir veritabanı için tek engine değil, kademe başına (`ro`/`rw`/`ddl`)
ayrı engine tutuluyor. Tek bir büyük havuz varsayımı üzerine kurulu
`pool_size=50` değeri bu yapıda anlamını yitirdi.

## Decision

### Havuz boyutları (ADR-0005 sonrası güncel)

Havuz, veritabanı başına değil **kademe başına** boyutlandırılır
(`_POOL_BY_TIER`):

| Kademe | `pool_size` | `max_overflow` | Gerekçe |
| --- | --- | --- | --- |
| `ro` | 10 | 20 | Sorguların ezici çoğunluğu salt-okuma |
| `rw` | 5 | 10 | Yazma daha seyrek ve genelde onaydan geçer |
| `ddl` | 1 | 2 | DDL tekil, planlı ve eşzamanlılık gerektirmeyen bir iştir |

Bu, OQ-2026-001'deki `pool_size=50, max_overflow=100` cevabının yerine geçer.
O cevap, veritabanı başına **tek** engine varsayımı altında verilmişti; kademe
ayrımıyla birlikte aynı toplam bağlantı bütçesi üç havuza dağıldı ve her
kademe kendi gerçek kullanımına göre boyutlandırıldı.

### Yaşam döngüsü

* **TTL temizliği:** Arka plan görevi, `ENGINE_CACHE_TTL_SECONDS` (varsayılan
  1800) süresince dokunulmamış engine'leri kapatır.
* **LRU tahliyesi:** Cache kapasitesindeyken yeni bir engine gerekirse en
  uzun süredir kullanılmayan engine kapatılır.
* **Aktif engine korunur:** `checkedout > 0` olan bir engine ne TTL ne de LRU
  yoluyla kapatılır. Her havuz meşgulse `EngineCacheExhaustedError` fırlatılır.
  Bu, kararın asıl yükü: eskiden bu durumda **aktif** bir havuz kapatılıyordu,
  yani o an çalışan bir sorgunun bağlantısı altından çekiliyordu.
* **Temizlik döngüsü ölmez:** Arka plan görevi beklenmedik bir hatada loglar
  ve devam eder. Eskiden sessizce sonlanıyordu; TTL temizliği bir daha hiç
  çalışmıyor, hiçbir log satırı da bırakmıyordu.
* **`pool_pre_ping=True`:** Yeniden başlatma veya güvenlik duvarı yüzünden
  düşmüş bağlantı, ilk sorguda hata vermek yerine şeffafça yenilenir.
* **Credential rotasyonunda tahliye:** Bir kaydın credential'ı güncellenince
  o veritabanının engine'leri kapatılır. Aksi hâlde cache'teki engine, TTL'i
  dolana kadar eski parolayla bağlanmaya devam eder ve rotasyon sessizce
  etkisiz kalır.

## Rejected Alternatives

### 1. İstek başına yeni engine

En basit ve tahliye sorununu tamamen ortadan kaldırır. Reddedilme nedeni:
MSSQL'de ODBC login maliyeti tipik bir raporlama sorgusunun süresiyle
karşılaştırılabilir düzeyde; sorgu başına bir login, hedef sunucuya da
gereksiz bir yük bindirir.

### 2. Sınırsız kalıcı cache

Tahliye mantığına hiç gerek bırakmaz. Reddedilme nedeni: kayıtlı veritabanı
sayısı arttıkça boşta duran bağlantılar hedef sunucuların bağlantı kotasını
tüketir ve bu tükenme WebQuery tarafında değil, hedef veritabanında başka
uygulamaların bağlanamaması olarak görünür.

### 3. Meşgulken en eski aktif engine'i kapatmak

Cache'in her zaman yeni bir engine verebilmesini garanti ederdi. Reddedilme
nedeni: çalışan bir sorgunun bağlantısını kapatmak, en iyi ihtimalle
anlaşılmaz bir sürücü hatası, en kötü ihtimalle yarım uygulanmış bir yazma
işlemi üretir. Bunun yerine istek reddedilir (`EngineCacheExhaustedError`);
geri basınç, veri bütünlüğü kaybından iyidir.

## Consequences

- Toplam eşzamanlı hedef DB bağlantısı, cache kapasitesi × kademe havuzları
  ile sınırlıdır ve öngörülebilir.
- Yoğun anlarda `EngineCacheExhaustedError` görülebilir; bu bir arıza değil,
  kasıtlı geri basınçtır. İzlemede bu hatanın sıklığı kapasite artırma
  sinyalidir.
- `ENGINE_CACHE_TTL_SECONDS` bir operasyon ayarıdır: düşürmek hedef DB'deki
  boşta bağlantıları azaltır, yükseltmek sıcak hedeflerde gecikmeyi azaltır.

## Accepted Risks

- Kademe havuz boyutları (`10/20`, `5/10`, `1/2`) ölçüme değil beklenen
  kullanım profiline dayanıyor. Gerçek yük altında doğrulanmadılar. Azaltma:
  değerler tek bir yerde (`_POOL_BY_TIER`) toplandı, ölçüm sonrası
  değiştirmek tek satırlık bir iş.
- Cache metadata'sı naive UTC zaman damgası kullanıyor (`_now()`), süreç içi
  bir karşılaştırma olduğu için yeterli; kalıcı bir kayıt değil.

## References

- Spec: yok — altyapı yaşam döngüsü kararı.
- Open question: `docs/open-questions.md` OQ-2026-001.
- Denetim: `webquery_denetim_raporu.md` P2-9, P2-17, P2-19.
- İlgili: `docs/adr/ADR-0005-role-based-target-database-credentials.md`
  (kademe başına engine), `docs/adr/ADR-0007-target-query-timeout.md`.
- Supersedes / Superseded by: havuz boyutlandırması bakımından ADR-0005
  tarafından değiştirildi; yaşam döngüsü kararları yürürlükte.

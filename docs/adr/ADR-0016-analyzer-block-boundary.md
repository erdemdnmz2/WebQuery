# Trade-off Tablosu

Senaryo: `QueryAnalyzer` hangi sorguyu kesin olarak reddedecek, hangisini
işaretleyip geçirecek ve veritabanı admin'i bu kararın neresinde duracak?
Analizci, kullanıcı tarafından yazılmış rastgele SQL'i üretim veritabanında
çalıştıran bir uygulamanın ilk kontrol katmanıdır.

Baştan tahminimizce en belirleyici kriter: onay kuyruğunun sinyal kalitesi.

| Kriter | 1. Tek seviye: her risk engeller | 2. İki seviye: sert blok + işaretlenen risk | 3. Her risk yalnız uyarı |
| --- | --- | --- | --- |
| Performans | Etkisiz | Etkisiz | Etkisiz |
| Kompleksite | En düşük | Bir risk kümesi ve bir bypass kuralı | En düşük |
| Ölçeklenebilirlik | Onay kuyruğu kullanıcı sayısıyla şişer | Kuyruk yalnız gerçek kararlarla dolar | Kuyruk yok |
| Bakım | Eşik ayarları sürekli çekişme konusu | Eşikler ayar, bloklar sabit | Bakımı yok |
| Maliyet | Onaylayan zamanı | Onaylayan zamanı, daha az | Sıfır |
| Onay kuyruğunun sinyal kalitesi | Düşük: sıradan sorgular kuyruğa düşer, onaylayan mekanikleşir | Yüksek: kuyrukta yalnız insan kararı gerektiren sorgular kalır | Yok: kayıt var, kapı yok |
| Kabuk/dosya erişimine karşı koruma | Var ama admin bypass'ı deliyor | Var ve bypass edilemez | Yok |

## Karar

Seçilen alternatif: 2. İki seviye — sert blok ve işaretlenen risk.

Gerekçe: Sorgu risklerinin hepsi aynı türden değil. `WHERE`'siz bir `DELETE`
meşru olabilir ve sorumluluğu üstlenecek bir insan kararı gerektirir; buna
karşılık `xp_cmdshell` veya `pg_read_file` için WebQuery'de desteklenen bir yol
yoktur — bunlar bir yetki sorusu değildir. Aynı mekanizmayla ele almak iki hataya
birden yol açıyordu: gerçekten yasak olanı admin atlayabiliyordu, sıradan olan
ise onay kuyruğunu dolduruyordu. Sürekli onaylayan bir insan lastik damgaya
döner, ve rutin onaylayan bir onaylayıcı hiç onay olmamasından daha kötüdür,
çünkü sahte güvence üretir.

# ADR-0016: Analizci blok sınırı ve admin bypass'ının daraltılması

## Status

Accepted

## Context

`QueryAnalyzer.analyze()` tek bir boolean döndürüyordu ve `QueryService` bunu
`if not query_analysis["return"] and not is_db_admin` ile değerlendiriyordu.
Sonuç iki yönden de yanlıştı:

- Veritabanı admin'i için SQL injection, DDL, `WHERE`'siz `DELETE` — hepsi
  atlanıyordu. Analizcinin varlık sebebi olan kontroller bir rol tarafından
  tamamen devre dışı bırakılabiliyordu.
- `_check_sql_injection` yalnız `exp.Command` düğümlerine bakıyordu.
  `SELECT pg_read_file('/etc/passwd')` bir `exp.Anonymous` fonksiyon çağrısıdır
  ve hiç incelenmiyordu. `EXPLAIN ANALYZE UPDATE ...` ise opak bir komut olarak
  parse edildiği için içine bakılamıyordu.
- `max_joins = 3` sabitti ve `>=` ile karşılaştırılıyordu; üç tabloyu birleştiren
  sıradan bir raporlama sorgusu engellenip onaya düşüyordu.

Ayrıca sorgu çalıştırmanın tek yolu `POST /api/execute_query` değil: onaylanmış
workspace tekrar çalıştırması ve admin sorgu önizlemesi de hedef veritabanında
ifade yürütür ve bunların hiçbiri `analyze()` çağırmıyordu.

## Decision

Riskler iki sınıfa ayrılır.

**Sert bloklar** (`HARD_BLOCKED_RISKS` = `sql_injection_risk`,
`blocked_operation`): kimse tarafından atlanamaz. Kapsamı; ayrıştırılamayan
sorgu, dinamik çalıştırma, tehlikeli fonksiyon blocklist'i, sınır dışı `sleep`,
`EXPLAIN ANALYZE` ve DDL ile veri ifadelerini karıştıran batch'lerdir. Sorgu
çalıştıran her yol — sorgu endpoint'i, workspace tekrar çalıştırma, admin
önizleme — bunları uygular; ortak giriş noktası `hard_block_reason()`.

**Değerlendirilebilir riskler** (`ddl_pattern`, `risky_pattern`,
`performance_risk`): non-admin için onay akışına gider, admin için onay
gerekliliği atlanır ve atlama `logger.warning` ile loglanır, `risk_level` audit
kaydına yazılır.

Performans riski varsayılan olarak engellemez. `MAX_JOINS` varsayılanı 8'e
çıkarıldı, karşılaştırma `>` yapıldı ve `PERFORMANCE_BLOCKS` ile eski davranış
açılabilir hâlde bırakıldı.

Kademe tutarlılığı kontrolü yalnız DDL karışımını reddeder. `SELECT; UPDATE`
batch'i kabul edilir.

## Rejected Alternatives

### 1. Bütün karışık kademeli batch'leri reddetmek

Uygulama planının ilk hâli `SELECT; UPDATE` batch'lerini de reddediyordu;
gerekçe, onaylayanın tek bir sınıflandırma görmesiydi. Reddedildi: bu batch tek
bağlantıda, tek transaction'da, zaten hem okuyup hem yazabilen `rw` hesabıyla
çalışır. Bölmek atomikliği kaybettirir ve gündelik bir iş akışını bozar. Rol
kontrolü (`check_permissions_match_role`) ve kademe seçimi (`required_tier`)
zaten her ifadeyi ayrı ayrı değerlendirdiği için onaylayan yanıltılmıyor. DDL
karışımı ise ayrı: farklı ve daha yetkili bir hesapla çalışır, varsayılan olarak
kapalıdır ve tek bir sınıflandırmayla incelenmesi gerçekten güçtür.

### 2. Admin bypass'ını tamamen kaldırmak

Reddedildi. DB ADMIN yalnız `sql_injection_risk` ve `blocked_operation` sert
bloklarında durdurulur; `ddl_pattern`, `risky_pattern` ve `performance_risk`
için bypass kalıcı mevcut politikadır. Bypass'ı kaldırmak admin'i kendi hedef
veritabanı hesabına yönlendirir ve WebQuery audit izini kaybettirir. Gelecekteki
isteğe bağlı yıkıcı DML politikası bu kararı ancak ayrı bir spec/ADR ile
değiştirebilir.

### 3. Fonksiyon blocklist'i yerine allowlist

Güvenlik açısından daha güçlüdür. Reddedildi: üç farklı veritabanı motorunun
yerleşik fonksiyon kümesini eksiksiz listelemek ve sürüm başına güncel tutmak
gerçekçi değil; eksik bir allowlist meşru sorguları sessizce kırar.

## Consequences

- `RiskLevel` sözlüğüne `blocked_operation` eklendi. `risk_type` audit kaydına
  ve Slack bildirimine olduğu gibi yazılır; frontend bu alanı çözümlemeden rozet
  olarak gösterdiği için arayüz değişikliği gerekmedi.
- `analyze()` sözlüğüne opsiyonel `reason` ve `warnings` alanları eklendi.
  `reason`, engellenen sorguda kullanıcıya gösterilen mesajdır.
- Onay kuyruğuna düşen sorgu sayısı azalır; kuyrukta kalanlar gerçek kararlardır.
- `MAX_JOINS` ve `PERFORMANCE_BLOCKS` deployment yapılandırmasına girdi.
- Workspace ve admin önizleme yolları artık `analyze()` çağırır. Yalnız sert
  blok alt kümesi uygulanır, böylece admin'in bilerek onayladığı riskli sorgu
  tekrar çalıştırılabilir kalır.

## Accepted Risks

- Blocklist eksik kalabilir: listede olmayan tehlikeli bir yerleşik fonksiyon
  geçer. Azaltma: hedef veritabanı hesapları en düşük yetkiyle açılır
  (SPEC-0002), böylece fonksiyon çağrısı da o hesabın yetkisiyle sınırlıdır.
- Analizci, hedef veritabanında tanımlı bir fonksiyonun gövdesindeki yazma
  işlemini göremez. Bu, tasarım gereği `ro` hesabının kapattığı risktir; ayrı
  bir kontrol eklenmedi.
- `EXPLAIN ANALYZE` kontrolü metin üzerinde çalışır; içinde bu ifadeyi geçiren
  bir string literal yanlış pozitif üretebilir. Fail-closed tercih edildi.
- Admin bypass'ı, değerlendirilebilir riskler için bilinçli olarak açıktır.
  Atlamalar log ve audit kaydında görünmeye devam eder; sert bloklar hiçbir
  rol tarafından atlanamaz.

## References

- Spec: `docs/specs/SPEC-0019-query-analyzer-hardening.md`
- İlgili: `docs/specs/SPEC-0002-role-based-target-database-credentials.md`,
  `docs/adr/ADR-0005-role-based-target-database-credentials.md`,
  `docs/adr/ADR-0007-target-query-timeout.md`
- Supersedes / Superseded by: yok

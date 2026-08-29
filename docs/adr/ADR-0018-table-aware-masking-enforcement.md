# Trade-off Tablosu

Senaryo: `MaskingRule` satırları `(database_id, table_name, column_name,
masking_type)` olarak saklanıyor ama uygulama yalnız `column_name` okuyor.
Model ile motor arasındaki bu fark iki yönden kapatılabilir: motoru modele
yükseltmek ya da modeli motora indirmek.

Baştan tahminimizce en belirleyici kriter: kuralın yazarının niyetine sadakat.
Bir yönetici `Customers.email` yazdığında `Suppliers.email`'i kastetmiyor.

| Kriter | 1. Enforcement tablo farkındalığına taşınır (seçilen) | 2. Model kolon bazına indirilir | 3. Sonuç kümesi kolonları kaynak tabloya çözülür |
| --- | --- | --- | --- |
| Performans | Ek maliyet yok: tablo kümesi mevcut `QueryPlan`'dan gelir | Yok | Yüksek: her sorgu için sürücüden kolon metadata'sı |
| Kompleksite | Düşük | En düşük | Yüksek; sürücüye ve dialect'e bağımlı |
| Ölçeklenebilirlik | Fark yok | Fark yok | Fark yok |
| Bakım | Şema ve motor aynı şeyi söyler | `table_name` sütunu ölü kalır | Her sürücü için ayrı yol |
| Maliyet | Düşük | Düşük (ama veri kaybı: mevcut `table_name` değerleri atılır) | Yüksek |
| **Kural yazarının niyetine sadakat** | Tam | Sıfır: kural veritabanı genelinde uygulanır | Tam, hatta JOIN'lerde de doğru |

## Karar

Seçilen alternatif: **1. Enforcement tablo farkındalığına taşınır.**

Gerekçe: Belirleyici kriter, kuralın yazıldığı yerde kalması. Alternatif 2 bu
kriteri tamamen feda ediyor ve üstelik mevcut kayıtlardaki `table_name`
değerlerini geri dönülemez biçimde anlamsızlaştırıyor. Alternatif 3 en doğru
sonucu verir ama JOIN'li sorgularda dahi doğru olmak için ödenecek bedel —
her dialect'te sonuç kümesi kolon metadata'sı çözümlemek — bu bulgunun
büyüklüğüyle orantısız. Alternatif 1, maliyeti sıfıra yakın (tablo kümesi
zaten risk analizi için yapılan parse'tan geliyor) ve JOIN belirsizliğinde
güvenli yönde (aşırı maskeleme) hata yapıyor.

# ADR-0018: Maskeleme enforcement'ı tablo farkındalıklı olur

## Status

Accepted

## Context

Maskeleme kuralları `(database_id, table_name, column_name, masking_type)`
olarak saklanıyordu. Çalıştırma yolu ise tüm kuralların `column_name`
değerlerini tek bir kümeye toplayıp sonuç kümesindeki eşleşen her kolonu
maskeliyordu. `table_name` ve `masking_type` hiç okunmuyordu.

İki somut sonuç:

* `Customers.email` için yazılmış bir kural, aynı veritabanındaki
  `Suppliers.email` sonuçlarını da maskeliyordu. Bu **aşırı maskeleme**
  kullanıcıya veri kaybı olarak görünüyor ve nedeni hiçbir yerde
  görünmüyordu.
* Yönetim arayüzü bir `masking_type` seçtiriyordu; motor bu değeri hiç
  okumuyordu. Yani arayüz, uygulanmayan bir ayrıntı seviyesi vaat ediyordu.

## Decision

1. `common/security.py` içindeki `columns_to_mask()`, saklanan kuralları
   sorgunun `QueryPlan`'ında geçen tablolara göre çözer. Tablo kümesi, risk
   analizi için zaten yapılan tek parse'tan gelir; maskeleme ikinci bir
   parse tetiklemez.
2. Eşleşme büyük/küçük harf duyarsızdır ve şema niteliğini iki yönde de
   tolere eder: `dbo.Customers` kuralı `Customers` yazan sorguyla, `Customers`
   kuralı `dbo.Customers` yazan sorguyla eşleşir.
3. `table_name` alanı boş olan eski kayıtlar **her tabloya** uygulanmaya
   devam eder. Bir güvenlik kontrolünü veri biçimi yüzünden sessizce devre
   dışı bırakmak, aşırı maskelemekten kötüdür.
4. `masking_type` şemada kalır ama API sınırında (`MaskingRuleSchema`) tek
   kabul edilen değer `full`'dür. Motorun uygulayamayacağı bir kural, yazma
   anında reddedilir.
5. `MaskingRule` üzerinde `(database_id, table_name, column_name)` unique
   kısıtı eklenir (migration `a1b2c3d4e5f6`), böylece aynı kolona çelişen iki
   kural yazılamaz.

## Rejected Alternatives

### 1. Modeli kolon bazına indirmek

`table_name` sütununu kaldırıp kuralı veritabanı genelinde kolon adına
uygulamak. Motoru ve modeli hizalardı ve en az koda mal olurdu. Reddedilme
nedeni: kuralın yazarının niyetini kalıcı olarak siler. Yönetici
`Customers.email` yazarken bir tablo seçmiştir; bu seçimi şemadan silmek,
aşırı maskelemeyi bir hata olmaktan çıkarıp belgelenmiş davranışa çevirir.
Ayrıca mevcut satırlardaki `table_name` değerleri geri dönülemez biçimde
kaybolur.

### 2. Sonuç kümesi kolonlarını kaynak tabloya çözmek

En doğru sonuç: JOIN'li bir sorguda `Customers.email` maskelenirken
`Suppliers.email` maskelenmez. Reddedilme nedeni: sürücü sonuç kümesinde
kolon adı döner, kaynak tablo dönmez. Bunu çözmek her dialect için ayrı
metadata sorgusu ya da AST'den kolon-tablo eşlemesi gerektirir — takma adlar,
`SELECT *`, türetilmiş tablolar ve CTE'lerle hızla güvenilmez hâle gelen bir
iş. Bu bulgunun büyüklüğüyle orantısız.

## Consequences

- Bir kural artık yazıldığı tabloda kalıyor; başka tabloların aynı adlı
  kolonlarını etkilemiyor.
- Yönetim arayüzü artık motorun gerçekten uyguladığı tek stratejiyi
  gösteriyor; uygulanmayan bir seçenek sunmuyor.
- Unique kısıt, aynı kolona iki kural yazan mevcut veri varsa migration
  sırasında çakışma üretir. Migration bu durumu tespit eder.

## Accepted Risks

- **JOIN belirsizliği.** İki tabloyu birleştiren bir sorguda ikisinde de
  `email` kolonu varsa ve yalnız biri kurallıysa, ikisi de maskelenir. Sonuç
  kümesi kolonun hangi tablodan geldiğini taşımıyor. Bu bilinçli olarak
  güvenli yön: sızdırmaktansa fazla maskelemek. Reddedilen alternatif 2'nin
  gerekçesi de burada.
- **Boş `table_name` eski kayıtları** hâlâ veritabanı genelinde uygulanıyor,
  yani bu ADR'nin çözdüğü aşırı maskeleme o satırlar için sürüyor. Azaltma:
  bunlar yönetim arayüzünden düzenlendiğinde tablo alanı zorunlu olduğu için
  doğal olarak temizleniyorlar.

## References

- Spec: `docs/specs/SPEC-0024-table-aware-masking.md`
- Open question: `docs/open-questions.md` OQ-2026-013
- Denetim: `webquery_denetim_raporu.md` P2-6, P2-20i
- İlgili: `docs/specs/SPEC-0012-masking-truthfulness-and-uuid-normalisation.md`
- Supersedes / Superseded by: yok.

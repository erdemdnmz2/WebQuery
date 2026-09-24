# Trade-off Tablosu

Senaryo: Tarama, artık npm üzerinde düzeltilmeyen `xlsx` paketinde yüksek
şiddetli açık bildirirken sonuçları tarayıcıdan tek sayfalı XLSX olarak dışa
aktarma davranışı korunmalıdır.

Baştan tahmininizce en belirleyici kriter: Güvenlik düzeltmesi alabilen,
tarayıcı uyumlu bir kütüphaneyle mevcut dışa aktarma sözleşmesini korumak.

| Kriter | 1. `xlsx` paketini korumak | 2. `write-excel-file` kullanmak | 3. Sunucuda XLSX üretmek |
| --- | --- | --- | --- |
| Güvenlik açığını kapatma | Hayır; düzeltme sürümü yok | Evet; açık paket ağaçtan çıkar | Evet, ancak yeni sunucu yüzeyi gerekir |
| Mevcut tarayıcı sözleşmesi | Korunur | Korunur | API sözleşmesi değişir |
| Uygulama karmaşıklığı | Düşük, fakat kabul edilemez risk | Düşük; yalnız export modülü değişir | Yüksek; endpoint, yetki ve kaynak sınırı gerekir |
| Bakım | Açık backlog'u sürdürür | Ayrı, aktif paket bağımlılığı | Yeni backend bağımlılığı ve operasyon sorumluluğu |
| Başlangıç bundle etkisi | Dinamik import ile ertelenmiş | Dinamik import ile ertelenir | Frontend etkisi düşük, backend etkisi artar |

## Karar

Seçilen alternatif: 2. `write-excel-file` kullanmak.

Gerekçe: Bu dar dışa aktarma yüzeyinde `write-excel-file`, güvenlik açığı
bulunan paketi kaldırırken kullanıcıya açık API veya sonuç ekranı davranışını
değiştirmez. ExcelJS ile yapılan doğrulama, dinamik çıktı paketinin önceki
`xlsx` çıktısından belirgin biçimde büyük olduğunu gösterdi; daha dar kütüphane
bu maliyeti taşımıyor. Sunucu tarafı üretim ise bu iş için gerekli olmayan yeni
bir yetki ve kaynak sınırı tasarımı getirir.

# ADR-0024: Tarayıcı XLSX dışa aktarımında ExcelJS kullanımı

## Status

Accepted (2026-09-24)

## Context

`frontend/lib/export.ts`, sonuç kümesini `xlsx` (SheetJS 0.18.5) ile çalışma
kitabına dönüştürür. Bu paket için npm üzerinde güvenlik düzeltmesi yoktur ve
CI'daki `npm audit` yüksek şiddetli bulgu üretir. Dışa aktarma yalnız kullanıcı
isteğiyle, dinamik import edilen tek bir istemci modülünde çalışır.

## Decision

`xlsx` kaldırılacak ve `write-excel-file/browser` dinamik olarak import
edilecek. Tek sayfalı çalışma kitabı, ilk sonuç satırının anahtarlarından
başlık satırı oluşturacak; sonraki satırlar bu başlıklara göre eklenecek.
Tarayıcı yazıcısı, kullanıcının indirme iletişimini başlatacak. `xlsx` için
bağımlılık veya transitive bağımlılık bırakılmayacak.

## Rejected Alternatives

### 1. `xlsx` paketini korumak

En az kod değişikliği sağlar ancak yüksek şiddetli açığı ve sürekli kırmızı
audit sonucunu kalıcılaştırır.

### 2. Sunucuda XLSX üretmek

İstemci bundle'ını küçültebilir, fakat yeni bir veri indirme endpoint'i,
yetkilendirme, zaman/aşım ve büyük sonuç kümesi kaynak kontrolleri gerektirir.
Bu kapsamın dışında kalır.

## Consequences

- İndirilen dosyanın kullanıcı deneyimi korunur; ayrı bir Excel kütüphanesi
  API'sine geçirilir.
- Dışa aktarma için `write-excel-file` yükü yalnız kullanıcı seçtiğinde
  indirilir.
- Çıktı işlevi, gerçek bir XLSX buffer'ını yeniden açan otomatik testle
  doğrulanır.

## Accepted Risks

- `write-excel-file`, değer odaklı dışa aktarma ihtiyacını karşılar; ileride
  şablon, pivot veya formül işlevleri gerekirse ayrı bir değerlendirme gerekir.
  Kütüphane sürümü pinlenir, lockfile denetlenir ve audit merge kapısı altında
  tutulur.

## References

- Spec: `docs/specs/SPEC-0029-dependency-vulnerability-remediation.md`
- Supersedes / Superseded by: Yok

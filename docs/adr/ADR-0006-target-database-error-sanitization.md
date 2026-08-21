# Trade-off Tablosu

Senaryo: Hedef veritabanı sorgu ve workspace yürütme hatalarının istemciye,
uygulama loglarına ve audit kayıtlarına aktarılması.

Baştan tahmininizce en belirleyici kriter: Hassas altyapı ve credential
sızıntısını önlerken operasyonel teşhisi korumak.

| Kriter | 1. Ham hatayı her yerde döndür | 2. Her yerde jenerik hata | 3. Katman bazlı temizleme |
| --- | --- | --- | --- |
| İstemci güvenliği | Zayıf | Güçlü | Güçlü |
| Teşhis edilebilirlik | Güçlü | Zayıf | Güçlü |
| API davranış değişikliği | Yok | Geniş | Sınırlı |
| Uygulama karmaşıklığı | Düşük | Düşük | Orta |
| Credential güvenliği | Zayıf | Güçlü | Güçlü |

# ADR-0006: Hedef Veritabanı Hatalarını Katman Bazlı Temizleme

## Status

Accepted

## Context

Hedef veritabanı sürücüleri bağlantı, sunucu, veritabanı, servis hesabı ve bazen
parola içerebilen ham hata mesajları üretir. Bu mesajların istemciye dönmesi
WebQuery'nin iç altyapısını açığa çıkarır. Buna karşın operasyon ekibinin
teşhis yapabilmesi için log ve audit kayıtlarında bağlantı bilgilerine ihtiyaç
vardır.

## Decision

Yalnızca sorgu ve workspace hedef veritabanı yürütme akışlarında iki katmanlı
hata işleme uygulanacaktır:

1. İstemci mesajı bağlantı/altyapı ayrıntılarından temizlenecek; tanınan ve
   kullanıcı tarafından düzeltilebilen SQL hatalarının özü korunacaktır.
2. Log ve audit mesajı bağlantı bilgilerini koruyacak, ancak parola değerlerini
   kaydetmeden önce `[REDACTED]` ile maskeleyecektir.

Temizleme merkezi `common.errors` yardımcılarıyla yapılacak ve hem ad hoc sorgu
hem workspace yürütme akışı aynı kuralları kullanacaktır.

## Rejected Alternatives

### 1. Ham hatayı istemciye döndürmek

Operasyonel olarak kolaydır ancak iç ağ, hedef sistem ve credential bilgisi
sızıntısı yaratır.

### 2. Her hatayı her katmanda tamamen jenerikleştirmek

İstemci güvenlidir ancak destek teşhisini ve kullanıcının kendi SQL hatasını
düzeltme yeteneğini gereksiz yere azaltır; ayrıca kapsamı bu adımdan büyüktür.

## Consequences

- İstemci API'si bağlantı hatalarında daha az ayrıntı gösterir.
- Destek ekibi trace ID ile log/audit kaydındaki bağlantı ayrıntılarına ulaşabilir.
- Orijinal exception traceback'i parola sızıntısı riski nedeniyle loglanmaz; tür ve parola-maskeli mesaj loglanır.
- Parola redaksiyonu için merkezi regex kuralları ve testler bakım gerektirir.

## Accepted Risks

- Log/audit kayıtlarında bağlantı bilgileri bulunmaya devam eder; bu proje kararıdır.
- Regex tabanlı redaksiyon bilinmeyen parola formatlarını kaçırabilir; yaygın
  ODBC ve URI biçimleri test kapsamına alınacaktır.

## References

- Spec: `docs/specs/SPEC-0003-target-database-error-sanitization.md`
- Supersedes / Superseded by: Yok

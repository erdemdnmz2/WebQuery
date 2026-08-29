# Trade-off Tablosu

Senaryo: WebQuery'de kullanıcı yaşam döngüsü, hedef DB kaydı ve ilk DB ADMIN
ataması gibi platform kapsamlı işlemlerin güven kökü.

Baştan tahminimizce en belirleyici kriter: En az yetkiyle denetlenebilir ve
kilitlenmeye dayanıklı bir platform bootstrap/yönetişim sınırı kurmak.

| Kriter | 1. Ortam değişkeni allowlist | 2. Kalıcı OWNER + CLI bootstrap | 3. Herhangi bir DB ADMIN |
| --- | --- | --- | --- |
| Yetki kapsamı | Platform ayrı, kimlik deploy'a bağlı | Platform ayrı ve kullanıcıya bağlı | DB kapsamı platforma taşar |
| Audit edilebilirlik | Değişiklik uygulama audit'inde yok | Grant ve kullanım audit edilir | Kullanım audit edilir, grant sınırı bulanık |
| Bootstrap güvenliği | Basit ama iki kaynaklı kimlik | Açık CLI güven kökü | İlk DB/ADMIN döngüsü belirsiz |
| Operasyon | Yetki değişimi deploy ister | Migration + bir defalık CLI gerekir | Kolay ama aşırı geniş |
| Veri erişiminden ayrışma | Kısmi | Güçlü | Zayıf |
| Kilitlenme riski | Env ile geri alınabilir | Son OWNER guard + CLI kurtarma | Bir DB ADMIN bulunduğu sürece açık |

## Karar

Seçilen alternatif: 2. Kalıcı OWNER + CLI bootstrap.

Gerekçe: Platform yetkisi kalıcı kullanıcı kimliğine, audit kaydına ve açık bir
sunucu tarafı güven köküne bağlanır. OWNER'a otomatik veri/sorgu yetkisi
verilmemesi, platform işletimi ile üretim verisine erişimi ayırır. Son aktif
OWNER ve son DB ADMIN korumaları yönetişim kapsamının yanlışlıkla sahipsiz
bırakılmasını engeller.

# ADR-0017: Kalıcı Platform OWNER Sınırı ve CLI Bootstrap

## Status

Accepted

## Context

Mevcut `PLATFORM_ADMINS` ortam değişkeni, kullanıcı aktivasyonunu DB
`ADMIN`inden ayıran geçici bir sınırdır. Ancak platform yetki değişiklikleri
deploy gerektirir, grant işlemi uygulama audit'inde görünmez ve kullanıcı
durumuyla aynı veri kaynağında değildir. Ayrıca hedef DB kaydı halen herhangi
bir DB ADMIN tarafından yapılabilmekte ve kaydı yapan kişi yeni DB'nin ADMIN'i
olmaktadır.

OWNER kalıcılaştırılırken iki ters risk vardır: OWNER'ı DB süperkullanıcısına
dönüştürmek en az yetkiyi bozar; ilk OWNER'ı normal API'den üretmek ise
self-escalation veya “ilk kayıt kazanır” yarışı oluşturur.

## Decision

- `Users.is_platform_owner` platform kapsamının runtime tek kaynağıdır.
- İlk veya ek OWNER yalnız uygulama sunucusunda çalışan CLI bootstrap komutuyla
  verilir. Komut mevcut kullanıcıyı etkinleştirip yükseltebilir veya parolayı
  `getpass` ile alarak ilk aktif kullanıcıyı oluşturabilir.
- Uygulama startup'ta en az bir aktif OWNER ister ve yoksa bootstrap talimatıyla
  fail-closed durur.
- API/UI OWNER grant veya revoke edemez.
- OWNER kullanıcı aktivasyonu/devre dışı bırakma, hedef DB kaydı ve DB ADMIN
  kapsamını yönetir.
- DB kapsamındaki ADMIN endpoint'i yalnız veri rollerini yönetir; `ADMIN`
  yönetişim rolünü veremez ve veri rolü değişikliği sırasında mevcut ADMIN'i
  silemez.
- Hedef DB kaydı aktif bir ilk DB ADMIN ile atomiktir; OWNER otomatik olarak
  DB ilişkisi almaz.
- OWNER sorgu çalıştırma, sorgu görme, önizleme veya onay yetkisi kazanmaz.
  Bunlar DB kapsamlı açık rollerle verilir.
- Son aktif OWNER ve bir DB'nin son ADMIN'i uygulama API'siyle kaldırılamaz.
- `PLATFORM_ADMINS` runtime yetkilendirmesinden çıkarılır; tek kaynak ilkesi
  korunur.

## Rejected Alternatives

### 1. `PLATFORM_ADMINS` allowlist'ini kalıcılaştırmak

Şema ve bootstrap maliyeti düşüktür. Ancak grant/revoke deployment
konfigürasyonuna bağlıdır, uygulama audit'ine girmez ve hesap disable durumu ile
kolayca ayrışabilir. Geçiş çözümü olarak görevini tamamlamıştır.

### 2. İlk kayıt olan kullanıcıyı otomatik OWNER yapmak

Kurulumu kolaylaştırır fakat public/self-registration yüzeyinde yarış ve hesap
ele geçirme riski yaratır. Güven kökü açık bir sunucu operatörü eylemi olmalıdır.

### 3. OWNER'a bütün DB'lerde otomatik ADMIN vermek

Operasyonel olarak pratiktir fakat platform yönetişimi ile veri erişimini tek
süperkullanıcıda birleştirir. OWNER gerekirse belirli bir DB rolünü ayrıca ve
audit edilebilir biçimde alabilir.

## Consequences

- Deployment, migration sonrasında ilk startup'tan önce bootstrap komutunu
  çalıştırmalıdır.
- Mevcut `PLATFORM_ADMINS` kullanıcıları otomatik OWNER yapılmaz; operatör açıkça
  bootstrap eder.
- Frontend `/api/me` sözleşmesi ve yönetim sekmeleri OWNER alanına geçer.
- Platform ve DB yönetimi farklı backend domain/router sınırlarına ayrılır.
- OWNER kaybında kurtarma yine sunucu erişimiyle aynı CLI üzerinden yapılır.

## Accepted Risks

- Sunucu/metadata DB erişimi olan operatör OWNER verebilir; bu zaten migration
  ve uygulama sırlarına erişebilen güvenli operasyon sınırıdır ve audit edilir.
- OWNER değişiklikleri yalnız CLI olduğu için günlük yönetimden daha yavaştır;
  bu, seyrek ve yüksek etkili privilege değişimi için bilinçli sürtünmedir.
- Hedef DB silme yaşam döngüsü bu karara dahil değildir; kayıtlar bu sürümde
  OWNER API'sinden silinemez.

## References

- Spec: `docs/specs/SPEC-0021-platform-owner-governance.md`
- Supersedes: ADR-0013 içindeki geçici `PLATFORM_ADMINS` runtime kararı

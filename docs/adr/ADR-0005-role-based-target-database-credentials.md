# ADR-0005: Rol bazlı hedef veritabanı kimlik bilgileri

## Status

Accepted

## Context

Mevcut runtime bağlantıları tüm hedef veritabanları ve roller için
`CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD` kullanıyor. Bu durumda WebQuery'nin
uygulama katmanındaki rol kontrolü atlanırsa, bağlantının arkasında hedef DB
seviyesinde ikinci bir yetki sınırı bulunmuyor.

Hedef veritabanları WebQuery tarafından yönetilmiyor; bunların DBA ekipleri
tarafından yönetildiği kabul ediliyor. Bu nedenle WebQuery'nin hedef DB'de login,
user veya grant oluşturabilecek yüksek yetkili bir hesabı saklaması güvenlik
sınırını zayıflatır.

## Decision

Hedef DB runtime bağlantıları veritabanı başına ve role göre ayrı credential
bilgileriyle kurulacak:

- `ro`: salt-okuma sorguları için
- `rw`: DML sorguları için
- `ddl`: yalnızca açıkça ihtiyaç duyulan ve ayrıca provision edilen hedef DB'ler
  için; varsayılanı yoktur

Hedef DB hesaplarını DBA hedef sunucuda manuel oluşturur. DBA credential'ları
admin'e güvenli kanal üzerinden verir. Admin bunları WebQuery'nin veritabanı
ekleme akışına girer. WebQuery yalnızca credential'ları kendi veritabanında
şifreli saklar ve sorgu kademesine göre kullanır; hedef DB'de provisioning veya
yetki değişikliği yapmaz.

## Rejected Alternatives

### 1. Tek merkezi hesabı runtime'da kullanmaya devam etmek

Uygulaması daha basittir ve env yönetimi gerektirir. Ancak tüm hedef DB'lerde ve
rollerde aynı yetkiye sahip olduğu için uygulama katmanındaki tek bir bypass,
hedef veride daha geniş etki yaratır. Savunma derinliği sağlanmadığı için
reddedildi.

### 2. WebQuery'nin hedef hesapları otomatik oluşturması

Admin deneyimini kolaylaştırır. Ancak bunun için WebQuery'nin `CREATE LOGIN`,
`CREATE USER` veya `GRANT` yetkisi taşıması gerekir. Böyle bir hesap, uygulamanın
kendi kısıtlarını kaldırabilmesi anlamına gelir; bu nedenle reddedildi.

### 3. Credential'ları yalnızca environment variable'larda tutmak

Secret yönetimi basit görünür. Ancak yeni hedef DB'ler çalışma zamanında
eklenebilir ve her DB/role için ayrı değerler gerektiğinden env modeli yeniden
başlatma ve ölçekleme operasyonunu gereksiz şekilde zorlaştırır. Credential'lar
WebQuery'nin kendi DB'sinde, Fernet ile şifreli veri olarak tutulacaktır.

## Consequences

- Uygulama katmanı ve hedef DB yetkileri birlikte savunma sağlar.
- Admin'e credential girişi ve güvenli DBA aktarım süreci eklenir.
- `Databases` modeline role bazlı credential alanları ve Alembic migration'ı
  gerekir.
- Engine cache anahtarları credential kademesini ayırt etmek zorunda kalır.
- Credential rotasyonu için ileride ayrı bir operasyonel akış tasarlanmalıdır.

## Accepted Risks

- Admin credential'ları WebQuery formuna girerken kısa süreli plaintext işleme
  ihtiyacı vardır; azaltma olarak TLS, erişim kontrolü, secret'ın response/list
  endpoint'lerinde gösterilmemesi ve şifreli at-rest saklama zorunludur.
- DBA provisioning adımı manuel kaldığı için hesap/yetki hataları mümkündür;
  azaltma olarak role başına minimum yetki scriptleri ve bağlantı doğrulaması
  kullanılacaktır.

## References

- Spec: `docs/specs/SPEC-0002-role-based-target-database-credentials.md`
- Open question: `OQ-2026-002`
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 16 (`3.1`)
- Supersedes / Superseded by: yok

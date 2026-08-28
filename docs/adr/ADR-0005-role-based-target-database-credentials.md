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

Admin kayıt ekranı yalnız üç hiyerarşik bağlantı modunu destekler: `ro`,
`ro + rw` ve `ro + rw + ddl`. Böylece `rw` veya `ddl` hesabı daha düşük
yetki kademeleri olmadan tek başına kaydedilemez.

Kademe, kullanıcı tarafından seçilmez. Hedef veritabanı arayüzde tek kayıttır;
çalıştırılacak kademe `QueryAnalyzer` tarafından sorgudan türetilir. Sorgu
ekranı yalnız türetilmiş bir `capability` değeri görür: kaydın bağlantı modunun
kullanıcının rolüyle kesişimi. Kaydın ham modu ve credential değerleri (şifre
ve kullanıcı adı) bu response'a girmez. Kaydın hangi kademeleri sağladığı
yalnız admin yüzeyinde gösterilir.

Yetki verme kaydın sağladığını aşamaz: bir kullanıcıya, hedef veritabanında
credential'ı tanımlı olmayan bir kademeyi gerektiren rol verilemez. `ADMIN`
yönetişim rolü olduğu ve kaydı yöneten kişiye her modda verildiği için muaftır.

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

### 4. Sorgu ekranında kaydın ham bağlantı modunu göstermek

Uygulaması daha ucuzdur; kullanıcı rolü hesaba katılmaz. Ancak `ro + rw`
moduyla kayıtlı bir veritabanı `READER` rolündeki kullanıcıya da "yazma"
yeteneği vaat eder ve sorgu çalıştırıldığında rol kontrolü reddeder. Rozetin
niyetten değil gerçekleşecek davranıştan türetilmesi gerektiği için reddedildi
(`frontend/DESIGN.md` §9, aynı ilke maskeleme rozeti için de geçerlidir).

### 5. Kademeleri ayrı veritabanı kayıtları olarak listelemek

Credential modelini doğrudan yansıtır. Ancak kullanıcı aynı veritabanını üç
kez görür ve kendi kademesini seçmek zorunda kalır; bu, en düşük yetkili hesabı
seçme kararını uygulamadan kullanıcıya taşır ve modelin güvenlik amacını
ortadan kaldırır. Reddedildi.

## Consequences

- Uygulama katmanı ve hedef DB yetkileri birlikte savunma sağlar.
- Admin'e credential girişi ve güvenli DBA aktarım süreci eklenir.
- `Databases` modeline role bazlı credential alanları ve Alembic migration'ı
  gerekir.
- Engine cache anahtarları credential kademesini ayırt etmek zorunda kalır.
- Credential rotasyonu için ileride ayrı bir operasyonel akış tasarlanmalıdır.
- `GET /api/database_information` kullanıcı rolünü de okumak zorundadır. Bu
  ek maliyet getirmez: rol, zaten okunan association satırının bir kolonudur ve
  bağlantı modu provider'ın bellek içi kataloğundan gelir.
- Bir hedef veritabanının bağlantı modu daraltılırsa, o kaydın önceden verilmiş
  yüksek kademeli yetkileri geçersiz kalır. Kayıt güncelleme akışı eklendiğinde
  mevcut association'ların da doğrulanması gerekir.

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
- Open question: `OQ-2026-007`
- Open question: `OQ-2026-008`
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 16 (`3.1`)
- Supersedes / Superseded by: yok

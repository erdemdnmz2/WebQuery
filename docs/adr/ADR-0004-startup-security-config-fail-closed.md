# ADR-0004: Kritik startup sırlarında fail-closed davranış

## Status

Accepted

## Context

WebQuery daha önce `SECRET_KEY` ve `QUERY_ENCRYPTION_KEY` eksikken bilinen
varsayılan değerlerle çalışabiliyordu. Bu davranış JWT imzalama anahtarını
tahmin edilebilir hale getiriyor ve şifreli görünen verilerin herkesçe bilinen
bir anahtarla korunmasına neden oluyordu.

Bu değerler ayrıca uygulamanın kimlik doğrulama ve `EncryptedText` katmanlarına
dağılıyor. Kontrolü ilk kullanıma bırakmak, hatayı startup yerine ilk istek veya
ilk şifreleme işlemine erteliyor.

## Decision

Uygulama startup'ının en başında merkezi bir konfigürasyon guard çalıştırılacak.
Guard, kritik ortam değişkenlerini, JWT anahtarı uzunluğunu ve Fernet anahtarı
geçerliliğini doğrulayacak. Başarısız doğrulama `SystemExit(1)` ile servisin
başlamasını engelleyecek.

`EncryptedText` fallback anahtar üretmeyecek; anahtar yoksa açıkça hata verecek.
Kimlik doğrulama konfigürasyonu varsayılan JWT anahtarı kullanmayacak.

Veritabanı bağlantı konfigürasyonu da yüksek yetkili `sa` hesabını sessiz
varsayılan olarak seçmeyecek. `CENTRAL_DB_USER` açıkça `sa`, `root`, `postgres`
veya `admin` olarak verilirse uygulama başlatılabilir, ancak bu tercih uyarı
olarak loglanacak. Hedef DB'lerde role bazlı credential modeline geçiş
`ADR-0005` ile tanımlanır.

## Rejected Alternatives

### 1. Eksik sırda bilinen varsayılanla devam etmek

Geliştirme ortamında kolaydır; ancak production'da sahte JWT ve çözülebilir
şifreli veri riski oluşturduğu için kabul edilemez.

### 2. Yalnızca warning loglayıp uygulamayı başlatmak

Operasyon ekibine görünürlük sağlar; fakat warning gözden kaçtığında servis
güvensiz durumda çalışmaya devam eder. Güvenlik sınırı için yeterli değildir.

### 3. Her kullanım noktasında ayrı ayrı kontrol yapmak

Kapsamı genişletir ve bir kullanım noktasının unutulması riskini taşır. Merkezi
startup kontrolü ile birlikte yalnızca savunma amaçlı fail-closed kontroller
korunacaktır.

## Consequences

- Production ve CI dışındaki her ortam geçerli test/development sırlarını açıkça
  sağlamalıdır.
- Yanlış veya eksik deploy konfigürasyonu servis başlamadan fark edilir.
- Eksik DB kullanıcı ayarı artık sessizce `sa` hesabına dönüşmez; yüksek yetkili
  hesap kullanımı görünür bir operasyonel uyarı üretir.
- Secret manager veya rotasyon sistemi bu ADR'nin kapsamı dışındadır.
- Test fixture'ları gerçek olmayan ancak biçimsel olarak geçerli değerler
  tanımlamak zorundadır.

## Accepted Risks

- Secret rotasyonu ve secret manager entegrasyonu henüz yoktur. Azaltma olarak
  varsayılan değerler tamamen kaldırılmış ve ileride rotasyon için açık bir
  ortam değişkeni sözleşmesi bırakılmıştır.

## References

- Spec: `docs/specs/SPEC-0001-startup-security-config-guard.md`
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 3 (`0.1`)
- Supersedes / Superseded by: yok

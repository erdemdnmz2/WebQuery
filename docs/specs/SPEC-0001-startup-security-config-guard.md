# Mini-Spec: Başlangıç güvenlik konfigürasyonu doğrulaması

## 1. Spec Kartı

- Özellik: Startup Security Config Guard
- Durum: Implemented
- Versiyon: 2026-08-21
- Tarih: 2026-08-21
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Uygulamanın güvenlik açısından kritik ortam değişkenleri eksik, zayıf veya
bilinen varsayılan değerlerdeyken çalışmasını engellemek.

### Başarı Sinyali

- Eksik veya geçersiz kritik konfigürasyonda uygulama startup sırasında
  `SystemExit(1)` ile kapanır.
- Geçerli konfigürasyonda uygulama mevcut başlangıç akışını sürdürür.
- Şifreleme katmanı, ortam değişkeni yokken sabit/fallback anahtar üretmez.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `SECRET_KEY`, `QUERY_ENCRYPTION_KEY`, `APP_DATABASE_URL`,
  `CENTRAL_DB_USER` ve `CENTRAL_DB_PASSWORD` doğrulaması.
- Veritabanı bağlantı konfigürasyonunda `sa` gibi yüksek yetkili kullanıcıların
  sessiz varsayılan olarak seçilmemesi.
- `CENTRAL_DB_USER` değeri yüksek yetkili bir hesap olduğunda uyarı loglanması.
- JWT anahtarı için minimum uzunluk kontrolü.
- Fernet anahtarı biçim kontrolü.
- Startup kontrolünün uygulama lifespan'ının en başında çalıştırılması.
- Test ve örnek ortamların açıkça geçerli, gerçek olmayan değerlerle kurulması.

### Kapsam Dışı

- Hedef veritabanı bağlantı kimlik bilgilerinin uygulanması; bu sözleşme
  `SPEC-0002` ile tanımlanır.
- Secret manager, anahtar rotasyonu veya secret dağıtım altyapısı.
- Mevcut JWT algoritmasının değiştirilmesi.

## 4. Sözleşme

Uygulama startup sırasında güvenlik konfigürasyonunu doğrular. Doğrulama
başarısızsa servis istek kabul etmeden kapanır ve stderr/log üzerinde hangi
konfigürasyon alanının eksik veya geçersiz olduğu bildirilir; secret değeri
loglanmaz.

## 5. İş Kuralları

### BR-01: Kritik değişkenler zorunludur

Kritik değişkenlerden biri eksik, boş veya bilinen güvensiz varsayılan değerdeyse
uygulama açılmaz.

### BR-02: JWT anahtarı yeterli uzunlukta olmalıdır

`SECRET_KEY` en az 32 karakter olmalıdır.

### BR-03: Şifreleme anahtarı geçerli Fernet anahtarı olmalıdır

`QUERY_ENCRYPTION_KEY`, Fernet tarafından kabul edilen bir anahtar değilse
uygulama açılmaz.

### BR-04: Şifreleme fail-closed çalışır

`QUERY_ENCRYPTION_KEY` runtime'da yoksa `EncryptedText` fallback anahtar
üretmez; açık bir hata verir.

### BR-05: Yüksek yetkili veritabanı kullanıcıları varsayılan olamaz

`DB_USER` veya uygulama veritabanı kullanıcı ayarı eksik olduğunda sistem
`sa` değerini kendiliğinden seçmez. `CENTRAL_DB_USER` yüksek yetkili bir hesap
(`sa`, `root`, `postgres`, `admin`) olarak verilmişse uygulama açılabilir ancak
uyarı loglanır; bu hesap seçimi sessiz gerçekleşmez.

## 6. Acceptance Criteria

- AC-01: Given `SECRET_KEY` boşken, when startup config doğrulanır, then
  `SystemExit(1)` oluşur.
- AC-02: Given bilinen varsayılan JWT anahtarı varken, when startup config
  doğrulanır, then `SystemExit(1)` oluşur.
- AC-03: Given 32 karakterden kısa `SECRET_KEY` varken, when startup config
  doğrulanır, then `SystemExit(1)` oluşur.
- AC-04: Given geçersiz Fernet anahtarı varken, when startup config doğrulanır,
  then `SystemExit(1)` oluşur.
- AC-05: Given kritik değişkenlerden biri eksikken, when uygulama lifespan'ı
  başlarsa, then veritabanı bağlantısı kurulmadan startup başarısız olur.
- AC-06: Given `QUERY_ENCRYPTION_KEY` yokken, when `EncryptedText` bir değeri
  işlemek için kullanılır, then fallback anahtar üretilmeden açık hata oluşur.
- AC-07: Given tüm değerler geçerliyken, when startup config doğrulanır, then
  doğrulama başarılı olur ve hiçbir secret loglanmaz.
- AC-08: Given `DB_USER` tanımlı değilken, when database config yüklenirse,
  then kullanıcı değeri `sa` olarak varsayılmaz.
- AC-09: Given `CENTRAL_DB_USER=sa` iken, when startup config doğrulanır, then
  doğrulama başarılı olabilir ancak yüksek yetkili hesap uyarısı loglanır.

## 7. Teknik ve Güvenlik Kısıtları

- Secret değerleri loglara, hata mesajlarına veya dokümantasyona yazılmaz.
- Test değerleri yalnızca test ortamına ait sahte değerler olmalıdır.
- Startup kontrolü veritabanı bağlantısı ve diğer servis başlatmalarından önce
  çalışmalıdır.
- Şema yönetimi Alembic kararından etkilenmez.

## 8. Open Questions

- Yok. OQ-2026-002, `SPEC-0002` ve `ADR-0005` ile cevaplanmıştır.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi
- [x] Doğrulama komutları çalıştırıldı; pytest ortamda kurulu olmadığı için
  doğrudan davranış ve derleme kontrolleri yapıldı

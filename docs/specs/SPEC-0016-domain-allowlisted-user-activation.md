# SPEC-0016: Şirket Alan Adı ile Kayıt ve Kullanıcı Aktivasyonu

## 1. Spec Kartı

- Özellik: Domain allowlist ile kayıt ve platform yöneticisi aktivasyonu
- Durum: Implemented
- Versiyon: 1.0.0
- Tarih: 2026-08-25
- Sahip: WebQuery

## 2. Amaç ve Başarı Sinyali

### Amaç

Şirket içi WebQuery kurulumunda çalışanların izin verilen şirket e-posta alan
adıyla kayıt başvurusu yapabilmesini, ancak uygulama ve hedef veritabanı
erişiminin platform yöneticisi tarafından etkinleştirilmesini sağlamak.

### Başarı Sinyali

- İzin verilen domain dışındaki kayıt istekleri kullanıcı oluşturmadan
  reddedilir.
- İzin verilen domain içindeki kullanıcı başvurusu `Users` tablosuna pasif
  hesap olarak kaydedilir.
- Pasif kullanıcı giriş yapamaz ve korumalı endpoint'lere erişemez.
- Platform yöneticisi bekleyen kullanıcıyı etkinleştirebilir.
- Kullanıcı veritabanı erişimi almadan sorgu çalıştıramaz.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `ALLOWED_EMAIL_DOMAINS` ile tam domain eşleşmesi.
- `POST /api/register` ile pasif kullanıcı oluşturulması.
- `PLATFORM_ADMINS` allowlist'i ile platform yöneticisi kontrolü.
- Platform yöneticisinin kullanıcıları listelemesi ve etkinleştirmesi.
- `/api/me` yanıtında `is_platform_admin` bilgisi.
- Kayıt, aktivasyon ve mevcut disable akışlarının audit edilmesi.
- Admin ekranında kullanıcıların bekleyen/aktif/devre dışı durumlarının
  gösterilmesi ve aktivasyon eylemi.

### Kapsam Dışı

- Bu değişiklikte kalıcı `OWNER` rolünün eklenmesi.
- E-posta doğrulama veya davet bağlantısı gönderimi.
- Kullanıcı-veritabanı rol ilişkilendirme modelinin değiştirilmesi.
- Yeni kullanıcıya otomatik veritabanı erişimi verilmesi.
- `ADMIN` rolünün platform yöneticisi rolüne dönüştürülmesi.

## 4. Sözleşme

### Ortam değişkenleri

```text
ALLOWED_EMAIL_DOMAINS=company.com,subsidiary.company.com
PLATFORM_ADMINS=platform-admin-username
REGISTRATION_REQUIRES_ACTIVATION=true
```

`ALLOWED_EMAIL_DOMAINS` boşsa self-registration kapalıdır. Domain değerleri
başında `@` olsa da olmasa da normalize edilir; eşleşme tam domain üzerinden
yapılır.

### Kayıt

`POST /api/register` izin verilen domain için kullanıcıyı `is_active=false`
olarak oluşturur ve genel bir başarı mesajı döndürür. Kullanıcıya otomatik
oturum açılmaz. Domain uygun değilse `403` döner ve kullanıcı oluşturulmaz.

Test ortamı veya kontrollü geçiş için `REGISTRATION_REQUIRES_ACTIVATION=false`
verildiğinde izin verilen domain kayıtları aktif oluşturulabilir; üretim
varsayılanı pasif aktivasyondur.

### Platform kullanıcı yönetimi

- `GET /api/admin/users`: yalnızca `PLATFORM_ADMINS` üyeleri çağırabilir.
- `POST /api/admin/users/{user_id}/enable`: yalnızca `PLATFORM_ADMINS`
  üyeleri çağırabilir; pasif hesabı etkinleştirir.

Kullanıcı aktivasyonu, hedef veritabanı erişimi vermez. Erişim ayrıca mevcut
`POST /api/admin/associate_user` akışıyla, ilgili veritabanındaki `ADMIN`
yetkisi kapsamında verilir.

## 5. İş Kuralları

### BR-01: Domain allowlist fail-closed

Allowlist boşsa veya kayıt e-postasının domain'i listede değilse kayıt
başvurusu reddedilir; hiçbir `User` satırı yazılmaz.

### BR-02: Kayıt ile erişim ayrıdır

Kayıt olan kullanıcıya otomatik hedef veritabanı ilişkisi veya rol verilmez.

### BR-03: Aktivasyon gereklidir

Aktivasyon gereken üretim akışında yeni kullanıcı pasif oluşturulur. Pasif
hesap login, refresh ve mevcut oturum doğrulama kontrollerinden geçemez.

### BR-04: Platform ve veritabanı kapsamları ayrıdır

`ADMIN`, veritabanı kapsamlı yönetişim rolüdür. Kullanıcı aktivasyonu platform
kapsamlı olduğu için bu değişiklikte `PLATFORM_ADMINS` allowlist'i ile korunur.

### BR-05: Aktivasyon idempotent ve audit edilebilir olmalıdır

Zaten aktif hesabı tekrar etkinleştirmek yeni bir durum değişikliği oluşturmaz;
gerçek durum değişiklikleri `USER_ENABLED` audit kaydı üretir.

## 6. Acceptance Criteria

- AC-01: Given `ALLOWED_EMAIL_DOMAINS` boş, when register çağrılır, then `403`
  döner ve kullanıcı oluşturulmaz.
- AC-02: Given e-posta domain'i allowlist'te değil, when register çağrılır,
  then `403` döner ve kullanıcı oluşturulmaz.
- AC-03: Given domain izinli ve aktivasyon gerekli, when register çağrılır,
  then kullanıcı `is_active=false` ile oluşturulur.
- AC-04: Given kullanıcı pasif, when login veya refresh denenir, then istek
  reddedilir.
- AC-05: Given platform yöneticisi, when kullanıcı listesi istenir, then
  bekleyen/aktif/devre dışı kullanıcılar durumlarıyla döner.
- AC-06: Given platform yöneticisi, when pasif kullanıcı enable edilir, then
  kullanıcı aktif olur ve `USER_ENABLED` audit kaydı yazılır.
- AC-07: Given normal veritabanı ADMIN'i, when platform kullanıcı listesi veya
  enable endpoint'i çağrılır, then istek `403` ile reddedilir.
- AC-08: Given aktif kullanıcı, when veritabanı ilişkisi yok, then sorgu
  çalıştırma yetkisi oluşmaz.

## 7. Teknik ve Güvenlik Kısıtları

- Domain kontrolü yalnız frontend'de değil backend'de zorunlu olarak yapılır.
- Parolalar mevcut `User.set_password` hash mekanizmasıyla saklanır.
- Aktivasyon ve kayıt audit log'a yazılır; parola audit detayına yazılmaz.
- `is_active` mevcut kullanıcı yaşam döngüsü alanı olarak korunur; bu değişiklik
  yeni bir OWNER rolü eklemez.
- `PLATFORM_ADMINS` boşsa platform kullanıcı yönetimi kapalı kalır; uygulama
  başlatılamaz hâle getirilmez ancak uyarı loglanır.

## 8. Open Questions

- Yok. Kalıcı `OWNER` rolü bu özelliğin kapsamı dışında bırakılmış ve Adım 20
  için ertelenmiştir.

## 9. Done Kontrolü

- [x] Acceptance criteria için backend testleri eklendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [x] Doğrulama komutları çalıştırıldı

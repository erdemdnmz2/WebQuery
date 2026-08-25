# ADR-0013: Domain Allowlist ve Platform Aktivasyonu

## Status

Accepted

## Context

WebQuery şirket içi bir SQL gateway olarak kullanılacak. Self-registration'ın
tamamen açık bırakılması istenmiyor; ancak çalışanların şirket e-posta alan
adıyla kayıt başvurusu yapabilmesi isteniyor. Mevcut `ADMIN` rolü bir hedef
veritabanına bağlıdır. Kullanıcı aktivasyonu ise platform seviyesinde bir
işlemdir ve herhangi bir veritabanının ADMIN'ine bırakılmamalıdır.

## Decision

Kayıt akışı şu şekilde uygulanır:

1. `ALLOWED_EMAIL_DOMAINS` backend tarafından kontrol edilir.
2. Allowlist dışı veya allowlist boşken kayıt reddedilir.
3. İzinli kullanıcı `Users` tablosuna pasif (`is_active=false`) oluşturulur.
4. Üretimde `REGISTRATION_REQUIRES_ACTIVATION=true` kullanılır.
5. Aktivasyon, geçici platform yetki sınırı olarak `PLATFORM_ADMINS`
   kullanıcı allowlist'i ile korunur.
6. Aktivasyon hedef veritabanı erişimi vermez; veritabanı rolü ayrı bir
   `UserDatabaseAssociation` işlemiyle atanır.
7. Kalıcı `OWNER` rolü ve kullanıcı tabanlı platform kapsamı Adım 20'ye
   bırakılır.

## Rejected Alternatives

### 1. Self-registration'ı tamamen kapatmak

En basit modeldir; ancak şirket içindeki çalışanların başvuru deneyimini
ortadan kaldırır ve her hesabın admin tarafından manuel oluşturulmasını
gerektirir.

### 2. Domain allowlist ile kullanıcıyı hemen aktif oluşturmak

Domain sahipliği tek başına kişinin WebQuery kullanmasına izin verilmesi için
yeterli kabul edilmez. Yanlış veya ele geçirilmiş bir şirket hesabı doğrudan
uygulama kimliği kazanabilir.

### 3. Aktivasyonu veritabanı ADMIN'ine vermek

`ADMIN` veritabanı kapsamlıdır. Bir DB ADMIN'inin platformdaki kullanıcıları
etkinleştirebilmesi yetki kapsamını gereksiz biçimde genişletir.

### 4. Hemen kalıcı OWNER rolü eklemek

OWNER uzun ömürlü bir yetki modeli, migration, bootstrap ve her platform
endpoint'inde ikinci bir kapsam kontrolü gerektirir. Mevcut ihtiyaç için
`PLATFORM_ADMINS` allowlist'i daha küçük ve geri alınabilir bir geçiş çözümüdür.

## Consequences

- Kullanıcı başvurusu ile uygulama erişimi ve hedef DB erişimi üç ayrı aşama
  olarak görünür hâle gelir.
- `is_active` alanı Adım 12'nin mevcut yaşam döngüsü kontrolüyle yeniden
  kullanılır; yeni şema alanı gerekmez.
- Platform yöneticisi allowlist'i güvenli şekilde boş bırakılabilir, fakat o
  durumda hiçbir kullanıcı aktivasyonu yapılamaz.
- Frontend kullanıcı yönetimi yalnızca platform yöneticilerine gösterilir.
- İleride `PLATFORM_ADMINS` yerine `User.is_platform_owner` geçirilebilir.

## Accepted Risks

- Başvuru sırasında parola hash'i Users tablosunda pasif hesapla birlikte
  tutulur; parola düz metin tutulmaz. E-posta tabanlı aktivasyon/davet akışı
  ileride eklenebilir.
- `is_active=false` ve `disabled_at is None` bekleyen aktivasyon olarak
  yorumlanır; mevcut eski/incomplete kayıtlar için geçiş sırasında dikkat
  gerekir.

## References

- Spec: `docs/specs/SPEC-0016-domain-allowlisted-user-activation.md`
- Plan: `webquery_implementasyon_sirasi.md`, Adım 13 ve Adım 20

# Adım 20 OWNER Yönetişimi — Uygulama Bilgilendirmesi

## Teslim durumu

- Durum: Uygulama tamamlandı, review ve deployment'a hazır
- Tarih: 2026-08-29
- Kapsam: Adım 20'nin kontrol hiyerarşisi ve platform OWNER bölümü
- Bilinçli erteleme: satır sayımı ve genel yıkıcı DML teyidi
- Spec: `docs/specs/SPEC-0021-platform-owner-governance.md`
- ADR: `docs/adr/ADR-0017-persisted-platform-owner-boundary.md`

## Sonuç

Platform kapsamı ile hedef veritabanı kapsamı birbirinden ayrıldı. Kalıcı
`OWNER`, kullanıcı yaşam döngüsünü, hedef veritabanı kaydını ve DB ADMIN
atamalarını yönetiyor. DB `ADMIN` ise yalnız ilişkili olduğu veritabanında
sorgu onayı, maskeleme ve veri rollerini yönetmeye devam ediyor.

OWNER olmak otomatik sorgu, onay, maskeleme veya hedef DB erişimi vermiyor.
OWNER bu yeteneklerden birine ihtiyaç duyarsa ilgili veritabanında ayrıca açık
bir ilişki/rol alması gerekiyor.

## Uygulanan kararlar

### Admin sorgu sınırı

DB ADMIN yalnız iki sert blokta durduruluyor:

- `sql_injection_risk`
- `blocked_operation`

`ddl_pattern`, `risky_pattern` ve `performance_risk` için mevcut admin bypass'ı
korundu. Bu atlamalar log ve audit kaydında görünmeye devam ediyor. Politika
ADR-0016'da geçici durum olmaktan çıkarılıp açık karar olarak kaydedildi.

### Satır sayımı ve DML teyidi

Bu teslimatta aşağıdakiler uygulanmadı:

- `UPDATE`/`DELETE` öncesi etkilenecek satır sayımı
- Sayıma bağlı onay eşiği
- Genel yıkıcı DML teyit penceresi veya teyit jetonu
- `CONFIRMATION_SECRET`

Ertelenen tasarım `docs/inbox/OPTIONAL-DESTRUCTIVE-DML-CONFIRMATION.md` içinde
ayrı bir isteğe bağlı özellik olarak tutuluyor.

## Backend uygulaması

### Kalıcı OWNER modeli

`Users` tablosuna `is_platform_owner` alanı eklendi:

- NOT NULL
- varsayılan `false`
- indexli
- SQLite ve MSSQL uyumlu Alembic migration ile yönetiliyor

Schema startup guard sözleşmesi yeni kolon ve index ile güncellendi. Eski
pre-Alembic kurulumları onaran migration, daha sonraki revision'larda gelecek
kolonları erkenden indexlemeye çalışmayacak şekilde ileri uyumlu hale getirildi.

### Bootstrap ve startup koruması

İlk ve ek OWNER yalnız sunucu tarafı komutuyla verilebiliyor. HTTP API veya
arayüz OWNER grant/revoke sunmuyor.

Mevcut kullanıcıyı OWNER yapmak için:

```bash
cd web_api
python -m alembic upgrade head
python -m scripts.bootstrap_owner --email owner@company.com
```

Yeni ilk kullanıcıyı OWNER olarak oluşturmak için:

```bash
cd web_api
python -m alembic upgrade head
python -m scripts.bootstrap_owner \
  --email owner@company.com \
  --username owner_username
```

Parola komut argümanı olarak kabul edilmiyor. Terminalde `getpass` ile iki kez,
görünmeden isteniyor. E-posta doğrulanıyor; parola mevcut güvenlik politikasıyla
hashleniyor. Grant işlemi `owner_granted` audit kaydı oluşturuyor.

Uygulama startup sırasında en az bir aktif OWNER arıyor. Bulamazsa fail-closed
duruyor ve bootstrap komutunu logda gösteriyor. Bu nedenle deployment sırası:

1. Migration'ı uygula.
2. İlk OWNER'ı bootstrap et.
3. Uygulamayı başlat.

### OWNER modülü ve API

Yeni `web_api/owner/` domain modülü kendi dependency, schema, exception,
service ve router katmanlarına sahip.

| Endpoint | Yetki | Davranış |
| --- | --- | --- |
| `GET /api/owner/users` | OWNER | Kullanıcıları durum ve OWNER bilgisiyle listeler |
| `POST /api/owner/users/{id}/enable` | OWNER | Hesabı etkinleştirir |
| `POST /api/owner/users/{id}/disable` | OWNER | Hesabı kapatır, oturumları iptal eder |
| `GET /api/owner/databases` | OWNER | Credential içermeyen DB listesini döner |
| `POST /api/owner/databases` | OWNER | DB ve ilk aktif DB ADMIN'i atomik oluşturur |
| `GET /api/owner/database-admins` | OWNER | DB ADMIN atamalarını listeler |
| `POST /api/owner/databases/{db}/admins/{user}` | OWNER | Aktif kullanıcıya DB ADMIN ekler |
| `DELETE /api/owner/databases/{db}/admins/{user}` | OWNER | ADMIN'i kaldırır, veri rollerini korur |

Eski platform yüzeyleri kaldırıldı:

- `/api/admin/add_database`
- `/api/admin/users`
- `/api/admin/users/{id}/enable`
- `/api/admin/users/{id}/disable`

`GET /api/me` artık `is_platform_owner` döndürüyor;
`is_platform_admin` sözleşmesi kaldırıldı. `PLATFORM_ADMINS` runtime
allowlist'i ve `.env.example` girdisi de kaldırıldı.

### Yönetişim invariant'ları

- OWNER kendi hesabını API'den devre dışı bırakamaz.
- Son aktif OWNER korunur.
- Pasif kullanıcı ilk veya ek DB ADMIN yapılamaz.
- Her yeni DB kaydı aktif bir ilk DB ADMIN gerektirir.
- DB kaydı, ilk ADMIN ilişkisi ve iki audit olayı tek transaction'dadır.
- Bir DB'nin son ADMIN rolü kaldırılamaz.
- ADMIN eklenip kaldırılırken mevcut `READER`/`WRITER`/`DDL` rolleri korunur.
- DB ADMIN'in eski veri rolü atama endpoint'i `ADMIN` rolünü artık kabul etmez.
- DB ADMIN bir veri rolü güncellerken hedefin mevcut ADMIN rolü silinmez.

Son iki madde, OWNER tarafındaki son-ADMIN korumasının eski
`/api/admin/associate_user` yoluyla dolanılmasını engelliyor.

### Audit

Audit sözlüğüne aşağıdaki durum değiştiren eylemler eklendi:

- `owner_granted`
- `grant_database_admin`
- `revoke_database_admin`

Kullanıcı enable/disable işlemleri `source=owner` ile; DB kaydı ve ilk ADMIN
ataması aynı transaction içinde kaydediliyor. Credential ve parola değerleri
audit detaylarına yazılmıyor.

## Frontend uygulaması

Yönetim ekranı rol kapsamına göre ayrıştırıldı:

- Yalnız DB ADMIN: Onaylar ve Maskeleme sekmelerini görür.
- Yalnız OWNER: Platform OWNER sekmesini görür; admin onay listesini yüklemez.
- Hem OWNER hem DB ADMIN: Üç sekmeyi de görür.
- Hiçbiri: Yönetim ekranına erişemez.

OWNER sekmesinde:

- kullanıcı listeleme, etkinleştirme ve teyitli devre dışı bırakma,
- hedef DB ve zorunlu ilk DB ADMIN kaydı,
- ek DB ADMIN atama,
- teyitli DB ADMIN geri alma,
- yükleniyor, boş, hata ve dolu durumları

uygulandı. Veritabanı kayıt formu DB ADMIN'in maskeleme ekranından
çıkarıldı. Tüm HTTP çağrıları `frontend/services/api.ts` üzerinden
geçiyor ve mevcut tasarım sistemi primitive'leri kullanılıyor.

## Doğrulama

| Komut | Sonuç | Kanıt |
| --- | --- | --- |
| `cd web_api && python3 -m pytest -q` | Geçti | 187 passed, 1 mevcut Pydantic deprecation warning, 109.45s |
| `cd frontend && npm run typecheck` | Geçti | TypeScript hata yok |
| `cd frontend && npm run audit:contrast` | Geçti | Açık/koyu tema tüm kontrast hedefleri geçti |
| `cd frontend && npm run audit:api` | Geçti | 31 frontend çağrısının tamamı backend rotasıyla eşleşti |
| `cd frontend && npm run build` | Geçti | Vite production build tamamlandı |
| `git diff --check` | Geçti | Whitespace hatası yok |

Test kapsamı; migration zinciri, bootstrap create/promote/idempotence,
fail-closed startup guard, OWNER/ADMIN yetki ayrımı, pasif admin reddi,
atomik ilk admin ataması, son admin koruması, oturum iptali, audit ve eski
admin yolundan rol dolanma girişimini içeriyor.

## Change-review sonucu

Yetkilendirme, input validation, audit, credential sızıntısı, transaction
sınırı, migration sırası ve frontend/backend sözleşmesi incelendi.

İnceleme sırasında bulunan iki sorun teslim içinde giderildi:

1. Eski schema-repair migration'ının yeni OWNER indexini kolon oluşmadan
   önce eklemeye çalışması engellendi.
2. DB ADMIN'in eski rol endpoint'iyle ADMIN grant/revoke yaparak OWNER
   invariant'larını dolanması kapatıldı.

Son incelemede yüksek, orta veya düşük seviye açık bulgu kalmadı.

## Deployment ve uyumluluk notları

- Bu bir API sözleşmesi değişikliğidir; eski frontend yeni backend ile veya
  yeni frontend eski backend ile birlikte deploy edilmemelidir.
- Migration sonrası ilk OWNER bootstrap edilmeden yeni backend başlamaz.
- Eski `PLATFORM_ADMINS` değerleri otomatik OWNER'a dönüştürülmez. Her
  gerekli kullanıcı CLI ile açıkça bootstrap edilmelidir.
- Canlı MSSQL instance'ında deployment smoke testi bu yerel teslimatta
  yapılmadı. Migration zinciri SQLite üzerinden otomatik test edildi ve MSSQL
  tipleri/kontratları mevcut migration yapısıyla korundu.
- Repository'nin mevcut Pydantic V2 `class Config` deprecation warning'i devam
  ediyor; bu özelliğe ait yeni bir test hatası değil.

## Bilinçli kapsam dışı

- Satır sayımı ve yıkıcı DML teyidi
- Hedef veritabanı silme/soft-delete
- Mevcut hedef DB credential rotasyonu
- UI/API üzerinden OWNER grant/revoke
- Break-glass ve harici erişim broker'ı
- Canlı tarayıcı E2E testi ve canlı MSSQL smoke testi

## Sonraki operasyonel adım

Değişiklikleri review ettikten sonra backend ve frontend'i birlikte deploy edin;
migration tamamlanır tamamlanmaz, uygulama prosesini kalıcı olarak başlatmadan
önce ilk OWNER'ı CLI ile bootstrap edin.

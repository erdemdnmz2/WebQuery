# ADR-0001: Şema değişiklikleri Alembic ile yönetilir

## Status

Proposed

## Context

`AppDatabase.create_tables()` (`web_api/app_database/app_database.py`), uygulama
açılışında `Base.metadata.create_all()` çağırıyor ve `create_db.py` da aynı işlemi
tekrarlıyor. `create_all()` **sadece var olmayan tabloyu yaratır** — var olan bir
tabloya yeni kolon veya index eklemez, hata da vermez, sessizce atlar.

Bu, sıradaki teslimat bloklarının (denetlenebilirlik, kimlik yaşam döngüsü,
savunma derinliği) hiçbirinin production'da çalışmayacağı anlamına geliyor:
`AuditLog` tablosu, `User.is_active`, `Databases` üzerindeki kimlik kolonları,
`QueryData.decision_reason` gibi eklemelerin tamamı var olan tablolara kolon
ekliyor. `create_all()` bunları atlar; uygulama ilk kullanımda
`Invalid column name` ile patlar — ve bu, deploy anında değil, o kolonu okuyan
ilk istek geldiğinde olur.

Ayrıca `create_tables()` her uygulama açılışında çalışıyor. Aynı anda birden
fazla instance açılırsa (rolling deploy, otomatik ölçekleme) şema değişikliği
yarışa girer; `create_all()` idempotent olsa da bu, şemanın *kim tarafından*
ve *ne zaman* değiştiğinin izlenebilir olmamasına yol açıyor.

## Decision

Şema değişiklikleri Alembic ile, açık migration dosyaları üzerinden yönetilir.

- `web_api/migrations/` altında Alembic ortamı kurulur; `env.py` async
  connection string'i (`aioodbc`/`asyncpg`/`aiomysql`/`aiosqlite`) senkron
  sürücüye çevirip Alembic'in senkron `engine_from_config` akışını kullanır.
- Mevcut production şeması, autogenerate ile üretilip elle gözden geçirilen bir
  **baseline revizyonla** temsil edilir; var olan ortamlarda bu revizyon
  `alembic stamp head` ile "uygulanmış" işaretlenir (DDL tekrar çalıştırılmaz).
- `AppDatabase.create_tables()` uygulamanın açılış akışından (`app.py`
  `lifespan`) kaldırılır. Metod, testlerin sqlite in-memory kurulumu için
  (`tests/conftest.py`) olduğu gibi kalır — testler her çalıştırmada temiz bir
  şema istiyor, migration geçmişi değil.
- `create_db.py`, yalnızca hedef veritabanı/login'in var olup olmadığını
  kontrol edip oluşturur (SQL Server sysadmin bootstrap); tablo şeması
  sorumluluğunu bırakır.
- `entrypoint.sh`, `create_db.py` (DB/login bootstrap) başarılı olduktan sonra
  `alembic upgrade head` çalıştırır, ardından uygulamayı başlatır.
- Yeni her model değişikliği, ayrı bir `alembic revision --autogenerate`
  komutuyla, gözden geçirilip commit edilen bir migration dosyası olarak
  eklenir.

## Rejected Alternatives

### 1. `create_all()` + elle `ALTER TABLE` script'leri

Basit kalır, yeni bağımlılık gerektirmez. Ancak "hangi script hangi ortamda
çalıştı" bilgisini hiçbir yerde tutmaz; iki ortam arasında şema sürüklenmesi
(schema drift) sessizce birikir ve geri alınamaz — tam da şu an yaşanan sorun.

### 2. Şema karşılaştırma aracı (ör. `alembic`'siz, doğrudan `sqlacodegen`/manuel
   diff) ile deploy zamanı senkronizasyon

Migration dosyası yazma yükünü ortadan kaldırır. Ama uygulanan her değişikliği
gözden geçirmeden doğrudan hedef şemaya uygulama riski taşır — özellikle veri
kaybına yol açabilecek `DROP COLUMN`/tip daraltma gibi işlemler için gözden
geçirme adımı olmadan production'a gitmesi kabul edilemez bir risk.

## Consequences

- Her şema değişikliği artık bir migration dosyası + commit gerektirir; bu,
  sıradaki tüm bloklar (AuditLog, kullanıcı kolonları, kimlik bilgisi modeli)
  için zorunlu bir ön koşuldur.
- Deploy süreci bir adım kazanır: `alembic upgrade head`. CI ve deploy
  script'leri bunu bilmek zorunda (`entrypoint.sh` güncellendi).
- Test ortamı (sqlite in-memory + `create_tables()`) migration akışının dışında
  kalır — bilinçli bir tercih, testler şema geçmişini değil güncel şemayı
  ister.
- Baseline revizyon, mevcut dokuz tablo eksiksiz bulunuyorsa DDL'yi tekrar
  çalıştırmadan migration'ı uygulanmış kabul eder. Kısmi veya şüpheli bir
  şemada migration bilerek hata verir; operatör şemayı inceleyip
  `alembic stamp head` kararını elle vermelidir.

## Accepted Risks

- Baseline migration, gerçek production şemasına karşı değil, modellerden
  türetilen boş bir sqlite veritabanına karşı üretildi (bu ortamda gerçek DB
  erişimi yok). Otomatik üretilen dosya elle gözden geçirildi ve app-seviyeli
  özel tipler (`EncryptedText`, `AppDateTime` vb.) düz SQLAlchemy tiplerine
  çevrildi. Gerçek production şemasıyla fiili bir fark varsa (ör. elle
  eklenmiş bir index), bu ortaya `alembic stamp head` öncesi
  `alembic upgrade head --sql` çıktısı production şemasıyla karşılaştırılarak
  çıkarılmalıdır — bu doğrulama operatörün sorumluluğundadır.
- Birden fazla instance'ın aynı anda `alembic upgrade head` çalıştırması
  (rolling deploy) hâlâ mümkün; Alembic bunu bir DB-seviyeli lock (`version
  table` üzerinde) ile büyük ölçüde güvenli hale getirir, ama bu ADR ek bir
  deploy-seviyeli kilitleme mekanizması eklemiyor.

## References

- Spec: yok — bu, kullanıcıya görünen davranışı değiştirmeyen bir operasyonel/
  mimari karar.
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 1 (`4.1`).
- Supersedes / Superseded by: yok.

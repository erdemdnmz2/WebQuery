# Mini-Spec: Rol bazlı hedef veritabanı kimlik bilgileri

## 1. Spec Kartı

- Özellik: Role-Based Target Database Credentials
- Durum: Implemented
- Versiyon: 2026-08-28
- Tarih: 2026-08-28
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Hedef veritabanlarına yapılan sorguların, sorgunun gerektirdiği en düşük yetkili
veritabanı hesabıyla çalıştırılmasını sağlamak. Uygulama katmanındaki bir hata
veya atlanan kontrol, veritabanı yetkileri tarafından da sınırlandırılmalıdır.

### Başarı Sinyali

- Her hedef veritabanı için gerçek DBA tarafından oluşturulmuş role hesapları
  kullanılabilir.
- WebQuery, hedef DB hesabı oluşturmaz ve hedef DB'de yetki vermez.
- Admin tarafından girilen şifreler WebQuery'nin kendi veritabanında şifreli
  saklanır.
- Sorgu `ro`, `rw` veya `ddl` kademesine göre yalnızca ilgili hesabı kullanır.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `Databases` kaydında hedef DB'ye ait `ro` ve `rw` kullanıcı adı/şifrelerinin;
  gerekirse `ddl` bilgilerinin tutulması.
- Admin'in veritabanı ekleme akışında bağlantı modunu (`ro`, `ro + rw` veya
  `ro + rw + ddl`) seçmesi ve yalnız seçilen kademeler için DBA tarafından
  sağlanan gerçek credential değerlerini girmesi.
- Şifrelerin `EncryptedText` ile WebQuery'nin kendi veritabanında şifreli
  saklanması.
- Sorgu kademesinin seçilmesi ve bağlantının o kademenin credential'ı ile
  kurulması.
- Hedef veritabanının sorgu ekranında tek kayıt olarak, kullanıcının etkin
  yetkisini bildiren bir rozetle gösterilmesi.
- Kullanıcıya verilen rolün, hedef veritabanının sağladığı kademeleri aşamaması.

### Kapsam Dışı

- WebQuery tarafından hedef DB'de `CREATE LOGIN`, `CREATE USER`, `CREATE ROLE`
  veya `GRANT` çalıştırılması.
- Hedef DB şemasının Alembic ile değiştirilmesi.
- Secret manager veya otomatik credential rotasyon sistemi.
- Credential kullanıcı adı veya şifresinin herhangi bir API response'unda
  gösterilmesi.
- Kullanıcının sorgu anında kademe seçmesi; kademe daima sorgudan türetilir.
- DDL hesabının her veritabanında zorunlu tutulması; varsayılanı yoktur.

## 4. Sözleşme

Hedef veritabanının DBA'i hesapları hedef sunucuda oluşturur ve credential
bilgilerini admin'e güvenli kanal üzerinden sağlar. Admin, WebQuery'nin
“Veritabanı Ekle” akışında yalnız `ro`, `ro + rw` veya `ro + rw + ddl`
bağlantı modlarından birini seçer; form yalnız bu modun gerektirdiği
credential alanlarını kabul eder. WebQuery şifreleri plaintext olarak saklamaz;
sorgu anında ilgili role ait şifreyi çözer ve bağlantı kurar.

## 5. İş Kuralları

### BR-01: Hedef hesapların sahibi DBA'dir

Hedef DB hesapları ve yetkileri DBA tarafından, hedef veritabanında manuel
provisioning ile oluşturulur. WebQuery bu hesapları oluşturabilecek yüksek
yetkili bir hesabı saklamaz.

### BR-02: Credential'lar veritabanı başınadır

Credential değerleri global `CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD` yerine
hedef veritabanı kaydından çözülür.

### BR-03: En düşük gerekli kademe kullanılır

Salt-okuma sorgusu `ro`, veri değiştiren sorgu `rw`, DDL gerektiren sorgu ise
yalnızca ilgili veritabanında ayrıca tanımlanmış `ddl` hesabı ile çalışır.
Eksik credential veya çözümlenemeyen kademe fail-closed davranır.

### BR-04: Şifreler şifreli saklanır

Hedef DB şifreleri `EncryptedText` ile saklanır. Fernet anahtarı eksik veya
geçersizse kayıt/yükleme işlemi güvenli şekilde başarısız olur.

### BR-05: DDL varsayılan olarak kapalıdır

Bir hedef DB için `ddl` credential'ı yoksa DDL çalıştırılamaz. DDL hesabı
yalnızca açık operasyonel ihtiyaç varsa DBA tarafından oluşturulur ve admin
tarafından kaydedilir.

### BR-06: Geçerli bağlantı modları hiyerarşiktir

Bir kayıt yalnız `ro`, `ro + rw` veya `ro + rw + ddl` modlarından biriyle
oluşturulur. `rw` veya `ddl` credential'ı, kendinden düşük kademe olmadan
tek başına kaydedilemez. Seçilmeyen kademede sorgu çalıştırma girişimi
fail-closed reddedilir.

### BR-07: Bir hedef veritabanı arayüzde tek kayıttır

Kademeler ayrı veritabanı gibi listelenmez. Sorgu ekranı hedef veritabanını tek
satır olarak gösterir ve kullanıcı kademe seçmez; kademe `QueryAnalyzer` ile
sorgudan türetilir.

### BR-08: Sorgu ekranındaki rozet etkin yetkiyi gösterir

`GET /api/database_information` her veritabanı için `capability` alanı döner.
Bu alan kaydın bağlantı modunun kullanıcının rolüyle kesişimidir; ikisinden
düşük olanıdır. `ro + rw` moduyla kayıtlı bir veritabanı `READER` rolündeki
kullanıcıya `ro` olarak görünür. Kaydın ham bağlantı modu bu response'a
yazılmaz. Credential kullanıcı adı ve şifresi hiçbir koşulda yazılmaz.

### BR-09: Yetki verme kaydın sağladığı kademeyi aşamaz

`POST /api/admin/associate_user` isteğinde verilen rolün gerektirdiği kademe,
hedef veritabanının bağlantı modunda tanımlı değilse istek `400` ile
reddedilir ve association yazılmaz. `ADMIN` bu kuraldan muaftır; yönetişim
rolüdür ve kaydı yöneten kişiye her modda verilir. Rol bazlı credential öncesi
kaydedilmiş, hiç kademe credential'ı olmayan kayıtlar da muaftır.

## 6. Acceptance Criteria

- AC-01: Given DBA tarafından oluşturulmuş `ro` ve `rw` hesapları, when admin
  hedef DB'yi ekler, then girilen gerçek credential'lar ilgili Databases
  kaydına yazılır.
- AC-02: Given kayıtlı bir hedef DB şifresi, when WebQuery veritabanı okunur,
  then şifre plaintext olarak görünmez.
- AC-03: Given salt-okuma sorgusu, when bağlantı kurulursa, then `ro` hesabı
  kullanılır.
- AC-04: Given veri değiştiren sorgu, when bağlantı kurulursa, then `rw`
  hesabı kullanılır.
- AC-05: Given DDL sorgusu ve `ddl` credential'ı olmayan hedef DB, when sorgu
  çalıştırılır, then işlem reddedilir ve yüksek yetkili merkezi hesaba geri
  dönülmez.
- AC-06: Given hedef DB hesabı oluşturma ihtiyacı, when sistem işletilir,
  then WebQuery hedef DB'de provisioning komutu çalıştırmaz.
- AC-07: Given admin `ro` modunu seçtiğinde, when kayıt gönderilirse, then
  yalnız `ro` credential'ları kabul edilir ve `rw`/`ddl` sorguları reddedilir.
- AC-08: Given admin `ro + rw` veya `ro + rw + ddl` modunu seçtiğinde, when
  kayıt gönderilirse, then seçilen her kademe için kullanıcı adı ve şifre
  zorunludur; tek başına `rw` veya `ddl` modu kabul edilmez.
- AC-09: Given `ro + rw` modunda kayıtlı bir veritabanı ve `READER` rolündeki
  kullanıcı, when `/api/database_information` çağrılır, then veritabanı tek
  kayıt olarak `capability: "ro"` ile döner ve response hiçbir kullanıcı adı
  veya şifre içermez.
- AC-10: Given aynı veritabanı ve `WRITER` rolündeki kullanıcı, when aynı uç
  nokta çağrılır, then `capability: "ro_rw"` döner.
- AC-11: Given `ro` modunda kayıtlı bir veritabanı ve `ADMIN` rolündeki
  kullanıcı, when aynı uç nokta çağrılır, then `capability: "ro"` döner;
  kaydın sağlamadığı bir kademe rozetle vaat edilmez.
- AC-12: Given `ro` modunda kayıtlı bir veritabanı, when admin bir kullanıcıya
  `WRITER` rolü vermeye çalışır, then istek `400` ile reddedilir ve
  association oluşmaz.
- AC-13: Given aynı veritabanı `ro + rw` moduna geçirildiğinde, when aynı
  `WRITER` yetkisi verilir, then istek başarılı olur.

## 7. Teknik ve Güvenlik Kısıtları

- `CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD` bu modelin runtime sorgu
  credential'ı değildir.
- Engine cache anahtarında hedef DB ve credential kademesi ayrımı korunmalıdır;
  `ro` ve `rw` engine'leri birbirine karışmamalıdır.
- Credential değerleri loglara, API response'larına listeleme endpoint'lerine
  veya audit kayıtlarına plaintext olarak yazılmaz. Bu kısıt hem şifreyi hem
  kullanıcı adını kapsar; sorgu ekranına yalnız türetilmiş `capability` değeri
  gider.
- `AppDatabase.get_db_info` credential taşır ve yalnız
  `DatabaseProvider.set_db_info` tarafından tüketilir. Provider, API'ye giden
  public kataloğu (`get_db_info_db`) credential taşıyan runtime haritasından
  (`db_by_uuid`) ayrı tutar; bu ayrım korunmalıdır.
- Bu spec'in uygulanması `ADR-0005`, `ADR-0004` ve Alembic şema yönetimiyle
  birlikte ele alınmalıdır.

## 8. Open Questions

- Yok. OQ-2026-002, OQ-2026-007 ve OQ-2026-008 cevaplanmıştır.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [ ] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

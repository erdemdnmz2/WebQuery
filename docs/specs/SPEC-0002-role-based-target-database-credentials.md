# Mini-Spec: Rol bazlı hedef veritabanı kimlik bilgileri

## 1. Spec Kartı

- Özellik: Role-Based Target Database Credentials
- Durum: Ready for implementation
- Versiyon: 2026-08-21
- Tarih: 2026-08-21
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
- Admin'in veritabanı ekleme akışında DBA tarafından sağlanan gerçek
  credential değerlerini girmesi.
- Şifrelerin `EncryptedText` ile WebQuery'nin kendi veritabanında şifreli
  saklanması.
- Sorgu kademesinin seçilmesi ve bağlantının o kademenin credential'ı ile
  kurulması.

### Kapsam Dışı

- WebQuery tarafından hedef DB'de `CREATE LOGIN`, `CREATE USER`, `CREATE ROLE`
  veya `GRANT` çalıştırılması.
- Hedef DB şemasının Alembic ile değiştirilmesi.
- Secret manager veya otomatik credential rotasyon sistemi.
- DDL hesabının her veritabanında zorunlu tutulması; varsayılanı yoktur.

## 4. Sözleşme

Hedef veritabanının DBA'i hesapları hedef sunucuda oluşturur ve credential
bilgilerini admin'e güvenli kanal üzerinden sağlar. Admin, WebQuery'nin
“Veritabanı Ekle” akışında bu bilgileri kaydeder. WebQuery şifreleri plaintext
olarak saklamaz; sorgu anında ilgili role ait şifreyi çözer ve bağlantı kurar.

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

## 7. Teknik ve Güvenlik Kısıtları

- `CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD` bu modelin runtime sorgu
  credential'ı değildir.
- Engine cache anahtarında hedef DB ve credential kademesi ayrımı korunmalıdır;
  `ro` ve `rw` engine'leri birbirine karışmamalıdır.
- Credential değerleri loglara, API response'larına listeleme endpoint'lerine
  veya audit kayıtlarına plaintext olarak yazılmaz.
- Bu spec'in uygulanması `ADR-0005`, `ADR-0004` ve Alembic şema yönetimiyle
  birlikte ele alınmalıdır.

## 8. Open Questions

- Yok. OQ-2026-002 cevaplanmıştır.

## 9. Done Kontrolü

- [ ] Acceptance criteria için test eklendi veya güncellendi
- [ ] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [ ] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

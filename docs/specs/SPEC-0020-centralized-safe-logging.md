# Mini-Spec: Merkezi ve Güvenli Uygulama Loglama

## 1. Spec Kartı

- Özellik: `print()` çağrılarının merkezi loglamaya taşınması
- Durum: Implemented
- Versiyon: 1.0.0
- Tarih: 2026-08-29
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Uygulamanın çalışma, hata ve başlatma olaylarını trace ve kullanıcı bağlamını
koruyan merkezi logging altyapısında toplamak; stdout'a yapılandırma, hata
mesajı veya hassas olabilecek ayrıntı yazılmasını önlemek.

### Başarı Sinyali

- Uygulama Python kodunda production `print()` çağrısı kalmaz.
- `LOG_LEVEL` ile DEBUG kayıtları kontrollü biçimde açılabilir.
- Veritabanı kataloğu yalnız kayıt sayılarını loglar; sunucu, veritabanı,
  UUID ve credential değerlerini loglamaz.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `web_api/` içindeki production Python modüllerinde `print()` yerine Python
  `logging` kullanımı.
- Başlangıç, kapanış, authentication, Slack bildirimleri ve DB bootstrap
  kayıtlarının güvenli özetlere dönüştürülmesi.
- `LOG_LEVEL` ile root logger ve console handler seviyesinin belirlenmesi.
- Bootstrap SQLAlchemy engine'in `echo` çıktısının kapatılması.

### Kapsam Dışı

- Hedef veritabanı sorgu/workspace hata temizleme sözleşmesinin değiştirilmesi
  (SPEC-0003).
- AuditLog veri modelinin veya saklama politikasının değiştirilmesi.
- Shell scriptlerindeki operatör odaklı `echo` çıktıları.

## 4. Sözleşme

`setup_logging()` root logger'ı `LOG_LEVEL` (varsayılan `INFO`) ile kurar ve
her kayda `trace_id` ile `user_id` bağlamını ekler. Bilinmeyen bir seviye
uygulamanın açılmasını engellemez; `INFO` kullanılır ve bir uyarı yazılır.

Bir request sırasında oluşan uygulama logları TraceMiddleware tarafından
yerleştirilen trace ID ile ilişkilendirilebilir. Bir hata logu, parolalar,
tokenlar, SQL metni, Slack yanıt gövdesi veya tüm DB yapılandırması yerine
işlemin güvenli özeti ve gerektiğinde exception türünü taşır.

## 5. İş Kuralları

### BR-01: Log seviyeleri anlamlı olmalıdır

Normal yaşam döngüsü olayları `INFO`, güvenli tanılama özeti `DEBUG`,
kurtarılabilen sorunlar `WARNING`, başarısız işlemler `ERROR`, uygulamayı
başlatmayı engelleyen durumlar `CRITICAL` olarak kaydedilir.

### BR-02: Hassas veri loglanmaz

Log mesajları credential, parola, token, tam yapılandırma nesnesi, SQL metni
veya harici servisin ham yanıt gövdesini içermez. Exception metni güvenli
olmadığı akışlarda yalnız exception türü kaydedilir.

### BR-03: Hedef katalog yalnız özetlenir

`DatabaseProvider.set_db_info()` yalnız işlenen sunucu ve veritabanı sayısını
DEBUG seviyesinde kaydeder.

### BR-04: Bootstrap SQL'i loglanmaz

`create_db.py`, `CREATE LOGIN ... PASSWORD` ifadesini içerebilen SQLAlchemy
echo çıktısını açmaz.

## 6. Acceptance Criteria

- AC-01: Given production Python modülleri, when AST ile taranırlar, then
  `print()` çağrısı bulunmaz.
- AC-02: Given `LOG_LEVEL=DEBUG`, when seviye çözülür, then DEBUG seviyesi
  döner; geçersiz değer INFO'ya düşer.
- AC-03: Given credential içeren hedef DB kataloğu, when `set_db_info()`
  çağrılır, then DEBUG kaydı yalnız sunucu/veritabanı sayılarını içerir.
- AC-04: Given bootstrap engine oluşturulur, when SQLAlchemy yapılandırması
  incelenir, then SQL echo devre dışıdır.
- AC-05: Given HTTP isteği, when TraceMiddleware bir kayıt üretir, then mevcut
  trace ID logging bağlamında kalır.

## 7. Teknik ve Güvenlik Kısıtları

- `logging` çağrıları, seviye kapalıyken gereksiz string biçimlendirmeyi
  önlemek için `%s`/`%d` parametreleri kullanmalıdır.
- Hedef DB yürütme hataları için SPEC-0003 ve ADR-0006'daki parola redaksiyonu
  korunur.
- `exc_info` ham traceback'in parola veya bağlantı bilgisi taşıyabileceği
  akışlarda kullanılmaz.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR gerekmez: mevcut Python stdlib logging altyapısı kullanıldı; yeni
  kalıcı mimari veya güvenlik sınırı seçilmedi.
- [x] Doğrulama komutları çalıştırıldı ve teslimde raporlandı

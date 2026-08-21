# Mini-Spec: Hedef sorgu zaman aşımı

## 1. Spec Kartı

- Özellik: Hedef veritabanı sorgu zaman aşımı
- Durum: Implemented
- Versiyon: 1.0.0
- Tarih: 2026-08-22
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Hatalı veya pahalı bir hedef veritabanı sorgusunun bağlantıyı ve async worker'ı
sınırsız süreyle meşgul etmesini engellemek.

### Başarı Sinyali

- Hedef sorgular, yapılandırılmış süre aşıldığında driver veya veritabanı
  tarafından sonlandırılır.
- Sorgu timeout'u, bağlantı kurma ve connection pool bekleme timeout'larından
  bağımsızdır.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `QUERY_TIMEOUT_SECONDS` ile varsayılan 300 saniyelik hedef sorgu sınırı.
- MSSQL, PostgreSQL ve MySQL için teknolojiye uygun bağlantı/session ayarları.
- Timeout argümanlarının engine cache üzerinden oluşturulan bağlantılara
  aktarılması.

### Kapsam Dışı

- SQL metnini `LIMIT`, `TOP` veya benzeri ifadelerle değiştirmek.
- `MAX_ROW_COUNT_LIMIT` davranışını değiştirmek.
- Uygulama veritabanı sorgularının timeout davranışını değiştirmek.
- Kullanıcı bazlı farklı timeout politikası uygulamak.

## 4. Sözleşme

`QUERY_TIMEOUT_SECONDS` pozitif saniye cinsinden bir ortam değişkenidir; değer
verilmezse `300` kullanılır. Hedef sorgu session'ı oluşturulurken teknolojiye
uygun driver/session timeout ayarları uygulanır.

## 5. İş Kuralları

### BR-01: Merkezi timeout

Hedef sorgular için timeout değeri `QUERY_TIMEOUT_SECONDS` üzerinden alınır.

### BR-02: Teknolojiye uygun uygulama

PostgreSQL'de client ve server-side statement timeout, MSSQL'de driver timeout,
MySQL'de session `max_execution_time` kullanılır.

### BR-03: Sorgu metni değişmez

Timeout uygulamak için kullanıcı SQL'ine herhangi bir clause eklenmez veya SQL
yeniden yazılmaz.

## 6. Acceptance Criteria

- AC-01: Given `QUERY_TIMEOUT_SECONDS` ayarlanmamışsa, when config yüklenirse,
  then hedef sorgu timeout'u 300 saniye olur.
- AC-02: Given MSSQL hedefi, when engine oluşturulursa, then driver'a saniye
  cinsinden `timeout` aktarılır.
- AC-03: Given PostgreSQL hedefi, when engine oluşturulursa, then
  `command_timeout`, `statement_timeout` ve idle transaction timeout aktarılır.
- AC-04: Given MySQL hedefi, when session oluşturulursa, then
  `max_execution_time` milisaniye cinsinden session'a uygulanır.
- AC-05: Given engine cache üzerinden oluşturulan hedef engine, when engine
  yaratılırsa, then `connect_args` SQLAlchemy engine'ine iletilir.

## 7. Teknik ve Güvenlik Kısıtları

- Timeout, `pool_timeout` ve bağlantı kurulumu `connection timeout` ayarlarıyla
  karıştırılmamalıdır.
- Engine cache yeniden düzenlenirken `connect_args` korunmalıdır.
- Mevcut engine cache anahtarı nedeniyle bu sürümde timeout kullanıcı bazlı
  değildir; çalışma zamanı değişikliği için engine'lerin yeniden oluşturulması
  gerekir.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [x] Doğrulama komutları çalıştırıldı

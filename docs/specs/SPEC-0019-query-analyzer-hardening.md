# Mini-Spec: Sorgu analizcisi sertleştirme

## 1. Spec Kartı

- Özellik: Query Analyzer Hardening
- Durum: Implemented
- Versiyon: 2026-08-28
- Tarih: 2026-08-28
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

`QueryAnalyzer`'ın gerçekten tehlikeli sorguları yakalamasını, sıradan sorguları
ise engellememesini sağlamak. Analizci iki yönden de hatalıydı: işletim sistemi
ve dosya sistemi erişimi sağlayan fonksiyon çağrılarını hiç görmüyordu, buna
karşılık üç JOIN'li normal bir raporlama sorgusunu onay kuyruğuna düşürüyordu.

### Başarı Sinyali

- `SELECT pg_read_file('/etc/passwd')` gibi fonksiyon çağrıları rol fark
  etmeksizin engellenir.
- `EXPLAIN ANALYZE` ile sarılan yazma sorguları çalıştırılamaz.
- Dört tabloya dokunan sıradan bir raporlama sorgusu onay kuyruğuna düşmez.
- Performans riski varsayılan olarak yalnız işaretlenir, engellemez.
- Veritabanı admin'i güvenlik kontrolünü değil, yalnız onay gerekliliğini atlar.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- Tehlikeli fonksiyon blocklist'i ve sınırlı `sleep` argümanı.
- `EXPLAIN ANALYZE` / `EXPLAIN ANALYSE` engeli.
- Şema değiştiren ifadelerin veri ifadeleriyle aynı batch'te gönderilememesi.
- `MAX_JOINS` ve `PERFORMANCE_BLOCKS` ayarları.
- Admin bypass'ının daraltılması ve atlanan riskin loglanması.
- Sert blokların workspace tekrar çalıştırma ve admin önizleme yollarında da
  uygulanması.

### Kapsam Dışı

- Yıkıcı DML için etki alanı teyidi (`3.4.2`); ayrı adım.
- Onay akışının kendisinin değiştirilmesi.
- Çoklu sonuç kümesi okuma ve hedef transaction commit davranışı.

## 4. Sözleşme

`QueryAnalyzer.analyze()` şu sözlüğü döner:

```python
{
    "risk_type": str | None,   # RiskLevel değeri
    "return": bool,            # False ise sorgu bu haliyle çalıştırılmaz
    "reason": str,             # opsiyonel; engelin kullanıcıya gösterilecek gerekçesi
    "warnings": list[str],     # opsiyonel; engellemeyen işaretler
}
```

`RiskLevel` değerlerine `blocked_operation` eklendi. `HARD_BLOCKED_RISKS`
kümesi `sql_injection_risk` ve `blocked_operation` değerlerini içerir; bu
kümedeki riskler hiçbir rol tarafından atlanamaz ve `POST /api/execute_query`
isteği `400` ile reddedilir.

`hard_block_reason(analyzer, query, technology)` yalnız bu alt kümeyi
sorgular; onaylanmış bir sorguyu tekrar çalıştıran yollar bunu kullanır.

## 5. İş Kuralları

### BR-01: Tehlikeli fonksiyon çağrıları engellenir

İşletim sistemi çalıştırma, dosya sistemi erişimi, küme kontrolü ve uzak SQL
fonksiyonları (`xp_cmdshell`, `pg_read_file`, `dblink_exec`, `load_file`,
`openrowset` ve benzerleri) `blocked_operation` riski üretir. Tırnaklı çağrı
biçimi de aynı şekilde yakalanır.

### BR-02: `sleep` argümanı sınırlıdır

`pg_sleep` ve eşdeğerleri en fazla 5 saniye ile çağrılabilir. Argüman sabit bir
sayı değilse veya okunamıyorsa çağrı engellenir.

### BR-03: `EXPLAIN ANALYZE` engellenir

`EXPLAIN ANALYZE` ve İngiliz yazımı `EXPLAIN ANALYSE`, sarılan ifadeyi gerçekten
çalıştırdığı için reddedilir. Düz `EXPLAIN` serbesttir. Kontrol ayrıştırmadan
önce yapılır, çünkü sqlglot bu formu opak bir komut olarak parse eder.

### BR-04: Şema ifadeleri veri ifadeleriyle aynı batch'te gönderilemez

Bir batch hem DDL hem de başka kademede ifade içeriyorsa reddedilir. Yalnız
okuma ve yazma içeren batch (`SELECT; UPDATE`) **kabul edilir**: tek bağlantıda,
tek transaction'da, zaten her ikisini de yapabilen `rw` hesabıyla çalışır ve
bölmek atomikliği bedelsiz kaybettirir.

### BR-05: Performans riski varsayılan olarak engellemez

`MAX_JOINS` (varsayılan 8) olağan sayılan en yüksek JOIN sayısıdır; üstü
`performance_risk` olarak işaretlenir. `PERFORMANCE_BLOCKS` varsayılan olarak
kapalıdır; risk işaretlenir, audit'e yazılır, ancak sorgu çalışır. Gerçek koruma
sorgu zaman aşımı ve satır sınırıdır.

### BR-06: Admin güvenlik kontrolünü atlamaz

`HARD_BLOCKED_RISKS` içindeki bir risk, veritabanı admin'i dahil herkes için
sorguyu reddeder. Diğer riskler admin için onay gerektirmez ancak
`logger.warning` ile ve audit kaydındaki `risk_level` alanıyla iz bırakır.

### BR-07: Sert bloklar her çalıştırma yolunda geçerlidir

Onaylanmış workspace tekrar çalıştırması ve admin sorgu önizlemesi de sert
blokları uygular. Onay, sert bloklu bir sorguyu çalıştırılabilir hâle getirmez.

## 6. Acceptance Criteria

- AC-01: Given bir ADMIN kullanıcı, when `SELECT pg_read_file('/etc/passwd')`
  çalıştırmayı denediğinde, then istek `400` döner ve hedef veritabanında hiçbir
  sorgu çalıştırılmaz.
- AC-02: Given bir ADMIN kullanıcı, when `DELETE FROM orders` çalıştırdığında,
  then sorgu çalışır ve atlanan risk loglanır.
- AC-03: Given dört tabloya dokunan bir `SELECT`, when çalıştırıldığında, then
  risk işaretlenmez ve onay kuyruğuna düşmez.
- AC-04: Given dokuz JOIN içeren bir `SELECT`, when çalıştırıldığında, then
  `performance_risk` işaretlenir ancak varsayılan ayarda sorgu çalışır.
- AC-05: Given `PERFORMANCE_BLOCKS=true`, when aynı sorgu çalıştırıldığında,
  then sorgu engellenir.
- AC-06: Given `SELECT ...; UPDATE ...` batch'i, when bir WRITER çalıştırdığında,
  then kabul edilir ve `required_tier` `rw` döner.
- AC-07: Given `SELECT ...; ALTER TABLE ...` batch'i, when çalıştırıldığında,
  then `blocked_operation` ile reddedilir.
- AC-08: Given `"pg_read_file"(...)` tırnaklı çağrısı, when analiz edildiğinde,
  then blocklist'i atlayamaz.
- AC-09: Given `EXPLAIN ANALYZE UPDATE ...`, when analiz edildiğinde, then
  reddedilir; düz `EXPLAIN SELECT ...` kabul edilir.

## 7. Teknik ve Güvenlik Kısıtları

- Ayrıştırılamayan sorgu `sql_injection_risk` ile engellenir; `required_tier`
  aynı durumda `ddl` döner. Her iki davranış da fail-closed'dır.
- `sleep` argümanı okunamadığında engellenir.
- Blocklist yalnız ayrıştırılabilen fonksiyon çağrılarını yakalar. Hedef
  veritabanında tanımlı bir fonksiyonun gövdesindeki yazma işlemi analizci
  tarafından görülemez; bu, rol bazlı hedef DB hesaplarının (SPEC-0002)
  kapsadığı risktir.
- `risk_type` alanına yeni bir değer eklenmesi frontend'i etkilemez; arayüz bu
  alanı çözümlemeden rozet olarak gösterir.

## 8. Open Questions

Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (ADR-0016)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

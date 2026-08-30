# Mini-Spec: Hedef Veritabanı Hata Temizleme

## 1. Spec Kartı

- Özellik: Hedef veritabanı hata mesajlarının temizlenmesi
- Durum: Implemented
- Versiyon: 1.0.0
- Tarih: 2026-08-21
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Sorgu ve workspace çalıştırma sırasında hedef veritabanından gelen ham hata
mesajlarının istemciye iç ağ, sunucu, veritabanı ve servis hesabı bilgisi
sızdırmasını engellemek.

### Başarı Sinyali

- Bağlantı/altyapı hataları istemciye jenerik ve trace ID içeren güvenli mesajla döner.
- Kullanıcının düzeltebileceği SQL hataları, sürücü gürültüsü temizlenerek korunur.
- Log ve audit kayıtlarında bağlantı bilgileri korunur, parola değerleri maskelenir.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `QueryService.execute_query` hedef veritabanı yürütme hataları.
- `WorkspaceService.execute_workspace` hedef veritabanı yürütme hataları.
- Bu iki akıştan dönen `QueryExecutionError` istemci mesajları.
- Aynı hataların uygulama logu ve `ActionLogging.ErrorMessage` alanına parola maskeli yazılması.

### Kapsam Dışı

- Kayıt, login, admin ve diğer endpoint'lerin hata çevirisi.
- Hedef veritabanı bağlantı bilgilerinin log/audit kaydından kaldırılması.
- Veritabanı sürücülerinin veya hedef veritabanlarının hata üretme biçiminin değiştirilmesi.

## 4. Sözleşme

Altyapı/bağlantı hataları için istemci cevabı:

```json
{
  "success": false,
  "error_code": "QUERY_EXECUTION_FAILED",
  "message": "Sorgu çalıştırılamadı. Ayrıntılar sunucu kaydına yazıldı — destek ekibine trace_id ile başvurun.",
  "error": "Sorgu çalıştırılamadı. Ayrıntılar sunucu kaydına yazıldı — destek ekibine trace_id ile başvurun.",
  "trace_id": "..."
}
```

Kullanıcının düzeltebileceği SQL hatalarında hata özü korunabilir; sürücü,
bağlantı ve altyapı ayrıntıları korunmaz.

## 5. İş Kuralları

### BR-01: İstemci mesajı güvenli olmalıdır

İstemciye dönen mesaj iç IP, iç DNS adı, sunucu adı, veritabanı adı, servis
hesabı, bağlantı dizesi parçası, dosya yolu veya sürücü ayrıntısı içermemelidir.

### BR-02: Düzeltilebilir SQL hatası korunmalıdır

Geçersiz kolon/nesne, sözdizimi, dönüşüm ve benzeri kullanıcının sorgusunu
düzeltebileceği hata özü, altyapı ayrıntıları temizlendikten sonra gösterilebilir.

### BR-03: Kayıtlar teşhis edilebilir kalmalıdır

Uygulama logu ve audit kaydı bağlantı bilgilerini koruyabilir; ancak `password`,
`pwd` ve eşdeğer parola değerleri `[REDACTED]` ile değiştirilmelidir.

### BR-04: Kapsam sınırlıdır

Temizleme yalnızca hedef veritabanı sorgu ve workspace yürütme hatalarında
uygulanır.

## 6. Acceptance Criteria

- AC-01: Given hedef veritabanı bağlantı hatası, when sorgu yürütülür, then istemci cevabında iç IP, sunucu adı, veritabanı adı ve servis hesabı bulunmaz.
- AC-02: Given kullanıcı tarafından düzeltilebilir kolon/sözdizimi hatası, when sorgu yürütülür, then hata özü istemci mesajında korunur ve sürücü gürültüsü kaldırılır.
- AC-03: Given hata mesajında `password=` veya `PWD=` değeri, when hata log/audit kaydına yazılır, then parola değeri `[REDACTED]` olur.
- AC-04: Given workspace hedef veritabanı yürütme hatası, when workspace çalıştırılır, then AC-01 ve AC-03 ile aynı temizleme uygulanır.
- AC-05: Given temizlenmiş `QueryExecutionError`, when global exception handler çalışır, then `message`, `error` ve `trace_id` alanları güvenli mesajı içerir.

## 7. Teknik ve Güvenlik Kısıtları

- Ham exception teşhis amacıyla `original_exception` olarak korunabilir; istemciye taşınmamalıdır.
- `original_exception` uygulama exception handler'ında loglanırken parola redaksiyonundan geçmelidir; ham traceback parola içerebileceği için yazılmamalıdır.
- Temizleme merkezi ve birim testlerle doğrulanabilir olmalıdır.
- Parola redaksiyonu ODBC bağlantı dizeleri ve URI biçimli bağlantı bilgilerini kapsamalıdır.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu
- [x] Doğrulama komutları çalıştırıldı

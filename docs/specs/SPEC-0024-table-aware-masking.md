# Mini-Spec: Tablo farkındalıklı maskeleme

## 1. Spec Kartı

- Özellik: Maskeleme kurallarının, sorgunun gerçekten okuduğu tablolara göre uygulanması
- Durum: Implemented
- Versiyon: 2026-08-30
- Tarih: 2026-08-30
- Sahip: WebQuery platform ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

`MaskingRule` satırları `(database_id, table_name, column_name, masking_type)`
olarak saklanıyordu, ama uygulama yalnız `column_name` okuyordu. İki sonucu
vardı:

1. **Aşırı maskeleme.** `Customers.email` için yazılmış bir kural,
   `Suppliers.email` sonuçlarını da maskeliyordu. Kullanıcı bunu veri kaybı
   olarak görüyor, hatanın kuraldan geldiğini anlayamıyordu. Sessiz, çünkü
   hiçbir yerde "bu kolon şu kural yüzünden maskelendi" bilgisi yoktu.
2. **Tutulmayan söz.** `masking_type` hiç okunmuyordu. Yönetim arayüzü,
   motorun uygulamadığı bir ayrıntı seviyesi (kısmi maskeleme, hash'leme vb.)
   vaat ediyordu.

### Başarı Sinyali

- `Customers.email` kuralı varken `SELECT email FROM Suppliers` sonucu
  maskelenmez; `SELECT email FROM Customers` maskelenir.
- Desteklenmeyen bir `masking_type` ile kural kaydetme isteği API sınırında
  reddedilir; sessizce `full` olarak kaydedilmez.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `common/security.py` `columns_to_mask()`: saklanan kuralların, sorgunun
  `QueryPlan`'ında geçen tablolara göre çözülmesi.
- Şema-nitelikli (`dbo.Customers`) ve çıplak (`Customers`) adların
  karşılıklı eşleşmesi.
- `masking_type` alanının Pydantic sınırında (`admin/schemas.py`,
  `MaskingRuleSchema`) yalnız `full` değerine kısıtlanması.
- `MaskingRule` üzerinde `(database_id, table_name, column_name)` unique
  kısıtı (migration `a1b2c3d4e5f6`).

### Kapsam Dışı

- Yeni maskeleme stratejileri (kısmi, hash, tokenize). Şema alanı korunuyor
  ama tek desteklenen değer `full`.
- Sonuç kümesindeki kolonun **hangi tablodan geldiğinin** çözülmesi. Sürücü
  sonuç kümesinde kolon adı döner, kaynak tablo dönmez; bu sınır aşağıda
  kabul edilen risk olarak kayıtlı.

## 4. Sözleşme

`GET/POST /api/masking_rules` sözleşmesi değişmedi; `masking_type` alanı
artık yalnız `"full"` kabul ediyor. Başka bir değer `422` ile reddedilir.

Çalıştırma yollarında (`query_execution/services.py`,
`workspaces/services.py`, `admin/services.py` preview) maskelenecek kolon
kümesi artık şu şekilde hesaplanır:

```
columns_to_mask(rules, referenced_tables=plan.tables)
```

`plan.tables`, sorgunun tek parse'ından üretilen `QueryPlan` üzerindeki
tablo kümesidir (şema-nitelikli ve çıplak yazımların ikisi de içerir).

## 5. İş Kuralları

### BR-01: Kural yalnız kendi tablosuna uygulanır

Bir `MaskingRule`, `table_name` alanı sorgunun referans verdiği tablolardan
biriyle eşleşiyorsa uygulanır. Eşleşme büyük/küçük harf duyarsızdır.

### BR-02: Şema niteliği eşleşmeyi bozmaz

`dbo.Customers` kuralı `Customers` yazan bir sorguyla eşleşir; `Customers`
kuralı `dbo.Customers` yazan bir sorguyla eşleşir.

### BR-03: `table_name` boş olan eski kayıt her yerde uygulanır

Tablo alanı boş bir kural, tablo kapsamlamasından önce yazılmış eski veridir.
Bu kural kapatılmaz, eski davranışıyla (her tabloya uygulanır) korunur.
Gerekçe: bir güvenlik kontrolünü veri biçimi yüzünden sessizce devre dışı
bırakmak, aşırı maskelemekten kötüdür.

### BR-04: `masking_type` yalnız `full` olabilir

API sınırında doğrulanır. Motorun uygulayamayacağı bir kural yazma anında
reddedilir, okuma anında sessizce düşürülmez.

### BR-05: Aynı kolon için tek kural

`(database_id, table_name, column_name)` üçlüsü benzersizdir. Aynı kolona
çelişen iki kural yazılamaz.

## 6. Acceptance Criteria

- AC-01: Given `Customers.email` için bir maskeleme kuralı, when kullanıcı
  `SELECT email FROM Suppliers` çalıştırır, then `email` maskelenmez.
- AC-02: Given aynı kural, when kullanıcı `SELECT email FROM Customers`
  çalıştırır, then `email` `********` olarak döner ve
  `applied_masking_rules` bu kolonu içerir.
- AC-03: Given `dbo.Customers.email` kuralı, when sorgu `FROM Customers`
  yazar, then kural uygulanır (ve tersi).
- AC-04: Given `table_name` boş bir eski kural, when herhangi bir sorgu
  çalıştırılır, then kural uygulanmaya devam eder.
- AC-05: Given `masking_type="partial"` içeren bir kural kaydetme isteği,
  when istek gönderilir, then `422` döner ve hiçbir kural yazılmaz.
- AC-06: Given ADMIN rolü, when sorgu çalıştırılır, then maskeleme
  uygulanmaz (mevcut davranış korunur).

Testler: `web_api/tests/unit/test_table_aware_masking.py`,
`web_api/tests/unit/test_masked_columns.py`,
`web_api/tests/unit/test_masking_rule_audit.py`.

## 7. Teknik ve Güvenlik Kısıtları

- Tablo kümesi, risk analizi için zaten yapılan **tek** parse'tan gelir
  (`QueryPlan`); maskeleme için ikinci bir parse yapılmaz.
- Maskeleme yalnız non-admin rollere uygulanır; bu davranış değişmedi.
- Maskeleme kararı sunucu tarafında verilir ve maskelenmiş değer istemciye
  öyle gider; istemci ham değeri hiçbir zaman görmez.
- Kural değişiklikleri `AuditAction.UPDATE_MASKING_RULES` ile denetlenir.

## 8. Open Questions

- OQ-2026-013: Yanıtlandı — enforcement tablo farkındalığına taşınacak,
  `masking_type` şemada kalacak ama tek desteklenen değer `full` olacak.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (ADR-0018)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

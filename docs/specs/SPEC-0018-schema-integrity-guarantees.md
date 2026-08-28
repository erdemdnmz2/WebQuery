# Mini-Spec: Şema bütünlüğü garantileri

## 1. Spec Kartı

- Özellik: Schema Integrity Guarantees
- Durum: Implemented
- Versiyon: 2026-08-28
- Tarih: 2026-08-28
- Sahip: WebQuery ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Uygulama veritabanının, modellerin bildirdiği index, unique kısıt ve NOT NULL
garantilerini eksiksiz taşıdığını garanti etmek. Eksik bir garanti, hatayı
nedeninden çok uzakta ve çok geç gösterir; bu yüzden eksiklik sessiz kalmamalı.

### Başarı Sinyali

- Eksik index veya kısıtla çalışan bir kurulum başlangıçta durur.
- `create_all()` ile kurulmuş eski veritabanları `alembic upgrade head` ile
  tamamlanır.
- Modele eklenen yeni bir index, sözleşmeye eklenmediğinde test kırılır.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- Gerekli index, unique kısıt ve NOT NULL kolonların tek listede tanımlanması.
- Bu listeyi karşılamayan veritabanında uygulamanın açılmaması.
- Eksik nesnelerin onarım revizyonuyla oluşturulması.

### Kapsam Dışı

- Hedef (target) veritabanlarının şeması. Bu spec yalnız WebQuery'nin kendi
  uygulama veritabanını kapsar.
- Foreign key ve kolon tipi doğrulaması.
- Değeri belirsiz olan NOT NULL kolonlarının otomatik doldurulması; bunlar
  guard tarafından raporlanır, elle çözülür.

## 4. Sözleşme

`web_api/common/schema_contract.py` gerekli şema nesnelerini listeler.
`common/schema_guard.verify_schema` uygulama başlangıcında bu listeyi
doğrular. Alembic revizyonu `e4b1c7a09d52` eksikleri oluşturur.

## 5. İş Kuralları

### BR-01: Eksik şema garantisiyle uygulama açılmaz

`verify_schema` eksik bulursa eksiklerin listesini yazar ve `SystemExit(1)` ile
çıkar. Uyarı verip devam etmek kabul edilebilir değildir.

### BR-02: Doğrulama migration'lardan sonra çalışır

Guard, `entrypoint.sh` içindeki `alembic upgrade head` tamamlandıktan sonra,
veritabanı bağlantısı doğrulanır doğrulanmaz çalışır. Böylece bir kurulum
"önce onar, sonra doğrula" sırasını izler.

### BR-03: Sözleşme modellerden sapamaz

`schema_contract` listesi `Base.metadata` ile birebir aynı olmak zorundadır.
Migration'lar model import edemediği için liste elle yazılır; eşitlik testle
zorlanır.

### BR-04: Onarım idempotenttir

`e4b1c7a09d52` yalnız eksik olanı oluşturur. Migration'larla kurulmuş bir
veritabanında hiçbir değişiklik yapmaz.

### BR-05: Belirsiz değer üretilmez

NOT NULL onarımı yalnız doğru değeri tartışmasız olan kolonlar için yapılır:
`Databases.uuid` (satır başına yeni kimlik; NULL uuid'yi hiçbir şey referans
edemez) ve `ActionLogging.approval_status` (model varsayılanı
`AUTO_APPROVED`). Diğer NOT NULL boşlukları guard raporlar, migration
doldurmaz.

### BR-06: Karşılanamayan kısıt sessizce atlanmaz

Yinelenen kayıt yüzünden unique kısıt oluşturulamıyorsa migration hata verir.
Atlayıp başarı bildirmek, garantisi olmayan bir veritabanını garantili gibi
göstermek olurdu.

## 6. Acceptance Criteria

- AC-01: Given tam şemalı bir veritabanı, when uygulama başlar, then
  `verify_schema` hata vermez ve başlangıç tamamlanır.
- AC-02: Given `ix_ActionLogging_trace_id` düşürülmüş bir veritabanı, when
  uygulama başlar, then `SystemExit(1)` ile durur ve eksik index adı çıktıda
  görünür.
- AC-03: Given `uq_server_database` bulunmayan bir veritabanı, when uygulama
  başlar, then başlangıç durur.
- AC-04: Given `Databases.uuid` nullable bir veritabanı, when uygulama başlar,
  then başlangıç durur.
- AC-05: Given eksikleri olan bir veritabanı, when `alembic upgrade head`
  çalışır, then eksik index ve kısıtlar oluşur ve sonraki başlangıç başarılı
  olur.
- AC-06: Given migration'larla kurulmuş bir veritabanı, when onarım revizyonu
  çalışır, then hiçbir şema değişikliği yapılmaz.
- AC-07: Given modele yeni bir index eklenmiş ancak sözleşmeye eklenmemiş,
  when testler çalışır, then `test_schema_contract.py` başarısız olur.

## 7. Teknik ve Güvenlik Kısıtları

- MSSQL, indexi olan kolonu `ALTER COLUMN` ettirmez (hata 5074). Onarım
  bağımlı index'leri düşürüp yeniden oluşturur; unique index'e rastlarsa
  hata verir.
- MSSQL diyalekti `get_unique_constraints()` implemente etmez; kontrol
  `get_indexes()` çıktısındaki unique index'leri de okur ve isim yerine kolon
  kümesiyle eşleştirir.
- Guard yalnız başlangıçta çalışır, sorgu yoluna girmez.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu (`ADR-0015`)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları raporlandı

# Spec: Maskeleme doğruluğu ve UUID anahtar normalizasyonu

## 1. Spec Kartı

- Özellik: Sonuç maskelemesinin arayüzde gerçeğe uygun gösterilmesi ve hedef
  veritabanı UUID anahtarlarının tek tipe indirilmesi
- Durum: Implemented
- Versiyon: 2026-08-25
- Tarih: 2026-08-25
- Sahip: WebQuery
- İlgili: `docs/specs/SPEC-0011-frontend-backend-contract-alignment.md`,
  `docs/adr/ADR-0001-schema-migrations-alembic.md`, `frontend/DESIGN.md`

## 2. Amaç ve Başarı Sinyali

### Amaç

Canlı ortamda yapılan uçtan uca testte üç kusur çıktı. Bu spec, ikisini
sözleşme düzeyinde kapatır:

1. `db_by_uuid` sözlüğü `Dict[str, ...]` olarak tanımlı olmasına rağmen ORM'den
   gelen `uuid.UUID` nesneleriyle anahtarlanıyordu. Sonuç: hiçbir sorgu
   çalışamıyor, kayıtlı çalışma alanı olan her kullanıcı için
   `GET /api/workspaces` 500 dönüyordu.
2. Arayüz, bir kolonu "maskeli" olarak etiketlerken backend'in o kolonu
   gerçekten maskeleyip maskelemediğini bilmiyordu. `is_db_admin` durumunda
   maskeleme bilinçli olarak atlanıyor, ama arayüz yine de maskeli rozeti
   basıyordu: yanlış güvence.

### Başarı Sinyali

- Hedef veritabanı araması, anahtarın kaynağı ne olursa olsun eşleşir.
- Arayüzdeki maskeli rozeti yalnızca backend o kolonu gerçekten maskelediğinde
  görünür.
- Her iki davranış da regresyon testiyle korunur.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `web_api/database_provider/database.py`, `web_api/workspaces/services.py`,
  `web_api/admin/services.py` içindeki UUID anahtar normalizasyonu.
- `SQLResponse` şemasına `masked_columns` alanının eklenmesi.
- `frontend/lib/execution.ts` ve sonuç tablosunun bu alandan beslenmesi.

### Kapsam Dışı

- Maskelemenin admin için atlanması kuralının kendisi. Bu bilinçli bir ürün
  kararıdır ve bu spec onu değiştirmez; yalnızca arayüzün bunu doğru
  yansıtmasını sağlar.
- Türkçe karakter kaybı (VARCHAR/NVARCHAR). Migration gerektirir,
  ADR-0001 kabul edilene kadar ertelenmiştir. Bkz. BR-05.

## 4. Davranış Kuralları

- **BR-01**: `DatabaseProvider.set_db_info`, `db_by_uuid` anahtarlarını her
  zaman `str` olarak yazar. Girdi `uuid.UUID` ya da `str` olabilir.
- **BR-02**: Hedef veritabanı UUID'sini bir istek dışı kaynaktan (ORM satırı)
  alan her çağrı, `get_session`'a `str` geçirir.
- **BR-03**: `SQLResponse.masked_columns`, bu yanıtta **gerçekten** maskelenmiş
  kolonların adlarını, sonuç kümesindeki yazımıyla taşır. Maskeleme
  uygulanmadıysa (admin atlaması dahil) liste boştur.
- **BR-04**: Arayüz maskeli rozetini yalnızca `masked_columns` içeriğine göre
  basar. İstenen maskeleme (`ad_hoc_mask_columns`) rozet için yeterli değildir.
- **BR-05**: Kullanıcının yazdığı serbest metin alanları Unicode saklanır.
  Model tarafı `AppNVarChar`'a geçirildi; **var olan kurulumlar için ALTER
  gerekir** ve `create_all` bunu yapmaz. Migration altyapısı inene kadar
  (ADR-0001) her ortamda elle uygulanmalıdır. Zaten bozulmuş kayıtlardaki
  karakterler geri gelmez.
- **BR-06**: Ayrıştırılamayan bir sorgu bir yetki kararı değildir. Rol
  denetimi ayrıştırma hatasını yutmaz; çağıran bunu sözdizimi hatası olarak
  bildirir. Sorgu yine engellenir, ama kullanıcıya yetkisi yokmuş gibi
  gösterilmez.

## 5. Kabul Kriterleri

- **AC-01**: `set_db_info` bir `uuid.UUID` ile beslendiğinde, `str` ile yapılan
  arama eşleşir.
- **AC-02**: `set_db_info` yeniden çağrıldığında eski UUID'ler haritada kalmaz.
- **AC-03**: Kayıtlı çalışma alanı olan bir kullanıcı için `GET /api/workspaces`
  200 döner ve `db_uuid` alanı string'tir.
- **AC-04**: READER rolüyle maskelenmiş bir sorguda `masked_columns`, maskelenen
  kolon adlarını içerir.
- **AC-05**: ADMIN rolüyle aynı sorguda maskeleme atlandığı için
  `masked_columns` boştur ve arayüzde rozet görünmez.
- **AC-06**: `masked_columns` içindeki adlar, sonuç satırlarındaki anahtar
  yazımıyla birebir eşleşir (büyük/küçük harf dahil).
- **AC-07**: Ayrıştırılamayan bir sorgu `QUERY_SYNTAX_ERROR` ile döner,
  `QUERY_REJECTED_BY_ANALYZER` ile değil.
- **AC-08**: Geçerli bir `SELECT` READER için hâlâ çalışır; `DELETE` hâlâ
  engellenir. Rol matrisi değişmedi.

## 6. Doğrulama

- `web_api/tests/unit/test_database_provider_uuid.py` (AC-01, AC-02)
- `web_api/tests/unit/test_masked_columns.py` (AC-04, AC-05, AC-06)
- `web_api/tests/unit/test_query_analyzer.py` (AC-07, AC-08)
- Tarayıcı üzerinden uçtan uca doğrulama (AC-03)

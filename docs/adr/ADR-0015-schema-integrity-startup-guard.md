# ADR-0015: Şema bütünlüğü startup guard'ı ve drift onarımı

## Status

Accepted

## Context

`ADR-0001` şema yönetimini Alembic'e taşıdı. Baseline revizyonu
(`5d2a9a282ea1`), Alembic'ten önce `Base.metadata.create_all()` ile kurulmuş
kurulumlarda tabloları yeniden oluşturmaya çalışıp patlamasın diye, beklenen
tabloların hepsi mevcutsa erken dönüyor:

```python
if expected_tables.issubset(existing_tables):
    return
```

Bu guard tabloların yeniden oluşturulmasını doğru şekilde engelliyor. Ancak
baseline yalnızca tablo oluşturmuyor; index'leri ve unique kısıtlarını da o
oluşturuyor. Erken dönüş bunları da atlıyor ve sonraki hiçbir revizyon geri
gelip tamamlamıyor. Sonuç, çalışan ama sessizce eksik bir şema.

Bu teorik bir risk değil. Projenin kendi geliştirme veritabanında ölçüldü:

| Eksik | Sonucu |
| --- | --- |
| `uq_server_database` | Aynı `(servername, database_name)` çiftinin iki kez kaydedilmesine karşı tek gerçek garanti. Yalnız Python tarafındaki kontrol kalıyor; iki eşzamanlı `add_database` isteği çift kayıt üretebilir. |
| `ix_Databases_uuid` | Her sorgu çalıştırması hedef veritabanını uuid ile çözüyor. |
| `ix_ActionLogging_trace_id` | Slack onay akışı `ActionLogging` kaydını `trace_id` ile buluyor. |
| `ix_ActionLogging_database_id`, `ix_ActionLogging_approval_status` | Audit ve onay listelemeleri. |
| `Databases.uuid` nullable | NULL uuid'li satır her API yüzeyinden erişilemez; tüm yüzeyler hedefi uuid ile adresliyor. |
| `ActionLogging.approval_status` nullable | Onay durumu olmayan log kaydı, denetim izinde anlamsız bir boşluk. |

Bu eksikliklerin ortak özelliği, hatanın nedeninden çok uzakta görünmesi:
veritabanı aylarca sorunsuz çalışır, sonra bir gün iki admin aynı hedefi
kaydeder ya da bir Slack onayı sorgusunu bulamaz.

## Decision

Şema garantileri hem onarılacak hem de doğrulanacak.

**1. Tek kaynak-doğru sözleşme.** `web_api/common/schema_contract.py`, gerekli
index'lerin, unique kısıtlarının ve NOT NULL kolonlarının düz veri listesini
tutar. Migration'lar model sınıflarını import edemediği için bu liste elle
yazılmıştır; `tests/unit/test_schema_contract.py` listenin `Base.metadata` ile
birebir aynı olduğunu doğrular, böylece sözleşme modellerden sapamaz.

**2. Onarım revizyonu.** `e4b1c7a09d52` eksik olan her şeyi oluşturur.
Guard'lıdır: migration'larla kurulmuş bir veritabanında hiçbir şey yapmaz.

**3. Fail-closed startup guard.** `common/schema_guard.verify_schema`, uygulama
başlangıcında — `entrypoint.sh` içindeki `alembic upgrade head` çalıştıktan
sonra — şemayı doğrular. Eksik varsa eksiklerin listesini yazıp `SystemExit(1)`
ile çıkar. Eksik index veya kısıtla uygulama açılmaz.

## Rejected Alternatives

### 1. Baseline'ın erken dönüşünü kaldırmak

En doğrudan çözüm gibi görünür. Ancak `create_all()` ile kurulmuş bir
veritabanında baseline'ın `create_table` çağrıları "tablo zaten var" hatasıyla
patlar; guard tam olarak bunun için konmuştu. Kaldırmak eski kurulumları
tamamen açılamaz hale getirir.

### 2. Yalnız onarım revizyonu yazmak, guard koymamak

Bugünkü sapmayı kapatır. Ancak sapmanın kaynağı bir revizyonun unutulması
değil, bir revizyonun **koşullu** çalışmasıdır; aynı desen ileride tekrar
edebilir. Ayrıca elle müdahale edilmiş, kısmen restore edilmiş veya farklı bir
branch'ten damgalanmış veritabanları da aynı duruma düşebilir. Doğrulama
olmadan bu durum yine sessiz kalır.

### 3. Guard'ı uyarı seviyesinde tutmak

Uygulama açılır, log'a uyarı düşer. Ancak startup logları rutin olarak
okunmuyor ve eksik kısıtın maliyeti veri bütünlüğü — çift hedef veritabanı
kaydı ya da adreslenemeyen bir satır. Uyarı, sorunu fark edilmesi en zor anda
bırakır. Kullanıcı bu kararı açıkça verdi: index ve kısıtlar olmadan
veritabanı ayağa kalkmamalı.

### 4. Şemayı `Base.metadata` ile doğrulamak

Sözleşmeyi elle yazmaktan kaçınırdı. Ancak migration'lar model import etmiyor
(baseline'daki yorum bunu açıkça belirtiyor: şema migration'ın kendi tarifidir,
modelin değil), dolayısıyla onarım revizyonu bu kaynağı kullanamazdı. Düz veri
listesi + eşitlik testi, DRY'liği bağımlılık yerine testle sağlıyor.

## Consequences

- Eksik şema garantisi olan bir kurulum açılmaz. Bu bilinçli bir kullanılabilirlik
  ödünüdür: sessizce eksik çalışmaktansa açılmamak tercih edilmiştir.
- Modele yeni bir index veya kısıt eklendiğinde `schema_contract` da
  güncellenmek zorundadır; unutulursa `test_schema_contract.py` kırmızıya döner.
- Guard her başlangıçta şema tanıtımı (introspection) yapar. Bu, başlangıçta bir
  kez çalışan ve sorgu yoluna girmeyen tek seferlik bir maliyettir.
- MSSQL, indexi olan bir kolonu `ALTER COLUMN` ettirmez (hata 5074). Onarım
  revizyonu bağımlı index'leri düşürüp değişiklikten sonra yeniden oluşturur;
  unique index'e rastlarsa elle müdahale istemek üzere hata verir.
- MSSQL diyalekti `get_unique_constraints()` implemente etmez; unique kısıtları
  `get_indexes()` üzerinden unique index olarak bildirir. Sözleşme kontrolü
  ikisini de okur ve isim yerine kolon kümesiyle eşleştirir, çünkü adsız
  tanımlanan kısıtların adını veritabanı üretir.

## References

- ADR: `docs/adr/ADR-0001-schema-migrations-alembic.md`
- Spec: `docs/specs/SPEC-0018-schema-integrity-guarantees.md`
- Kod: `web_api/common/schema_contract.py`, `web_api/common/schema_guard.py`
- Migration: `web_api/migrations/versions/e4b1c7a09d52_repair_schema_drift.py`
- Supersedes / Superseded by: yok

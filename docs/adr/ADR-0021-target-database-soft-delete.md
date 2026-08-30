# Trade-off Tablosu

Senaryo: Kayıtlı bir hedef veritabanı kaydı kaldırılmak istendiğinde ne olur?
`Databases.id` üç tablodan yabancı anahtarla referans alınıyor
(`UserDatabaseAssociation`, `MaskingRule`, `ActionLogging`) ve `QueryData`
hedefe yabancı anahtarla değil `(servername, database_name)` **metin
çiftiyle** bağlı.

Baştan tahminimizce en belirleyici kriter: denetim izinin bütünlüğü. Bir
veritabanının kaydı kaldırıldı diye o veritabanında kimin ne çalıştırdığının
kaydı kaybolmamalı.

| Kriter | 1. Sert silme + cascade | 2. Sert silme, referans varsa reddet | 3. Yumuşak silme (seçilen) |
| --- | --- | --- | --- |
| Performans | Fark yok | Fark yok | Fark yok |
| Kompleksite | Düşük | Düşük | Orta: her listeleme ve çalıştırma yolu `is_active` bilmeli |
| Ölçeklenebilirlik | Fark yok | Fark yok | Emekli satırlar birikir (küçük tablo) |
| Bakım | Cascade zinciri gözden kaçabilir | Kaldırma çoğu zaman mümkün olmaz | Filtrenin unutulduğu yer bir sızıntı olur |
| Maliyet | Düşük | Düşük | Düşük |
| **Denetim izinin bütünlüğü** | Yok edilir | Korunur ama kayıt hiç kaldırılamaz | Korunur ve kayıt kaldırılabilir |
| **Yeniden kayıt** | Yeni `id`, geçmişle bağ kopar | Konu dışı | Aynı satır dirilir, geçmiş bağlı kalır |

## Karar

Seçilen alternatif: **3. Yumuşak silme.**

Gerekçe: Belirleyici kriter denetim izinin bütünlüğü. Alternatif 1 bunu
doğrudan yok eder — `ActionLogging` satırları cascade ile silinir ya da
öksüz kalır, `QueryData` metin çiftiyle bağlı olduğu için hiç haber almaz ve
kayıtlı workspace'ler sessizce çalışamaz hâle gelir. Alternatif 2 izi korur
ama pratikte hiçbir kaydın kaldırılamaması demektir: bir hedef veritabanı bir
kez sorgulandığı anda kalıcı olur. Yumuşak silme ikisinin de sorununu
çözer; bedeli, `is_active` filtresinin her okuma yolunda uygulanması
gerektiğidir.

# ADR-0021: Hedef veritabanı kaydı yumuşak silinir

## Status

Accepted

## Context

Kayıt edilen bir hedef veritabanı hiçbir şekilde kaldırılamıyordu ve
güncellenemiyordu (denetim bulgusu P1-10). Kaldırma yolunu tasarlarken veri
modelindeki iki gerçek belirleyici oldu:

1. `Databases.id`, üç tablodan yabancı anahtarla referans alınıyor. Bunların
   biri `ActionLogging` — yani sorgu çalıştırma denetim kaydı.
2. `QueryData` (kayıtlı workspace sorguları) hedefe yabancı anahtarla değil,
   `(servername, database_name)` metin çiftiyle bağlı. Veritabanı bu bağı
   bilmiyor; hiçbir cascade, hiçbir kısıt onu korumuyor.

İkinci nokta, sert silmeyi yalnız "kötü" değil, **sessizce kötü** yapıyor:
`Databases` satırı silindiğinde ilgili `QueryData` satırları yerinde kalır,
hiçbir hata üretmez, ama artık hiçbir kayda çözülmedikleri için
`db_uuid=""` döndürürler. Kullanıcının kayıtlı sorgusu, sebebi görünmeden
çalıştırılamaz olur.

## Decision

1. `DELETE /api/owner/databases/{id}` kaydı **emekliye ayırır**:
   `is_active=False`, `retired_at`, `retired_by` yazılır. Hiçbir satır
   silinmez. İşlem `AuditAction.REMOVE_DATABASE` ile denetlenir.
2. Emekli kayıt **çalışma zamanı kataloğunda yer almaz**: `get_db_info()`
   yalnız `is_active=True` satırları döndürür, dolayısıyla her çalıştırma
   yolu emekli bir hedefe karşı fail-closed davranır.
3. Okuma yolları emekli kaydı canlıymış gibi göstermez. Workspace
   listeleme ve detay uçları `db_uuid` olarak boş dize döndürür; workspace
   çalıştırma yolu kaydı bulunamamış gibi reddeder.
4. Aynı `(servername, database_name)` yeniden kaydedilmek istenirse **emekli
   satır diriltilir** (`is_active=True`, `retired_at=None`,
   `retired_by=None`), yeni bir satır oluşturulmaz. `id` korunduğu için
   geçmiş audit ve sorgu kayıtları bağlı kalır.
5. Sert silme (hard delete) desteklenen bir işlem değildir. Bir kaydı ve
   geçmişini gerçekten yok etmek gerekiyorsa bu bir veri saklama kararıdır,
   bir API işlemi değil.

## Rejected Alternatives

### 1. Sert silme + cascade

En basit ve tabloyu temiz tutar. Reddedilme nedeni: `ActionLogging`
satırlarını da silmek, denetim kaydının amacını ortadan kaldırır — bir
veritabanının kaydını kaldırmak, orada ne yapıldığının kaydını silmenin bir
yolu hâline gelirdi. Ayrıca `QueryData` bağı yabancı anahtar olmadığı için
cascade ona zaten ulaşmaz; kayıtlı workspace'ler sessizce bozulurdu.

### 2. Sert silme, referans varsa reddetmek

Denetim izini korur ve uygulaması basittir. Reddedilme nedeni: bir hedef
veritabanı bir kez sorgulandığı anda `ActionLogging` referansı oluşur ve
kayıt kalıcı olur. Yani pratikte "kaldırma" özelliği hiç çalışmayan bir uç
olurdu; bulgunun kendisi kapanmazdı.

### 3. Emekli kaydı listeden tamamen gizlemek (OWNER'dan da)

Basit görünür. Reddedilme nedeni: OWNER'ın emekli kayıtları görebilmesi
gerekiyor — yeniden etkinleştirme, `retired_by`/`retired_at` ile kimin ne
zaman kaldırdığını görme ve aynı adla yeni kayıt denemesinin neden mevcut
satırı dirilttiğini anlama, hepsi bu görünürlüğe bağlı.

## Consequences

- Denetim kaydı ve kayıtlı sorgu geçmişi, hedef veritabanının kaydı
  kaldırıldıktan sonra da eksiksiz kalır.
- `Databases` tablosunda emekli satırlar birikir. Tablo doğası gereği küçük
  (kayıtlı hedef veritabanı sayısı kadar), bu bir ölçek sorunu değil.
- Her yeni okuma yolu `is_active` filtresini uygulamak zorunda. Unutulan bir
  filtre, emekli bir kaydı canlıymış gibi gösterir. `get_db_info()` merkezi
  filtre olduğu için çalıştırma yolları otomatik korunuyor; risk, doğrudan
  `Databases` sorgulayan yeni kodda.
- `retired_by` kullanıcı adını metin olarak saklar; kullanıcı sonradan
  silinse bile kaydın kim tarafından kaldırıldığı okunabilir kalır.

## Accepted Risks

- **`is_active` filtresinin unutulması** bir bilgi sızıntısı değil ama bir
  doğruluk hatasıdır: kullanıcı çalıştıramayacağı bir hedefi seçilebilir
  görür. Azaltma: runtime kataloğu tek bir yerden (`get_db_info`)
  filtreleniyor ve `tests/integration/test_database_lifecycle.py` emekli bir
  kaydın listeleme ve çalıştırma yollarında görünmediğini doğruluyor.
- **`QueryData` metin çifti bağı** bu ADR ile ortadan kalkmıyor, yalnız
  telafi ediliyor (kimlik değişikliğinde satırlar aynı transaction içinde
  taşınıyor). Kalıcı çözüm — yabancı anahtar veya kalıcı dış tanımlayıcı —
  ayrı bir iş olarak izleniyor
  (`docs/inbox/DATABASE-EXTERNAL-IDENTIFIER-UUID.md`).

## References

- Spec: `docs/specs/SPEC-0027-target-database-lifecycle.md`
- Open questions: `docs/open-questions.md` OQ-2026-016, OQ-2026-017,
  OQ-2026-018, OQ-2026-019
- Denetim: `webquery_denetim_raporu.md` P1-10, P2-20c
- İlgili: `docs/adr/ADR-0005-role-based-target-database-credentials.md`,
  `docs/adr/ADR-0017-persisted-platform-owner-boundary.md`,
  `docs/adr/ADR-0009-audit-log-foundation.md`
- Supersedes / Superseded by: yok.

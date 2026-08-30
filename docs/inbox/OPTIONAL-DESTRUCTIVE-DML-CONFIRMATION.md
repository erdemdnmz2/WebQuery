# Hedef veritabanı bazında isteğe bağlı yıkıcı DML teyidi

**Durum:** Inbox / ertelendi
**Kaydedildi:** 2026-08-29
**Kapsam:** hedef veritabanı kayıt akışı, `Databases` modeli, sorgu çalıştırma
servisi ve Studio sorgu arayüzü

Bu kayıt, planın eski Adım 20'sindeki (`3.4.2`) yıkıcı DML etki alanı teyidini
çekirdek akıştan çıkarır. Karar: WebQuery'nin tüm hedef veritabanlarında
zorunlu bir `DELETE`/`UPDATE` teyidi uygulanmayacak. İhtiyaç duyan bir hedef
veritabanı, **eklenirken** bu korumayı isteğe bağlı olarak etkinleştirebilir.
Bu belge uygulanacak işin kaydıdır; mevcut runtime davranışını değiştirmez.

## Neden ertelendi

Rol bazlı hedef DB hesapları, sorgu kademesi seçimi ve sert SQL analiz blokları
zaten temel güvenlik sınırını oluşturur:

- salt-okuma sorguları `ro` hesabıyla çalışır;
- veri değiştiren sorgular `rw` hesabı olmadan çalışamaz;
- SQL injection ve yasaklı operasyonlar hiçbir role istisna tanımadan reddedilir.

Etki alanını `SELECT COUNT(*)` ile gösterme, yanlışlıkla geniş kapsamlı
`DELETE`/`UPDATE` için faydalı ek bir insan-hatası korumasıdır; ancak her hedef
veritabanının operasyonel ihtiyacı değildir. Bu nedenle uygulama genelinde
zorunlu bir akış yerine, kayıt sırasında seçilen bir veritabanı politikası
olacaktır.

## Hedef davranış

Hedef veritabanı ekleme formu/API'si, credential modu seçiminden bağımsız bir
"Yıkıcı DML teyidi" seçeneği sunar.

| Kayıt ayarı | `UPDATE` / `DELETE` çalıştırıldığında |
| --- | --- |
| Kapalı | Mevcut yetki, analiz ve audit akışıyla çalışır; satır sayımı/teyit istenmez. |
| Açık | Uygun tek-statement `UPDATE`/`DELETE` için eşdeğer `SELECT COUNT(*)` `ro` kademesinde çalışır; kullanıcıya etki bilgisi gösterilir ve aynı sorguya bağlı kısa ömürlü teyit alınır. |

Sayıma güvenle çevrilemeyen sorgu biçimleri (ör. JOIN'li `UPDATE`, CTE veya
çoklu statement) teyidi atlayarak çalıştırılmaz. Bu durum için nihai ürün
politikası, özellik planlandığında ayrıca belirlenmelidir: reddetmek veya ikinci
insan onayına göndermek olası seçeneklerdir.

## Uygulama kalemleri

1. Veritabanı kaydına, migration ile kalıcı bir `destructive_dml_confirmation_enabled`
   bayrağı ekleyin. Yeni ve mevcut kayıtların varsayılanı kapalı olmalıdır;
   etkinleştirme açık bir admin seçimi olmalıdır.
2. `POST /api/admin/add_database` sözleşmesine ve ekleme formuna bu seçeneği
   ekleyin. Ayar, credential veya kullanıcı adı/şifre değerleriyle birlikte
   public listeleme uçlarına taşınmamalıdır; yalnız yetkili yönetim yüzeyinde
   görünmelidir.
3. Bayrak açıkken `QueryAnalyzer.is_destructive()` ve
   `count_equivalent()` ile satır sayısını çıkarın; sayımı yalnız `ro`
   oturumunda yapın.
4. Teyit jetonunu kullanıcı ve SQL özetine bağlayın; SQL değiştiğinde veya
   süre dolduğunda jeton geçersiz olmalıdır. `CONFIRMATION_SECRET` yoksa bu
   seçenek etkinleştirilememeli ve etkin kayıt için sorgu çalıştırma
   fail-closed reddedilmelidir; uygulamanın tümü sır bu özellik kullanılmadığı
   için açılmayı reddetmemelidir.
5. Teyit, sayım sonucu ve sonuçta çalıştırma/ret kararı audit kaydına yazılsın;
   SQL veya credential değerleri loglara eklenmesin.
6. Ayar kapalıyken ek sayım sorgusu, teyit ekranı veya ek API çağrısı olmaması;
   ayar açıkken ise sorgu değiştirilince jetonun reddedilmesi testle sabitlensin.

## Bağımlılıklar

- Zorunlu: `3.1` rol bazlı `ro`/`rw` credential kademeleri. Sayım sorgusu
  yazma hesabıyla değil `ro` hesabıyla çalışmalıdır.
- Zorunlu: `3.3` sqlglot yükseltmesi; builder API'si sürümle uyumlu test
  edilmelidir.
- Opsiyonel özellikle birlikte: `CONFIRMATION_SECRET` config doğrulaması.
- Bağımsız: `3.2` analyzer sertleştirmesi, `PLATFORM_ADMINS`, logging ve
  streaming işleri bu özelliğin uygulanmasını beklemez.

## Riskler

- Sayım ve gerçek yazma arasında veri değişebilir; gösterilen sayı teyit
  anındaki etkidir, transaction garantisi değildir.
- Sayıma çevrilemeyen SQL için fail-open davranış, bu özelliğin korumasını
  delmemelidir.
- Büyük tablolardaki `COUNT(*)` maliyetli olabilir; bu nedenle özellik her
  veritabanında varsayılan kapalıdır ve etkinleştirilecek hedeflerde sorgu
  planları değerlendirilmelidir.

## Bu kayıt uygulanırken oluşturulacak artefaktlar

- Yeni/ayrı mini-spec: kayıt ayarı, API/UI sözleşmesi ve fail-closed kuralı.
- Proposed ADR: satır sayımı ile teyit yaklaşımının, tüm platform yerine hedef
  veritabanı bazında uygulanması.
- Backend ve frontend testleri; Alembic migration.

# Mini-Spec: Tasarım sisteminin sertleştirilmiş backend'e hizalanması

## 1. Spec Kartı

- Özellik: Yeni arayüzün güvenlik sertleştirmesi sonrası sözleşmeye bağlanması
- Durum: Implemented
- Versiyon: 2026-08-25
- Tarih: 2026-08-25
- Sahip: WebQuery
- İlgili: `docs/specs/SPEC-0005-access-refresh-session-auth.md`,
  `docs/specs/SPEC-0011-frontend-backend-contract-alignment.md`,
  `docs/specs/SPEC-0013-approval-concurrency.md`,
  `docs/adr/ADR-0008-access-refresh-session-auth.md`,
  `docs/adr/ADR-0011-conditional-approval-update.md`, `frontend/DESIGN.md`

## 2. Amaç ve Başarı Sinyali

### Amaç

`redesign/frontend-design-system` üzerinde üretilen arayüz, `main`'deki API
sözleşmesine göre yazılmıştı. Bu branch o tarihten sonra oturum yönetimini,
onay/red akışını ve hedef veritabanı hata davranışını değiştirdi. Arayüz bu
branch'e alındığında aradaki farkın kapatılması gerekir; kapatılmazsa red akışı
422 ile başarısız olur ve kullanıcı erişim jetonu her dolduğunda giriş ekranına
düşer.

### Başarı Sinyali

- Red kararı, backend'in zorunlu tuttuğu gerekçeyle birlikte gider ve başarılı olur.
- Erişim jetonu dolduğunda oturum kullanıcıya görünmeden yenilenir.
- Aynı talebi iki yönetici sonuçlandırdığında kaybeden taraf sessiz hata değil,
  açık bir "başkası karar verdi" durumu görür.
- `npm run audit:api` bu branch'in rotalarına karşı geçer.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `frontend/services/api.ts`: oturum yenileme, red gövdesi, hata kodu sabitleri.
- `frontend/components/app/admin/ReviewDialog.tsx`: red gerekçesi alanı ve
  eşzamanlılık çatışması davranışı.
- `frontend/lib/execution.ts`: `QUERY_SYNTAX_ERROR` ayrımı.

### Kapsam Dışı

- Backend'de davranış değişikliği yok. Bu iş yalnızca arayüzü yürürlükteki
  sözleşmeye bağlar.
- `GET /api/admin/audit_log` için arayüz üretilmedi (bkz. BR-05).
- `POST /api/multiple_query` için arayüz (SPEC-0011'de de kapsam dışıydı).

## 4. Sözleşme

Bu branch'in getirdiği ve arayüzün bağlandığı sözleşme:

| Endpoint | İstek | Yanıt |
| --- | --- | --- |
| `POST /api/refresh` | gövdesiz, yalnız bu endpoint'e gönderilen `refresh_token` çerezi (`path=/api/refresh`) | `{ok: true}`; oturum yoksa/yeniden kullanıldıysa 401 |
| `POST /api/admin/reject_query/{workspace_id}` | `{reason}`, 3-500 karakter | 200, gövdesiz |
| `POST /api/admin/approve_query/{workspace_id}` | `{show_results}` | `{success, ...}` |
| Karar çakışması | - | 409, `error_code = "APPROVAL_CONFLICT"` |
| Karar yetkisizliği | - | 403, `error_code = "APPROVAL_FORBIDDEN"` |
| Çözümlenemeyen SQL | - | 400, `error_code = "QUERY_SYNTAX_ERROR"` |

`ACCESS_TOKEN_EXPIRE_MINUTES` varsayılanı 20 dakika,
`REFRESH_TOKEN_EXPIRE_HOURS` varsayılanı 12 saattir.

## 5. İş Kuralları

### BR-01: 401 önce yenilenir, sonra oturum ölü sayılır

Oturum içi bir 401, çoğunlukla "erişim jetonu doldu" demektir. Arayüz giriş
ekranına yönlendirmeden önce bir kez `POST /api/refresh` dener; başarılıysa
özgün isteği aynı gövdeyle tekrarlar. Yenileme başarısızsa yönlendirme yapılır.
Tekrar edilen istek ikinci kez yenileme denemez.

### BR-02: Eşzamanlı 401'ler tek yenileme paylaşır

Refresh jetonu tek kullanımlıktır. Aynı anda 401 alan isteklerin her biri kendi
yenilemesini gönderirse, biri hariç hepsi bir sonraki isteğin ihtiyaç duyduğu
jetonu yakar. Arayüz uçuştaki tek yenileme sözünü paylaştırır.

### BR-03: Giriş, kayıt ve yenilemenin kendisi yenileme denemez

Bu üç çağrıda 401 normal sonuçtur; henüz kurulmamış bir oturum yenilenemez.
Bunlar `skipAuthRedirect` ile işaretlidir ve yenileme yolunun dışındadır.

### BR-04: Red gerekçesi zorunludur ve istemcide doğrulanır

Reddetme, kırpılmış hâli en az 3 karakter olan bir gerekçe olmadan
gönderilmez. Doğrulama istemcide yapılır; kullanıcı yazdığını kaybetmez ve
odak gerekçe alanına gider. Sunucu aynı kuralı bağımsız olarak uygular; istemci
doğrulaması sunucununkinin yerine geçmez.

### BR-05: Karar çakışması listeyi bayat kabul eder

`APPROVAL_CONFLICT` alan arayüz, kararı tekrar denemez. Sunucudaki karar
kesindir; bayat olan taleptir. Arayüz uyarı gösterir, diyaloğu kapatır ve
bekleyen talep listesini yeniler.

### BR-06: Sözdizimi hatası onay bekleyen durum değildir

`QUERY_SYNTAX_ERROR`, ifadenin çözümlenemediğini ve hiçbir rol kararına
varılmadığını söyler; çalışma alanı da oluşturulmaz. Arayüz bunu
`QUERY_REJECTED_BY_ANALYZER` gibi sarı bekleme durumu değil, kullanıcının kendi
SQL'ine dönmesini isteyen bir hata olarak gösterir.

### BR-07: Denetim kaydı ekranı üretilmedi

`GET /api/admin/audit_log` bu branch'te eklendi ve arayüzü yoktur. Bu iş
arayüzü yürürlükteki sözleşmeye hizalar; yeni ekran üretmez. Endpoint denetimi
bunu "arayüzü olmayan rota" olarak listelemeye devam eder.

## 6. Acceptance Criteria

- AC-01: Given geçerli bir oturum, when erişim jetonu dolduktan sonra bir istek
  yapılır, then arayüz `POST /api/refresh` çağırır, isteği tekrarlar ve kullanıcı
  giriş ekranını görmez.
- AC-02: Given refresh çerezi de geçersiz, when bir istek 401 alır, then arayüz
  bir kez yenileme dener ve ardından `/login` rotasına yönlendirir.
- AC-03: Given aynı anda 401 alan birden çok istek, when yenileme tetiklenir,
  then yalnızca bir `POST /api/refresh` gönderilir.
- AC-04: Given inceleme diyaloğu açık ve gerekçe boş, when "Reddet" tıklanır,
  then istek gönderilmez, alan altında hata görünür ve odak alana gider.
- AC-05: Given 3 karakterden uzun bir gerekçe, when "Reddet" tıklanır, then
  `{reason}` gövdesiyle istek gider ve talep listeden düşer.
- AC-06: Given talep başka bir yönetici tarafından sonuçlandırılmış, when karar
  verilir, then uyarı bildirimi gösterilir, diyalog kapanır ve liste yenilenir.
- AC-07: Given çözümlenemeyen bir SQL, when çalıştırılır, then sonuç paneli
  Türkçe sözdizimi hatası gösterir; "onaya gönderildi" durumu görünmez.
- AC-08: Given diyalog kapatılır, when yeniden açılır, then önceki gerekçe metni
  ve önizleme sonucu taşınmaz.
- AC-09: `npm run audit:api` bu branch'in rotalarına karşı sıfır hatayla geçer.

## 7. Teknik ve Güvenlik Kısıtları

- Bileşenler doğrudan `fetch` çağırmaz; yenileme dâhil her çağrı
  `services/api.ts` içindeki `request` üzerinden geçer (DESIGN.md §15.6).
- Yenileme yalnız çerezle çalışır; arayüz refresh jetonunu okumaz, saklamaz veya
  bir gövdeye yazmaz. Jetonlar `httponly` kalır.
- Login yanıtı token değeri içermez; access ve refresh tokenlar yalnız cookie
  üzerinden tarayıcıya ulaşır.
- İstemci doğrulaması bir kolaylıktır; yetki ve gerekçe kuralının kaynağı
  `web_api/approval/service.py` içindeki `decide` fonksiyonudur.
- Red gerekçesi talebi gönderen kullanıcıya çalışma alanı açıklaması üzerinden
  görünür; gerekçe alanının yardım metni bu görünürlüğü doğru anlatmalıdır.

## 8. Open Questions

- Yok. `docs/open-questions.md` içindeki tüm kayıtlar `Answered` durumundadır.

## 9. Done Kontrolü

- [x] Acceptance criteria için doğrulama yapıldı (tip kontrolü, endpoint
      denetimi, kontrast denetimi, üretim derlemesi)
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (yeni ADR gerekmedi; ADR-0008 ve
      ADR-0011 geçerli kararlardır)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

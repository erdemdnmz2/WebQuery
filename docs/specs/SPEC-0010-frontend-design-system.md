# Mini-Spec: `Frontend tasarım sistemi ve arayüz yenilemesi`

## 1. Spec Kartı

- Özellik: `WebQuery arayüz yenilemesi`
- Durum: Implemented
- Versiyon: `2026-08-24`
- Tarih: `2026-08-24`
- Sahip: `WebQuery ekibi`

## 2. Amaç ve Başarı Sinyali

### Amaç

Mevcut arayüz, üretim veritabanlarına sorgu çalıştıran bir denetim konsolundan
çok bir demo gibi görünüyordu: tek tema, CDN bağımlı yükleme, `window.alert`
ile geri bildirim, klavye ile kullanılamayan menüler, karışık dil ve durum
rengiyle marka renginin birbirine karıştığı bir palet. Amaç, ürünü günlük
kullanan veri mühendisi ve yöneticiler için okunabilir, klavye öncelikli ve
erişilebilir bir arayüz kurmak; bunu tek bir token katmanı üzerine oturan bir
tasarım sistemiyle tekrar edilebilir kılmak.

### Başarı Sinyali

- `npm run audit:contrast` her iki temada da sıfır hata ile geçer.
- `npx tsc --noEmit` strict mod altında hatasız çalışır.
- Ana eylemler (çalıştır, kaydet, arama, gezinme, tema) fare olmadan yapılabilir.
- Her uzak çağrının yükleniyor, boş, hata ve dolu durumu ekranda karşılığı vardır.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- Token katmanı, primitive bileşen kütüphanesi ve tüm ekranların yeniden yazımı.
- Açık ve koyu tema, sistem tercihi desteği ve kalıcı tema seçimi.
- Klavye kısayolları, komut paleti, odak halkası ve içeriğe atlama bağlantısı.
- Ace Editor yerine tema token'larıyla boyanan CodeMirror 6 tabanlı SQL düzenleyici.
- Türkçe dil birliği: daha önce İngilizce olan ekranlar da Türkçeye alındı.

### Kapsam Dışı

- Backend sözleşmeleri. Hiçbir endpoint, istek gövdesi veya yanıt alanı değişmedi.
- Bilgi mimarisi ve rota yapısı. `/`, `/editor`, `/editor/:id`, `/execute/:id`,
  `/admin`, `/login`, `/register` aynı kaldı.
- Risk analizi, onay akışı, maskeleme kuralı semantiği ve denetim kayıtları.
- `xlsx` paketinin güvenlik güncellemesi (bkz. Bölüm 7).

## 4. Sözleşme

Backend sözleşmesi değişmedi. Frontend, tüm çağrıları
`frontend/services/api.ts` içindeki tek tip istemci üzerinden yapar:

| Ekran | Çağrı |
| --- | --- |
| Oturum | `GET /api/me`, `POST /api/login`, `POST /api/register`, `POST /api/logout` |
| Çalışma alanları | `GET /api/workspaces`, `DELETE /api/workspaces/{id}` |
| Studio | `GET /api/database_information`, `GET /api/get_workspace_by_id/{id}`, `GET /api/masking_rules`, `POST /api/execute_query`, `POST /api/workspaces`, `PUT /api/workspaces/{id}` |
| Çalıştırma | `GET /api/get_workspace_by_id/{id}`, `POST /api/execute_workspace/{id}` |
| Yönetim | `GET /api/admin/queries_to_approve`, `POST /api/admin/execute_for_preview/{id}`, `POST /api/admin/approve_query/{id}`, `POST /api/admin/reject_query/{id}`, `GET/POST /api/admin/databases...` |

UI akışında değişen tek şey sunum katmanıdır: `401` yanıtı artık tek noktadan
`/login` yönlendirmesine dönüşür ve hata gövdeleri (`detail`, `error`,
`message`, FastAPI doğrulama dizisi) tek bir okunabilir mesaja indirgenir.

## 5. İş Kuralları

### BR-01: Renk anlam taşır

Uygulama kromu akromatiktir. Kroma yalnızca durum için ayrılmıştır: risk,
onay bekleyen, onaylanmış, reddedilmiş, maskeli. Birincil eylem düğmesi marka
rengi değil maksimum kontrastlı mürekkep rengidir, böylece onay düğmesi bir
durum rozetiyle dikkat için yarışmaz. Tek aksan rengi (düşük doygunlukta
teal) sadece odak, seçim, aktif gezinme ve marka işareti için kullanılır.

### BR-02: Çalışma alanı durumu tek kaynaktan okunur

Etiket, renk ve "şimdi ne yapabilirim" açıklaması
`frontend/lib/workspace-status.ts` içinde tanımlıdır. Hiçbir ekran kendi
etiketini üretmez.

### BR-03: Düzenlenebilirlik durumdan türetilir

`waiting_for_approval` ve `rejected` durumlarındaki çalışma alanlarında
düzenleyici salt okunur olur ve nedeni ekranda yazılır. `Çalıştır` ekranı
yalnızca `approved_with_results` ve `show_results = true` olduğunda açılır.

### BR-04: Maskeleme görünürdür

Yönetici kuralları kullanıcı arayüzünde kaldırılamaz olarak gösterilir.
Sonuç ızgarasında maskelenen kolon başlığı işaretlenir. Geçici (ad-hoc)
kurallar yalnızca o çalıştırmaya uygulanır ve kaydedilmez.

### BR-05: Yıkıcı işlem adını söyler

`window.confirm` kaldırıldı. Silme işlemi, silinecek kaydın adını ve hedefini
gösteren bir onay penceresi açar; odak önce vazgeç eylemine gider.

### BR-06: Üretilen veritabanı parolası varsayılan olarak gizlidir

Yeni veritabanı kaydından dönen parola maskeli gösterilir, ancak açık istekle
görünür olur ve panoya kopyalanabilir. Uyarı metni parolanın tekrar
gösterilmeyeceğini belirtir.

## 6. Acceptance Criteria

- AC-01: Given oturum açmış bir kullanıcı, when çalışma alanları listesi
  yüklenirken, then önce içerik şeklinde iskelet gösterilir, veri gelince
  liste yerine oturur ve düzen sıçraması olmaz.
- AC-02: Given kayıtlı çalışma alanı yok, when liste yüklenir, then ne
  yapılacağını söyleyen bir boş durum ve "İlk sorgunuzu yazın" eylemi görünür.
- AC-03: Given Studio ekranı, when `Cmd/Ctrl + Enter` basılır, then sorgu
  çalıştırılır; `Cmd/Ctrl + S` kaydeder; `Cmd/Ctrl + K` komut paletini açar.
- AC-04: Given sorgu hata döndürür, when yanıt gelir, then hata `role="alert"`
  ile sonuç panelinde tam metin olarak gösterilir ve ızgara gösterilmez.
- AC-05: Given onay bekleyen bir çalışma alanı, when Studio'da açılır, then
  düzenleyici salt okunur olur ve kilit nedeni ekranda yazar.
- AC-06: Given yönetici olmayan bir kullanıcı, when `/admin` adresine gider,
  then yetki uyarısı görür ve yönetim içeriği render edilmez.
- AC-07: Given herhangi bir tema, when `npm run audit:contrast` çalıştırılır,
  then tüm metin çiftleri WCAG AA (4.5:1) ve tüm kontrol kenarları 3:1 eşiğini
  karşılar.
- AC-08: Given klavye kullanıcısı, when `Tab` ile gezinir, then her odaklanan
  öğede görünür odak halkası vardır ve ilk `Tab` içeriğe atlama bağlantısını
  gösterir.
- AC-09: Given `prefers-reduced-motion: reduce`, when arayüz kullanılır, then
  tüm geçiş ve animasyonlar devre dışı kalır.
- AC-10: Given sonuç kümesi 200 satırdan uzun, when ızgara render edilir, then
  ilk 200 satır basılır ve kalanı isteğe bağlı olarak açılır.

## 7. Teknik ve Güvenlik Kısıtları

- Çalışma zamanında hiçbir üçüncü taraf CDN'e istek yapılmaz. Tailwind, yazı
  tipleri ve düzenleyici paket içine alınır; bu, kapalı ağ kurulumları ve
  tedarik zinciri yüzeyi için gereklidir.
- Yetkilendirme, denetim kaydı, risk analizi ve maskeleme davranışı backend'de
  kaldığı gibidir; frontend bunları yalnızca görünür kılar.
- Oturum çerezi davranışı değişmedi (`credentials: 'include'`).
- Üretilen veritabanı parolası yalnızca kayıt yanıtında gösterilir; frontend
  bunu saklamaz, loglamaz veya `localStorage`'a yazmaz.
- `localStorage` yalnızca tema tercihi, aktif yönetim sekmesi ve bölme genişliği
  için kullanılır. Hiçbir kimlik bilgisi veya sorgu içeriği saklanmaz.
- Bilinen açık: `xlsx@0.18.5` npm dağıtımının bilinen güvenlik uyarıları vardır.
  Bu yenilemede sürüm değiştirilmedi; dışa aktarma davranışını bozmamak için
  ayrı bir iş olarak ele alınmalıdır.

## 8. Open Questions

- `OQ-2026-002`: Runtime hedef DB bağlantısında hangi kimlik bilgisi modeli
  kullanılacak? Kullanıcı 2026-08-24'te erteledi. Bu spec'in kapsamı dışında;
  frontend backend davranışına dokunmaz.

## 9. Done Kontrolü

- [x] Acceptance criteria için doğrulama yapıldı (tip kontrolü, kontrast denetimi, tarayıcı üzerinde manuel geçiş)
- [x] İlgili güvenlik ve hata davranışları doğrulandı (401 yönlendirmesi, salt okunur kilit, maskeleme göstergeleri, gizli parola)
- [x] ADR oluşturuldu: `docs/adr/ADR-0010-frontend-design-system.md`
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

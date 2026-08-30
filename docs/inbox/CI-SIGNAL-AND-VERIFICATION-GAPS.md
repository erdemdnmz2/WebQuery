# CI sinyalinin bozuk olduğu ve doğrulamadığı yerler

**Durum:** Inbox / kısmen karar bekliyor
**Kaydedildi:** 2026-08-30
**Kapsam:** `.github/workflows/ci.yml`, `frontend/`, `docs/adr/ADR-0002`
**Kaynak:** 2026-08-30 oturumu; `docs/adr/ADR-0002` ikinci güncellemesi

CI bugün yeşil ve blocking kapıların hepsi gerçekten çalışıyor. Bu kayıt,
kapıların **arkasında** kalan iki sınıfı takip eder: sinyali okunamayan
adımlar, ve hiç doğrulanmayan davranışlar. Kardeş kayıt:
`MSSQL-VERIFICATION-GAP.md` (aynı ikinci sınıfın veritabanı tarafı).

## 1. Üç adım sürekli kırmızı, yani sinyal vermiyor

`ci.yml` içindeki üç `continue-on-error: true` adımı — backend stil lint'i
(`ruff check .`, 34 bulgu), `pip-audit` (16 pakette 75 advisory) ve
`npm audit` (1 high) — eklendiklerinden beri **her** çalışmada exit 1
veriyor.

Sonuç: yeni bir bulgu ile duran backlog GitHub arayüzünde aynı görünüyor.
Adım "kırmızı"dan "kırmızı"ya geçtiği için hiçbir şey değişmiş gibi
durmuyor.

Bunun somut bedeli ölçüldü: `DEPENDENCY-ADVISORY-UPGRADES.md`'nin ilk sürümü
dört paket kaydetmişti, gerçek sayı 16'ydı. Fark bir gün boyunca kimsenin
dikkatini çekmedi, çünkü adım zaten kırmızıydı.

Geçici azaltma uygulandı: beklenen bulgu sayıları `ci.yml` yorumlarına
yazıldı, yani okunacak şey pass/fail değil sayı. Kalıcı çözüm iki seçenekten
biri ve ayrı bir karar:

- Bilinen advisory ID'lerini `pip-audit --ignore-vuln` / `npm audit`
  allowlist'ine alıp adımı blocking yapmak. Yeni bulgu anında kırmızı olur;
  bedeli allowlist bakımı.
- Eşik tabanlı kontrol (bulgu sayısı N'i aşarsa fail). Bakımı ucuz, ama
  "bir advisory kapandı, bir yenisi açıldı" durumunu kaçırır.

Bu adımların ne zaman blocking olacağı `DEPENDENCY-ADVISORY-UPGRADES.md`
8. maddesine bağlı; buradaki seçim ise o gelmeden önce sinyali nasıl
okunur kılacağımız.

## 2. Frontend'in birim testi yok

`frontend` job'ı dört adım çalıştırıyor: `typecheck`, `build`, `audit:api`,
`audit:contrast`. Dördü de yapısal kontrol — hiçbiri bir bileşenin davranışını
çalıştırmıyor. Bir birim test komutu yok ve ADR-0002 bunu bilerek boş
bırakıyor ("suite var olmadan buraya sahte bir adım eklenmeyecek").

Doğrulanmayan yüzey, 2026-08-29/30 oturumlarında eklenen ekranlar da dahil:
erişim yönetimi, parola değiştirme, kayıt yaşam döngüsü, veritabanı yetki
rozeti (SPEC-0002 §7'nin "etkin yetki" hesabı), maskeleme kuralı arayüzü.
Bunların hiçbirinin mantığı test edilmiyor; yalnız derlendiği biliniyor.

Bu bir **iş kalemi değil, henüz bir karar**: suite'in kurulup kurulmayacağı,
kurulacaksa hangi araçla (Vitest, projenin Vite tabanıyla doğal eşleşme) ve
hangi yüzeyden başlanacağı belirlenmedi. Not olarak buraya kaydedildi çünkü
tek başına bir inbox dosyası açmayı hak edecek kadar tanımlı değil.

## 3. `cancel-in-progress` kararı doğrulanmadı

2026-08-30'da iş akışına `concurrency` grubu eklendi
(`cancel-in-progress: true`). Faydası: üzerine commit atılmış çalışmalar
runner'ı sonuna kadar tutmuyor.

Bedeli: bu proje tüm işi tek uzun ömürlü branch'te yürütüyor ve arka arkaya
push yapıldığında aradaki commit'lerin run'ı "cancelled" olarak kapanacak,
yani **her commit'in tamamlanmış bir CI kaydı olmayacak.** Bu, "CI yeşil"
ifadesini bir geçiş kontrolü olarak kullanan bir projede kayda değer bir
takas.

Karar gerektiriyor; seçim yapılmadı. Bu soru `docs/open-questions.md`
içinden kaldırıldı, karar bu kayıtta izleniyor. Şu anki ayar
`cancel-in-progress: true` olarak duruyor.

## İlgili kayıtlar

- `MSSQL-VERIFICATION-GAP.md` — aynı "doğrulanmayan davranış" sınıfının
  veritabanı tarafı; CI yalnız SQLite'a karşı koşuyor.
- `DEPENDENCY-ADVISORY-UPGRADES.md` — 1. maddedeki taramaların içeriği ve
  blocking'e geçme koşulu.

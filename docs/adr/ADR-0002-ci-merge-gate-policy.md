# ADR-0002: CI merge kapısı — pytest blocking, ruff bilgilendirici

## Status

Amended (2026-08-30) — özgün karar korunuyor; ruff'ın `F`/`E9` kuralları
blocking hâle getirildi ve bir frontend job'ı eklendi. Bkz. "2026-08-30
Güncellemesi".

## Context

Blok 0'ın geçiş kontrolü ("CI yeşil ve kırmızı bir test merge'ü engelliyor")
GitHub Actions ile bir CI iş akışı kurulmasını gerektiriyor. Kaynak plan
(`webquery_implementasyon_sirasi.md`, Adım 2 · `4.2`) hem `pytest` hem de
`ruff check web_api/` adımlarını, ikisi de merge'ü bloklayacak şekilde
öngörüyordu.

`ruff check web_api/` mevcut kod tabanına karşı çalıştırıldığında **383 hata**
üretti (204'ü otomatik düzeltilebilir). Bu hatalar bu oturumun kapsamının
tamamen dışında, geçmişten gelen bir birikim. `ruff`'u olduğu gibi blocking
yaparsak:

- İlk CI çalışması, bu adımla hiçbir ilgisi olmayan 383 hata yüzünden kırmızı
  olurdu.
- Bu birikimi düzeltmek (veya geniş bir `--fix` uygulamak) "CI kurulumu"
  adımının kapsamını, ilgisiz yüzlerce dosyayı değiştirecek şekilde
  büyütürdü — `AGENTS.md`'nin "keep the change scoped" ilkesine aykırı.

Aynı şekilde plandaki sır sızıntısı taraması (`grep ... web_api/`) test
fixture'larındaki kasıtlı sahte parolalarla (`db_password="password"`) yanlış
pozitif üretiyordu; bu adım `--exclude-dir=tests` ile düzeltildi ve blocking
bırakıldı çünkü düzeltme sonrası tarama tamamen temiz.

## Decision

CI'da (`.github/workflows/ci.yml`):

- **`pytest`** (blocking): kırmızıysa merge engellenir. Bu, davranış
  doğruluğunun tek kaynağı.
- **`ruff check`** (bilgilendirici, `continue-on-error: true`): sonuç
  raporlanır ama merge'ü bloklamaz. Amaç, yazılan **yeni** kodun kalitesini
  görünür kılmak; geçmiş borcu şimdi zorunlu kılmamak.
- **Sır sızıntısı taraması** (blocking, `tests/` hariç): kaynak kodda
  parola/secret görünümlü sabit değer varsa merge engellenir.
- Python sürümü CI'da `3.11` — `web_api/Dockerfile`'daki (`python:3.11-slim`)
  ile aynı, CI'da geçen bir şeyin farklı bir Python sürümü yüzünden
  production'da farklı davranmasını önlemek için.
- Tetikleyici her `push` ve her `pull_request` — planın önerdiği yalnızca
  `main`/`master` push'u değil. Gerekçe: bu proje tüm 22 adımı tek uzun ömürlü
  branch'te (`feature/security-hardening-implementation`) yürütüyor; PR
  açılana kadar geri bildirim almamak, o branch'te haftalarca kör
  ilerlemek anlamına gelir.

## Rejected Alternatives

### 1. `ruff check` de blocking, mevcut 383 hata bu adımda düzeltilir

En "temiz" sonucu verirdi. Ama kapsamı, ilgisiz yüzlerce satırlık bir
refactor'a genişletir ve bu PR'ın gözden geçirilmesini gereksiz yere
zorlaştırır. Borcu ayrı, kendi başına gözden geçirilebilir bir işe
bırakmak daha güvenli.

### 2. `ruff` tamamen CI'dan çıkarılır

Basit, ama yeni yazılan kodun kalite sinyalini tamamen kaybettirir. Bilgi-
lendirici modda tutmak, ileride "ruff'u ne zaman blocking yapabiliriz"
sorusuna cevap verecek bir trend (azalan/artan hata sayısı) sağlar.

## Consequences

- Merge kararı yalnızca test doğruluğuna bağlı; stil/lint borcunun ayrıca
  ele alınması gerekiyor (bir sonraki adımlarda veya ayrı bir "lint
  temizliği" işi olarak).
- `ruff` çıktısı her CI çalışmasında görünür durumda; 383 sayısının zamanla
  azalıp azalmadığı izlenebilir.
- CI'nin `QUERY_ENCRYPTION_KEY` env değişkeni, `CI_FERNET_KEY` tanımlıysa onu
  kullanır; tanımlı değilse yalnızca ephemeral CI verisi için geçerli bir test
  Fernet anahtarına düşer. Bu anahtar production sırrı değildir. Adım 3
  (`0.1` config guard) sonrasında da CI kendi geçerli test anahtarıyla
  çalışabilir; production ortamı yine kendi gerçek anahtarını sağlamak zorundadır.

## Accepted Risks

- Lint borcu (383 hata) şimdilik CI tarafından zorunlu kılınmıyor; bu, o
  hataların bir kısmının süresiz birikebileceği riski taşır. Azaltma:
  `ruff` çıktısı her çalışmada görünür, sessizce kaybolmuyor.
- `pytest`, testlerin tamamı bittikten ve sonucu yazdıktan **sonra**
  kapanmıyordu — bu ortamda 3 kez tekrarlanan bir davranış. Kaynağı
  `EngineCache`'in arka plan temizlik döngüsü (`engine_cache.py:100`,
  `asyncio.create_task`); `tests/conftest.py`'deki `async_client`
  fixture'ı bunu `DatabaseProvider.start_cache_loop()` ile başlatıyordu ama
  hiçbir yerde iptal etmiyordu. CI job'u fiilen hiç yeşil yanmayacağı
  (her seferinde timeout ile "cancelled" olarak kapanacağı) için bu, bu
  adımın kapsamına alınıp düzeltildi: `async_client` fixture'ı artık
  `finally` bloğunda `db_provider.close_engines()` ve
  `app_db.app_engine.dispose()` çağırıyor — `app.py`'nin kendi lifespan
  shutdown akışıyla aynı desen. Düzeltme sonrası doğrulama: aynı 38
  passed / 2 failed sonucu (regresyon yok) ve process artık ~64 saniyede
  temiz çıkıyor. `timeout-minutes: 15` yine de savunma amaçlı korundu
  (gelecekte benzer bir sızıntı olursa CI sonsuza kadar asılı kalmasın).

## 2026-08-30 Güncellemesi (denetim bulguları P2-15, P2-16)

### Bağlam

Özgün karar, lint borcunun (383 hata) tamamını blocking yapmanın kapsamı
şişireceğini söylüyordu; bu hâlâ doğru. Ancak 2026-08-29 denetimi, o borcun
içinde **gerçek bir hata** buldu: `static_files/router.py` içinde üç `F821`
(tanımsız `get_current_user`). Modül `app.py`'de yorum satırındaydı, yani
import edilse `NameError` verecekti. Bilgilendirici lint bunu her çalışmada
raporladı ama kimse durmadı.

Ayrıca frontend için hiçbir CI job'ı yoktu: `typecheck`, `build`, `audit:api`
ve `audit:contrast` yalnızca yerelde çalışıyordu.

### Karar

1. **`ruff check --select F,E9` blocking.** `F` (pyflakes) ve `E9`
   (sözdizimi/IO hataları) stil değil, doğruluk kurallarıdır: tanımsız isim,
   taşınmış bir sembolü gizleyen kullanılmayan import, ayrıştırılamayan dosya.
   Bu seçim bugün temiz (`static_files` P2-12 ile kaldırıldıktan sonra), yani
   kapı hiçbir birikmiş borcu merge önüne koymuyor.
2. **`ruff check .` (tüm kurallar) bilgilendirici kalıyor.** Kalan 34 bulgu
   `BLE001`, `SIM117` ve bir `B017`; hepsi stil/desen borcu.
3. **Yeni `frontend` job'ı, dört adımı da blocking:** `npm run typecheck`,
   `npm run build`, `npm run audit:api`, `npm run audit:contrast`. Dördü de
   bugün yeşil, dolayısıyla kapı yapmanın anlık maliyeti yok. `audit:api`
   özellikle değerli: denetimin tekrar tekrar bulduğu frontend↔backend
   sözleşme kayması sınıfını yakalıyor. Frontend'in henüz bir birim test
   komutu yok; suite var olmadan buraya sahte bir adım eklenmeyecek.
4. **Bağımlılık taraması (`pip-audit`, `npm audit --audit-level=high`)
   eklendi ama `continue-on-error: true`.** Gerekçe: açık bulgular sürüm
   yükseltmesi gerektiriyor (`aiohttp` 3.9.5, `httpx` 0.24.1) ve `xlsx`
   (SheetJS 0.18.5) upstream npm'i terk ettiği için kütüphane değişimi
   istiyor. Bunlar kendi doğrulama turlarını hak eden işler; tamamlanmadan
   kapı yapmak, ilgisiz her değişikliğin önüne kırmızı CI koyardı.

### Kabul edilen riskler (güncel)

- Bağımlılık taraması bilgilendirici olduğu sürece bilinen açıklar merge'ü
  engellemez. Azaltma: çıktı her çalışmada görünür ve yükseltme işi ayrı bir
  kalem olarak izleniyor.
- Testler hâlâ yalnız SQLite'a karşı çalışıyor. MSSQL'e özgü davranış
  (`NVARCHAR`, `DATETIME2`, `UNIQUEIDENTIFIER`, statement timeout, satır
  değerli `IN` desteğinin yokluğu) CI'da doğrulanmıyor. Bu, denetimin de
  işaret ettiği kalıcı boşluk; MSSQL servis konteynerli bir nightly job
  ayrı bir karar olarak duruyor ve bu güncellemeyle kapatılmadı.

## References

- Spec: yok — operasyonel tooling kararı.
- Kaynak plan: `webquery_implementasyon_sirasi.md`, Adım 2 (`4.2`).
- Denetim: `webquery_denetim_raporu.md` P2-15, P2-16.
- Supersedes / Superseded by: yok.

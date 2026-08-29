# Bilinen açığı olan bağımlılıkların yükseltilmesi

**Durum:** Inbox / uygulanacak iş
**Kaydedildi:** 2026-08-30
**Kapsam:** `web_api/requirements.txt`, `frontend/package.json`,
`.github/workflows/ci.yml`
**Kaynak:** `webquery_denetim_raporu.md` P2-15

Denetim, dört bağımlılıkta bilinen açık ya da bakımsızlık tespit etti.
2026-08-30 düzeltmesinde **taramaları CI'ya ekledim ama paketleri
yükseltmedim**; her biri kendi doğrulama turunu gerektiriyor ve
`aiohttp`/`httpx` yükseltmesini denetim düzeltmesinin içine sıkıştırmak,
zaten 116 dosyalık olan inceleme yüzeyini davranış değiştiren bir bağımlılık
sıçramasıyla büyütürdü.

Yani **bu açıklar hâlâ açık.** CI onları her çalışmada raporluyor
(`pip-audit`, `npm audit --audit-level=high`) ama `continue-on-error: true`
olduğu için merge'ü engellemiyor. Bu bilinçli bir ara durumdur ve ADR-0002'nin
2026-08-30 güncellemesinde kabul edilmiş risk olarak kayıtlıdır.

## Kalemler

| Paket | Pinlenen sürüm | Yer | Not |
| --- | --- | --- | --- |
| `aiohttp` | 3.9.5 | `requirements.txt:82` | Sonraki sürümlerde giderilmiş request smuggling ve static route traversal kayıtları var. Doğrudan kullanılmıyor; Slack Bolt'un `AsyncApp`'i üzerinden geliyor |
| `httpx` | 0.24.1 | `requirements.txt:68` | 2023 sürümü, iki majör geride. `NotificationService` ve testler kullanıyor |
| `python-jose` | 3.5.0 | `requirements.txt:40` | Bilinen CVE'ler bu sürümde kapalı ama proje fiilen bakımsız. Denetimin önerisi `PyJWT`'ye geçiş |
| `xlsx` (SheetJS) | ^0.18.5 | `package.json:33` | npm'deki bu sürüm için prototype pollution / ReDoS kayıtları var. **Upstream npm'i terk etti**, yani sürüm yükseltmesiyle çözülmez |

## Neden her biri ayrı iş

**`aiohttp`** — Slack Bolt'un bağımlılığı. Yükseltme, Bolt'un desteklediği
aralıkla uyum kontrolü ister. Slack onay akışı (socket mode listener) bu
kütüphanenin üstünde çalışıyor ve entegrasyon testleri mock'lu, yani gerçek
bir bağlantı regresyonunu yakalamazlar. Manuel bir socket-mode doğrulaması
gerekir.

**`httpx`** — 0.24 → güncel arasında `AsyncClient` API'sinde kırıcı
değişiklikler var (`app=` parametresinin kaldırılması gibi).
`web_api/tests/conftest.py` `ASGITransport` kullanıyor, dolayısıyla test
tarafı muhtemelen uyumlu; `NotificationService._send_message_to_slack`
ayrıca kontrol edilmeli.

**`python-jose` → `PyJWT`** — Bu bir kütüphane değişimi, yükseltme değil.
Dokunacağı yerler: `authentication/sessions.py` (`mint_access`, doğrulama),
`middlewares/auth_middleware.py`, `authentication/router.py`. Token formatı
değişmez (HS256, aynı claim'ler) ama hata tipleri değişir
(`jose.JWTError` → `jwt.PyJWTError`) ve bunlar oturum doğrulama yolunda
yakalanıyor. **Güvenlik-hassas alan**: `docs/ai/playbooks/change-review.md`
uygulanmalı.

**`xlsx`** — Alternatif değerlendirmesi gerekiyor (`exceljs` denetimin
önerisi). Kullanım yüzeyi dar: sonuç kümesinin Excel'e aktarımı. Önce
`frontend/` içinde gerçek kullanım noktalarının çıkarılması, sonra API
eşleşmesi. Bundle boyutu da bir kriter — mevcut `xlsx` chunk'ı 429 kB.

## İş kalemleri

Sırasız; her biri bağımsız teslim edilebilir.

1. `httpx` yükselt. En düşük riskli olan; testler yakalar.
2. `aiohttp` yükselt + manuel socket-mode doğrulaması.
3. `xlsx` yerine bakımlı bir alternatif; frontend `build` ve manuel dışa
   aktarım doğrulaması.
4. `python-jose` → `PyJWT`. Spec gerekmez (token sözleşmesi değişmiyor) ama
   change-review playbook'u ve oturum testlerinin tamamı çalıştırılmalı.
5. Dördü de bittiğinde `.github/workflows/ci.yml` içindeki iki
   `continue-on-error: true` kaldırılıp taramalar merge kapısı yapılır ve
   ADR-0002'nin kabul edilen riski güncellenir.

## Teslim kontrolü

- Her yükseltmeden sonra `web_api/` dizininden `pytest`.
- Frontend değişiminde `frontend/` dizininden `npm run typecheck` ve
  `npm run build`.
- `pip-audit -r web_api/requirements.txt` ve `npm audit --audit-level=high`
  çıktısındaki bulgu sayısının azaldığı raporlanır.
- 5. madde ADR-0002'yi güncellediği için o adımda ADR düzenlenir.

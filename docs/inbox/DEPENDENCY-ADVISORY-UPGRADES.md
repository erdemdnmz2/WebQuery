# Bilinen açığı olan bağımlılıkların yükseltilmesi

**Durum:** Inbox / uygulanacak iş
**Kaydedildi:** 2026-08-30
**Güncellendi:** 2026-08-30 (CI çıktısı okunarak; ilk sürüm eksikti — aşağıya bkz.)
**Kapsam:** `web_api/requirements.txt`, `frontend/package.json`,
`.github/workflows/ci.yml`
**Kaynak:** `webquery_denetim_raporu.md` P2-15 + CI run 33280496747 tarama
çıktısı

## Bu notun ilk sürümü yanlıştı

İlk sürüm dört paket sayıyordu (`aiohttp`, `httpx`, `python-jose`, `xlsx`) ve
bunları denetim raporundan almıştı. Taramaları CI'ya ekledikten sonra çıktının
kendisi hiç okunmamıştı. Okununca tablo şu:

- `pip-audit`, **16 pakette 75 ayrı advisory** raporluyor (pip-audit 85 satır
  yazıyor; bazı advisory'ler alias başına tekrar ediyor).
- Bu 16 paketin **13'ü ilk sürümde hiç geçmiyordu**.
- Denetimin öne çıkardığı iki paket, `httpx` 0.24.1 ve `python-jose` 3.5.0,
  `pip-audit` çıktısında **yok**. İkisi de açık advisory taşımıyor; denetim
  onları bayatlık/bakımsızlık gerekçesiyle işaretlemişti. Bu geçerli bir
  gerekçe ama farklı bir gerekçe, ve bu notta öyle işaretlenmeleri gerekiyordu.

Yani sorun ilk sürümün kaydettiğinden büyük, ve önceliklendirmesi farklı.

## Backend: `pip-audit -r web_api/requirements.txt`

2026-08-29 CI çalışmasından (Python 3.11), advisory sayısına göre:

| Paket | Pin | Advisory | En düşük düzeltme | Not |
| --- | --- | --- | --- | --- |
| `aiohttp` | 3.9.5 | 34 | 3.14.3 | Tek başına toplamın yarısı. Doğrudan kullanılmıyor; Slack Bolt `AsyncApp` üzerinden geliyor |
| `cryptography` | 45.0.5 | 7 | 50.0.0 | Beş majör geride. `EncryptedText` ve Fernet yolu bunun üstünde |
| `starlette` | 0.47.1 | 7 | 0.47.2 | En düşük düzeltme yama seviyesinde; `fastapi==0.116.1`'in aralığı içinde |
| `python-multipart` | 0.0.20 | 6 | 0.0.31 | FastAPI form/upload ayrıştırması |
| `pyasn1` | 0.6.1 | 5 | 0.6.4 | `python-jose` bağımlılığı |
| `urllib3` | 2.5.0 | 4 | 2.7.0 | `requests` bağımlılığı |
| `ecdsa` | 0.19.1 | 2 | 0.19.2 | Biri için düzeltme yok; `python-jose` bağımlılığı |
| `requests` | 2.32.3 | 2 | 2.33.0 | |
| `aiomysql` | 0.2.0 | 1 | 0.3.0 | Minör atlama; MySQL sürücüsü |
| `click` | 8.2.1 | 1 | 8.3.3 | |
| `h11` | 0.14.0 | 1 | 0.16.0 | **Pinlenmemiş.** `httpx` 0.24.1 → `httpcore` → `h11<0.15` zinciri 0.14'e sabitliyor |
| `idna` | 3.10 | 1 | 3.15 | |
| `pymysql` | 1.1.0 | 1 | 1.1.1 | |
| `pytest` | 8.1.1 | 1 | 9.0.3 | Yalnız test bağımlılığı; `pytest-asyncio` 0.23.6 uyumu kontrol edilmeli |
| `python-dotenv` | 1.0.1 | 1 | 1.2.2 | |
| `setuptools` | 80.9.0 | 1 | 83.0.0 | Yalnız build |

Advisory taşımayan ama denetimin ayrıca işaretlediği iki kalem:

| Paket | Pin | Gerekçe |
| --- | --- | --- |
| `httpx` | 0.24.1 | Açık advisory yok. İki majör geride ve `h11` 0.14'ü aşağıda tutan zincirin başı — yani bu yükseltme başka bir advisory'yi de kapatıyor |
| `python-jose` | 3.5.0 | Açık advisory yok; bilinen CVE'ler bu sürümde kapalı. Proje fiilen bakımsız. Denetimin önerisi `PyJWT`'ye geçiş |

## Frontend: `npm audit --audit-level=high`

2026-08-30'da dört paket high seviyesinde raporlanıyordu. Üçü aralık içinde
yama sürümüydü ve o gün lockfile'a alındı (`package.json` değişmedi):

| Paket | Değişim | Durum |
| --- | --- | --- |
| `react-router` / `react-router-dom` | 7.18.0 → 7.18.3 | Kapandı |
| `postcss` | 8.5.15 → 8.5.26 | Kapandı (Vite zinciri, geçişli) |
| `nanoid` | 3.3.15 → 3.3.18 | Kapandı (Vite zinciri, geçişli) |
| `xlsx` (SheetJS) | ^0.18.5 | **Açık.** Upstream npm'i terk etti; düzeltme sürümü yok |

Doğrulama: temiz `npm ci` sonrası `typecheck`, `build`, `audit:api`,
`audit:contrast` dördü de geçti. `npm audit` 5 high → 1 high.

## Neden her biri ayrı iş

**`aiohttp`** — Slack Bolt'un bağımlılığı, ve tek başına listenin yarısı.
Yükseltme Bolt'un desteklediği aralıkla uyum kontrolü ister. Slack onay akışı
(socket mode listener) bu kütüphanenin üstünde çalışıyor ve entegrasyon
testleri mock'lu, yani gerçek bir bağlantı regresyonunu yakalamazlar. Manuel
bir socket-mode doğrulaması gerekir.

**`cryptography`** — 45 → 50 beş majör. `EncryptedText` ve query encryption
yolu bunun üstünde çalışıyor, yani bir regresyon doğrudan saklanan credential
okunabilirliğini vurur. **Güvenlik-hassas**: `docs/ai/playbooks/change-review.md`.
Yükseltme öncesi mevcut şifreli verinin okunabilirliğinin doğrulanması şart.

**`httpx`** — 0.24 → güncel arasında `AsyncClient` API'sinde kırıcı
değişiklikler var (`app=` parametresinin kaldırılması gibi).
`web_api/tests/conftest.py` `ASGITransport` kullanıyor, dolayısıyla test
tarafı muhtemelen uyumlu; `NotificationService._send_message_to_slack`
ayrıca kontrol edilmeli. `h11` advisory'sini de bu kapatıyor.

**`python-jose` → `PyJWT`** — Bu bir kütüphane değişimi, yükseltme değil.
Dokunacağı yerler: `authentication/sessions.py` (`mint_access`, doğrulama),
`middlewares/auth_middleware.py`, `authentication/router.py`. Token formatı
değişmez (HS256, aynı claim'ler) ama hata tipleri değişir
(`jose.JWTError` → `jwt.PyJWTError`) ve bunlar oturum doğrulama yolunda
yakalanıyor. `pyasn1` ve `ecdsa` yalnız `python-jose` için var, yani bu geçiş
o iki paketi bağımlılık ağacından tamamen çıkarır ve 7 advisory daha kapanır.
**Güvenlik-hassas**: `docs/ai/playbooks/change-review.md` uygulanmalı.

**`xlsx`** — Alternatif değerlendirmesi gerekiyor (`exceljs` denetimin
önerisi). Kullanım yüzeyi dar: sonuç kümesinin Excel'e aktarımı. Önce
`frontend/` içinde gerçek kullanım noktalarının çıkarılması, sonra API
eşleşmesi. Bundle boyutu da bir kriter — mevcut `xlsx` chunk'ı 429 kB.

**Kalan yama seviyesi kalemler** (`starlette`, `python-multipart`, `urllib3`,
`requests`, `idna`, `pymysql`, `click`, `python-dotenv`, `setuptools`,
`ecdsa`) — hepsinin en düşük düzeltmesi aynı majör içinde. Tek bir iş olarak
alınabilirler; doğrulaması `web_api/` içinden `pytest`. `starlette`'in
`fastapi==0.116.1` ile uyumlu kalması tek dikkat noktası.

**`aiomysql` 0.2.0 → 0.3.0** ve **`pytest` 8 → 9** ayrı: ilki sürücü minör
atlaması, ikincisi `pytest-asyncio` 0.23.6 ile uyum sorusu doğuruyor.

## İş kalemleri

Sırasız; her biri bağımsız teslim edilebilir. Parantez içi rakam kapanacak
advisory sayısı.

1. Yama seviyesi toplu yükseltme: `starlette`, `python-multipart`, `urllib3`,
   `requests`, `idna`, `pymysql`, `click`, `python-dotenv`, `setuptools`,
   `ecdsa` (24). En düşük riskli; testler yakalar.
2. `httpx` yükselt — `h11`'i de kapatır (1).
3. `aiohttp` yükselt + manuel socket-mode doğrulaması (34).
4. `cryptography` yükselt + şifreli veri okunabilirliği doğrulaması (7).
5. `python-jose` → `PyJWT`; `pyasn1` ve `ecdsa` ağaçtan düşer (5+).
6. `aiomysql` 0.3.0; `pytest` 9 + `pytest-asyncio` uyumu (2).
7. `xlsx` yerine bakımlı bir alternatif; frontend `build` ve manuel dışa
   aktarım doğrulaması.
8. Backend sıfırlandığında `.github/workflows/ci.yml` içindeki `pip-audit`
   `continue-on-error: true` kalkar. `npm audit` için aynı şey 7. maddeye
   bağlı. ADR-0002'nin kabul edilen riski o adımda güncellenir.

## Taramanın kendisiyle ilgili bilinen sorun

Üç `continue-on-error` adımı da (backend stil lint, `pip-audit`, `npm audit`)
eklendiklerinden beri **her çalışmada** kırmızı. Yani yeni bir advisory ile
duran backlog CI arayüzünde birbirinden ayırt edilemiyor; sinyal yalnız
sayıyı okuyan birine görünür. Bu notun ilk sürümünün yanlış olması tam olarak
bu yüzden fark edilmedi.

İki çözüm var, ikisi de ayrı bir karar: bilinen ID'leri `--ignore-vuln` ile
allowlist'e alıp adımı blocking yapmak (yeni advisory anında kırmızı olur,
ama allowlist bakım ister), ya da eşik tabanlı bir kontrol yazmak. Şimdilik
`ci.yml` yorumları beklenen sayıyı kaydediyor.

## Teslim kontrolü

- Her yükseltmeden sonra `web_api/` dizininden `pytest`.
- Frontend değişiminde `frontend/` dizininden temiz `npm ci`, ardından
  `npm run typecheck` ve `npm run build`.
- `pip-audit -r web_api/requirements.txt` ve `npm audit --audit-level=high`
  çıktısındaki bulgu sayısının azaldığı, yukarıdaki tablo güncellenerek
  raporlanır.
- 8. madde ADR-0002'yi güncellediği için o adımda ADR düzenlenir.

## İlgili kayıtlar

- Yükseltmelerin GCP denemesinden önce nereye kadar yapılacağı **OQ-2026-021**
  ile karar bekliyor; bağlam `GCP-STAGING-DEPLOYMENT-READINESS.md`.
- Taramaların sinyal vermemesi `CI-SIGNAL-AND-VERIFICATION-GAPS.md` §1'de.

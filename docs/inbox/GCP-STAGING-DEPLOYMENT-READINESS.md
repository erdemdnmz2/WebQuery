# GCP staging denemesi öncesi kapatılması gerekenler

**Durum:** Inbox / deploy öncesi bloklayıcı
**Kaydedildi:** 2026-08-30
**Kapsam:** `nginx.conf`, `docker-compose.yml`, `frontend/Dockerfile`,
`web_api/common/config_guard.py`, `web_api/authentication/router.py`
**Kaynak:** 2026-08-30 oturumu; hafta içi planlanan GCP test dağıtımı

Bu kayıt, WebQuery'nin ilk kez yerel makine dışında çalıştırılacak olmasından
doğuyor. Aşağıdaki birinci madde **bloklayıcı**: kapatılmadan yapılan bir GCP
denemesi, hatası görünmeyen bir biçimde başarısız olur.

## 1. TLS olmadan oturum açılamaz (bloklayıcı)

İki mekanizma birlikte bir çıkmaz üretiyor:

- `common/config_guard.py:98` — `DEBUG=false` (üretim modu) iken
  `COOKIE_SECURE=true` değilse uygulama **açılmıyor**.
- `authentication/router.py` içindeki altı `set_cookie` çağrısı ve
  `middlewares/auth_middleware.py:118`, access ve refresh çerezlerini
  `secure=COOKIE_SECURE` ile işaretliyor.
- `nginx.conf`'ta aktif tek server bloğu `listen 80`; TLS bloğu yorum
  satırında ve `docker-compose.yml` yalnız `80:80` yayımlıyor.

Yani üretim modunda çerezler `Secure` işaretli çıkıyor ama taşıma düz HTTP.
Tarayıcı `Secure` çerezi HTTPS olmayan bir origin'de saklamaz — `localhost`
istisnadır, bir GCP VM'inin public IP'si değildir.

**Görünen davranış:** `POST /api/login` `200` döner, kullanıcı giriş yapmış
görünür, sonraki her istek kimliksiz gider. Hiçbir yerde hata logu oluşmaz.
Bu yüzden bloklayıcı olarak işaretlendi: sessiz başarısızlık.

**`DEBUG=true` ile atlatmak çözüm değil.** O durumda `app.py:292`
`reload=debug` üzerinden uvicorn auto-reload'a geçer ve bulutta geliştirme
modunda çalışırsınız; ayrıca çerezler düz HTTP üzerinde korumasız gider —
`config_guard`'ın engellemek için var olduğu şey tam olarak budur.

Karar gerektiriyor; seçim yapılmadı. Bu soru `docs/open-questions.md`
içinden kaldırıldı, karar bu kayıtta izleniyor.

Hangi seçenek seçilirse seçilsin, TLS compose ağının **dışında**
sonlandırıldığı sürece `TRUSTED_PROXY_IPS=172.16.0.0/12` doğru kalır, çünkü
`web`'in doğrudan komşusu hâlâ `nginx`. Sonlandırmayı nginx'in kendisine
almak (yorumdaki 443 bloğu) compose'da `443` publish'i ve sertifika mount'u
da gerektirir.

## 2. `frontend` imajı hiç build edilmedi

2026-08-30'da `frontend/Dockerfile` iki noktada değişti: `npm install` →
`npm ci` (imaj artık lockfile'ı birebir kuruyor; öncesinde her caret
aralığını build anında yeniden çözüyordu) ve `node:20-alpine` →
`node:24-alpine`.

Bu değişiklik **gerçek bir build'den geçmedi** — o oturumda Docker daemon
erişilebilir değildi. Dolaylı kanıt güçlü ama yeterli değil:

- Temiz `npm ci` yerelde çalıştı, `package.json` ↔ lockfile senkron.
- `frontend/.dockerignore` `node_modules` ve `dist`'i dışlıyor, yani
  `COPY . .` konteynerdeki kurulumu host binary'leriyle ezmiyor.
- Kurulu 193 paketin hiçbirinde Node 24'ü dışlayan `engines` kısıtı yok.

GCP denemesi bu imajı build edeceği için doğrulama orada değil, önceden
yapılmalı: `make build`.

## 3. `TRUSTED_PROXY_IPS` varsayılanı ilk kez gerçek bir ağda çalışacak

`docs/inbox/TRUSTED-PROXY-SUBNET-VERIFICATION.md` bu değerin bir **tahmin**
olduğunu ve deploy öncesi doğrulanması gerektiğini zaten kaydediyor. GCP
denemesi o kaydın tetiklendiği andır; doğrulama komutları o dosyada.

İki yönde de sessiz başarısızlık: fazla geniş liste `X-Forwarded-For`
sahteciliğine izin verir, eşleşmeyen liste tüm istekleri tek IP'ye toplar ve
per-IP throttle bütün platformu tek kovaya sokar.

## 4. Makine boyutu

`db` servisi `mcr.microsoft.com/mssql/server:2022-latest`. Microsoft'un
belgelenen minimumu 2 GB RAM; konteyner altında kalırsa açılmadan çıkar.
`web`, `redis`, `frontend` ve `nginx` de aynı VM'de olacağı için en az 4 GB
(GCP'de `e2-medium` ya da üstü) seçilmeli. `e2-micro`/`e2-small` yeterli
değil.

## 5. Dağıtım komutu

2026-08-30'da compose dosyalarının varsayılanı değişti (OQ-2026-015
düzeltmesi): `docker compose up` artık üretim-güvenli tabanı çözüyor,
geliştirme kolaylıkları `docker-compose.dev.yml` içinde ve otomatik
yüklenmiyor. GCP'de bayraksız komut doğru olandır.

Deploy öncesi `make prod-config` çalıştırılmalı; çıktı yayımlanmış tek port
olarak `80` ve `nginx.conf` dışında bind mount olmadığını göstermeli.

## Deploy öncesi kontrol listesi

- [ ] TLS sonlandırma seçildi (madde 1) ve kuruldu; `https://` üzerinden
      login sonrası ikinci bir isteğin kimlikli gittiği doğrulandı
- [ ] `make build` yerelde geçti (madde 2)
- [ ] `TRUSTED-PROXY-SUBNET-VERIFICATION.md` komutları GCP'de çalıştırıldı
- [ ] VM ≥ 4 GB RAM
- [ ] `make prod-config` çıktısı tek `80` portu ve bind mount yokluğu gösteriyor
- [ ] `.env` sunucuda yeniden üretildi; `SECRET_KEY` ve
      `QUERY_ENCRYPTION_KEY` yerel değerlerden farklı

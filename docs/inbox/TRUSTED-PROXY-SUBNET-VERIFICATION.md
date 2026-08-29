# `TRUSTED_PROXY_IPS` varsayılanı doğrulanmadı

**Durum:** Inbox / deploy öncesi doğrulanmalı
**Kaydedildi:** 2026-08-30
**Kapsam:** `docker-compose.yml:22`, `docker-compose.override.yml`,
`web_api/middlewares/proxy_middleware.py`
**Kaynak:** `webquery_denetim_raporu.md` P0-4 düzeltmesinin artık riski;
`docs/specs/SPEC-0026-deployment-hardening.md` §10

P0-4 düzeltmesi, gerçek istemci IP'sini `X-Forwarded-For` başlığından
**yalnız doğrudan bağlanan eş `TRUSTED_PROXY_IPS` içindeyse** okuyor. Mekanizma
doğru; sorun listenin kendisinde.

`docker-compose.yml` şu değeri taşıyor:

```yaml
- TRUSTED_PROXY_IPS=${TRUSTED_PROXY_IPS:-172.16.0.0/12}
```

Bu **tahmindir.** Docker'ın tipik bridge aralığına dayanıyor, bu compose
projesinin gerçek subnet'ine göre doğrulanmadı. Compose, dosyada açıkça
sabitlenmedikçe proje başına subnet atar; dolayısıyla değer bir ortamda tutar,
diğerinde tutmaz.

## Yanlış olursa ne olur

İki yönde de sessiz başarısızlık:

**Aralık dar / yanlış (nginx bu CIDR'ın dışında kalırsa).** Başlık hiç
okunmaz, her istek nginx'in IP'sinden geliyormuş gibi görünür. Bu tam olarak
P0-4'ün düzeltmeye çalıştığı durumdur: rate limit ve login throttle tüm
platform için tek kovaya bağlanır, bir kullanıcı herkesin giriş hakkını
tüketebilir. **Düzeltme uygulanmış görünür ama çalışmaz.**

**Aralık gereğinden geniş.** Güvenilen aralıktaki herhangi bir konteyner
`X-Forwarded-For` uydurabilir ve kendini başka bir IP olarak gösterip
throttle'ı atlayabilir.

Hiçbiri log üretmez; ikisi de ancak aranırsa görülür.

## Yapılacak

1. Projeyi ayağa kaldır ve gerçek aralığı oku:

   ```bash
   docker compose up -d
   docker network inspect $(docker compose ps --format '{{.Name}}' | head -1 | xargs docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}') \
     -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
   ```

   Ya da doğrudan `web` konteynerinden nginx'in görünen adresini kontrol et.

2. İki seçenekten birini uygula:

   - **A (önerilen):** compose dosyasında subnet'i sabitle, böylece değer
     tahmin olmaktan çıkar:

     ```yaml
     networks:
       default:
         ipam:
           config:
             - subnet: 172.28.0.0/16
     ```

     ve `TRUSTED_PROXY_IPS` varsayılanını bu değere eşitle.

   - **B:** varsayılanı kaldır (`${TRUSTED_PROXY_IPS}`), böylece ayar
     verilmediğinde liste boş kalır ve middleware fail-closed davranır —
     hiçbir başlık okunmaz. Bu güvenli ama sessiz: dağıtım ayarı unutursa
     P0-4 düzeltmesi devre dışı kalır ve kimse fark etmez.

   A tercih edilmeli; B yalnız subnet sabitlenemiyorsa.

3. Doğrulamayı gerçekten yap: nginx üzerinden iki farklı istemci IP'siyle
   login dene, `AuditLog.client_ip` değerlerinin farklı olduğunu gör.
   `LOGIN_MAX_FAILURES` bir IP için dolarken diğerinin etkilenmediğini
   doğrula. Bu, düzeltmenin çalıştığının tek gerçek kanıtıdır; birim testi
   (`tests/unit/test_trusted_proxy.py`) mekanizmayı doğruluyor, dağıtımdaki
   aralığı değil.

4. Üretim (compose dışı) dağıtımı için aynı soru ayrıca cevaplanmalı:
   `TRUSTED_PROXY_IPS` oradaki load balancer / ingress aralığını içermeli.

## Not

`docker-compose.override.yml` bu değeri bilinçli olarak boşaltıyor: yerelde
`web`'e çoğu zaman nginx üzerinden değil doğrudan (curl, tarayıcı) gidiliyor,
yani isteğin eşi bir compose servisi olmuyor. Yerel davranış bu kaydın
kapsamı dışında; sorun yalnız üretim tabanındaki değerdedir.

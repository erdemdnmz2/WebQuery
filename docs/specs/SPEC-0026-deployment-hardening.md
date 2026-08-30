# Mini-Spec: Dağıtım yapılandırmasının sertleştirilmesi

## 1. Spec Kartı

- Özellik: Üretim-güvenli Compose tabanı, geliştirme kolaylıklarının ayrı ve
  otomatik yüklenmeyen bir dosyaya taşınması, imaj ve nginx sertleştirmesi
- Durum: Implemented
- Versiyon: 2026-08-30
- Tarih: 2026-08-30
- Sahip: WebQuery platform ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Tek bir `docker-compose.yml`, hem yerel geliştirmeyi hem de dağıtımı
tanımlıyordu. İçindeki iki geliştirme kolaylığı üretimde doğrudan risk
üretiyordu:

- `./web_api:/app` bind mount, build edilen imajın değişmezliğini bozuyordu:
  çalışan kod, test edilen kod değildi.
- `1433:1433` publish, veritabanını host ağına ve oradan erişilebilen her
  yere açıyordu.

Ayrıca uygulama konteyner içinde `root` olarak çalışıyor ve nginx hiçbir
güvenlik başlığı ya da istek limiti uygulamıyordu.

### Başarı Sinyali

- `docker compose up` — bayraksız, yani bir dağıtımın yazacağı komut — bind
  mount ve yayımlanmış veritabanı portu olmadan çalışır.
- `make up` (taban + `docker-compose.dev.yml`) yerel akışı değiştirmeden
  çalışmaya devam eder.
- Konteyner içinde uygulama süreci `root` değildir.
- `DEBUG=false` ile `COOKIE_SECURE=true` olmadan uygulama açılmaz.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `docker-compose.yml`: bind mount ve `web`/`db` host port publish'lerinin
  kaldırılması, `TRUSTED_PROXY_IPS` tanımı, `DB_USER` için sessiz `sa`
  fallback'inin kaldırılması.
- `docker-compose.dev.yml`: bind mount, `web` ve `db` port publish'leri,
  gevşetilmiş `TRUSTED_PROXY_IPS`.
- `web_api/Dockerfile`: root olmayan kullanıcı.
- `nginx.conf`: güvenlik başlıkları, `/api/login` ve `/api` için
  `limit_req` bölgeleri, yorum satırı hâlinde TLS server-block şablonu.
- `common/config_guard.py`: `DEBUG=false` iken `COOKIE_SECURE=true`
  zorunluluğu.
- `web_api/wait_for_db.py`: gerçek "SQL Server ayakta mı" yoklaması ve
  doğru çıkış kodu; `create_db.py`'nin her istisnayı yutmayı bırakması.

### Kapsam Dışı

- Gerçek bir TLS sertifikası ve onunla çalışan bir server-block. Sertifika
  bu depoda bulunmadığı için şablon yorum satırı olarak bırakıldı.
- Kubernetes/Swarm manifestleri.
- Görüntü tarama (image scanning) ve imzalama.

## 4. Sözleşme

Compose dosyaları, çalıştırma biçimine göre iki farklı topoloji üretir:

| Komut | Sonuç |
| --- | --- |
| `docker compose up` | Yalnız taban. Bind mount yok, `web`/`db` host portu yok; tek giriş nginx. **Varsayılan bu.** |
| `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` (veya `make up`) | Taban + geliştirme. Kod bind mount'lu, `web` ve `db` host'tan erişilebilir. |

2026-08-30 düzeltmesi: dosya `docker-compose.override.yml` adıyla otomatik
yükleniyordu, yani yukarıdaki iki satır terstiydi — kısa komut geliştirme
topolojisini veriyordu. `docker-compose.dev.yml` adı otomatik yüklemeyi
kaldırıyor. Doğrulama komutu: `make prod-config`, yayımlanmış tek port `80`
ve `nginx.conf` dışında bind mount olmadığını göstermeli.

Yeni ortam değişkeni: `TRUSTED_PROXY_IPS` (virgülle ayrılmış CIDR listesi).
Boş bırakılırsa hiçbir `X-Forwarded-For` başlığı okunmaz.

## 5. İş Kuralları

### BR-01: Taban dosya üretim varsayılanıdır

`docker-compose.yml` hiçbir geliştirme kolaylığı içermez. Yeni bir kolaylık
`docker-compose.dev.yml` dosyasına eklenir; taban dosyaya değil.

### BR-02: Geliştirme dosyası yalnız erişilebilirlik ve iterasyon hızını değiştirir

`docker-compose.dev.yml` uygulama **davranışını** değiştiren hiçbir ayar içermez.
Yerelde geçen bir davranış, üretimde de aynı olmalıdır.

### BR-03: `DB_USER` sessizce `sa` olmaz

`DB_USER` tanımsızsa Compose değişkeni boş kalır ve `config_guard` açılışta
durdurur. Eskiden `${DB_USER:-sa}` fallback'i, ayarı unutan bir dağıtımı
sessizce en yetkili hesapla çalıştırıyordu.

### BR-04: Üretimde güvenli çerez zorunlu

`DEBUG=false` iken `COOKIE_SECURE` değeri `true` değilse
`verify_startup_config` uygulamayı başlatmaz.

### BR-05: Uygulama root olarak çalışmaz

`web_api/Dockerfile` ayrı bir kullanıcı oluşturur ve süreç o kullanıcıyla
çalışır.

## 6. Acceptance Criteria

- AC-01: Given hiçbir bayrak verilmemiş, when `docker compose config`
  çalıştırılır, then `web` servisinde `volumes` ve host `ports` yoktur —
  yani taban dosya varsayılan olarak çözülür.
- AC-02: Given yalnız `docker-compose.yml`, when yapılandırma incelenir,
  then `db` servisi host'a port yayımlamaz.
- AC-03: Given `-f docker-compose.yml -f docker-compose.dev.yml` (veya
  `make up`), when yapılandırma çözülür, then bind mount ve `1433` publish
  geri gelir.
- AC-07: Given `docker-compose.dev.yml` diskte duruyor, when bayraksız
  `docker compose config` çalıştırılır, then çıktıda `1433` ve `./web_api`
  bind mount **yoktur** — dosya adı otomatik yüklenmeyi engellemelidir.
- AC-04: Given `DEBUG=false` ve `COOKIE_SECURE=false`, when uygulama
  başlatılır, then `SystemExit(1)` ile durur ve neden loglanır.
- AC-05: Given `DB_USER` tanımsız, when uygulama başlatılır, then
  `config_guard` eksik değişkeni raporlayarak durdurur.
- AC-06: Given veritabanı henüz ayakta değil, when `entrypoint.sh` çalışır,
  then `wait_for_db.py` başarısız çıkış kodu döndürür ve döngü gerçekten
  yeniden dener.

Testler: `web_api/tests/unit/test_config_guard.py`,
`web_api/tests/unit/test_create_db_bootstrap.py`.
Yapılandırma doğrulaması: `docker compose config -q`, `bash -n
web_api/entrypoint.sh`.

## 7. Teknik ve Güvenlik Kısıtları

- `TRUSTED_PROXY_IPS` yanlışsa iki yönde de hata üretir: fazla geniş liste
  başlık sahteciliğine izin verir, boş liste tüm istekleri proxy'nin IP'sine
  toplar. Değer, dağıtımın gerçek ağ topolojisine göre doğrulanmalıdır.
- nginx `limit_req` bölgeleri, uygulama içindeki `slowapi` limitlerinin
  yerine geçmez; önünde durur.
- Bu spec TLS sonlandırmasını **çözmez**; yalnız şablon bırakır.

## 8. Open Questions

- OQ-2026-015: Yanıtlandı — taban dosya üretim-güvenli olacak, geliştirme
  kolaylıkları ayrı bir dosyaya taşınacak. 2026-08-30'da düzeltildi: dosya
  `docker-compose.dev.yml`, otomatik yüklenmiyor; varsayılan üretim-güvenli.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (dağıtım paketleme kararı;
      ayrı ADR gerekmedi, karar OQ-2026-015 ve bu spec'te kayıtlı)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

## 10. Bilinen Risk

`docker-compose.yml` içindeki `TRUSTED_PROXY_IPS` varsayılanı
(`172.16.0.0/12`) Docker'ın tipik bridge aralığına dayanan bir **tahmindir**,
bu compose projesinin gerçek subnet'i için doğrulanmış bir değer değildir.
Compose, dosyada sabitlenmedikçe proje başına subnet atar. Dağıtımdan önce
`docker network inspect` çıktısıyla doğrulanmalı ya da compose dosyasında
açık bir subnet sabitlenmelidir.

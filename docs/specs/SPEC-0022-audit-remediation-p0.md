# Mini-Spec: Denetim P0 düzeltmeleri ve `multiple_query` kaldırılması

## 1. Spec Kartı

- Özellik: 2026-08-29 denetim raporundaki P0 bulgularının kapatılması ve
  `POST /api/multiple_query` ucunun kaldırılması
- Durum: Implemented
- Versiyon: 2026-08-30
- Tarih: 2026-08-30
- Sahip: WebQuery platform ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Denetimin "kesin değişmeli" olarak işaretlediği dört bulgunun her biri, tek
başına veri kaybı ya da yetki atlaması üretebiliyordu. Ayrıca hiçbir
arayüzden çağrılmayan, rate limit'i olmayan bir çalıştırma ucu duruyordu.

### Başarı Sinyali

- `ro` dışındaki kademelerde çalışan bir `INSERT`/`UPDATE` kalıcı olur;
  hata durumunda hiçbiri kalıcı olmaz.
- İçinde `@`, `:`, `?` veya `#` geçen bir hedef DB parolasıyla bağlantı
  kurulabilir.
- Onaylanmış bir workspace'in SQL'i, onay sonrası düzenlenemez.
- Reverse proxy arkasında rate limit ve login throttle gerçek istemci
  IP'sine uygulanır.
- `POST /api/multiple_query` artık yoktur (`404`).

## 3. Kapsam / Kapsam Dışı

### Kapsam

- **P0-1:** Hedef veritabanı transaction'larının commit/rollback davranışı.
- **P0-2:** Bağlantı dizelerinin `sqlalchemy.engine.URL.create` ile
  kurulması (hedef DB ve uygulama DB'si).
- **P0-3:** Workspace düzenlemesinin, onay durumunu istemciden kabul
  etmemesi.
- **P0-4:** Güvenilir proxy üzerinden gerçek istemci IP'sinin çözülmesi.
- **P1-1:** `POST /api/multiple_query` ve `MULTIPLE_QUERY_COUNT`
  yapılandırmasının kaldırılması.

### Kapsam Dışı

- P1/P2 bulgularının geri kalanı; ayrı spec'lerde
  (SPEC-0024..SPEC-0027) ve doğrudan uygulamada ele alındı.
- Yıkıcı DML teyidi (OQ-2026-010 ile ertelendi).

## 4. Sözleşme

### Kaldırılan uç

`POST /api/multiple_query` kaldırıldı. Rotası, şeması ve
`MULTIPLE_QUERY_COUNT` ortam değişkeni silindi. Hiçbir arayüz bu ucu
çağırmıyordu.

### Değişen uç

`PUT /api/workspaces/{id}` gövdesi artık `status` alanını **kabul etmiyor**
(`WorkspaceUpdate`, `extra="forbid"`). Bilinmeyen alan `422` ile reddedilir.

Yalnız `WORKSPACE_EDITABLE_STATUSES` (`saved_in_workspace`, `rejected`)
durumundaki bir workspace düzenlenebilir. Başka bir durumda `409`
(`WorkspaceNotEditableError`) döner.

### Yeni middleware

`TrustedProxyMiddleware` (en dıştaki middleware): `X-Forwarded-For`
başlığındaki istemci IP'si **yalnız** doğrudan bağlanan eşin
`TRUSTED_PROXY_IPS` içinde olması hâlinde dikkate alınır.

## 5. İş Kuralları

### BR-01: Yazan kademe commit eder, `ro` etmez

`ro` dışındaki bir kademeyle açılan hedef DB transaction'ı, çalıştırma
başarıyla biterse commit edilir; herhangi bir istisnada rollback edilir.
`ro` kademesi hiçbir koşulda commit etmez.

### BR-02: Credential'lar bağlantı dizesine kodlanarak yazılır

Kullanıcı adı ve parola, dizeye biçimlendirilerek değil
`sqlalchemy.engine.URL.create` ile yerleştirilir. `@`, `:`, `?`, `#` gibi
karakterler bağlantıyı bozmaz ve dizeyi yeniden yorumlatamaz.

### BR-03: Onay durumu istemciden gelmez

Workspace'in `status` alanı yalnız sunucu tarafındaki akışlarla değişir.
Kabul edilen bir düzenleme `show_results` ve `status` değerlerini taslak
durumuna geri alır — düzenlenen SQL, eski onayı devralamaz.

### BR-04: Güvenilmeyen eşin başlığı okunmaz

`X-Forwarded-For`, yalnız doğrudan bağlanan eş `TRUSTED_PROXY_IPS`
listesindeyse okunur. Aksi hâlde istemci IP'si soketin kendi adresidir.

### BR-05: `DEBUG` varsayılanı `false`

Ortam değişkeni tanımlı değilse üretim davranışı geçerlidir; geliştirme
kolaylıkları açıkça açılmalıdır.

## 6. Acceptance Criteria

- AC-01: Given `rw` kademesinde bir `INSERT`, when sorgu başarıyla biter,
  then satır yeni bir bağlantıda okunabilir.
- AC-02: Given `rw` kademesinde bir `INSERT`, when çalıştırma istisna
  fırlatır, then hiçbir satır kalıcı olmaz.
- AC-03: Given `ro` kademesinde bir sorgu, when çalıştırma biter, then
  commit çağrılmaz.
- AC-04: Given parolası `p@ss:w?rd#1` olan bir hedef DB kaydı, when bağlantı
  kurulur, then kimlik doğrulama parolanın tamamıyla yapılır.
- AC-05: Given gövdesinde `status` alanı olan bir `PUT /api/workspaces/{id}`
  isteği, when istek gönderilir, then `422` döner.
- AC-06: Given `approved` durumundaki bir workspace, when düzenleme
  denenir, then `409` döner ve SQL değişmez.
- AC-07: Given `saved_in_workspace` durumundaki bir workspace, when SQL
  düzenlenir, then `status` taslağa döner ve `show_results` sıfırlanır.
- AC-08: Given güvenilmeyen bir eşten gelen `X-Forwarded-For` başlığı, when
  istek işlenir, then rate limit soketin gerçek adresine uygulanır.
- AC-09: Given `POST /api/multiple_query`, when istek gönderilir, then
  `404` döner.

Testler: `web_api/tests/integration/test_target_transaction.py`,
`web_api/tests/unit/test_database_config.py`,
`web_api/tests/unit/test_trusted_proxy.py`,
`web_api/tests/integration/test_workspaces.py`.

## 7. Teknik ve Güvenlik Kısıtları

- `TrustedProxyMiddleware` en dıştaki middleware olmalıdır; aksi hâlde
  içteki middleware'ler düzeltilmemiş IP'yi görür.
- Middleware kullanmayan sunucu başlatmaları için `uvicorn.run` çağrısına
  `proxy_headers`/`forwarded_allow_ips` geçirilir.
- `TRUSTED_PROXY_IPS` boşsa hiçbir `X-Forwarded-For` başlığı okunmaz
  (fail-closed).

## 8. Open Questions

- OQ-2026-012: Yanıtlandı — `POST /api/multiple_query` limiter eklenmeden
  tamamen kaldırılacak.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (bu bulgular için ayrı ADR
      gerekmedi; kalıcı mimari kararlar SPEC-0026 ve SPEC-0027'de)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

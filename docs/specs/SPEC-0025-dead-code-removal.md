# Mini-Spec: Ölü kod ve ölü şema temizliği

## 1. Spec Kartı

- Özellik: Hiç çalışmayan güvenlik mekanizmalarının ve ölü modüllerin
  kaldırılması
- Durum: Implemented
- Versiyon: 2026-08-30
- Tarih: 2026-08-30
- Sahip: WebQuery platform ekibi

## 2. Amaç ve Başarı Sinyali

### Amaç

Kod tabanında, **bir güvenlik kontrolü vaat eden ama hiç çalışmayan**
parçalar duruyordu. En kötü hâl budur: gözden geçiren kişi kontrolün var
olduğunu görür, kontrol yoktur.

En belirgin örnek `BlacklistedToken`: tablo, model ve iki yardımcı fonksiyon
mevcuttu, ama `mint_access` hiç `jti` üretmediği için tabloya tek satır
yazılmıyor ve kontrol hiç çalışmıyordu.

### Başarı Sinyali

- Kod tabanında "var ama çalışmıyor" durumda bir yetkilendirme veya iptal
  mekanizması kalmaz.
- `ruff check --select F,E9 web_api/` temiz geçer ve CI'da merge kapısıdır.

## 3. Kapsam / Kapsam Dışı

### Kapsam

| Öğe | İşlem |
| --- | --- |
| `BlacklistedToken` modeli + tablosu | Kaldırıldı (migration `a1b2c3d4e5f6`) |
| `blacklist_token`, `is_token_blacklisted` | Kaldırıldı |
| `AuthMiddleware`/`get_current_user`/`logout` içindeki JTI dalı | Kaldırıldı |
| `create_access_token` | Kaldırıldı (`sessions.mint_access` kullanılıyor) |
| `generate_secure_credentials` | Kaldırıldı (ADR-0005 ile WebQuery hesap üretmiyor) |
| `static_files/router.py` + paketi | Kaldırıldı (3 × `F821`, referans verdiği `templates/` yok) |
| `passlib`, `Jinja2` | `requirements.txt` içinden kaldırıldı |
| `AuditAction.USER_CREATED` | Kaldırıldı (`USER_REGISTERED` kullanılıyor) |
| `sessions.py` kullanılmayan `User` import'u | Kaldırıldı |

### Kapsam Dışı

- `Databases.db_username` / `db_password` sütunları. Kaldırılmaları
  `docs/inbox/LEGACY-CENTRAL-CREDENTIAL-FALLBACK.md` gereğince üretim
  verisinin ölçülmesine bağlı; ölçüm yapılmadan sütun düşürülmez.
- `CONFIRMATION_SECRET`: hiçbir yerde tanımlı değil ve olması da beklenmiyor,
  çünkü yıkıcı DML teyidi OQ-2026-010 ile ertelendi. Yalnız uygulama sırası
  kontrol listesinde geçiyor.

## 4. Sözleşme

Kullanıcıya görünür API sözleşmesi **değişmedi**. `POST /api/logout` aynı
yanıtı döndürüyor; iptal artık yalnız sunucu tarafındaki `UserSessions`
satırı üzerinden yapılıyor (zaten öyle yapılıyordu — JTI dalı hiç
tetiklenmiyordu).

Migration `a1b2c3d4e5f6` `BlacklistedTokens` tablosunu düşürür. Tablo hiç
yazılmadığı için veri kaybı yoktur.

## 5. İş Kuralları

### BR-01: Access token iptali oturum modeline dayanır

Anlık access-token iptali, ADR-0008'deki sunucu tarafı `UserSessions` +
rotasyonlu refresh mekanizmasıyla sağlanır. Access token'ın kendisi kısa
ömürlüdür ve ayrı bir kara listeye yazılmaz.

### BR-02: Kaldırılan denetim eylemi yeniden kullanılmaz

`user_created` değeri `AuditAction` içinden çıkarıldı. Aynı dize başka bir
anlam için yeniden kullanılmaz; geçmiş kayıtların yorumu bozulmasın diye
`AuditLog.action` bir serbest metin sütunudur ve eski satırlar okunabilir
kalır.

## 6. Acceptance Criteria

- AC-01: Given çalışan uygulama, when `BlacklistedTokens` tablosu sorgulanır,
  then tablo yoktur ve hiçbir kod yolu ona başvurmaz.
- AC-02: Given geçerli bir oturum, when kullanıcı `logout` olur, then oturum
  satırı iptal edilir ve sonraki istek `401` alır.
- AC-03: Given migration `a1b2c3d4e5f6`, when `alembic upgrade head`
  çalıştırılır, then şema doğrulaması (`common/schema_guard.py`) geçer.
- AC-04: Given kod tabanı, when `ruff check --select F,E9 web_api/`
  çalıştırılır, then bulgu yoktur.

Testler: `web_api/tests/unit/test_baseline_migration.py`,
`web_api/tests/unit/test_schema_contract.py`,
`web_api/tests/integration/test_auth_api.py`,
`web_api/tests/unit/test_audit_log.py`.

## 7. Teknik ve Güvenlik Kısıtları

- `schema_contract.py` içindeki sözleşme, kaldırılan tabloyu artık
  içermiyor; `schema_guard` açılışta bunu doğruluyor.
- `ruff --select F,E9` CI'da blocking (ADR-0002, 2026-08-30 güncellemesi):
  bu spec'in kapattığı `F821` sınıfı bir daha sessizce birikemez.

## 8. Open Questions

- OQ-2026-014: Yanıtlandı — `BlacklistedToken` mekanizması yeniden
  bağlanmayacak, migration ile kaldırılacak.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (yeni ADR gerekmedi; iptal
      modeli ADR-0008'de zaten kayıtlı)
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

# Spec: Frontend/backend sözleşme hizalaması

## 1. Spec Kartı

- Özellik: Arayüzün gerçek API sözleşmesine bağlanması
- Durum: Implemented
- Versiyon: 2026-08-24
- Tarih: 2026-08-24
- Sahip: WebQuery
- İlgili: `docs/specs/SPEC-0010-frontend-design-system.md`,
  `docs/adr/ADR-0010-frontend-design-system.md`, `frontend/DESIGN.md`

## 2. Amaç ve Başarı Sinyali

### Amaç

Arayüzün, backend'in UUID tabanlı hedef erişimine geçmesinden sonra geride
kalan API sözleşmesiyle konuşmayı bırakıp yürürlükteki sözleşmeye bağlanması.

### Başarı Sinyali

- Arayüzün yaptığı her istek, yürürlükteki bir FastAPI rotasına ve onun Pydantic
  şemasına uyar.
- Sözleşme kayması otomatik denetimle yakalanır.
- Risk analizine takılan sorgu, hata değil bekleyen inceleme olarak gösterilir.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `frontend/types.ts`, `frontend/services/api.ts` ve bunları kullanan ekranlar.
- `db_uuid` tabanlı hedef seçimi.
- Çalıştırma sonucu ve hata zarfının çözümlenmesi.
- Endpoint denetim betiği.

### Kapsam Dışı

- Backend'de hiçbir değişiklik. Rotalar, şemalar ve davranış aynen korunmuştur.
- `POST /api/multiple_query` için arayüz.
- `POST /api/admin/associate_user` için arayüz (bkz. BR-06).

## 4. Sözleşme

Arayüz aşağıdaki yürürlükteki sözleşmeye bağlanır:

| Endpoint | İstek | Yanıt |
| --- | --- | --- |
| `POST /api/execute_query` | `{db_uuid, query, ad_hoc_mask_columns?}` | `{response_type, data, message?, error?}` |
| `GET /api/masking_rules` | `?db_uuid=` | `string[]` |
| `GET /api/database_information` | - | `{db_info: {server: {databases: [{name, uuid}], technology}}}` |
| `POST /api/workspaces` | `{name, description?, query, db_uuid}` | `{success, workspace_id}` |
| `PUT /api/workspaces/{id}` | `{query, status?}` | 200, gövdesiz |
| `POST /api/execute_workspace/{id}` | `{ad_hoc_mask_columns?}` | `SQLResponse` |
| `GET /api/me` | - | `{username, is_admin}` |
| `POST /api/admin/execute_for_preview/{id}` | - | `{response_type, data, columns?, row_count?, message?, error?}` |
| Servis hatası | - | `{success, error_code, message, error, trace_id}` |

## 5. İş Kuralları

### BR-01: Hedef uuid ile adreslenir

Sunucu ve veritabanı adları yalnızca gösterim içindir. Çalıştırma, maskeleme ve
kayıt çağrıları `db_uuid` gönderir.

### BR-02: Hedef sessizce değiştirilmez

Bir çalışma alanının hedefi kullanıcının yetkileri arasında değilse seçim boş
bırakılır ve arayüz durumu açıkça bildirir. Erişilebilir başka bir veritabanına
otomatik geçilmez.

### BR-03: Sonuç metni tek yerde çözümlenir

Satır sayısı ve kırpma bilgisi `SQLResponse.message` içindedir.
`lib/execution.ts` bunu bir kez `ExecutionOutcome`'a çevirir.

### BR-04: Analiz reddi bekleyen durumdur

`error_code == "QUERY_REJECTED_BY_ANALYZER"` alan çalıştırma, başarısızlık
olarak değil "onaya gönderildi" olarak gösterilir ve çalışma alanı listesi
yenilenir.

### BR-05: Hata izlenebilirliği

Servis hatalarında `trace_id` kullanıcıya gösterilir.

### BR-06: Yetkilendirme ekranı üretilmedi

`POST /api/admin/associate_user` `user_id` ister ve backend'de kullanıcı
listeleyen bir endpoint yoktur. Yöneticinin sayısal kullanıcı kimliği yazmasını
gerektiren bir ekran üretmek yerine bu akış bilinçli olarak dışarıda
bırakılmıştır.

## 6. Acceptance Criteria

- AC-01: `execute_query` isteği `db_uuid` taşır; `servername`/`database_name`
  göndermez.
- AC-02: `masking_rules` isteği `db_uuid` sorgu parametresiyle çağrılır.
- AC-03: Veritabanı seçicisi `{name, uuid}` nesnelerini okur ve değeri uuid'dir.
- AC-04: Çalışma alanı oluşturma `{success, workspace_id}` yanıtından yeni kayda
  yönlenir.
- AC-05: Çalışma alanı güncelleme yalnız `query` gönderir.
- AC-06: 1000 satırlık kırpılmış sonuç "İlk 1.000 satır (kırpıldı)" olarak
  özetlenir ve tablo altında açıklanır.
- AC-07: Riskli ifade çalıştırıldığında sarı "Sorgu onaya gönderildi" durumu ve
  bilgilendirme bildirimi görünür.
- AC-08: Başarısız çalıştırmada hata mesajı ve `trace_id` gösterilir.
- AC-09: Yetkisi olmayan kullanıcıya "hiçbir veritabanına erişim yetkiniz yok"
  durumu gösterilir.
- AC-10: `npm run audit:api` tüm çağrılar için geçer.
- AC-11: Tam ekran rotalarda sayfa gövdesi kaymaz; sonuç tablosu kendi içinde
  kaydırılır.

## 7. Teknik ve Güvenlik Kısıtları

- Backend sözleşmesi arayüzden değiştirilmez; uyumsuzluk arayüz tarafında
  düzeltilir.
- Maskelenmiş kolonlar sonuç tablosunda işaretli kalır.
- Kimlik bilgisi üreten yanıt (`add_database`) yalnız tek seferlik gösterim
  diyaloğunda kullanılır, hiçbir yere kaydedilmez.

## 8. Open Questions

- Yok. OQ-2026-002 kullanıcı tarafından ertelenmiştir ve bu iş onu bağlamaz.

## 9. Done Kontrolü

- [x] Acceptance criteria doğrulandı (endpoint denetimi + sözleşmeye birebir uyan
      yerel doğrulama sunucusuyla uçtan uca tıklama)
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi (yeni ADR gerekmedi; ADR-0010 geçerli)
- [x] İlgili doğrulama komutları çalıştırıldı

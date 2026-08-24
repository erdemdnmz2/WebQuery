# Mini-Spec: Onay kararlarında eşzamanlılık kontrolü

## 1. Spec Kartı

- Özellik: Sorgu onay/red kararlarında koşullu durum geçişi
- Durum: Ready for implementation
- Versiyon: 1.0.0
- Tarih: 2026-08-25
- Sahip: WebQuery backend

## 2. Amaç ve Başarı Sinyali

### Amaç

Aynı `QueryData` kaydı için iki yönetici aynı anda onay veya red verdiğinde,
son yazanın önceki kararı sessizce ezmesini engellemek.

### Başarı Sinyali

- Aynı bekleyen sorguya yapılan eşzamanlı kararlardan yalnızca biri başarılı olur.
- Kaybeden istek açık bir çakışma hatası (`409`) alır.
- Karara bağlanmış bir sorgu ikinci kez onaylanamaz veya reddedilemez.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- Web approval servisinde `status == "waiting_for_approval"` koşullu `UPDATE`.
- Slack approval servisinde aynı koşullu durum geçişi.
- Slack kararlarında aktörün hedef veritabanında `ADMIN` rolünün doğrulanması.
- Çakışmanın API ve Slack yanıtlarında görünür hâle getirilmesi.
- `Workspace` ve `ActionLogging` güncellemelerinin başarılı durum geçişiyle aynı transaction içinde yapılması.

### Kapsam Dışı

- Yeni bir `AuditLog` modeli veya audit action sözleşmesi eklemek.
- Slack için yeni bir red-gerekçesi modalı tasarlamak.
- Veritabanı migration altyapısını bu değişiklik kapsamında yeniden kurmak.

## 4. Sözleşme

Onay veya red işlemi yalnızca şu koşul sağlanıyorsa başarılıdır:

```sql
UPDATE QueryData
SET status = :new_status
WHERE id = :query_id
  AND status = 'waiting_for_approval'
```

Etkilenen satır sayısı `1` değilse servis `APPROVAL_CONFLICT` kodlu ve HTTP
`409 Conflict` durumlu hata döndürür.

## 5. İş Kuralları

### BR-01: Bekleyen sorgu tek kez karara bağlanır

`waiting_for_approval` durumundaki sorgu ilk başarılı kararla yeni duruma geçer;
sonraki kararlar mevcut durumu değiştiremez.

### BR-02: Karar geçişi koşullu ve atomiktir

Durum kontrolü ve durum değişikliği ayrı Python işlemleri olarak yapılamaz;
aynı koşullu SQL `UPDATE` ifadesinde gerçekleştirilir.

### BR-03: Yan etkiler yalnızca kazanan karardan sonra yazılır

`Workspace` ve varsa `ActionLogging` güncellemeleri, koşullu `UPDATE` başarılı
olduktan sonra aynı transaction içinde yapılır.

### BR-04: Slack kararı hedef veritabanı yetkisi ister

Slack kullanıcısı WebQuery kullanıcısına eşlenmeli ve hedef veritabanında
`ADMIN` rolüne sahip değilse karar uygulanmamalıdır.

## 6. Acceptance Criteria

- AC-01: Given bekleyen bir sorgu, when iki karar aynı anda gönderilir, then tam olarak bir karar başarılı olur ve diğeri `409` alır.
- AC-02: Given karara bağlanmış bir sorgu, when tekrar karar gönderilir, then durum değişmez ve `APPROVAL_CONFLICT` döner.
- AC-03: Given başarılı bir onay, when transaction tamamlanır, then `Workspace` ve `ActionLogging` kayıtları yeni kararla tutarlıdır.
- AC-04: Given başarısız koşullu geçiş, when işlem tamamlanır, then kaybeden istek başarı mesajı göndermez.
- AC-05: Given Slack kullanıcısının hedef veritabanında `ADMIN` rolü yok, when karar gönderilir, then karar reddedilir ve sorgu beklemede kalır.

## 7. Teknik ve Güvenlik Kısıtları

- `SELECT` sonrası Python tarafında yapılan ayrı bir durum kontrolü yarış koruması
  olarak kabul edilmez.
- Web ve Slack yolları aynı `waiting_for_approval` koşulunu kullanmalıdır.
- Yetki kontrolleri koşullu durum değişikliğinden önce korunur.
- SQL Server sürücü davranışı nedeniyle `rowcount` doğrulaması üretim motorunda
  ayrıca teyit edilmelidir.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [ ] Acceptance criteria için test eklendi veya güncellendi
- [ ] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi
- [ ] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

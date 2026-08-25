# Mini-Spec: Onay kararlarında eşzamanlılık kontrolü

## 1. Spec Kartı

- Özellik: Birleşik sorgu onay/red karar akışı
- Durum: Implemented
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

- Web ve Slack'in çağırdığı tek transport-bağımsız `approval.service.decide()` fonksiyonu.
- `status == "waiting_for_approval"` koşullu `UPDATE` ile atomik durum geçişi.
- Slack kararlarında aktörün hedef veritabanında `ADMIN` rolünün doğrulanması.
- Red gerekçesinin web ve Slack kanallarında zorunlu tutulması.
- `QueryData` karar metadatası (`decision_reason`, `decided_by`, `decided_at`) ve Alembic migration'ı.
- Çakışmanın API ve Slack yanıtlarında görünür hâle getirilmesi.
- `Workspace`, `ActionLogging` ve `AuditLog` güncellemelerinin başarılı durum geçişiyle aynı transaction içinde yapılması.

### Kapsam Dışı

- Yeni bir onay politikası veya ADMIN dışı roller için karar yetkisi tanımlamak.
- Admin'in riskli sorgularının onay kuyruğuna alınması (mevcut admin bypass politikası korunur).

## 4. Sözleşme

Web ve Slack taşıyıcıları aynı `approval.service.decide()` fonksiyonunu çağırır.
Onay veya red işlemi yalnızca şu koşul sağlanıyorsa başarılıdır:

```sql
UPDATE QueryData
SET status = :new_status
WHERE id = :query_id
  AND status = 'waiting_for_approval'
```

Etkilenen satır sayısı `1` değilse servis `APPROVAL_CONFLICT` kodlu ve HTTP
`409 Conflict` durumlu hata döndürür. Web red endpoint'i `{ "reason": "..." }`
body'si ister; Slack red butonu aynı gerekçeyi bir modal üzerinden toplar.

## 5. İş Kuralları

### BR-01: Bekleyen sorgu tek kez karara bağlanır

`waiting_for_approval` durumundaki sorgu ilk başarılı kararla yeni duruma geçer;
sonraki kararlar mevcut durumu değiştiremez.

### BR-02: Karar geçişi koşullu ve atomiktir

Durum kontrolü ve durum değişikliği ayrı Python işlemleri olarak yapılamaz;
aynı koşullu SQL `UPDATE` ifadesinde gerçekleştirilir.

### BR-03: Yan etkiler yalnızca kazanan karardan sonra yazılır

`Workspace`, `ActionLogging` ve `AuditLog` güncellemeleri, koşullu `UPDATE` başarılı
olduktan sonra aynı transaction içinde yapılır.

### BR-04: Slack kararı hedef veritabanı yetkisi ister

Slack kullanıcısı WebQuery kullanıcısına eşlenmeli ve hedef veritabanında
`ADMIN` rolüne sahip değilse karar uygulanmamalıdır.

### BR-05: Red gerekçesi saklanır

Red kararı en az üç karakterlik bir gerekçe içermelidir. Bu gerekçe `QueryData`
üzerinde saklanır ve workspace açıklaması ile audit detaylarında görünür.

### BR-06: Taşıyıcılar karar kuralı uygulamaz

Web router/service adapter'ı ile Slack listener; yetki, durum geçişi, audit ve
yan etki kurallarını kopyalamaz. Bu kurallar yalnızca `approval.service.decide()`
içinde bulunur.

## 6. Acceptance Criteria

- AC-01: Given bekleyen bir sorgu, when iki karar aynı anda gönderilir, then tam olarak bir karar başarılı olur ve diğeri `409` alır.
- AC-02: Given karara bağlanmış bir sorgu, when tekrar karar gönderilir, then durum değişmez ve `APPROVAL_CONFLICT` döner.
- AC-03: Given başarılı bir onay, when transaction tamamlanır, then `Workspace` ve `ActionLogging` kayıtları yeni kararla tutarlıdır.
- AC-04: Given başarısız koşullu geçiş, when işlem tamamlanır, then kaybeden istek başarı mesajı göndermez.
- AC-05: Given Slack kullanıcısının hedef veritabanında `ADMIN` rolü yok, when karar gönderilir, then karar reddedilir ve sorgu beklemede kalır.
- AC-06: Given web veya Slack üzerinden red gerekçesi yok, when red gönderilir, then karar uygulanmaz.
- AC-07: Given web ve Slack kararı, when başarılı olarak tamamlanır, then her iki taşıyıcı aynı ortak karar fonksiyonunu kullanır.

## 7. Teknik ve Güvenlik Kısıtları

- `SELECT` sonrası Python tarafında yapılan ayrı bir durum kontrolü yarış koruması
  olarak kabul edilmez.
- Web ve Slack yolları aynı `waiting_for_approval` koşulunu kullanmalıdır.
- Yetki ve self-approval kontrolleri koşullu durum değişikliğinden önce ortak
  serviste uygulanır.
- `QueryData` alan değişikliği Alembic migration'ı olmadan dağıtılamaz.
- SQL Server sürücü davranışı nedeniyle `rowcount` doğrulaması üretim motorunda
  ayrıca teyit edilmelidir.

## 8. Open Questions

- Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [ ] İlgili güvenlik ve hata davranışları doğrulandı
- [x] Gerekliyse ADR oluşturuldu/güncellendi
- [x] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

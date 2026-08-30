# Mini-Spec: `<Özellik adı>`

## 1. Spec Kartı

- Özellik: `<Kısa ad>`
- Durum: Draft | Ready for implementation | Implemented | Superseded
- Versiyon: `<semver veya tarih>`
- Tarih: `<YYYY-MM-DD>`
- Sahip: `<kişi veya ekip>`

## 2. Amaç ve Başarı Sinyali

### Amaç

`<Kullanıcı veya iş problemi.>`

### Başarı Sinyali

- `<Gözlemlenebilir ve test edilebilir sonuç>`

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `<Dahil olan davranış>`

### Kapsam Dışı

- `<Bu değişiklikte özellikle yapılmayacak davranış>`

## 4. Sözleşme

`<Endpoint, UI akışı, olay veya veri sözleşmesini yazın. Request/response örneği gerekiyorsa ekleyin.>`

## 5. İş Kuralları

### BR-01: `<Kural adı>`

`<Açık, tek anlamlı kural.>`

## 6. Acceptance Criteria

- AC-01: Given `<başlangıç durumu>`, when `<eylem>`, then `<doğrulanabilir sonuç>`.
- AC-02: `<Hata, yetki veya sınır durumu>`.

## 7. Teknik ve Güvenlik Kısıtları

- `<Performans, uyumluluk, veri, kimlik doğrulama, audit veya masking kısıtı>`

## 8. Open Questions

- `<OQ-YYYY-NNN>`: `<Soru>`

Bir soru açıksa, `docs/open-questions.md` içine de girilmelidir. Status `Ready
for implementation` olabilmesi için açık soruların çözülmüş veya kullanıcı
tarafından açıkça ertelenmiş olması gerekir.

## 9. Done Kontrolü

- [ ] Acceptance criteria için test eklendi veya güncellendi
- [ ] İlgili güvenlik ve hata davranışları doğrulandı
- [ ] Gerekliyse ADR oluşturuldu/güncellendi
- [ ] Doğrulama komutları çalıştırıldı ve sonuçları handoff'a yazıldı

# Mini-Spec: Redis tabanlı giriş kısıtlaması

## 1. Spec Kartı

- Özellik: Redis tabanlı kullanıcı ve IP giriş kısıtlaması
- Durum: Implemented
- Versiyon: 2026-08-27
- Tarih: 2026-08-27
- Sahip: WebQuery

## 2. Amaç ve Başarı Sinyali

### Amaç

Birden çok Uvicorn worker'ı çalışırken başarısız login denemelerini kullanıcı
hesabı ve istemci IP'si üzerinden ortak olarak sınırlamak; bcrypt kaynak
tüketimini brute-force saldırısına karşı korumak.

### Başarı Sinyali

- Aynı Redis'e bağlı tüm worker'lar, aynı kullanıcı veya IP için tek bir
  başarısız-deneme penceresi görür.
- Limitli istekte parola doğrulama fonksiyonu çağrılmaz.
- Redis erişilemezse login işlemi token üretmeden `503` döner.

## 3. Kapsam / Kapsam Dışı

### Kapsam

- `POST /api/login` için Redis'te kullanıcı hesabı ve IP bazlı kayan pencere.
- Redis client yaşam döngüsü, Redis health check ve Docker Compose hizmeti.
- Mevcut IP bazlı SlowAPI limiter'ın yanında ek koruma olarak çalışma.

### Kapsam Dışı

- Workspace, veritabanı metadata'sı veya sorgu sonucu için genel cache.
- SQLAlchemy engine nesnelerini process'ler arasında paylaşma.
- Kalıcı hesap kilitleme veya kullanıcı tablosuna lock alanı ekleme.

## 4. Sözleşme

`POST /api/login` mevcut request ve başarılı response sözleşmesini korur.

- Kullanıcı veya IP son pencerede limitteyse `429` döner.
- Redis kullanılamıyorsa `503` döner; parola sorgusu ve token üretimi yapılmaz.
- Kullanıcı yok, parola yanlış veya hesap pasif durumları aynı jenerik `400`
  mesajıyla döner.

## 5. İş Kuralları

### BR-01: Ortak kayan pencere

Başarısız login denemeleri Redis sorted set ile hesaplanır. Varsayılan limit 15
dakikada 5 başarısız denemedir ve `LOGIN_MAX_FAILURES` ile
`LOGIN_WINDOW_MINUTES` ayarlarıyla değiştirilebilir.

### BR-02: İki boyutlu koruma

Bir kullanıcı hesabı veya istemci IP'si limitteyse istek reddedilir. Redis
anahtarları ham e-posta ve IP içermez.

### BR-03: KDF öncesi kontrol

Limit denetimi kullanıcı sorgusu ve `check_password()` çağrısından önce yapılır.

### BR-04: Başarıdaki temizleme

Başarılı login yalnızca kullanıcı hesabı sayacını temizler; IP sayacı korunur.

### BR-05: Redis fail-closed

Redis başlangıçta erişilemezse uygulama başlamaz. Runtime'da Redis işlemi
başarısız olursa login `503` döner ve token oluşturulmaz.

## 6. Acceptance Criteria

- AC-01: Given farklı worker'lar aynı Redis'i kullanır, when aynı kullanıcı
  hesabına limit kadar başarısız giriş yapılır, then sonraki istek her worker'da
  `429` döner.
- AC-02: Given bir IP'den farklı hesaplara limit kadar başarısız giriş yapılır,
  when aynı IP'den tekrar giriş denenir, then `429` döner.
- AC-03: Given kullanıcı veya IP limitte, when login çağrılır, then
  `check_password()` çağrılmaz.
- AC-04: Given Redis erişilemez, when login çağrılır, then `503` döner ve token
  üretilmez.
- AC-05: Given geçerli kimlik bilgileri, when login başarılı olur, then kullanıcı
  sayacı temizlenir, IP sayacı temizlenmez.
- AC-06: Given Redis URL'i yok veya startup ping'i başarısız, when uygulama
  başlatılır, then uygulama trafik kabul etmeden kapanır.

## 7. Teknik ve Güvenlik Kısıtları

- Redis, login throttle için tüm ortamlarda zorunlu runtime bağımlılığıdır;
  worker sayısı backend seçimini değiştirmez.
- Kayan pencere güncellemesi Redis tarafında atomik olmalıdır.
- Redis URL'i ve anahtarları loglanmamalı; Redis anahtarlarında ham e-posta veya
  IP tutulmamalıdır.
- SlowAPI'nin mevcut process-local IP limiti ek savunma katmanı olarak korunur;
  dağıtık güvenlik garantisi Redis throttle'dan gelir.

## 8. Open Questions

Yok.

## 9. Done Kontrolü

- [x] Acceptance criteria için test eklendi veya güncellendi
- [x] İlgili güvenlik ve hata davranışları doğrulandı
- [x] ADR oluşturuldu/güncellendi
- [x] Doğrulama komutları handoff'a yazıldı

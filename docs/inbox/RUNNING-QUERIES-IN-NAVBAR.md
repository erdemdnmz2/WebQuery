# Navbar'da çalışan sorguları gösterme

**Durum:** Ertelendi / gelecekte değerlendirilecek
**Kaydedildi:** 2026-10-02
**Kaynak:** Kullanıcının sorgu ekranlarına Cancel/İptal butonu ekleme isteği
**Kapsam:** Gelecekte frontend navbar ve çalışan sorguların durum takibi

## Hatırlanacak fikir

İleride kullanıcı, çalışan sorgularını navbar üzerinden görebilsin. Bu fikir,
sorgu ekranlarına eklenecek Cancel/İptal butonundan ayrı bir gelecek işidir.
Kullanıcının mevcut isteği: yeni iptal butonu yalnız sorgu çalıştırılan
ekranlarda bulunsun; navbar özelliği şimdi uygulanmasın.

## İleride değerlendirilecek noktalar

- Kullanıcı başka bir ekrana geçtiğinde çalışan sorgunun durumu nasıl izlenecek?
- Navbar'dan ilgili sorgu ekranına dönüş nasıl yapılacak?
- Birden fazla sorgu çalışıyorsa sayı ve durum nasıl gösterilecek?
- Tamamlanma, hata ve iptal durumları kullanıcıya nasıl bildirilecek?
- Kullanıcı yalnız görmeye yetkili olduğu sorguları görebilmeli.
- Görünüm `frontend/DESIGN.md`, mevcut `AppShell` ve tema token'larıyla uyumlu
  olmalı.

Bu kayıt bir hatırlatmadır. Navbar'dan iptal, kalıcı sorgu işleri veya yeni bir
backend sözleşmesi için uygulama kararı verilmiş değildir. Özellik ele
alındığında kapsam ve davranış ilgili spec'e yazılmalıdır.

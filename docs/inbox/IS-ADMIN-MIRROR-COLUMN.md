# `UserDatabaseAssociation.is_admin` aynası: senkron tutulmak yerine düşürülmeli

**Durum:** Inbox / karar bekliyor
**Kaydedildi:** 2026-08-30
**Kapsam:** `web_api/app_database/models.py`, `web_api/admin/services.py`,
`web_api/owner/services.py`, `web_api/common/schema_contract.py`,
`web_api/tests/unit/test_association_is_admin_mirror.py`
**Kaynak:** 2026-08-29/30 commit serisinin gözden geçirmesi;
`webquery_denetim_raporu.md` P2-20b'nin uygulanış biçimi

Denetim bulgusu P2-20b doğruydu: `UserDatabaseAssociation` hem `role` hem
`is_admin` tutuyor, yetkilendirme yalnız `role`'ü okuyor, yani iki alan
sessizce çelişebilir. Uygulanan çözüm ise soruna göre ağır kaçtı. Bu kayıt
alternatifi ve bedelini tutuyor; **kod tarafında acil bir şey yok**, mevcut
hâl doğru çalışıyor.

## Şu anki durum

`24ee98f` ile bir mapper event eklendi:

```python
@event.listens_for(UserDatabaseAssociation, "before_insert")
@event.listens_for(UserDatabaseAssociation, "before_update")
def _derive_is_admin(mapper, connection, target) -> None:
    target.is_admin = ADMIN in parse_roles(target.role)
```

Yanına 91 satırlık `test_association_is_admin_mirror.py` geldi.

İki gözlem:

1. **Kolonu hiçbir üretim kodu okumuyor.** Yetki kararlarının tamamı
   `common.roles.is_admin(role_string)` üzerinden gidiyor. `grep` ile
   doğrulandı: kolona dokunan 8 üretim satırının **hepsi yazma**
   (`owner/services.py` 279, 286, 608, 613, 669; `admin/services.py` 278,
   907, 913). Tek okuma `models.py:397`, yani event'in kendisi.
2. **API'de görünen `is_admin` alanı da kolondan gelmiyor.**
   `authentication/schemas.py` ve `admin/schemas.py` bu alanı taşıyor ama
   değeri `any_admin(assocs)` (`authentication/router.py:353`) ve
   `is_admin(association.role)` (`admin/services.py:186`) hesaplıyor —
   ikisi de `role`'den.

Sonuç: türetilmiş bir alanı artık **iki mekanizma** yazıyor. Event eklendi
ama 8 manuel atama yerinde bırakıldı, dolayısıyla çağrı yerine bakan biri
alanın nasıl doğru kaldığını göremiyor; asıl yazıcı görünmez olan.

## Önerilen alternatif

Kolonu düşürmek. Denetimin "iki alan çelişebilir" endişesini, ikinci alanı
senkron tutarak değil, ortadan kaldırarak kapatır — ve `role` zaten tek
otorite olduğu için hiçbir davranış değişmez.

## İş kalemleri

1. `UserDatabaseAssociation.is_admin` kolonunu ve `_derive_is_admin` event'ini
   `models.py`'den kaldır.
2. 8 üretim yazma noktasını sil (`owner/services.py` 5, `admin/services.py` 3).
   `admin/services.py:903`'teki `is_admin_val` yalnız bu atamalar için
   hesaplanıyorsa o da düşer.
3. `common/schema_contract.py:119`'daki `("UserDatabaseAssociation",
   "is_admin")` kaydını çıkar — startup şema guard'ı kolonu bekliyor, aksi
   hâlde uygulama açılmaz.
4. Migration yaz (`a1b2c3d4e5f6` içinde `BlacklistedTokens`'ın düşürülmesi
   aynı serideki örnek).
5. `test_association_is_admin_mirror.py` kaldırılır; testlerdeki 28
   `is_admin=` kullanımı 13 dosyada temizlenir. Çoğu
   `UserDatabaseAssociation(...)` fixture'ı.
6. API cevaplarındaki `is_admin` alanı **korunur** — zaten `role`'den
   hesaplanıyor, frontend sözleşmesi değişmez.

## Karşı argüman

Kolon `Databases` sayfasındaki listeleme sorgularında ileride bir `WHERE`
koşulu olarak işe yarayabilir; şu an `is_admin(role)` Python tarafında
filtreliyor (`admin/services.py:326, 495, 647`) ve bu, ilişki sayısı
büyürse tam tarama demek. Kolon düşürülürse o filtre kalıcı olarak Python
tarafında kalır. Bu ölçekte (kullanıcı × veritabanı ilişkisi) gerçek bir
sorun değil, ama kararın bilinerek verilmesi gerekiyor.

## Doğrulama

- `web_api/` dizininden `pytest`.
- Uygulamayı açıp startup şema guard'ının geçtiğini görmek (3. madde
  atlanırsa tam burada durur).
- `frontend/` dizininden `npm run build`; `is_admin` alanı değişmediği için
  arayüz tarafında değişiklik beklenmiyor.

## İlgili kayıtlar

- `webquery_denetim_raporu.md` P2-20b — özgün bulgu.
- `AUDIT-REMEDIATION-COMMIT-SERIES-BISECTABILITY.md` — aynı serinin
  paketleme sorunları.

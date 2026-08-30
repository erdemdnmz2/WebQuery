# Eski kayıtların merkezi credential fallback'i

**Durum:** Inbox / uygulanacak iş
**Kaydedildi:** 2026-08-28
**Kapsam:** `web_api/database_provider/database.py`,
`web_api/app_database/models.py`

Bu kayıt, rol bazlı credential'lara geçişte bırakılan geçici fallback'in
kapatılmasını takip eder.

## Sorun

`DatabaseProvider._credentials_for` (`web_api/database_provider/database.py:73`),
hiçbir kademe credential'ı olmayan kayıtlar için `ro` ve `rw` isteklerini
merkezi hesaba yönlendiriyor:

```python
        if not has_any_tier_credential and tier in {"ro", "rw"}:
            return CENTRAL_DB_USER, CENTRAL_DB_PASSWORD
```

Bu bilinçli bir geçiş kapısı: SPEC-0002 öncesinde kaydedilmiş veritabanları
uygulama açılmaz hâle gelmeden migrasyon edilebilsin diye kondu.

Ancak sonucu şu: migrasyonu tamamlanmamış her kayıt fiilen **tek hesap**
modelinde çalışıyor. Salt-okuma sorguları da yazma yetkisi olan merkezi hesapla
açılıyor ve SPEC-0002'nin dayandığı en düşük yetki güvencesi o kayıtlar için
geçerli değil.

`Databases.db_username` / `db_password` kolonları da aynı geçiş için duruyor
(`web_api/app_database/models.py:237-240`).

## Neden şimdi yapılmadı

Kaç kaydın bu durumda olduğu bilinmiyor. Ölçmeden fallback'i kaldırmak, çalışan
kurulumlarda sorguları fail-closed hâle getirir.

## İş kalemleri

1. **Ölç.** Kademe credential'ı olmayan `Databases` satırlarını say. Üretim ve
   stage için ayrı ayrı:

   ```sql
   SELECT COUNT(*) FROM Databases
   WHERE (username_ro IS NULL OR password_ro IS NULL)
     AND (username_rw IS NULL OR password_rw IS NULL)
     AND (username_ddl IS NULL OR password_ddl IS NULL);
   ```

2. Sayı sıfırsa fallback'i ve `db_username`/`db_password` kolonlarını kaldır;
   kolon kaldırma için Alembic migration gerekir.
3. Sayı sıfır değilse önce kayıtları güncelleme yolu gerekir — bu,
   `docs/inbox/DATABASE-REGISTRATION-LIFECYCLE.md` kaydına bağlıdır. Kayıt
   güncellenemediği için bugün migrasyonun tek yolu veritabanına elle müdahale.
4. Fallback kaldırıldığında `_credentials_for` fail-closed kalmalı: eksik
   kademe için `None` döner ve `get_session` anlaşılır bir hata fırlatır.
5. Geçiş süresince, fallback'e düşen her bağlantı için bir kez `logger.warning`
   yazılmasını değerlendir; hangi kayıtların migrasyon beklediği loglardan
   görülebilir olur.

## Bağlantılı kayıtlar

- `docs/specs/SPEC-0002-role-based-target-database-credentials.md`
- `docs/adr/ADR-0005-role-based-target-database-credentials.md`
- `docs/inbox/DATABASE-REGISTRATION-LIFECYCLE.md`

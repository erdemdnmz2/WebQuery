# Hedef veritabanı transaction'ı commit edilmiyor

**Durum:** Inbox / uygulanacak iş — **en yüksek öncelik**
**Kaydedildi:** 2026-08-28
**Kapsam:** `web_api/database_provider/database.py`,
`web_api/query_execution/services.py`, `web_api/workspaces/services.py`,
`web_api/admin/services.py`

Bu kayıt, hedef veritabanında çalıştırılan yazma işlemlerinin kalıcı
olmamasını takip eder. Statik kod okumasıyla tespit edildi; gerçek bir hedef
veritabanına karşı henüz ölçülmedi.

## Sorun

`DatabaseProvider.get_session` oturumu `autocommit=False` ile açıyor
(`web_api/database_provider/database.py:142`) ve engine `create_async_engine`
çağrısında `isolation_level="AUTOCOMMIT"` verilmiyor
(`web_api/database_provider/engine_cache.py:106`). Context manager çıkışta
yalnız `session.close()` çağırıyor:

```python
        async with AsyncSessionLocal() as session:
            try:
                ...
                yield session
            finally:
                await session.close()
```

Hedef oturum üzerinde hiçbir yerde `commit()` çağrılmıyor.
`web_api/query_execution/services.py:199` içindeki tek `commit()` uygulama
metadata veritabanına aittir, hedefe değil. SQLAlchemy açık bir transaction'ı
`close()` sırasında geri alır.

Beklenen sonuç: `INSERT`, `UPDATE`, `DELETE` hedef veritabanında çalışır,
`rowcount` döner, audit kaydı `successfull=True` yazar — sonra rollback olur.
Kullanıcı yazdığını sanır, veri değişmemiştir.

Aynı davranış üç çalıştırma yolunun üçünde de var:

| Yol | Yer |
| --- | --- |
| Sorgu çalıştırma | `web_api/query_execution/services.py:224` |
| Workspace tekrar çalıştırma | `web_api/workspaces/services.py:364` |
| Admin önizleme | `web_api/admin/services.py:436` |

## Neden şimdi yapılmadı

Adım 19 analizci sertleştirmesi sırasında tespit edildi; o değişikliğin kapsamı
analizciydi. Düzeltme tek satır değil, bir davranış kararı gerektiriyor
(aşağıya bakınız) ve SQL çalıştırma davranışını değiştirdiği için
`AGENTS.md` gereği regresyon testiyle birlikte gitmeli.

## Doğrulama

Düzeltmeden **önce** sorunun gerçekliğini ölçün. En kısa yol: `rw` kademesinde
bir `UPDATE` çalıştırıp ardından ayrı bir istekte aynı satırı okumak. Satır
değişmemişse kayıt doğrulanmıştır.

`git log -S "commit" -- web_api/database_provider/database.py` ile commit'in
hiç var olup olmadığına da bakılmalı; bilinçli olarak kaldırılmış olabilir.

## Hedef durum

- Batch hatasız tamamlandığında hedef transaction commit edilir.
- Herhangi bir hata durumunda rollback edilir.
- `ro` kademesinde commit hiç denenmez; o oturum salt okumadır.
- Sonuç satırları, oturum kapanmadan önce okunmuş olmalıdır — commit sonrası
  cursor'dan okumaya çalışmak yeni bir hata sınıfı üretir.

## İş kalemleri

1. Yazmanın kalıcı olmadığını gösteren, kırmızıya düşen bir regresyon testi
   yaz. Gerçek bir hedef DB gerekiyorsa sqlite veya container tabanlı bir
   entegrasyon testi kullan; mock'lanmış oturum bu hatayı yakalayamaz.
2. `get_session` içinde commit/rollback davranışını uygula. Kademeyi de dikkate
   al: `tier == "ro"` ise commit yok.
3. Üç çalıştırma yolunun üçünü de aynı davranışa bağla.
4. `MAX_ROW_COUNT_LIMIT` ile kesilen bir `SELECT`'in commit davranışını netleştir.
5. Testleri `web_api/` dizininden `pytest` ile çalıştır.

## Bağlantılı kayıtlar

- `docs/inbox/MULTI-RESULT-SET-REPORTING.md` — bu düzeltilmeden "kaç satır
  etkilendi" bilgisi zaten anlamsızdır; sıralama olarak bu kayıt önce gelir.

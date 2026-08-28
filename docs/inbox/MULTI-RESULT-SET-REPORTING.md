# Çoklu ifadeli batch'te sonuç raporlaması

**Durum:** Inbox / ertelendi — gerçek talep geldiğinde
**Kaydedildi:** 2026-08-28
**Kapsam:** `web_api/query_execution/services.py`,
`web_api/workspaces/services.py`, `web_api/admin/services.py`,
`frontend/pages/Studio.tsx`

Bu kayıt, `SELECT ...; UPDATE ...` gibi çoklu ifadeli bir batch çalıştırıldığında
yalnız ilk sonuç kümesinin okunmasını takip eder.

## Sorun

Batch tek bir string olarak gönderiliyor:

```python
sql_query = text(query)
result = await session.execute(sql_query)
```

Veritabanı motoru her ifade için ayrı bir sonuç üretir: `SELECT` bir satır
kümesi, `UPDATE` bir `rowcount`. Sürücü bunları sırayla verir ve bir sonrakine
geçmek için `cursor.nextset()` gerekir. Kod tabanında `nextset` çağrısı yok.

Sonuç:

- `result.returns_rows` ilk kümeye (SELECT) göre `True` olur.
- Kullanıcı SELECT'in satırlarını görür.
- `UPDATE`'in etkilediği satır sayısı hiç okunmaz.
- Audit kaydındaki `row_count` da SELECT'in satır sayısı olur — yani **yanlış
  bilgi**, eksik bilgi değil. Kullanıcı bu sayıyı UPDATE'in etkisi sanabilir.

## Neden ertelendi

Kazanç ile maliyet orantısız. Kazanılan şey karma batch'te bir sayı göstermek;
ödenen bedel SQLAlchemy async soyutlamasını delip ham DBAPI cursor'a inmek,
sürücüye göre değişen davranış, API sözleşmesi değişikliği, frontend'de çoklu
grid ve masking/satır limiti/audit semantiği kararları.

Tek ifadeli bir `UPDATE ... WHERE ...` gönderildiğinde `rowcount` zaten doğru
çalışıyor; çoğu yazma işlemi bu biçimdedir.

## Ucuz ara çözüm (önerilen ilk adım)

Sorunun asıl zararı yanlış bilgi. `QueryAnalyzer` zaten `sqlglot.parse()` ile
ifade listesini çıkarıyor. Batch birden fazla ifade içeriyorsa yanlış sayıyı
raporlamak yerine dürüst davranmak yeterli:

- Yanıtta: ilk sonuç kümesinin satırları + "çoklu ifade çalıştırıldı, ifade
  başına satır sayısı raporlanmıyor" notu.
- Audit'te: `row_count` yerine batch olduğunu belirten bir işaret.

Birkaç satır; ham cursor, sözleşme değişikliği ve sürücü farkı yok.

## Tam çözüm — yapılırsa

Döngüyü **sürücü sürmeli**, sqlglot'un saydığı ifade sayısı değil. İkisi eşit
olmak zorunda değildir: `SET NOCOUNT ON` sonuçları bastırır, trigger'lı bir
`INSERT` fazladan sonuç üretebilir, tek bir stored procedure çağrısı birden çok
küme döndürebilir. Parser'ın sayısına güvenip cursor'ı o kadar ilerletmek,
ADR-0016'da adı konan parser/motor ayrışmasının aynı sınıfıdır.

```python
results = []
while True:
    if cursor.description is not None:
        results.append({"columns": [...], "rows": cursor.fetchmany(LIMIT)})
    else:
        results.append({"rowcount": cursor.rowcount})
    if not cursor.nextset():
        break
```

Üst sınır koyun (örneğin 50 iterasyon).

SQLAlchemy async katmanında `AsyncSession.execute()` sonucu tamponlayıp cursor'ı
kapattığı için ham cursor'a `await session.connection()` ve `run_sync()`
üzerinden inilmesi gerekir.

## Önce doğrulanması gereken

Kullanılan sürücüler (`web_api/database_provider/config.py:75`): MSSQL →
`aioodbc`, MySQL → `aiomysql`, PostgreSQL → `asyncpg`.

Çoklu ifadeyi muhtemelen yalnız `aioodbc` destekliyor:

- `asyncpg` her sorguyu prepared statement olarak gönderir ve çoklu komut içeren
  string'i reddeder. PostgreSQL'de `SELECT; UPDATE` batch'i bugün hiç
  çalışmıyor olabilir.
- `aiomysql`/`pymysql` varsayılan olarak `MULTI_STATEMENTS` client flag'ini
  açmaz.

Bunlar gerçek sunucuya karşı ölçülmedi. Ölçüm "yalnız MSSQL" derse özelliğin
sözleşmesi teknolojiye göre farklılaşır ve tasarım kararı değişir.

## Karar gerektiren noktalar

Uygulamadan önce `docs/open-questions.md` içine `Open` statüsüyle eklenmeli:

1. Yanıt şekli: sonuç kümelerinin dizisi mi, ilk küme + toplam etkilenen satır mı?
2. `MAX_ROW_COUNT_LIMIT` küme başına mı, toplam mı uygulanacak?
3. Audit'teki `row_count` hangi kümenin sayısı olacak?
4. Desteklenmeyen teknolojide batch nasıl reddedilecek?

## Bağlantılı kayıtlar

- `docs/inbox/TARGET-TRANSACTION-COMMIT.md` — önce o.
- `docs/adr/ADR-0016-analyzer-block-boundary.md` — `SELECT; UPDATE` batch'inin
  neden kabul edildiği.

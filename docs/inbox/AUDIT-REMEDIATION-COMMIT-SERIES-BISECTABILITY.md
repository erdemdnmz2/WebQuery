# Denetim düzeltmesi commit serisi `git bisect` ile güvenilir değil

**Durum:** Inbox / karar bekliyor
**Kaydedildi:** 2026-08-30
**Kapsam:** `feature/security-hardening-implementation` branch'i,
`1112a7f..54ba258` aralığındaki 15 commit
**İlgili:** `docs/handoffs/2026-08-29-audit-remediation-p0-p1-p2.yaml`

2026-08-29 denetim raporunun P0/P1/P2 düzeltmesi, 116 dosyalık tek bir çalışma
ağacından 15 commit'e bölündü. Bölme **modül/alan bazında** yapıldı, bulgu
bazında değil. Bu kayıt, o bölmenin bilinen sınırını ve düzeltilip
düzeltilmeyeceği kararını takip eder. Kod tarafında yapılacak bir şey yok;
`HEAD` doğru ve yeşil.

## Sorun

Serinin **uç noktası** (`54ba258`) doğrulandı: 317 test geçiyor,
`ruff --select F,E9` temiz, frontend'in dört kontrolü de geçiyor,
`docker compose config -q` ve `bash -n entrypoint.sh` geçiyor.

**Ara commit'lerin hepsi yeşil değil.** Ölçüldü, tahmin edilmedi:

| Commit | Konu | `pytest --collect-only` | Tam suite |
| --- | --- | --- | --- |
| `9a2f28d` | denetim raporu | 187 toplandı | ölçülmedi (yalnız doküman) |
| `85ae124` | common: clock, roles, audit | **1 hata** | çalıştırılamadı |
| `24ee98f` | app-db: modeller, migration | 208 toplandı | ölçülmedi |
| `a8c1602` | target-db: bağlantı, engine cache | 217 toplandı | ölçülmedi |
| `525aeef` | query: transaction, parse, masking | 248 toplandı | **3 failed, 245 passed** |
| `014de36` | pipeline: proxy, trace, task | 264 toplandı | ölçülmedi |
| `327a614` | auth: bcrypt, şifre değişimi | 264 toplandı | ölçülmedi |
| `632ad7c` | workspaces: onay bypass | 270 toplandı | **2 failed, 268 passed** |
| `6cf0d4b` | governance: erişim, DB yaşam döngüsü | 301 toplandı | ölçülmedi |
| `bffedcf` | slack: payload sınırı | 305 toplandı | ölçülmedi |
| `821a8bd` | ölü kod temizliği | 305 toplandı | ölçülmedi |
| `0633fa0` | frontend | 305 toplandı | ölçülmedi (backend'e dokunmuyor) |
| `6308055` | dağıtım sertleştirmesi | 317 toplandı | ölçülmedi |
| `8216c31` | CI | 317 toplandı | ölçülmedi (backend'e dokunmuyor) |
| `54ba258` | dokümantasyon | 317 toplandı | **317 passed** |

"Ölçülmedi" satırları için tam suite çalıştırılmadı; her biri ~3,5 dakika ve
serinin tamamı ~50 dakika sürüyor. Yalnız çapraz bağımlılık nedeniyle riskli
görülen iki commit ölçüldü ve ikisi de kırmızı çıktı. Yani ölçülmeyen
commit'lerin yeşil olduğu **varsayılamaz**.

### Somut kırılmalar

**1. `85ae124` — import hatası (tek dosyanın yanlış commit'te olması)**

```
tests/unit/test_audit_log.py:7: in <module>
    from app_database.models import AuditLog, AuditLogImmutableError, Base
E   ImportError: cannot import name 'AuditLogImmutableError' from 'app_database.models'
```

`AuditLogImmutableError` bir sonraki commit'te (`24ee98f`, `models.py`)
geliyor. Bu tek başına önemsiz bir yerleştirme hatası: `test_audit_log.py`
2. commit yerine 3. commit'te olmalıydı.

**2. `525aeef` ve `632ad7c` — imza değişikliğinin çağıranları geride kalıyor**

```
FAILED tests/integration/test_admin_auth.py::test_admin_user_association_and_visibility
FAILED tests/integration/test_advanced_security.py::test_dynamic_data_masking
FAILED tests/integration/test_error_handling_and_trace.py::test_query_execution_error_translation  (yalnız 525aeef)
```

Asıl neden yapısal: `common/security.py` içindeki `columns_to_mask()` bu
seride `columns_to_mask(rules)` → `columns_to_mask(rules, referenced_tables)`
oldu. Üç çağıranı var — `query_execution/services.py`, `workspaces/services.py`
ve `admin/services.py` — ve bunlar üç ayrı commit'e dağıldı. `security.py`'nin
bulunduğu commit'te (`525aeef`) diğer iki çağıran hâlâ eski imzayı kullanıyor.

## Neden böyle oldu

Commit'ler **dosya bütünlüğünde** kuruldu (`git add <dosya>`), hunk
bazında değil. Değişiklik kümesindeki bağımlılık grafiği ise fazla bağlı:

- `query_execution/services.py` tek başına 5-6 farklı bulgunun değişikliğini
  taşıyor (P0-1 transaction, P1-5 streaming, P2-1 hata ayrımı, P2-6 masking).
- `common/security.py`'nin yeni imzası üç farklı modüldeki çağıranlara bağlı.
- `app_database/models.py` hem P1-11 (şifreleme), hem P2-11 (zaman damgası),
  hem P2-20b (role mirror), hem P2-20j (audit değişmezliği) taşıyor.

Bu yüzden "her adımda yeşil" bir sıralama, dosya bütünlüğünde çıkarılamadı.
Handoff'taki özgün öneri commit'leri **bulgu bazında** bölüyordu; o da
uygulanabilir değildi, çünkü tek dosya birden çok bulgu taşıyor ve dosyanın
tamamı commit'lendiğinde "bu commit sadece P0-1'dir" demek yanlış olurdu.
Modül bazında bölme, mesajların dürüst kalmasını sağladı (her commit
`Findings:` satırında içindeki tüm bulguları listeliyor) ama bisect'i feda
etti.

## Sonucu ne?

- **`git bisect` bu aralıkta güvenilir değil.** Kırmızı bir ara commit,
  aranan regresyonu değil bu yerleştirme sorununu gösterebilir.
- Commit-commit inceleme **çalışıyor** ve bölmenin asıl amacı buydu: her
  commit tek bir alanı, kendi testleri ve kendi spec/ADR'siyle birlikte
  taşıyor.
- Uç nokta doğru. Deploy edilen veya merge edilen şey `HEAD`, dolayısıyla
  üretim riski yok.

## Seçenekler

### A. Hiçbir şey yapma, sınırı belgele (varsayılan)

Bu dosya zaten belgeliyor. Maliyeti sıfır. Bedeli: ileride bu aralıkta bir
regresyon aranırsa bisect yanıltır ve bunu bilen birinin uyarması gerekir.

### B. Yalnız `85ae124`'ü düzelt

`tests/unit/test_audit_log.py`'yi 2. commit'ten 3. commit'e taşı
(`git rebase -i 1112a7f`, iki commit'i düzenle). Bir import hatasını kaldırır,
en az riskli müdahale. Ama `525aeef`/`632ad7c` kırmızı kalmaya devam eder,
yani bisect yine güvenilir olmaz. **Yarım çözüm** — asıl faydayı vermez.

### C. Seriyi tamamen yeşil olacak şekilde yeniden kur

Bağımlılık kapanışına göre grupla: `common/security.py` ve üç çağıranı aynı
commit'te olsun, `test_audit_log.py` `models.py` ile birlikte gelsin, vb.
Sonuç muhtemelen 15 değil ~8 commit olur ve bazıları belirgin biçimde büyür
(masking commit'i `admin/services.py` ve `workspaces/services.py`'yi de
yutar, ki onlar kendi bulgularını da taşıyor — yani o bulgular da o commit'e
taşınır).

Bedeli: incelenebilirlik düşer, tam da bölmenin amacı olan şey. Ayrıca
`--force-with-lease` push gerektirir; branch paylaşılmışsa koordinasyon ister.
Her adımın gerçekten yeşil olduğunu göstermek için serinin tamamında tam
suite çalıştırmak gerekir (~50 dk).

### D. Aralığı bisect'e kapat

`.git-blame-ignore-revs` benzeri bir bisect atlama listesi git'te yok, ama
`git bisect skip <aralık>` elle verilebilir. Bu dosyaya atlanacak SHA
listesini yazmak, B veya C'ye göre çok daha ucuz ve bisect'i fiilen
kullanılabilir kılar.

## Öneri

**A + D.** Bu aralıkta bisect ihtiyacı doğarsa aşağıdaki komut yeterli:

```
git bisect skip 85ae124 525aeef 632ad7c
```

C'nin maliyeti (incelenebilirliğin düşmesi + force push + 50 dakika
doğrulama), tek bir branch'in geçmişinde bisect'i mükemmelleştirmenin
değerinden büyük görünüyor. Ama bu bir tercih; karar verilmeden C
uygulanmamalı.

Karar verilirse bu dosya silinir ve sonuç handoff'a yazılır.

## Nasıl yeniden ölçülür

```bash
# toplama (hızlı, ~15 sn tüm seri)
for c in $(git rev-list --reverse 1112a7f..HEAD); do
  git checkout -q $c
  echo "$c $(cd web_api && ../.venv/bin/python -m pytest tests/ --collect-only -q -p no:randomly 2>&1 | tail -1)"
done

# tam suite tek commit (~3,5 dk)
git checkout -q <sha> && cd web_api && ../.venv/bin/python -m pytest tests/ -q -p no:randomly
```

Sonrasında `git checkout feature/security-hardening-implementation` ile
dönmeyi unutmayın; yukarıdaki döngü detached HEAD'de bırakır.

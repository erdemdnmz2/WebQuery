# Trade-off Tablosu

Senaryo: Riskli bir sorgu onaya düştüğünde Slack'e giden bildirimde sorgu
metninin ne kadarının yer alacağı. Sorgu, literal değerler içerebilir (TCKN,
IBAN, e-posta adresi filtreleri); WebQuery bu metni kendi veritabanında
`EncryptedText` ile şifreliyor ve sonuç kümesine maskeleme uyguluyor, ama Slack
kanalı bu kontrollerin hiçbirinin geçerli olmadığı bir dış yüzey.

Baştan tahminimizce en belirleyici kriter: onaylayanın kararı verebilmesi —
göremediği bir sorguyu onaylamak, onay kapısını tamamen anlamsızlaştırır.

| Kriter | 1. Tam sorgu gönderilir | 2. Yalnız metadata + WebQuery bağlantısı | 3. Sorgu literal'leri maskelenip gönderilir |
| --- | --- | --- | --- |
| Performans | Fark yok | Fark yok | Her bildirimde ek parse + yeniden yazma |
| Kompleksite | En düşük; mevcut davranış | Düşük; derin bağlantı üretimi gerekir | Yüksek; AST üzerinden literal değiştirme, her dialect için |
| Ölçeklenebilirlik | Slack 3000 karakter blok sınırına takılır | Sınır sorunu yok | Sınır sorunu yine var |
| Bakım | Yok | Frontend rota sözleşmesine bağımlılık | Analyzer ile birlikte sürekli bakım |
| Maliyet | Yok | Düşük | Orta |
| **Onaylayanın karar verebilmesi** | Tam bilgi | Slack'te hiç bilgi yok; her onay için uygulamaya geçiş | Yanıltıcı: `WHERE tckn = '***'` bir sorgunun kapsamını gizler, onaylayan neyi onayladığını bilmez |
| **Veri çıkışı (hassasiyet)** | Sorgu literal'leri Slack'e çıkar | Hiç veri çıkmaz | Literal'ler çıkmaz ama tablo/kolon adları çıkar |

## Karar

Seçilen alternatif: **1. Tam sorgu gönderilir** (uzunluk sınırıyla).

Gerekçe: Belirleyici kriter onaylayanın karar verebilmesi. Alternatif 3 bu
kriterde alternatif 2'den de kötü: maskelenmiş bir sorgu okunabilir görünür ama
kapsamı gizler, yani onaylayanı yanlış bir güvenle onaylamaya iter. Alternatif 2
güvenlik açısından en temizi, ancak Slack onayının tek amacı olan "kanaldan
hızlı karar" özelliğini ortadan kaldırır; o hâlde Slack entegrasyonunun kendisi
gereksizleşir. Veri çıkışı riski, kanalın erişim kontrolüyle (aşağıda kabul
edilen risk) yönetilir.

# ADR-0019: Slack onay bildiriminin içeriği

## Status

Accepted

## Context

`NotificationService.send_approval_notification` riskli sorgunun **tam metnini**
Slack webhook'una gönderiyor (`slack_integration/schemas.py`,
`create_approval_message`). Bu davranış ilk günden beri var ama hiçbir spec ya
da ADR'de kayıtlı değil; 2026-08-29 denetimi (P2-18) bunu "belgelenmemiş veri
çıkışı" olarak işaretledi.

İki ayrı mesele var:

1. **Karar kaydı yok.** Uygulama içinde şifrelenen ve maskelenen veri, Slack
   kanalında düz metin duruyor. Bu bilinçli bir tasarım tercihi olabilir, ama
   yazılı olmadığı için gözden geçirenin bunu bir sızıntı mı yoksa karar mı
   olduğunu ayırt etmesi imkânsız.
2. **Uzunluk sınırı yok.** Slack, `section` bloğunun metnini 3000 karakterle
   sınırlıyor ve sınırı aşan **tüm payload'ı** reddediyor. Uzun bir sorgu, onay
   bildiriminin hiç ulaşmaması demekti — kullanıcı "onaya gönderildi" cevabı
   alıyor, kanalda hiçbir şey görünmüyor, geriye yalnızca bir `logger.error`
   satırı kalıyordu. Onay kapısı, en uzun (ve tipik olarak en karmaşık)
   sorgularda sessizce çalışmıyordu.

## Decision

1. Riskli sorgunun **tam metni** Slack onay bildirimine dâhil edilmeye devam
   edecek. Bu, kararın kaydıdır; yeni bir davranış değil.
2. Sorgu metni Slack'in blok sınırının altında tutulacak
   (`_QUERY_TEXT_BUDGET = 2700`, `slack_integration/schemas.py`). Sınırı aşan
   sorgunun ilk 2700 karakteri gönderilecek, blok metni bunun kırpıldığını
   söyleyecek ve onaylayanı istek kimliğiyle birlikte WebQuery onay kuyruğuna
   yönlendirecek. Bildirimin hiç gönderilememesi yerine kısmi gönderilmesi
   tercih edilir: onaylayan en azından bir sorgunun beklediğini görür.
3. Slack'e giden hiçbir bildirimde hedef veritabanı **credential**'ı,
   oturum belirteci veya bağlantı dizesi yer almaz. Bu ADR yalnız sorgu
   metnini kapsar.

## Rejected Alternatives

### 1. Yalnız metadata gönderip sorguyu WebQuery'de gösterme

Veri çıkışını sıfırlardı. Reddedilme nedeni: Slack onayının tek gerekçesi
kanaldan hızlı karar vermek; her onay için uygulamaya geçmek gerekiyorsa
bildirimin bir onay butonu taşımasının anlamı kalmaz ve entegrasyon salt bir
haber verme aracına iner. Karar, entegrasyonun varlık sebebini ortadan
kaldırmadan alınmalıydı.

### 2. Sorgu literal'lerini maskeleyip gönderme

`WHERE tckn = '***'` biçiminde bir gövde göndermek. Reddedilme nedeni: teknik
maliyeti yüksek (her dialect için AST üzerinden literal yeniden yazımı) ve
güvenlik açısından yanıltıcı. Onaylayan, maskelenmiş bir `WHERE`'in kaç satırı
kapsadığını göremez; okunabilir görünen ama kapsamı gizleyen bir metin, hiç
metin olmamasından daha risklidir çünkü onaylayanı yanlış bir güvenle "Onayla"ya
iter.

### 3. Kırpma yerine uzun sorgunun bildirimini hiç göndermemek

Mevcut (kazara) davranış. Reddedilme nedeni: onay kapısının en karmaşık
sorgularda sessizce devre dışı kalması, kapının kendisinden daha kötü bir
sonuçtur.

## Consequences

- Slack kanalı, WebQuery'nin şifreleme ve maskeleme sınırının **dışında** bir
  veri yüzeyidir ve bu artık yazılı. Kanalın erişim kontrolü bir dağıtım
  gereksinimidir, isteğe bağlı bir sıkılaştırma değil.
- Uzun sorgular artık bildirimi düşürmüyor; kırpıldıkları bildirimde açıkça
  belirtiliyor.
- `SLACK_URL` yapılandırılmadığında davranış değişmedi: bildirim gönderilmez,
  sorgu yine onay kuyruğuna yazılır ve uygulama içinden onaylanabilir.

## Accepted Risks

- **Slack kanalındaki sorgu metni, WebQuery'nin denetim ve maskeleme
  kontrollerinin kapsamı dışındadır.** Kanalda geçmişe dönük arama yapılabilir,
  mesajlar Slack'in kendi saklama politikasına tabidir ve WebQuery bunları
  silemez. Azaltma: onay kanalı yalnız DB ADMIN yetkisi olan kişilerin bulunduğu
  özel bir kanal olmalıdır; bu bir dağıtım gereksinimi olarak kaydedilmiştir.
- Kırpma sınırı (2700) Slack'in 3000 karakterlik blok sınırına göre seçilmiş
  sabit bir değerdir. Slack sınırı değişirse bu değerin güncellenmesi gerekir;
  aşılırsa bildirim yine reddedilir.

## References

- Spec: yok — mevcut davranışın kaydı; yeni kullanıcıya görünür davranış
  eklenmedi (kırpma notu hariç).
- Denetim: `webquery_denetim_raporu.md` P2-18.
- İlgili: `docs/adr/ADR-0009-audit-log-foundation.md` (uygulama içi denetim
  kaydı, Slack dışıdır).
- Supersedes / Superseded by: yok.

# WebQuery Frontend

Vite + React + TypeScript. Kurumsal SQL sorgu konsolunun arayüzü.

## Çalıştırma

```bash
npm install
npm run dev
```

Dev sunucusu `http://localhost:3000` adresinde açılır ve `/api` isteklerini
`http://localhost:8080` adresindeki backend'e proxy'ler. Backend başka bir
adresteyse `VITE_API_TARGET` ile belirtin.

| Komut | Ne yapar |
| --- | --- |
| `npm run dev` | Geliştirme sunucusu, API proxy'si ile |
| `npm run build` | Üretim derlemesi (`dist/`) |
| `npm run preview` | Derlenmiş çıktıyı yerelde sunar |
| `npm run typecheck` | `tsc --noEmit`, strict mod |
| `npm run audit:contrast` | Paletin WCAG kontrast hedeflerini doğrular |

## Tasarım sistemi

**Arayüzde bir şey değiştirmeden önce [`DESIGN.md`](DESIGN.md) okunur.** Token
ölçekleri, bileşen envanteri, erişilebilirlik sözleşmesi ve yasak listesi
oradadır; aşağıdaki bölüm yalnızca özettir.

Ayrıntılı karar kaydı: `docs/adr/ADR-0010-frontend-design-system.md`.
Davranış sözleşmesi: `docs/specs/SPEC-0010-frontend-design-system.md`.

### Renk anlam taşır

Uygulama kromu akromatik, sıcak grafit tonlarındadır. Kroma yalnızca bir
gözden geçirenin kaçırmaması gereken durum için ayrılmıştır: risk, onay
bekleyen, onaylanmış, reddedilmiş, maskeli. Birincil eylem düğmesi marka rengi
değil maksimum kontrastlı mürekkep rengidir, böylece bir onay düğmesi bir risk
rozetiyle dikkat için yarışmaz. Tek aksan rengi (düşük doygunluklu teal)
yalnızca odak halkası, seçim, aktif gezinme ve marka işareti içindir.

### Token katmanı

`styles/tokens.css` tek kaynaktır. Değerler OKLCH'tir, böylece açık ve koyu
ramplar algısal olarak eşit adımlıdır. Açık tema çıplak `:root` üzerinde
tanımlanır; koyu tema hem `prefers-color-scheme` altında hem de
`:root[data-theme="dark"]` ile yeniden tanımlanır, bu yüzden tema seçici her
iki yönde de kazanır.

`styles/global.css` bu token'ları `@theme inline` ile Tailwind'e bağlar.
`inline` önemlidir: üretilen yardımcı sınıflar değeri kopyalamak yerine CSS
değişkenine referans verir, bu yüzden tema değişimi yeniden derleme
gerektirmez.

Paleti değiştirdikten sonra `npm run audit:contrast` çalıştırın. Betik, her
metin çiftini 4.5:1 ve her kontrol kenarını 3:1 hedefine karşı ölçer ve
karşılanmayan çiftleri isimlendirerek başarısız olur.

### Şekil ve yükseklik

Tek bir yarıçap ölçeği vardır: kontroller 6px, paneller 10px, üst katmanlar
14px. Hap şekli yalnızca durum rozetlerine aittir. Hiyerarşi gölgeyle değil,
dört basamaklı yüzey merdiveni (`sunken` → `canvas` → `surface` → `raised`) ve
saç çizgisi kenarlarla kurulur; gölge yalnızca gerçek üst katmanlara
(iletişim kutusu, menü, bildirim) uygulanır.

### Hareket

Hareket geri bildirimdir, süsleme değil. Süreler 110-260 ms arasındadır ve
yalnızca `transform` ile `opacity` animasyonlanır. `prefers-reduced-motion:
reduce` altında tüm geçişler kapanır.

## Dizin yapısı

```
styles/     token katmanı ve global stil
lib/        tema, oturum, çalışma alanı önbelleği, biçimlendirme, kısayollar
components/ui/    ürüne özgü olmayan primitive'ler
components/app/   ürüne özgü bileşenler (kabuk, düzenleyici, sonuç paneli)
pages/      rota bileşenleri
services/   tek tip API istemcisi
scripts/    kontrast denetimi
```

## Klavye

| Kısayol | Eylem |
| --- | --- |
| `Cmd/Ctrl + K` | Komut paleti |
| `Cmd/Ctrl + Enter` | Sorguyu çalıştır |
| `Cmd/Ctrl + S` | Çalışma alanını kaydet |
| `Tab` (sayfa başında) | İçeriğe atla |
| `Ok tuşları` | Bölme genişliği (ayırıcı odaklıyken), seçici listeleri |

## Çalışma zamanı bağımlılıkları

Uygulama çalışma zamanında hiçbir üçüncü taraf CDN'e istek atmaz. Tailwind,
yazı tipleri ve SQL düzenleyicisi pakete gömülüdür. Bu, kapalı ağ kurulumları
ve tedarik zinciri yüzeyi için bilinçli bir kısıttır; yeni bir CDN bağlantısı
eklemeden önce ADR-0010'a bakın.

# Trade-off Tablosu

Senaryo: WebQuery frontend'i, çalışma zamanında `cdn.tailwindcss.com`,
`cdnjs` (Ace Editor) ve `aistudiocdn.com` (React import map) üzerinden yüklenen
bir tek sayfa uygulamasıydı. Stil, yardımcı sınıflarla dosya dosya tekrar
ediliyordu; tema tek ve sabitti; erişilebilir menü, iletişim kutusu ve seçici
yoktu. Kurumsal bir SQL yönetişim konsolunu tekrar edilebilir biçimde
sürdürebilmek için bir tasarım sistemi tabanı seçilmesi gerekti.

Baştan tahminimizce en belirleyici kriter: tema token'larının tek kaynaktan
yönetilebilmesi ve çalışma zamanında dış ağ bağımlılığı bırakmaması.

| Kriter | 1. Tailwind v4 + CSS token katmanı + Radix primitives | 2. Hazır bileşen kütüphanesi (MUI / Ant Design) | 3. Mevcut CDN Tailwind + elle yazılmış bileşenler |
| --- | --- | --- | --- |
| Performans | İlk yük 150 kB gzip; ağır rotalar tembel yüklenir | Tema motoru ve ikon seti ile daha büyük taban paket | CDN Tailwind çalışma zamanında derler; ilk boya gecikir |
| Kompleksite | Token katmanı + ince sarmalayıcılar; öğrenme yüzeyi dar | Kendi tema/override sistemi öğrenilmeli, kaçış yolları dolambaçlı | Basit görünür, ancak erişilebilirlik elle yeniden yazılır |
| Ölçeklenebilirlik | Yeni bileşen mevcut token'ları tüketir | Kütüphanenin bileşen sınırlarına bağımlı | Her yeni ekran kendi stilini icat eder |
| Bakım | Palet tek dosyada; kontrast betikle denetlenir | Sürüm yükseltmeleri görsel regresyon riski taşır | Sınıf tekrarları dağılır, tutarlılık erozyona uğrar |
| Maliyet | Ek çalışma zamanı bağımlılığı sınırlı | Büyük bağımlılık ağacı | Sıfır kurulum, yüksek gizli maliyet |
| Kapalı ağ / tedarik zinciri (belirleyici) | Tüm varlıklar pakete gömülür, dış istek yok | Paket içinde, ancak yüzey daha geniş | Üç ayrı CDN'e çalışma zamanı bağımlılığı |

## Karar

Seçilen alternatif: `1. Tailwind v4 + CSS token katmanı + Radix primitives`

Gerekçe: Belirleyici kriter kapalı ağ uyumluluğu ve tedarik zinciri yüzeyiydi.
Seçenek 1 tüm varlıkları pakete alır ve `@theme inline` sayesinde üretilen her
yardımcı sınıf CSS değişkenine referans verir; bu da temayı çalışma zamanında
yeniden derleme olmadan değiştirilebilir kılar. Radix, odak tuzağı, kaçış
tuşu, kaydırma kilidi ve etiketleme ilişkilerini bize yazdırmadan verir, ancak
görünümü tamamen bize bırakır; bu, hazır kütüphanelerin görsel kimliğine
mahkum olmadan erişilebilirlik borcunu kapatır.

# ADR-0010: Frontend tasarım sistemi ve çalışma zamanı bağımlılıkları

## Status

Accepted

## Context

Arayüz üç ayrı CDN'e çalışma zamanında bağımlıydı: Tailwind Play CDN, Ace
Editor ve React için bir import map. Bu, kapalı ağ kurulumlarını imkânsız
kılıyor ve üretim veritabanlarına sorgu çalıştıran bir uygulamada gereksiz bir
tedarik zinciri yüzeyi bırakıyordu. `index.html` ayrıca var olmayan bir
`/index.css` dosyasını isteyerek her yüklemede 404 üretiyordu.

Stil katmanında tek bir kaynak yoktu: renkler, yarıçaplar ve gölgeler yardımcı
sınıf olarak dosyalara dağılmıştı. Marka rengi (indigo) ile durum renkleri aynı
görsel ağırlığa sahipti, bu yüzden bir onay düğmesi ile bir risk rozeti aynı
anda dikkat çekiyordu. Menüler, açılır seçiciler ve iletişim kutuları elle
yazılmıştı; odak tuzağı, `Escape` desteği ve `aria` ilişkileri yoktu. Geri
bildirim `window.alert` ve `window.confirm` ile veriliyordu. Ekranların bir
kısmı İngilizce, bir kısmı Türkçeydi.

Ayrıca `@types/react` hiç kurulu değildi; bu yüzden tüm React API'leri `any`
olarak tipleniyor ve tip denetimi gerçekte hiçbir şey doğrulamıyordu.

## Decision

Frontend aşağıdaki temel üzerine yeniden kuruldu:

1. **Token katmanı** (`styles/tokens.css`): OKLCH ile tanımlı, açık ve koyu
   ramplar. Tema, `prefers-color-scheme` ile çözülür ve `data-theme`
   niteliğiyle her iki yönde de geçersiz kılınabilir.
2. **Tailwind v4** (`@tailwindcss/vite`), token'ları `@theme inline` ile
   tüketir; üretilen yardımcı sınıflar CSS değişkenine referans verdiği için
   tema değişimi yeniden derleme gerektirmez.
3. **Radix primitives** (tek `radix-ui` paketi) iletişim kutusu, menü, seçim,
   ipucu, onay kutusu ve bildirim davranışı için. Görünüm tamamen token
   katmanından gelir.
4. **CodeMirror 6** (`@codemirror/lang-sql`), Ace Editor yerine. Tema tamamen
   CSS değişkenleriyle tanımlandığı için düzenleyici, tema değişiminde
   yeniden oluşturulmadan yeniden boyanır; dil lehçesi seçili sunucunun
   teknolojisine göre `Compartment` ile değiştirilir.
5. **Paket içi yazı tipleri** (`@fontsource-variable/geist`,
   `geist-mono`). Tüm sayısal içerik `tabular-nums` kullanır.
6. **Renk anlam taşır kuralı**: krom akromatik, kroma yalnızca duruma ayrılmış,
   birincil eylem mürekkep rengi, tek aksan yalnızca odak/seçim/kimlik için.
7. **Kontrast bütçesi bir betikle zorunlu kılınır**:
   `frontend/scripts/contrast-audit.mjs`, `npm run audit:contrast`.
8. **TypeScript strict** açıldı ve `@types/react` / `@types/react-dom` eklendi.

## Rejected Alternatives

### 1. Hazır bileşen kütüphanesi (MUI, Ant Design, Chakra)

Erişilebilirlik ve bileşen kapsamını hazır verir. Reddedildi: her birinin kendi
tema motoru vardır ve bizim istediğimiz "krom akromatik, kroma yalnızca durum
için" kuralını uygulamak, kütüphanenin varsayılan görsel kimliğine karşı sürekli
override yazmak anlamına gelir. Ayrıca taban paket boyutu, dahili bir konsol
için gereğinden geniş.

### 2. Mevcut CDN kurulumunu koruyup yalnızca stil elden geçirmek

En düşük değişiklik riski. Reddedildi: kapalı ağ kurulumunu ve tedarik zinciri
riskini çözmez, Ace Editor'ın sabit `dracula` teması açık temayla uyumsuz
kalır, ve Tailwind Play CDN üretim için desteklenmez.

### 3. Tailwind'i tamamen bırakıp sade CSS modülleri yazmak

Bağımlılığı sıfırlar. Reddedildi: token katmanı zaten sade CSS; Tailwind'in
kattığı değer, yoğun bir arayüzde aralık ve durum varyantlarını tutarlı
tutmasıdır. Elle CSS'te aynı tutarlılığı korumak, bu boyutta bir yenilemede
görünür bir kazanç sağlamadan iş yükünü artırırdı.

## Consequences

- Çalışma zamanında dış ağ isteği kalmadı; uygulama kapalı ağda çalışabilir.
- Tema değişimi tek bir `data-theme` niteliğiyle olur; hiçbir bileşen kendi
  koyu tema varyantını taşımaz.
- İlk yük 150 kB gzip'e indi; düzenleyici, yönetim ekranı ve elektronik tablo
  kütüphanesi yalnızca gerektiğinde indirilir.
- Palet değişikliği artık denetlenebilir: `npm run audit:contrast` hedefleri
  karşılamayan her çifti isimlendirerek başarısız olur.
- Strict TypeScript, bundan sonraki her frontend değişikliğinde gerçek tip
  hatalarını yakalayacak; daha önce sessizce `any` olan yüzey kapandı.
- `frontend/components/AceEditor.tsx`, `Layout.tsx`, `Modal.tsx` ve rota
  bağlanmamış `pages/ConnectDb.tsx` kaldırıldı. `ConnectDb` hiçbir rotadan
  erişilemiyordu ve var olmayan bir `/api/mssql-connect` uç noktasına istek
  atıyordu.

## Accepted Risks

- Tailwind v4 ve OKLCH modern tarayıcı gerektirir (Safari 16.4+, Chrome 111+).
  Dahili bir konsol için kabul edilebilir; eski tarayıcı desteği gerekirse
  token katmanı sRGB karşılıklarıyla genişletilmelidir.
- Radix ve CodeMirror yeni birinci sınıf bağımlılıklardır; sürüm yükseltmeleri
  görsel regresyon riski taşır. Azaltma: token katmanı bileşenlerin dışındadır,
  bu yüzden yükseltmeler paleti etkilemez.
- Arayüz dili Türkçede birleştirildi. Çok dilli kullanım gerekirse metinler
  bir sözlük katmanına taşınmalıdır; bugün doğrudan bileşenlerin içindedir.
- `xlsx@0.18.5` bilinen güvenlik uyarılarıyla birlikte korundu. Dışa aktarma
  davranışını bozmamak için ayrı bir iş olarak ele alınmalıdır.

## References

- Spec: `docs/specs/SPEC-0010-frontend-design-system.md`
- Supersedes / Superseded by: yok

# WebQuery Tasarım Sistemi

Bu dosya WebQuery arayüzünün anayasasıdır. Bir ekran, bileşen veya stil
değişikliğine başlamadan önce okunur; değişiklik bittiğinde burada yazan bir
kural bozulduysa değişiklik yanlıştır.

Kapsam: yalnızca `frontend/`. Backend sözleşmeleri, rota yapısı ve bilgi
mimarisi bu dosyanın konusu değildir.

İlgili kayıtlar: `docs/specs/SPEC-0010-frontend-design-system.md` (kabul
kriterleri), `docs/adr/ADR-0010-frontend-design-system.md` (teknoloji seçimi ve
reddedilen alternatifler).

---

## 1. Ürünün ne olduğu

WebQuery, kayıtlı veritabanlarına **denetlenebilir** SQL sorguları çalıştırılan
kurumsal bir konsoldur. Kullanıcı sorgu yazar, riskli ifadeler yönetici onayına
düşer, sonuçlar maskeleme kurallarından geçer ve her adım loglanır.

Bunun tasarıma üç doğrudan sonucu vardır:

1. **Yoğunluk yüksek olmalı.** Bu bir pazarlama sayfası değil, günde saatlerce
   açık kalan bir çalışma aracıdır. Boş alan cömertliği burada bilgi kaybıdır.
2. **Durum her zaman görünür olmalı.** Kullanıcı sorgusunun onay bekleyip
   beklemediğini, hangi sütunun maskelendiğini, sonucun kırpılıp
   kırpılmadığını tahmin etmek zorunda kalmamalı.
3. **Yıkıcı eylem asla dekoratif renkle yarışmamalı.** Onay/red kararı veren
   bir yönetici, risk rozetiyle buton arasında bir saniye bile duraksamamalı.

## 2. Çekirdek ilke: renk anlam taşır

**Uygulama kromu akromatiktir.** Sıcak grafit (OKLCH hue 85–95, chroma ≤ 0.008).
Arka planlar, kenarlar, gövde metni, panel başlıkları: hiçbiri renkli değildir.

**Kroma yalnızca üç işe ayrılmıştır:**

| Kullanım | Token ailesi |
| --- | --- |
| Durum: taslak / onay bekliyor / onaylandı / reddedildi / riskli | `--success`, `--warning`, `--danger` |
| Odak, seçim, aktif gezinme, marka işareti | `--accent` (tek hue: 205, teal) |
| SQL sözdizimi vurgusu | `--code-*` |

**Birincil eylem butonu marka rengi değil, mürekkeptir** (`--primary`, sayfadaki
en yüksek kontrastlı nesne). Böylece "Çalıştır" butonu bir durum rozeti gibi
okunmaz; hiyerarşi kontrastla kurulur, renkle değil.

Bu tek kural sistemin geri kalanını türetir. Yeni bir renk eklemek istiyorsanız
önce sorun: bu renk bir **durumu** mu işaretliyor? Hayırsa, akromatik kalır.

## 3. Tasarım kadranları

Bu üç değer bilinçli seçildi; değiştirilmeden önce tartışılmalı.

| Kadran | Değer (0–10) | Anlamı |
| --- | --- | --- |
| Görsel varyans | 3 | Sistematik ve öngörülebilir. Ekranlar birbirine benzer, sürpriz yok. |
| Hareket yoğunluğu | 3 | Hareket geri bildirimdir, dekorasyon değil. 110–260 ms, tek easing. |
| Görsel yoğunluk | 7 | Sıkı bir konsol. 32 px kontrol yüksekliği, 13 px gövde metni. |

## 4. Token katmanı

Tek kaynak: [`styles/tokens.css`](styles/tokens.css). Değerler OKLCH; açık tema
çıplak `:root` üzerinde, koyu tema hem `@media (prefers-color-scheme: dark)`
altında hem de `:root[data-theme='dark']` üzerinde tanımlı, böylece kullanıcı
seçimi her iki yönde de sistem tercihini yener.

[`styles/global.css`](styles/global.css) bu değişkenleri Tailwind v4'e
`@theme inline` ile bağlar. `inline` kritiktir: üretilen utility sınıfı değeri
kopyalamaz, `var(--...)`'a referans verir. Bu yüzden tema değişimi tek bir
attribute yazımıyla, yeniden derleme olmadan çalışır.

### 4.1 Yüzey merdiveni

Dört basamak, aşağıdan yukarı:

| Token | Utility | Nerede |
| --- | --- | --- |
| `--bg-sunken` | `bg-sunken` | Editör alanı, tablo başlığı, devre dışı input. Sayfanın **altında** duran şeyler. |
| `--bg-canvas` | `bg-canvas` | Sayfa zemini. `body` bunu kullanır. |
| `--bg-surface` | `bg-surface` | Panel, kart, satır. İçerik burada yaşar. |
| `--bg-raised` | `bg-raised` | Dialog, menü, popover, toast. Sayfanın **üstünde** duranlar. |

Etkileşim: `--bg-hover` (`bg-hover`), `--bg-active` (`bg-pressed`),
`--bg-selected` (`bg-selected`, tek renkli istisna: seçim accent taşır).

**Kural:** hiyerarşi gölgeyle değil, bu merdiven artı saç çizgisiyle kurulur.
Gölge yalnızca gerçekten üstte yüzen katmanlarda (`shadow-overlay`).

### 4.2 Metin rampası

| Token | Utility | Kullanım | Kontrast hedefi |
| --- | --- | --- | --- |
| `--fg` | `text-fg` | Gövde metni, başlık, veri hücresi | ≥ 4.5:1 |
| `--fg-muted` | `text-muted` | Etiket, ikincil açıklama, ikon | ≥ 4.5:1 |
| `--fg-subtle` | `text-subtle` | Placeholder, satır numarası, yardım metni | ≥ 4.5:1 |
| `--fg-faint` | `text-faint` | **Yalnızca dekoratif**: ayraç, devre dışı glif | denetlenmez |
| `--fg-on-solid` | `text-on-solid` | Dolu renkli zemin üzerindeki metin | ≥ 4.5:1 |

**`text-faint` asla anlam taşıyan metinde kullanılmaz.** Bu tek istisna
bilinçlidir ve `tokens.css` içinde yorumla işaretlidir.

### 4.3 Çizgiler

| Token | Utility | Kullanım |
| --- | --- | --- |
| `--line` | `border-line` | Varsayılan ayraç. Panel kenarı, satır arası. |
| `--line-strong` | `border-line-strong` | Vurgulu ayraç, scrollbar başparmağı. |
| `--control-line` | `border-control-line` | **Etkileşimli kontrolün kenarı.** 3:1'de tutulur (WCAG 1.4.11). |

Bir input, select veya `secondary` buton `border-line` kullanamaz. Kontrolün
sınırı, kontrol olduğunu belli edecek kadar kontrastlı olmak zorundadır.

### 4.4 Durum renkleri

Her durumun dört varyantı var ve hepsi bir arada kullanılır:

```
--success       metin tonu       text-success
--success-soft  yumuşak dolgu    bg-success-soft
--success-line  yumuşak kenar    border-success-line
--success-solid dolu işaret      bg-success-solid  (yalnız nokta/çubuk)
```

Aynı yapı `--warning` ve `--danger` için de geçerlidir. `--info` accent'e
takma addır; ayrı bir bilgi rengi yoktur.

Rozet formülü daima: `text-{tone} bg-{tone}-soft border border-{tone}-line`.

### 4.5 Yarıçap, gölge, hareket, katman

```
--r-xs  4px    ikon butonu, küçük çip, odak halkası yarıçapı
--r-sm  6px    KONTROLLER: buton, input, select, checkbox
--r-md  10px   PANELLER: kart, tablo çerçevesi, bölüm
--r-lg  14px   KATMANLAR: dialog, komut paleti
--r-pill       YALNIZCA durum rozeti ve scrollbar
```

Bu kilitli bir ölçektir. Beşinci bir yarıçap eklemek karışıklık üretir.

```
--dur-fast 110ms   hover, aktif, renk geçişi
--dur      170ms   menü, tooltip, panel açılışı
--dur-slow 260ms   sayfa girişi, dialog
--ease     cubic-bezier(0.2, 0, 0, 1)   tek easing, istisnasız
```

`prefers-reduced-motion: reduce` altında tüm animasyon ve geçiş 1 ms'ye
düşürülür. Hareket geri bildirimden ibaret olduğu için bunun bir maliyeti yok.

```
--z-sticky   20   yapışkan tablo başlığı
--z-nav      30   üst gezinme
--z-overlay  50   dialog arka planı
--z-dialog   60
--z-toast    70
--z-tooltip  80
```

**Hiçbir bileşen kendi z-index'ini uydurmaz.** İhtiyaç varsa buraya eklenir.

## 5. Tipografi

Geist Variable (metin) ve Geist Mono Variable (kod, tanımlayıcı, sayı). İkisi de
`@fontsource-variable` ile **paketin içine gömülü**; CDN yok.

| Rol | Boyut | Ağırlık | Not |
| --- | --- | --- | --- |
| `h1` | 22px | 560 | Sayfa başlığı, sayfada bir tane |
| `h2` | 16px | 560 | Bölüm başlığı |
| `h3` | 14px | 560 | Panel başlığı |
| Gövde | 14px | 400 | `body` varsayılanı |
| Kontrol / tablo | 13px | 400 | Buton, input, hücre |
| Yardım metni | 12px | 400 | `text-subtle` ile |

Başlıklarda `letter-spacing: -0.018em` ve `text-wrap: balance`; paragraflarda
`text-wrap: pretty`.

**Sayılar her yerde `tabular-nums`.** `th`, `td`, `code`, `kbd`, `pre` ve
`[data-numeric]` taşıyan her element otomatik alır. Bu üründe her sayı başka
bir sayıyla karşılaştırılır; hizalanmayan rakam okuma hatası üretir.

`font-feature-settings: 'cv11', 'ss01'` ile tek katlı `a` ve düz `l` açık,
böylece `1`/`l`/`I` karışmaz.

## 6. Boşluk ve düzen

4 px tabanlı Tailwind ölçeği. Pratikte kullanılan değerler: `gap-1.5` (6),
`gap-2` (8), `gap-3` (12), `gap-4` (16), `gap-6` (24).

- Gezinme yüksekliği: `--nav-h` = 56 px, tek satır.
- İçerik genişliği: `--shell-max` = 1440 px.
- Kontrol yükseklikleri: `sm` 28 px, `md` 32 px (varsayılan), `lg` 36 px.

**Liste satırlarında flex-wrap yerine grid.** Birden çok satırda aynı bilginin
farklı x konumunda başlaması taranabilirliği bitirir. Örnek
([`pages/Workspaces.tsx`](pages/Workspaces.tsx)):

```tsx
'grid grid-cols-1 items-center gap-x-4 gap-y-2 px-4 py-3',
'md:grid-cols-[minmax(0,1fr)_15rem_8.5rem_9.5rem]',
```

Mobilde tek sütuna iner, sütun genişlikleri sabit kalır, butonlar sabit
genişlik alır (`w-[6.25rem]`) ki satırlar arasında tırtıklı kenar oluşmasın.

## 7. Bileşen envanteri

### 7.1 Primitifler (`components/ui/`, 18 dosya)

| Dosya | Dışa aktarılan | Notlar |
| --- | --- | --- |
| `Button.tsx` | `Button`, `IconButton` | 5 varyant, 3 boyut, `loading` durumu |
| `Input.tsx` | `Input`, `Textarea`, `ReadonlyValue` | `controlClasses` paylaşır |
| `Select.tsx` | `Select` | Radix Select, `Field` bağlamını okur |
| `Checkbox.tsx` | `Checkbox` | Radix Checkbox |
| `Field.tsx` | `Field`, `useField`, `useOptionalField`, `controlClasses` | Etiket/hata/yardım ilişkilendirmesi |
| `Panel.tsx` | `Panel`, `PanelHeader` | Yüzey + `--r-md` + saç çizgisi |
| `Dialog.tsx` | `Dialog`, `ConfirmDialog` | 4 boyut; `ConfirmDialog` `window.confirm` yerine geçer |
| `Menu.tsx` | `Menu`, `MenuTrigger`, `MenuContent`, `MenuItem`, `MenuRadioGroup`, `MenuRadioItem`, `MenuLabel`, `MenuSeparator` | Radix DropdownMenu |
| `Toast.tsx` | `ToastProvider`, `useToast` | `window.alert` yerine geçer |
| `Tooltip.tsx` | `TooltipProvider`, `Tooltip` | Yalnız ikon butonlarında zorunlu |
| `Badge.tsx` | `Badge`, `Identifier` | `Identifier` mono, sunucu/veritabanı adı için |
| `DataGrid.tsx` | `DataGrid` | Sonuç tablosu |
| `EmptyState.tsx` | `EmptyState` | İkon + başlık + açıklama + eylem |
| `Skeleton.tsx` | `Skeleton`, `SkeletonRows` | Yükleniyor iskeleti |
| `Spinner.tsx` | `Spinner` | Yalnız butonda ve satır içinde |
| `Kbd.tsx` | `Kbd` | Kısayol gösterimi |
| `Picker.tsx` | `Picker` | Aranabilir liste (sunucu/veritabanı seçimi) |
| `SegmentedControl.tsx` | `SegmentedControl` | `role="group"` + `aria-pressed` |

### 7.2 Buton varyantları

```
primary     bg-primary text-primary-fg          Sayfadaki tek asıl eylem
secondary   bg-surface + border-control-line    Varsayılan
ghost       şeffaf, hover'da bg-hover           Araç çubuğu, ikon yanı
danger      şeffaf + border-danger-line         Yıkıcı eylem
quiet       altı çizili bağlantı görünümü       Satır içi ikincil eylem
```

**Bir ekranda birden fazla `primary` buton olamaz.** İki eşit önemde eylem
varsa ikisi de `secondary` olur.

`danger` varyantı dolu değil, kenarlıdır. Silme butonu, ekrandaki en dikkat
çekici nesne olmamalı; onay diyaloğu zaten yıkıcılığı anlatır.

### 7.3 Ürün bileşenleri (`components/app/`)

| Dosya | İşi |
| --- | --- |
| `AppShell.tsx` | 56 px gezinme, atlama bağlantısı, tema menüsü, hesap menüsü, palet tetikleyicisi |
| `AuthLayout.tsx` | Giriş/kayıt için iki sütunlu düzen |
| `BrandMark.tsx` | Geometrik SVG marka işareti |
| `CodeEditor.tsx` | CodeMirror 6, token temalı, lehçe duyarlı |
| `CommandPalette.tsx` | ⌘K; Git / Eylem / Çalışma alanları / Görünüm / Hesap grupları |
| `ResultPanel.tsx` | Sonuç durumları + dışa aktarma menüsü |
| `SplitPane.tsx` | Sürükle veya ok tuşuyla ayarlanır, oran kalıcı, `lg` altında dikey yığılır |
| `admin/*.tsx` | Onaylar, inceleme diyaloğu, maskeleme sekmesi, kimlik bilgisi diyaloğu |

## 8. Durum örüntüleri

Her veri gösteren yüzeyin **dört** durumu vardır ve dördü de yazılmak zorundadır:

| Durum | Ne gösterilir |
| --- | --- |
| Yükleniyor | `SkeletonRows` veya `Skeleton`. Asla ortada dönen tek spinner değil. |
| Boş | `EmptyState`: ne olduğu, neden boş olduğu, sonraki adım. |
| Hata | Satır içi mesaj + yeniden dene eylemi. Toast tek başına yeterli değil. |
| Dolu | İçerik. |

`api.ts` içindeki `errorMessage(error)` her fırlatılan değeri kullanıcıya
gösterilebilir tek bir cümleye çevirir. Ham `Error.message`'ı doğrudan
basmayın.

**Yükleniyor iskeleti gerçek düzeni taklit eder.** Yükleme bittiğinde içerik
yerinden oynamamalı.

## 9. Veri tablosu kuralları

[`components/ui/DataGrid.tsx`](components/ui/DataGrid.tsx):

- Aynı anda 200 satır render edilir, kullanıcı istedikçe artar. Yeni sonuç
  geldiğinde sayaç sıfırlanır (`useEffect(() => setVisible(PAGE), [rows])`).
- Sayısal sütunlar sağa hizalı ve mono; `isNumericColumn()` ile tespit edilir.
- Maskelenmiş sütunlar başlıkta işaretlenir. Kullanıcı gördüğü değerin
  maskelendiğini bilmek zorundadır.
- Bu işaret **yalnızca** yanıttaki `masked_columns` alanından beslenir; istenen
  maskeleme kümesinden değil. İkisi ayrışır: veritabanı yöneticisi için
  maskeleme bilinçli olarak atlanır, o zaman rozet de çıkmamalıdır. Rozeti
  niyetten türetmek, maskelenmemiş veriyi maskeliymiş gibi göstermek demektir.
  Bkz. SPEC-0012 BR-04.
- `NULL`, boş metin ve gerçek değer üç ayrı görünümdür. `formatCell()` bunu
  döndürür; `NULL`'u boş hücre gibi göstermek veri yanlışı üretir.
- Başlık yapışkandır (`.grid-head-cell`), bulanıklık değil opak zemin kullanır.
- Sonuç kırpıldıysa (`truncated`) tablo bunu açıkça söyler.

## 10. Erişilebilirlik sözleşmesi

Bunlar isteğe bağlı değil, kabul kriteri (SPEC-0010 AC-07..AC-10).

1. **Tek odak göstergesi.** `global.css` içinde bir `:focus-visible` kuralı.
   Bileşen bunu kaldıramaz, yerine kendi halkasını koyamaz.
2. **Kontrast.** Metin 4.5:1, kontrol kenarı ve odak halkası 3:1.
   `npm run audit:contrast` 32 renk çiftini iki temada da ölçer, toplam 64 kontrol.
   Token değeri değiştiren her değişiklikte çalıştırılır.
3. **İsimlendirme.** Her ikon butonunun `aria-label`'ı ve `Tooltip`'i var.
   Her form kontrolü `Field` üzerinden etiketiyle ilişkili.
4. **Klavye.** Tüm akış klavyeyle tamamlanabilir. Dialog ve menülerde odak
   tuzağı Radix'ten gelir. `SplitPane` ok tuşlarıyla ayarlanır.
5. **Atlama bağlantısı.** `.skip-link` ilk sekmede görünür ve gerçek içeriğe
   iner.
6. **Hareket.** `prefers-reduced-motion` her animasyonu iptal eder.
7. **Rol dürüstlüğü.** Roving focus uygulamıyorsanız `role="radiogroup"`
   kullanmayın. `SegmentedControl` bu yüzden `role="group"` + `aria-pressed`.

## 11. Klavye haritası

| Kısayol | Etki | Nerede |
| --- | --- | --- |
| `⌘K` / `Ctrl+K` | Komut paletini aç/kapat | Her yerde, metin alanı içinde bile |
| `⌘↵` / `Ctrl+↵` | Sorguyu çalıştır | Studio, RunWorkspace |
| `⌘S` / `Ctrl+S` | Çalışma alanını kaydet | Studio |
| `Esc` | Katmanı kapat | Dialog, menü, palet |

**Çift tetikleme tuzağı:** CodeMirror `Mod-Enter`'ı kendi keymap'inde bağlar.
Pencere seviyesindeki `useHotkey('mod+enter', ...)` bu yüzden
`allowInEditable` **almaz**; alırsa sorgu iki kez çalışır. Bu hata bir kez
yaşandı, tekrarlamayın.

## 12. Yasak listesi

Bunlar "klasik AI tasarımı" izleridir ve bu kod tabanında bulunmamalıdır.

| Yasak | Neden |
| --- | --- |
| Gradient arka plan, glow, blur "blob" | Anlam taşımaz, kroma bütçesini yer |
| Mor/indigo → pembe geçişli marka rengi | Ürünün rengi durum rengidir |
| `uppercase tracking-[0.3em]` mikro etiket | Okunabilirliği düşürür, hiçbir bilgi eklemez |
| Karışık yarıçap (`rounded-3xl` + `rounded-lg` aynı ekranda) | Ölçek Bölüm 4.5'te kilitli |
| Dekoratif renkli nokta, atan gradient nokta | Renk yalnız durum içindir |
| "Initialize / Establish / Purge" gibi sahte teknik dil | Kullanıcı taslak siler, "purge" etmez |
| `window.alert` / `window.confirm` | `useToast` ve `ConfirmDialog` var |
| Yeni z-index sayısı | `--z-*` ölçeğine ekleyin |
| Yeni renk sabiti (hex, rgb) | Token yoksa token ekleyin |
| CDN'den script, font veya stil | Bölüm 14'e bakın |
| Emoji ikon | `@phosphor-icons/react` kullanılır |
| Lucide ikonları | Bu projede Phosphor seçildi, karıştırmayın |

## 13. Dil ve terminoloji

Arayüz **tamamen Türkçedir**. Karışık dil bu üründe daha önce vardı ve
kaldırıldı. Sözlük katmanı yok; metinler bileşenlerin içinde yaşar.

Çalışma alanı durumlarının tek kaynağı
[`lib/workspace-status.ts`](lib/workspace-status.ts):

| Backend değeri | Etiket | Ton |
| --- | --- | --- |
| `saved_in_workspace` | Taslak | neutral |
| `waiting_for_approval` | Onay bekliyor | warning |
| `approved_and_executed` | Onaylandı | success |
| `approved_with_results` | Çalıştırılabilir | success |
| `rejected` | Reddedildi | danger |

Her durumun bir `hint` alanı vardır: kullanıcının bu durumda **ne
yapabileceğini** bir cümleyle anlatır. Yeni bir ekran durum gösterecekse
etiketi ve rengi buradan okur, kendi eşlemesini yazmaz.

Yazım kuralları:

- Butonlar fiil: "Kaydet", "Çalıştır", "Onayla". "Tamam" değil.
- Hata mesajı ne olduğunu ve ne yapılacağını söyler: "Sunucuya ulaşılamıyor.
  Ağ bağlantınızı kontrol edin."
- Teknik terim şişirilmez. "Sorgu çalıştırılıyor", "Sorgu yürütme motoru
  başlatılıyor" değil.

## 14. Backend sözleşmesi

Bu bölüm bir kez gerçekten kayan sözleşmenin tekrar kaymaması içindir. Arayüz
uzun süre, backend'in çoktan değiştirdiği bir API şekliyle konuştu ve hiçbir
şey çalışma anına kadar hata vermedi.

### 14.1 Tek kaynak: `types.ts`

[`types.ts`](types.ts) backend'in Pydantic şemalarını **birebir**, snake_case
alan adlarıyla yansıtır. Alan adını arayüz için güzelleştirmek yasaktır; uyumsuzluk
burada görünmelidir, çalışma anında değil. Yeniden şekillendirme `lib/` altında,
onu yapan kodun yanında yaşar.

### 14.2 Hedef veritabanı uuid ile adreslenir

`servername` ve `database_name` yalnızca **gösterim** içindir. Çalıştırma,
maskeleme kuralı okuma ve çalışma alanı oluşturma çağrılarının hepsi `db_uuid`
ister. Seçim bileşenlerinin `value`'su uuid'dir, etiketi addır.

[`lib/targets.ts`](lib/targets.ts) bu dönüşümü kapsar. Bir çalışma alanının
hedefi kullanıcının yetkileri arasında değilse hedef **boş bırakılır ve
bildirilir**; sessizce başka bir veritabanına düşmek üretim verisinde yanlış
yere sorgu çalıştırmak demektir.

### 14.3 Çalıştırma sonucu tek yerde çözümlenir

`SQLResponse` `{response_type, data, message, error, masked_columns}` döndürür.
`masked_columns`, bu yanıtta **gerçekten** maskelenmiş sütunların adlarını
sonuç satırlarındaki yazımıyla taşır. Satır
sayısı ve kırpma bilgisi İngilizce `message` metninin içindedir
(`"Truncated to MAX_ROW_COUNT_LIMIT (1000)"`, `"42 rows affected"`).

[`lib/execution.ts`](lib/execution.ts) bu metni bir kez ayrıştırıp
`ExecutionOutcome` üretir. Hiçbir ekran `message` içinde arama yapmaz.

### 14.4 Hata zarfı

Servis katmanı hataları `{success, error_code, message, error, trace_id}`
döndürür. `ApiError` bunlardan `code` ve `traceId` alanlarını taşır.

- **`error_code` ile dallanın, mesaj metniyle değil.** Mesaj değişir, kod
  geçmiş veri sözleşmesidir.
- **`QUERY_REJECTED_BY_ANALYZER` bir hata değildir.** Risk analizi sorguyu
  çalışma alanı olarak kaydedip yöneticiye yönlendirmiştir. Arayüz bunu kırmızı
  başarısızlık değil, sarı bekleme durumu olarak gösterir.
- **`QUERY_SYNTAX_ERROR` ile karıştırmayın.** Bu kod, ifadenin hiç
  çözümlenemediğini ve bir rol kararına varılmadığını söyler; çalışma alanı da
  oluşturulmaz. Kullanıcı bir yöneticiyi beklemez, kendi SQL'ine döner.
- `trace_id` kullanıcıya gösterilir; destek talebinde tek bağlayıcı referans odur.

### 14.5 Oturum kendini yeniler

Erişim çerezi kısa ömürlüdür (`ACCESS_TOKEN_EXPIRE_MINUTES`, varsayılan 20
dakika); dönen refresh çerezi saatlerce yaşar. Oturum ortasında gelen 401
neredeyse her zaman "yeni erişim jetonu üret" demektir, "tekrar giriş yap"
değil.

`services/api.ts` içindeki `request`, yönlendirmeden önce bir kez
`POST /api/refresh` dener ve başarılıysa özgün isteği aynı gövdeyle tekrarlar.
Tekrarlanan istek ikinci kez yenileme denemez.

- **Refresh jetonu tek kullanımlıktır.** Aynı anda 401 alan istekler kendi
  yenilemelerini gönderirse biri hariç hepsi bir sonraki isteğin ihtiyaç duyduğu
  jetonu yakar. Bu yüzden uçuştaki tek bir yenileme sözü paylaştırılır
  (`refreshInFlight`).
- **Giriş, kayıt ve yenilemenin kendisi bu yolun dışındadır.** Üçünde de 401
  normal sonuçtur; henüz kurulmamış bir oturum yenilenemez. `skipAuthRedirect`
  bu üçünü işaretler.
- **Arayüz jetonu görmez.** Çerezler `httponly`'dir; yenileme yalnızca çerezle
  çalışır. Jetonu okumaya, saklamaya veya bir gövdeye yazmaya çalışmayın.

### 14.6 Onay kararı geri alınamaz ve gerekçelidir

- **Reddetme gerekçe ister.** Backend 3-500 karakter zorunlu tutar. Arayüz aynı
  kuralı önden uygular ki kullanıcı yazdığını 422 ile kaybetmesin. İstemci
  doğrulaması sunucununkinin yerine geçmez, önüne geçer.
- **Gerekçe talep sahibine gider.** Karar servisi çalışma alanının açıklamasını
  `"Rejected by <yönetici>: <gerekçe>"` olarak yazar ve çalışma alanları listesi
  bu açıklamayı gösterir. Gerekçe alanının yardım metni bunu vaat eder; vaadi
  bozacak bir değişiklik yardım metnini de düzeltmelidir.
- **`APPROVAL_CONFLICT` yeniden denenmez.** Karar sunucuda atomiktir; 409 alan
  taraf yarışı kaybetmiştir. Bayat olan karar değil listedir: uyarı gösterilir,
  diyalog kapanır, liste yenilenir.

### 14.7 Bilinen sözleşme sınırları

| Sınır | Sonuç |
| --- | --- |
| `PUT /api/workspaces/{id}` yalnız `query` ve `status` kabul eder | Ad, açıklama ve hedef arayüzden güncellenemez |
| `GET /api/me` e-posta döndürmez | Hesap menüsü kullanıcı adı ve rol gösterir |
| `POST /api/workspaces` `{success, workspace_id}` döndürür | Oluşturulan kayıt ayrıca okunur |
| `POST /api/admin/associate_user` `user_id` ister, kullanıcı listeleyen endpoint yok | Yetkilendirme ekranı yapılamadı |
| `GET /api/admin/audit_log` var, arayüzü yok | Denetim kayıtları yalnız API'den okunur |

### 14.8 Otomatik denetim

```bash
npm --prefix frontend run audit:api
```

[`scripts/api-contract-audit.mjs`](scripts/api-contract-audit.mjs) `services/api.ts`
içindeki her çağrıyı FastAPI router'larındaki rotalarla karşılaştırır ve
karşılığı olmayan çağrıda sıfırdan farklı çıkış verir. Ayrıca arayüzü olmayan
backend rotalarını bilgi olarak listeler. Endpoint ekleyen veya değiştiren her
işten sonra çalıştırılır.

Bu betik yolu ve metodu doğrular, gövde alanlarını **doğrulamaz**. Gövde
değişikliklerinde ilgili Pydantic şeması hâlâ elle okunmalıdır.

## 15. Kırılmaz teknik kısıtlar

1. **Çalışma zamanında CDN yok.** Bu uygulama üretim veritabanlarını sorgular
   ve kapalı ağda çalışabilmelidir. Font, stil ve script paketin içinde
   gelir. `index.html`'e `<script src="https://...">` eklemek regresyondur.
2. **Tema ilk boyamadan önce uygulanır.** `index.html` içindeki satır içi
   script `localStorage['webquery.theme']` okur. Bu script silinirse koyu tema
   kullanıcısı beyaz bir flaş görür.
3. **TypeScript strict.** `noUnusedLocals`, `noUnusedParameters`,
   `noFallthroughCasesInSwitch` açık. `any` ile susturmayın.
4. **Ağır modüller tembel yüklenir.** Studio, RunWorkspace ve Admin
   `React.lazy`; `xlsx` dinamik `import()`. İlk yük ~150 kB gzip; bunu
   büyüten değişiklik gerekçelendirilmeli.
5. **Rota yapısı sabit.** `/`, `/login`, `/register`, `/editor`,
   `/editor/:id`, `/execute/:id`, `/admin`. HashRouter kullanılıyor.
6. **API sözleşmesi frontend'den değiştirilmez.** Tüm çağrılar
   [`services/api.ts`](services/api.ts) içindeki `api` nesnesinden geçer;
   bileşenler doğrudan `fetch` çağırmaz.

## 16. Yeni bir şey eklerken

Sırayla:

1. **Var olanı kullan.** İhtiyacınız olan şey `components/ui/` içinde büyük
   ihtimalle var. Yoksa, var olanın bir varyantı olarak eklenebilir mi?
2. **Token kullan.** Sabit renk, sabit yarıçap, sabit süre yazmayın.
   İhtiyacınız olan token yoksa `tokens.css`'e ekleyin ve `global.css`'teki
   `@theme inline` bloğuna bağlayın. İkisini birden yapın.
3. **Dört durumu da yaz.** Yükleniyor, boş, hata, dolu.
4. **Klavyeyle dene.** Sekme sırası mantıklı mı, odak görünüyor mu, Esc
   çalışıyor mu?
5. **İki temayı da aç.** Koyu temada kontrast kaybı en sık burada çıkar.
6. **Doğrula:**

```bash
npm --prefix frontend run typecheck && npm --prefix frontend run audit:contrast && npm --prefix frontend run audit:api && npm --prefix frontend run build
```

Bu projede frontend için otomatik test komutu **yoktur**. Test sonucu
uydurmayın; yukarıdaki üç komut artı tarayıcı kontrolü mevcut doğrulama
yüzeyidir.

## 17. Dosya haritası

```
frontend/
├── DESIGN.md            bu dosya
├── README.md            kurulum, komutlar, mimari özet
├── index.html           tema ön-yükleyici, favicon, noscript
├── index.tsx            kök, global.css importu
├── App.tsx              sağlayıcı zinciri, rotalar, guard'lar
├── types.ts             backend sözleşmesinin TypeScript karşılığı
├── styles/
│   ├── tokens.css       TEK renk/ölçek kaynağı
│   └── global.css       Tailwind bağlama + base + components + utilities
├── lib/
│   ├── cn.ts            clsx + tailwind-merge
│   ├── theme.tsx        tema tercihi ve çözümlemesi
│   ├── session.tsx      oturum durumu
│   ├── workspaces.tsx   paylaşılan çalışma alanı önbelleği
│   ├── workspace-status.ts  durum sözlüğü
│   ├── targets.ts       db_uuid <-> sunucu/veritabanı çözümlemesi
│   ├── execution.ts     SQLResponse -> ExecutionOutcome adaptörü
│   ├── format.ts        sayı, boyut, süre, hücre biçimleme
│   ├── hooks.ts         useHotkey, useIsMac, usePersistentState
│   └── export.ts        xlsx ve csv dışa aktarma
├── components/
│   ├── ui/              18 primitif
│   └── app/             ürün bileşenleri + admin/
├── pages/               Workspaces, Studio, RunWorkspace, Admin, Login,
│                        Register, NotFound
├── services/api.ts      tek tip API istemcisi
└── scripts/
    ├── contrast-audit.mjs      WCAG kontrast kapısı
    └── api-contract-audit.mjs  frontend/backend endpoint kapısı
```

## 18. Sonraki oturum için kısa özet

Bir şey değiştirecekseniz dört dosyaya bakmanız yeter:

1. Renk veya ölçek → `styles/tokens.css`
2. Bir kontrolün nasıl göründüğü → `components/ui/` içindeki ilgili dosya
3. Bir ekranın nasıl kurulduğu → `pages/` içindeki ilgili dosya
4. Bir endpoint'in ne kabul ettiği → `services/api.ts` ve `types.ts`

Ve bir kural hatırlayın: **renk anlam taşır.** Eklediğiniz renk bir durumu
işaretlemiyorsa, gri olmalı.

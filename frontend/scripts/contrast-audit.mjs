#!/usr/bin/env node
/**
 * Reads styles/tokens.css and checks every colour pair the product actually
 * renders against its WCAG 2.1 target, in both themes. Run it after touching
 * the palette: `npm run audit:contrast`.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const tokensPath = resolve(here, '..', 'styles', 'tokens.css');

function oklchToSrgb(L, C, H) {
  const h = (H * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const lin = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return lin.map((value) => {
    const clamped = Math.min(1, Math.max(0, value));
    return clamped > 0.0031308 ? 1.055 * clamped ** (1 / 2.4) - 0.055 : 12.92 * clamped;
  });
}

function relativeLuminance([r, g, b]) {
  const channel = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a, b) {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function readBlock(css, marker) {
  const start = css.indexOf(marker);
  if (start === -1) throw new Error(`Block not found: ${marker}`);
  let depth = 0;
  let index = start;
  for (; index < css.length; index += 1) {
    if (css[index] === '{') depth += 1;
    else if (css[index] === '}') {
      depth -= 1;
      if (depth === 0) break;
    }
  }
  const body = css.slice(start, index);
  const tokens = {};
  const pattern = /(--[a-z0-9-]+):\s*oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)/g;
  let match;
  while ((match = pattern.exec(body)) !== null) {
    tokens[match[1]] = [Number(match[2]), Number(match[3]), Number(match[4])];
  }
  return tokens;
}

/* Every pair below corresponds to something the interface really renders. */
const PAIRS = [
  ['--fg', '--bg-canvas', 4.5, 'gövde metni / sayfa'],
  ['--fg', '--bg-surface', 4.5, 'gövde metni / panel'],
  ['--fg', '--bg-sunken', 4.5, 'gövde metni / gömük yüzey'],
  ['--fg-muted', '--bg-canvas', 4.5, 'ikincil metin / sayfa'],
  ['--fg-muted', '--bg-surface', 4.5, 'ikincil metin / panel'],
  ['--fg-subtle', '--bg-canvas', 4.5, 'üçüncül metin / sayfa'],
  ['--fg-subtle', '--bg-surface', 4.5, 'üçüncül metin / panel'],
  ['--fg-subtle', '--bg-sunken', 4.5, 'üçüncül metin / gömük yüzey'],
  ['--fg-subtle', '--bg-raised', 4.5, 'placeholder / açılır katman'],
  ['--control-line', '--bg-surface', 3.0, 'kontrol kenarı / panel'],
  ['--control-line', '--bg-canvas', 3.0, 'kontrol kenarı / sayfa'],
  ['--control-line', '--bg-sunken', 3.0, 'kontrol kenarı / gömük yüzey'],
  ['--control-line', '--bg-raised', 3.0, 'kontrol kenarı / açılır katman'],
  ['--accent', '--bg-canvas', 4.5, 'bağlantı / sayfa'],
  ['--accent', '--bg-surface', 4.5, 'bağlantı / panel'],
  ['--accent', '--accent-soft', 4.5, 'accent rozet'],
  ['--success', '--success-soft', 4.5, 'başarı rozeti'],
  ['--warning', '--warning-soft', 4.5, 'uyarı rozeti'],
  ['--danger', '--danger-soft', 4.5, 'tehlike rozeti'],
  ['--success', '--bg-surface', 4.5, 'başarı metni / panel'],
  ['--warning', '--bg-surface', 4.5, 'uyarı metni / panel'],
  ['--danger', '--bg-surface', 4.5, 'tehlike metni / panel'],
  ['--primary-fg', '--primary', 4.5, 'birincil buton'],
  ['--accent-fg', '--accent', 4.5, 'accent buton'],
  ['--ring', '--bg-canvas', 3.0, 'odak halkası / sayfa'],
  ['--ring', '--bg-surface', 3.0, 'odak halkası / panel'],
  ['--code-keyword', '--bg-sunken', 4.5, 'SQL anahtar kelimesi'],
  ['--code-string', '--bg-sunken', 4.5, 'SQL metin sabiti'],
  ['--code-number', '--bg-sunken', 4.5, 'SQL sayı sabiti'],
  ['--code-comment', '--bg-sunken', 4.5, 'SQL yorumu'],
  ['--code-fn', '--bg-sunken', 4.5, 'SQL fonksiyonu'],
  ['--code-operator', '--bg-sunken', 4.5, 'SQL operatörü'],
];

const css = readFileSync(tokensPath, 'utf8');
const themes = {
  light: readBlock(css, ':root {'),
  dark: readBlock(css, ":root[data-theme='dark'] {"),
};

let failures = 0;
for (const [name, tokens] of Object.entries(themes)) {
  console.log(`\n${name.toUpperCase()}`);
  for (const [fgToken, bgToken, minimum, label] of PAIRS) {
    const fg = tokens[fgToken];
    const bg = tokens[bgToken];
    if (!fg || !bg) {
      failures += 1;
      console.log(`  MISSING  ${label} (${fgToken} / ${bgToken})`);
      continue;
    }
    const value = contrast(oklchToSrgb(...fg), oklchToSrgb(...bg));
    const ok = value >= minimum;
    if (!ok) failures += 1;
    console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${value.toFixed(2).padStart(5)} (min ${minimum.toFixed(1)})  ${label}`);
  }
}

console.log(`\n${failures === 0 ? 'Tüm kontrast hedefleri karşılandı.' : `${failures} kontrast hedefi karşılanmadı.`}`);
process.exit(failures === 0 ? 0 : 1);

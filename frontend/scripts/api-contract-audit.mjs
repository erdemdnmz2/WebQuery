/*
 * Checks that every endpoint the frontend calls exists in the FastAPI routers,
 * and reports backend routes that no screen calls yet.
 *
 * The frontend once drifted onto an API shape the backend had already
 * replaced, and nothing failed until runtime. This script turns that class of
 * mistake back into a build-time error.
 *
 * Run: npm run audit:api
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const clientPath = join(here, '..', 'services', 'api.ts');
const backendRoot = join(here, '..', '..', 'web_api');

/** Path params differ in spelling on each side, so compare their positions. */
function normalise(path) {
  return path
    .replace(/\$\{[^}]*\}/g, '{}')
    .replace(/\{[^}]*\}/g, '{}')
    .replace(/\?.*$/, '')
    .replace(/\/+$/, '');
}

function collectFrontendCalls() {
  const source = readFileSync(clientPath, 'utf8');
  const calls = [];
  // Every endpoint in the client goes through exactly one request<...> call.
  for (const chunk of source.split('request<').slice(1)) {
    const url = /['`](\/api[^'`]*)['`]/.exec(chunk);
    if (!url) continue;
    const method = /method:\s*'([A-Z]+)'/.exec(chunk);
    calls.push({
      method: method ? method[1] : 'GET',
      path: normalise(url[1]),
      raw: url[1],
    });
  }
  return calls;
}

function pythonFiles(dir) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    if (entry === '__pycache__' || entry === 'tests' || entry === 'migrations') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) found.push(...pythonFiles(full));
    else if (entry.endsWith('.py')) found.push(full);
  }
  return found;
}

function collectBackendRoutes() {
  const routes = [];
  for (const file of pythonFiles(backendRoot)) {
    const source = readFileSync(file, 'utf8');
    const prefixMatch = /APIRouter\(\s*prefix\s*=\s*["']([^"']*)["']/.exec(source);
    const prefix = prefixMatch ? prefixMatch[1] : '';
    const pattern = /@(?:router|app)\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']/g;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      routes.push({
        method: match[1].toUpperCase(),
        path: normalise(prefix + match[2]),
        file: relative(backendRoot, file),
      });
    }
  }
  return routes;
}

const calls = collectFrontendCalls();
const routes = collectBackendRoutes();
const routeKeys = new Set(routes.map((route) => `${route.method} ${route.path}`));
const callKeys = new Set(calls.map((call) => `${call.method} ${call.path}`));

let failures = 0;

console.log(`Frontend çağrısı: ${calls.length}  ·  Backend rotası: ${routes.length}\n`);

console.log('FRONTEND -> BACKEND');
for (const call of calls) {
  const key = `${call.method} ${call.path}`;
  const ok = routeKeys.has(key);
  if (!ok) failures += 1;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${call.method.padEnd(6)} ${call.raw}`);
}

/* Only API routes matter here; /health and the static file routes do not. */
const uncalled = routes.filter(
  (route) => route.path.startsWith('/api') && !callKeys.has(`${route.method} ${route.path}`),
);

if (uncalled.length > 0) {
  console.log('\nARAYÜZÜ OLMAYAN BACKEND ROTALARI (bilgi amaçlı)');
  for (const route of uncalled) {
    console.log(`  ---   ${route.method.padEnd(6)} ${route.path}  (${route.file})`);
  }
}

console.log(
  `\n${failures === 0 ? 'Tüm frontend çağrıları bir backend rotasına karşılık geliyor.' : `${failures} çağrının backend karşılığı yok.`}`,
);
process.exit(failures === 0 ? 0 : 1);

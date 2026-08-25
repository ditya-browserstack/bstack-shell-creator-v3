#!/usr/bin/env node
/**
 * Stitch a chrome capture + N screen-content captures into ONE navigable shell — the sidebar
 * switches screens client-side (plain-HTML "photo" multi-screen). Proven live on LCA.
 *
 *   node scripts/assemble-multiscreen.mjs --slug <slug>
 *
 * Expects, under products/<slug>/app-shell/screens/:
 *   chrome.html          the chrome (topbar + rails + sidebar) with an empty <div id="screen-mount">
 *   <screen>.html        one file per screen = the outerHTML of the content region only
 *   screens.json         [{ "slug":"tests","label":"Tests" }, ...]  (sidebar order)
 * Writes products/<slug>/app-shell/multiscreen-shell.html.
 *
 * Hardening from the live LCA run:
 *  - content-wrapper id varies per route (#webapp-content vs #app-main-content) — capture whichever
 *    exists; some routes' wrapper wrongly includes the sidebar, so this PRUNES any chrome that leaked
 *    into a panel (nav/rail/topbar) — panels must be content-only.
 *  - the sidebar's baked "active" state is neutralized; the current screen's nav link gets ms-nav-active.
 */
import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const arg = (f) => process.argv.includes(f) ? process.argv[process.argv.indexOf(f) + 1] : null;
const slug = arg('--slug');
if (!slug) { console.error('assemble-multiscreen: --slug <slug> required'); process.exit(1); }
// --screens-dir / --out let the share build (scrub-for-share.mjs) assemble a scrubbed copy elsewhere
const dir = arg('--screens-dir') || join(SKILL, 'products', slug, 'app-shell', 'screens');
if (!existsSync(dir)) { console.error(`no screens dir: ${dir} — capture screens first (see capture-multiscreen.md)`); process.exit(1); }
const outArg = arg('--out');

// PRODUCT-AGNOSTIC: the prune's chrome selectors come from THIS product's config (chrome.topbar /
// chrome.sidebar the designer filled), plus DesignStack-generic patterns shared across BrowserStack
// products. No product name is hardcoded — a designer's own product works from their own config.
let cfgChrome = {};
try { cfgChrome = (JSON.parse(readFileSync(join(SKILL, 'products', slug, 'product.config.json'), 'utf8')).chrome) || {}; } catch {}

const screens = JSON.parse(readFileSync(join(dir, 'screens.json'), 'utf8'));
// detail-route wiring is DATA-DRIVEN: any screen with "detailFor":"<section>" claims the
// section's row-detail route (e.g. {slug:"test-editor",detailFor:"tests"} => /tests/<id> opens it).
// This replaces the old hardcoded tests->test-editor special-case, so any product wires its own
// detail pages (suite-detail, build-detail, run-report…) just by adding screens.json entries.
const detailMap = {};
for (const s of screens) if (s.detailFor) detailMap[s.detailFor] = s.slug;
let chrome = readFileSync(join(dir, 'chrome.html'), 'utf8');
if (!chrome.includes('id="screen-mount"')) { console.error('chrome.html has no <div id="screen-mount">'); process.exit(1); }
// SCALABLE responsiveness: a snapshot has no viewport meta, so the browser assumes a fixed desktop
// width and the app's own Tailwind breakpoints never fire. Add the meta once so they do.
if (!/name=["']viewport["']/i.test(chrome)) chrome = chrome.replace(/<head([^>]*)>/i, '<head$1><meta name="viewport" content="width=device-width, initial-scale=1">');

const panels = screens.map((s, i) =>
  `<div class="ms-panel" data-screen="${s.slug}"${i ? ' hidden' : ''}>${readFileSync(join(dir, `${s.slug}.html`), 'utf8')}</div>`
).join('\n');
chrome = chrome.replace(/<div id="screen-mount"><\/div>/, `<div id="screen-mount">${panels}</div>`);

const script = `
<style>.ms-panel[hidden]{display:none!important}
/* SCALABLE responsive normalization (product-agnostic, all screens): fit the display and scroll
   genuinely-wide content instead of cropping the page. The app's own breakpoints do the real work. */
html,body{max-width:100vw!important}
body{overflow-x:hidden!important}
#screen-mount,.ms-panel{width:100%!important;max-width:100%!important;overflow-x:auto}
.ms-panel img,.ms-panel svg,.ms-panel video{max-width:100%;height:auto}
.ms-panel table,.ms-panel pre{max-width:100%}</style>
<script>(function(){
  var SLUGS=${JSON.stringify(screens.map((s) => s.slug))};
  var DETAIL=${JSON.stringify(detailMap)};   // { section-slug : detail-screen-slug }
  // Replicate the app's REAL active state (from the live DOM): active link = bg-neutral-strong +
  // text-brand-default; inactive = text-neutral-weak. No invented bar.
  function setActive(a, on){
    a.classList.toggle('bg-neutral-strong', on);
    a.classList.toggle('text-brand-default', on);
    a.classList.toggle('text-neutral-weak', !on);
  }
  function slugOf(a){
    var href=(a.getAttribute('href')||'').split(/[?#]/)[0];
    var segs=href.split('/').filter(Boolean);
    // detail route: /<section>/<id> where the section declared a detail screen (id=6+ alnum/hash or 4+ digits)
    for(var i=1;i<segs.length;i++){
      if(DETAIL[segs[i-1]] && /^([A-Za-z0-9_-]{6,}|[0-9]{4,})$/.test(segs[i])) return DETAIL[segs[i-1]];
    }
    // top-level: the last path segment that is a known screen slug
    for(var j=segs.length-1;j>=0;j--){ if(SLUGS.indexOf(segs[j])>-1) return segs[j]; }
    return null;
  }
  function show(slug){
    document.querySelectorAll('.ms-panel').forEach(function(p){p.hidden=p.getAttribute('data-screen')!==slug;});
    document.querySelectorAll('a[href]').forEach(function(a){ var s=slugOf(a); if(s&&SLUGS.indexOf(s)>-1) setActive(a, s===slug); });
    window.scrollTo(0,0);
  }
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[href]'); if(!a) return; var s=slugOf(a);
    if(s && SLUGS.indexOf(s)>-1){e.preventDefault(); show(s);}
  },true);
  show(SLUGS[0]);
})();</script>`;
chrome = chrome.replace('</body>', script + '</body>');

const out = outArg || join(SKILL, 'products', slug, 'app-shell', 'multiscreen-shell.html');
writeFileSync(out, chrome, 'utf8');

// prune chrome that leaked INTO panels (headless DOM pass) + re-serialize
async function importPlaywright() {
  // product-agnostic: PLAYWRIGHT_CORE env → local install → any npx cache. No hardcoded repo path.
  if (process.env.PLAYWRIGHT_CORE) { try { return await import(pathToFileURL(process.env.PLAYWRIGHT_CORE).href); } catch {} }
  try { return await import('playwright-core'); } catch {}
  const bases = [process.cwd()];
  try { const npx = join(homedir(), '.npm/_npx'); for (const h of readdirSync(npx)) bases.push(join(npx, h, 'node_modules')); } catch {}
  for (const base of bases) {
    try { const req = createRequire(join(base, 'package.json')); return await import(pathToFileURL(req.resolve('playwright-core')).href); } catch {}
    try { const p = join(base, 'playwright-core', 'index.mjs'); if (existsSync(p)) return await import(pathToFileURL(p).href); } catch {}
  }
  return null;
}
// ---- SELF-CONTAINMENT: inline remote images + fonts as data URIs ----
// Phase-A audit: 128 imgs (browser icons, favicons) + the Inter font load from the network, so the
// shell breaks offline — and the share-scrub used to rewrite CDN URLs, breaking them even online.
// Inlining once (dedupe by URL, base64, size-capped) fixes both: data URIs carry no hostnames, so
// neither offline viewing nor the scrub can break them. Skip with --no-inline.
async function inlineAssets(html) {
  if (process.argv.includes('--no-inline')) return { html, inlined: 0, skipped: 0, bytes: 0 };
  const CAP = 400 * 1024; // per asset
  const urls = new Set();
  // img/src, source/srcset, and CSS url(...) in <style> blocks
  for (const m of html.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)) urls.add(m[1]);
  for (const m of html.matchAll(/srcset="([^"]+)"/g)) for (const c of m[1].split(',')) { const u = c.trim().split(/\s+/)[0]; if (/^https?:/.test(u)) urls.add(u); }
  for (const m of html.matchAll(/url\((['"]?)(https?:\/\/[^)'"]+)\1\)/g)) urls.add(m[2]);
  let inlined = 0, skipped = 0, bytes = 0;
  for (const u of urls) {
    if (!/\.(svg|png|jpe?g|gif|webp|ico|woff2?|ttf|otf)(\?|$)/i.test(u) && !/favicons\?/.test(u)) continue;
    try {
      const res = await fetch(u, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) { skipped++; continue; }
      const ct = res.headers.get('content-type') || '';
      if (!/^(image\/|font\/|application\/(font|octet-stream))/.test(ct) && !/\.(woff2?|ttf|svg)(\?|$)/i.test(u)) { skipped++; continue; }
      const buf = Buffer.from(await res.arrayBuffer());
      if (buf.length > CAP) { skipped++; continue; }
      const mime = ct.split(';')[0] || (u.endsWith('.svg') ? 'image/svg+xml' : 'application/octet-stream');
      const dataUri = `data:${mime};base64,${buf.toString('base64')}`;
      html = html.split(u).join(dataUri); // replaces src, srcset, and url() occurrences alike
      inlined++; bytes += buf.length;
    } catch { skipped++; }
  }
  return { html, inlined, skipped, bytes };
}

const pw = await importPlaywright();
if (pw) {
  const chromium = pw.chromium ?? pw.default?.chromium;
  const cache = join(homedir(), 'Library/Caches/ms-playwright');
  let exe;
  if (existsSync(cache)) {
    const d = readdirSync(cache).filter((x) => /^chromium-\d+$/.test(x)).sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))[0];
    for (const l of ['chrome-mac-arm64', 'chrome-mac']) for (const [a, b] of [['Google Chrome for Testing.app', 'Google Chrome for Testing'], ['Chromium.app', 'Chromium']]) {
      const p = join(cache, d || '', l, a, 'Contents/MacOS', b); if (existsSync(p)) exe = p;
    }
  }
  const browser = await chromium.launch(exe ? { executablePath: exe } : {});
  const page = await browser.newPage();
  await page.goto(pathToFileURL(out).href, { waitUntil: 'load' });
  // SEL = this product's chrome selectors (from product.config.json) + DesignStack-generic patterns
  // that hold across BrowserStack products. Built in Node so it carries no hardcoded product name.
  const SEL = [cfgChrome.topbar, cfgChrome.sidebar, 'nav.fixed', '[class*="inset-y-0"]', '[id*="sidenav"]', '[class*="left-0"][class*="z-300"]']
    .filter(Boolean).join(', ');
  const removed = await page.evaluate((SEL) => {
    // Prune only chrome that DUPLICATES the real chrome — never the product-nav sidebar, which
    // legitimately lives inside the content region (it shares `fixed inset-y-0` with the icon rail).
    // Fingerprint every chrome-ish element that sits OUTSIDE the panels (= genuine chrome); then
    // inside panels remove only elements whose fingerprint matches one of those.
    const key = (el) => (el.getAttribute('aria-label') || el.id || (el.className || '').toString().slice(0, 60)).trim();
    const chromeKeys = new Set();
    document.querySelectorAll(SEL).forEach((el) => { if (!el.closest('.ms-panel')) chromeKeys.add(key(el)); });
    let n = 0;
    document.querySelectorAll('.ms-panel').forEach((panel) => {
      panel.querySelectorAll(SEL).forEach((el) => { if (chromeKeys.has(key(el))) { el.remove(); n++; } });
    });
    return n;
  }, SEL);
  const html = '<!DOCTYPE html>' + await page.evaluate(() => document.documentElement.outerHTML);
  await browser.close();
  const inl = await inlineAssets(html);
  writeFileSync(out, inl.html);
  console.log(`assemble-multiscreen: ${screens.length} screens, pruned ${removed} leaked chrome node(s), inlined ${inl.inlined} asset(s) (${Math.round(inl.bytes / 1024)}KB${inl.skipped ? `, ${inl.skipped} skipped` : ''})`);
} else {
  const inl = await inlineAssets(chrome);
  writeFileSync(out, inl.html);
  console.log(`assemble-multiscreen: ${screens.length} screens (playwright unavailable — panels NOT pruned; run the prune manually); inlined ${inl.inlined} asset(s)`);
}
console.log('  wrote', out);

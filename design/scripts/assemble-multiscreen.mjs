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

const screens = JSON.parse(readFileSync(join(dir, 'screens.json'), 'utf8'));
// detail-route wiring is DATA-DRIVEN: any screen with "detailFor":"<section>" claims the
// section's row-detail route (e.g. {slug:"test-editor",detailFor:"tests"} => /tests/<id> opens it).
// This replaces the old hardcoded tests->test-editor special-case, so any product wires its own
// detail pages (suite-detail, build-detail, run-report…) just by adding screens.json entries.
const detailMap = {};
for (const s of screens) if (s.detailFor) detailMap[s.detailFor] = s.slug;
let chrome = readFileSync(join(dir, 'chrome.html'), 'utf8');
if (!chrome.includes('id="screen-mount"')) { console.error('chrome.html has no <div id="screen-mount">'); process.exit(1); }

const panels = screens.map((s, i) =>
  `<div class="ms-panel" data-screen="${s.slug}"${i ? ' hidden' : ''}>${readFileSync(join(dir, `${s.slug}.html`), 'utf8')}</div>`
).join('\n');
chrome = chrome.replace(/<div id="screen-mount"><\/div>/, `<div id="screen-mount">${panels}</div>`);

const script = `
<style>.ms-panel[hidden]{display:none!important}</style>
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
  try { return await import('playwright-core'); } catch {}
  for (const base of [process.cwd(), join(homedir(), 'projects/lcnc-workspace/frontend/packages/design-stack')]) {
    try { const req = createRequire(join(base, 'package.json')); return await import(pathToFileURL(req.resolve('playwright-core')).href); } catch {}
  }
  return null;
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
  const removed = await page.evaluate(() => {
    // Prune only chrome that DUPLICATES the real chrome — never the product-nav sidebar, which
    // legitimately lives inside the content region (it shares `fixed inset-y-0` with the icon rail).
    // Fingerprint every chrome-ish element that sits OUTSIDE the panels (= genuine chrome); then
    // inside panels remove only elements whose fingerprint matches one of those.
    const SEL = '#lcnc-bstack-header, nav.fixed, [class*="inset-y-0"], [id*="sidenav"], [class*="left-0"][class*="z-300"]';
    const key = (el) => (el.getAttribute('aria-label') || el.id || (el.className || '').toString().slice(0, 60)).trim();
    const chromeKeys = new Set();
    document.querySelectorAll(SEL).forEach((el) => { if (!el.closest('.ms-panel')) chromeKeys.add(key(el)); });
    let n = 0;
    document.querySelectorAll('.ms-panel').forEach((panel) => {
      panel.querySelectorAll(SEL).forEach((el) => { if (chromeKeys.has(key(el))) { el.remove(); n++; } });
    });
    return n;
  });
  const html = '<!DOCTYPE html>' + await page.evaluate(() => document.documentElement.outerHTML);
  writeFileSync(out, html);
  await browser.close();
  console.log(`assemble-multiscreen: ${screens.length} screens, pruned ${removed} leaked chrome node(s)`);
} else {
  console.log(`assemble-multiscreen: ${screens.length} screens (playwright unavailable — panels NOT pruned; run the prune manually)`);
}
console.log('  wrote', out);

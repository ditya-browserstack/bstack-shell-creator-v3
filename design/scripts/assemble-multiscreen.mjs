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
const slug = process.argv.includes('--slug') ? process.argv[process.argv.indexOf('--slug') + 1] : null;
if (!slug) { console.error('assemble-multiscreen: --slug <slug> required'); process.exit(1); }
const dir = join(SKILL, 'products', slug, 'app-shell', 'screens');
if (!existsSync(dir)) { console.error(`no screens dir: ${dir} — capture screens first (see capture-multiscreen.md)`); process.exit(1); }

const screens = JSON.parse(readFileSync(join(dir, 'screens.json'), 'utf8'));
let chrome = readFileSync(join(dir, 'chrome.html'), 'utf8');
if (!chrome.includes('id="screen-mount"')) { console.error('chrome.html has no <div id="screen-mount">'); process.exit(1); }

const panels = screens.map((s, i) =>
  `<div class="ms-panel" data-screen="${s.slug}"${i ? ' hidden' : ''}>${readFileSync(join(dir, `${s.slug}.html`), 'utf8')}</div>`
).join('\n');
chrome = chrome.replace(/<div id="screen-mount"><\/div>/, `<div id="screen-mount">${panels}</div>`);

const script = `
<style>.ms-panel[hidden]{display:none!important} .ms-nav-active{box-shadow:inset 3px 0 0 0 #2563eb;background:rgba(37,99,235,.06);border-radius:6px}</style>
<script>(function(){
  var SLUGS=${JSON.stringify(screens.map((s) => s.slug))};
  function show(slug){
    document.querySelectorAll('.ms-panel').forEach(function(p){p.hidden=p.getAttribute('data-screen')!==slug;});
    document.querySelectorAll('a[href]').forEach(function(a){
      var m=(a.getAttribute('href')||'').match(/\\/([a-z-]+)(?:$|[/?#])/);
      a.classList.toggle('ms-nav-active', !!m && m[1]===slug);
    });
    window.scrollTo(0,0);
  }
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[href]'); if(!a) return;
    var m=(a.getAttribute('href')||'').match(/\\/([a-z-]+)(?:$|[/?#])/);
    if(m && SLUGS.indexOf(m[1])>-1){e.preventDefault(); show(m[1]);}
  },true);
  show(SLUGS[0]);
})();</script>`;
chrome = chrome.replace('</body>', script + '</body>');

const out = join(SKILL, 'products', slug, 'app-shell', 'multiscreen-shell.html');
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
    let n = 0;
    document.querySelectorAll('.ms-panel').forEach((panel) => {
      panel.querySelectorAll('#lcnc-bstack-header, nav.fixed, [class*="inset-y-0"], [id*="sidenav"], [class*="left-0"][class*="z-300"]').forEach((el) => { el.remove(); n++; });
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

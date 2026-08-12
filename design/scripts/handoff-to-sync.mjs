#!/usr/bin/env node
/**
 * ONE-COMMAND handoff from design/ (capture) to sync/ (freshness + storyboard).
 *
 *   node scripts/handoff-to-sync.mjs --slug <slug> [--no-shots]
 *
 * Closes two handoff pains without touching Harsh's forked sync/ code:
 *
 *  (1) NO MORE MANUAL PASTE. The multi-screen capture already knows every screen's
 *      name + has each panel's HTML, so we emit a COMPLETE screen map — nav + verify
 *      filled from the capture, no TODO blanks — as products/<slug>/app-shell/
 *      shell-sync-screens.json. That file is the exact shape sync/lib/capture.mjs
 *      already reads (external arg, not the hardcoded storyboard.py SCREENS).
 *
 *  (2) HARSH'S CAMERA ON MY SHELL. sync/lib/capture.mjs is format-agnostic (it clicks
 *      nav labels + asserts `verify` text), so we run it UNMODIFIED against our
 *      plain-HTML multiscreen-shell.html to screenshot every screen, then wrap each
 *      PNG into a self-contained @dsCard preview the Claude Design pane indexes.
 *
 * We deliberately DON'T touch storyboard.py's x-dc component scanner — that needs the
 * Claude Design format (the "deep data" seam), which is out of scope here.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync, readdirSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { homedir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const argv = process.argv.slice(2);
const slug = argv.includes('--slug') ? argv[argv.indexOf('--slug') + 1] : null;
const noShots = argv.includes('--no-shots');
if (!slug) { console.error('handoff-to-sync: --slug <slug> required'); process.exit(1); }

// Prefer the SHARE build — cards feed Claude Design (a shared surface), so they must be scrubbed.
// Fall back to the raw working set only with a loud warning (cards would carry real data).
const appShell = join(SKILL, 'products', slug, 'app-shell');
const shareBuilt = existsSync(join(appShell, 'share', 'multiscreen-shell.html'));
const dir = shareBuilt ? join(appShell, 'share', 'screens') : join(appShell, 'screens');
const shell = shareBuilt ? join(appShell, 'share', 'multiscreen-shell.html') : join(appShell, 'multiscreen-shell.html');
if (!shareBuilt) console.warn('handoff-to-sync: no share/ build — using the RAW shell. Cards will contain real data; run scrub-for-share.mjs first before sharing them.');
if (!existsSync(dir)) { console.error(`no screens dir: ${dir} — run the multi-screen capture first`); process.exit(1); }
const screens = JSON.parse(readFileSync(join(dir, 'screens.json'), 'utf8'));

// ---------- (1) derive a COMPLETE screen map from the capture ----------
const stripTags = (h) => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const oneLine = (h) => stripTags(h).replace(/\{\{[^}]*\}\}/g, '').trim();

const pushUniq = (out, raw) => { const t = oneLine(raw); if (t.length >= 3 && t.length <= 44 && /[A-Za-z]/.test(t) && !out.includes(t)) out.push(t); };
/** Heading texts only (h1-h3) — the most reliably-visible label on a panel. */
function headingsOf(html) {
  const out = [];
  for (const re of [/<h1[^>]*>([\s\S]*?)<\/h1>/gi, /<h2[^>]*>([\s\S]*?)<\/h2>/gi, /<h3[^>]*>([\s\S]*?)<\/h3>/gi]) {
    let m; re.lastIndex = 0; while ((m = re.exec(html))) pushUniq(out, m[1]);
  }
  return out;
}
/** Headings + tabs + buttons — the pool we search for a panel-UNIQUE verify (detail pages). */
function candidatesOf(html) {
  const out = headingsOf(html);
  for (const re of [/<button[^>]*>([\s\S]*?)<\/button>/gi, /role="tab"[^>]*>([\s\S]*?)<\//gi]) {
    let m; re.lastIndex = 0; while ((m = re.exec(html))) pushUniq(out, m[1]);
  }
  return out;
}

/** For a row-detail screen: a short, clickable row TITLE from the parent list (not the whole row). */
function rowLabelFor(section) {
  const f = join(dir, `${section}.html`);
  if (!existsSync(f)) return null;
  const html = readFileSync(f, 'utf8');
  const anchor = html.match(new RegExp(`<a[^>]*href="[^"]*\\/${section}\\/[A-Za-z0-9_-]{6,}"[^>]*>([\\s\\S]*?)<\\/a>`, 'i'));
  if (!anchor) return null;
  // pull the first short "wordy" text node inside the row anchor (skip dates/numbers/whitespace)
  let m; const leaf = /<[^>]+>([^<>{}]{2,40})</g; leaf.lastIndex = 0;
  while ((m = leaf.exec(anchor[1]))) {
    const t = oneLine(m[1]);
    if (t.length >= 2 && t.length <= 40 && /[A-Za-z]/.test(t) && !/^(updated|created|by|on|ago|last)\b/i.test(t)) return t;
  }
  return null;
}

// full stripped text per screen, so we can pick a verify string that is UNIQUE across panels —
// capture.mjs asserts body.innerText.includes(verify), so a non-unique string mislabels a screen.
const panelHtml = Object.fromEntries(screens.map((s) => [s.slug, existsSync(join(dir, `${s.slug}.html`)) ? readFileSync(join(dir, `${s.slug}.html`), 'utf8') : '']));
const panelText = Object.fromEntries(screens.map((s) => [s.slug, oneLine(panelHtml[s.slug])]));
const labelBySlug = Object.fromEntries(screens.map((s) => [s.slug, s.label]));
const softVerify = [];

const map = screens.map((s) => {
  const heads = headingsOf(panelHtml[s.slug]);
  let verify, nav;
  if (s.detailFor) {
    // DETAIL: parent list is shown en route, so verify MUST be panel-unique — else a failed
    // row-click leaves us on the parent and capture.mjs would mislabel it as the detail screen.
    const others = screens.filter((o) => o.slug !== s.slug).map((o) => panelText[o.slug]).join(' ␟ ');
    const cands = candidatesOf(panelHtml[s.slug]);
    verify = cands.find((c) => !others.includes(c));
    if (!verify) { verify = heads[0] || cands[0] || s.label; softVerify.push(s.slug); }
    const parent = labelBySlug[s.detailFor] || s.detailFor;
    const row = rowLabelFor(s.detailFor);
    nav = row ? [parent, row] : [parent]; // best-effort; a miss is reported, not a mislabel (verify is unique)
  } else {
    // TOP-LEVEL: nav=[exact label] shows exactly this panel (others are display:none, out of
    // innerText), so the heading is the most reliable verify — uniqueness is unnecessary.
    verify = heads[0] || candidatesOf(panelHtml[s.slug])[0] || s.label;
    nav = [s.label];
  }
  return { slug: s.slug, title: s.label, group: s.group || 'Screens', nav, gate: s.slug, verify };
});

const mapPath = join(appShell, 'shell-sync-screens.json');
writeFileSync(mapPath, JSON.stringify(map, null, 2) + '\n');
console.log(`handoff: wrote ${mapPath}  (${map.length} screens, complete — no blanks to fill)`);
for (const m of map) console.log(`  ${m.slug.padEnd(14)} nav=${JSON.stringify(m.nav).padEnd(30)} verify=${JSON.stringify(m.verify)}`);
if (softVerify.length) console.log(`  ⚠ no panel-unique verify for: ${softVerify.join(', ')} — capture.mjs may mislabel; give these a distinct heading.`);

if (noShots) { console.log('\nhandoff: --no-shots → skipped screenshots. Feed the file to sync/lib/capture.mjs yourself.'); process.exit(0); }

// ---------- (2) run Harsh's capture.mjs UNMODIFIED against our shell ----------
if (!existsSync(shell)) { console.error(`no shell: ${shell} — run assemble-multiscreen.mjs first`); process.exit(1); }

// locate playwright-core (module) + a chromium binary for capture.mjs's env overrides
function findPlaywrightCore() {
  if (process.env.PLAYWRIGHT_CORE) return process.env.PLAYWRIGHT_CORE;
  const npx = join(homedir(), '.npm/_npx');
  if (existsSync(npx)) {
    for (const h of readdirSync(npx)) {
      const p = join(npx, h, 'node_modules/playwright-core/index.mjs');
      if (existsSync(p)) return p;
    }
  }
  return null;
}
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const sys = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (existsSync(sys)) return sys;
  const cache = join(homedir(), 'Library/Caches/ms-playwright');
  if (existsSync(cache)) {
    const d = readdirSync(cache).filter((x) => /^chromium-\d+$/.test(x)).sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))[0];
    for (const l of ['chrome-mac-arm64', 'chrome-mac']) for (const [a, b] of [['Google Chrome for Testing.app', 'Google Chrome for Testing'], ['Chromium.app', 'Chromium']]) {
      const p = join(cache, d || '', l, a, 'Contents/MacOS', b); if (existsSync(p)) return p;
    }
  }
  return null;
}
const PWC = findPlaywrightCore();
const CHROME = findChrome();
const captureMjs = resolve(SKILL, '..', 'sync', 'lib', 'capture.mjs');
if (!PWC || !CHROME || !existsSync(captureMjs)) {
  console.error(`\nhandoff: screenshots need playwright-core (${PWC ? 'ok' : 'MISSING'}), Chrome (${CHROME ? 'ok' : 'MISSING'}), and sync/lib/capture.mjs (${existsSync(captureMjs) ? 'ok' : 'MISSING'}).`);
  console.error('The screen map above is still valid — feed it to capture.mjs on a machine that has them, or set PLAYWRIGHT_CORE / CHROME_PATH.');
  process.exit(existsSync(captureMjs) ? 0 : 1);
}

const shotsDir = join(appShell, 'shots');
rmSync(shotsDir, { recursive: true, force: true }); mkdirSync(shotsDir, { recursive: true });

// tiny static server so capture.mjs can page.goto(http://…) — the shell is self-contained
const CT = { '.html': 'text/html', '.png': 'image/png', '.css': 'text/css', '.js': 'text/javascript', '.woff2': 'font/woff2' };
const server = createServer((req, res) => {
  const rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '');
  const f = join(appShell, rel || 'multiscreen-shell.html');
  if (!f.startsWith(appShell) || !existsSync(f)) { res.statusCode = 404; return res.end('not found'); }
  const ext = f.slice(f.lastIndexOf('.'));
  res.setHeader('Content-Type', CT[ext] || 'application/octet-stream');
  res.end(readFileSync(f));
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;
const base = `http://127.0.0.1:${port}`;
console.log(`\nhandoff: serving ${appShell} at ${base}, running Harsh's capture.mjs on multiscreen-shell.html …\n`);

const code = await new Promise((res) => {
  const ps = spawn('node', [captureMjs, base, 'multiscreen-shell.html', mapPath, shotsDir],
    { stdio: 'inherit', env: { ...process.env, PLAYWRIGHT_CORE: PWC, CHROME_PATH: CHROME } });
  ps.on('exit', res);
});
server.close();

// ---------- wrap each PNG into a self-contained @dsCard preview ----------
const cardsDir = join(appShell, 'cards');
rmSync(cardsDir, { recursive: true, force: true }); mkdirSync(cardsDir, { recursive: true });
let cards = 0;
const missed = [];
for (const m of map) {
  const png = join(shotsDir, `${m.slug}.png`);
  if (!existsSync(png)) { missed.push(m.slug); continue; }
  const b64 = readFileSync(png).toString('base64');
  const card = `<!-- @dsCard group="${m.group}" -->
<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${m.title}</title>
<style>body{margin:0;background:#fff;font:13px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#111827}
figure{margin:0}img{display:block;width:100%;height:auto;border-bottom:1px solid #E5E7EB}
figcaption{padding:10px 14px;font-weight:600}</style></head>
<body><figure><img alt="${m.title}" src="data:image/png;base64,${b64}"><figcaption>${m.title}</figcaption></figure></body></html>`;
  writeFileSync(join(cardsDir, `${m.slug}-card.html`), card);
  cards++;
}
console.log(`\nhandoff: ${cards}/${map.length} @dsCard preview(s) → ${cardsDir}`);
if (missed.length) console.log(`  NEEDS_SCREENSHOT (capture.mjs could not reach): ${missed.join(', ')}`);
console.log(`  capture.mjs exit=${code}`);

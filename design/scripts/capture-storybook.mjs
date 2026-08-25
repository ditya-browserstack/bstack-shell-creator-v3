#!/usr/bin/env node
/**
 * Capture real design-system markup + the real compiled stylesheet out of a running
 * Storybook, and write one self-contained component sheet.
 *
 * Usage, from packages/design-stack (so playwright-core resolves):
 *   node <skill>/scripts/capture-storybook.mjs --core --dry-run
 *   node <skill>/scripts/capture-storybook.mjs --core
 *   node <skill>/scripts/capture-storybook.mjs --map <path> --out <path>   # product SETUP
 *
 * --core       target the shared DesignStack tier map + core/ outputs.
 * --dry-run    check every story id in the tier map against the live index and exit.
 * --tier N     capture only that tier.
 * --url U      override the Storybook base url.
 * --map P      tier map to read (SETUP passes the product/custom map).
 * --out P      output html path (.css is derived).
 * --manifest P manifest output path.
 * --ds-pkg P   design-system package.json to read the version from.
 * --title T    sheet title (defaults DESIGNSTACK for --core).
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { resolveCaptureOptions } from '../lib/options.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');

// ---------- args ----------
const o = resolveCaptureOptions(process.argv.slice(2), { skillRoot: SKILL, cwd: process.cwd() });
if (o.reusesCore)
  fail(
    `Product "${o.productSlug}" is designSystem:"designstack" — it reuses the shared core, ` +
      `it does not recapture.\n         Copy the core into its app-shell instead:\n` +
      `           cp core/designstack-sheet.html products/${o.productSlug}/app-shell/component-sheet.html\n` +
      `           cp core/designstack-sheet.css  products/${o.productSlug}/app-shell/component-sheet.css\n` +
      `         Only --product with designSystem:"custom" captures its own primitives.`
  );
if (!o.mapPath || !o.outHtml)
  fail('Pass --core, --product <slug> (custom), or --map and --out.');

const map = JSON.parse(readFileSync(o.mapPath, 'utf8'));
const BASE = (o.base || map.storybookUrl || '').replace(/\/$/, '');
const OUT = o.outHtml;
const MANIFEST = o.manifestPath;
const DEFAULT_ROOT = map.defaultRoot || '#storybook-root';
const DRY = o.dry;
const ONLY_TIER = o.onlyTier;

let blocks = map.blocks || [];
if (ONLY_TIER !== null) blocks = blocks.filter((b) => b.tier === ONLY_TIER);

// ---------- helpers ----------
const log = (...a) => console.log(...a);
function fail(m) {
  console.error(`\n  ERROR  ${m}\n`);
  process.exit(1);
}

async function fetchIndex() {
  let res;
  try {
    res = await fetch(`${BASE}/index.json`);
  } catch {
    fail(
      `Storybook is not answering at ${BASE}.\n` +
        `         Start it first:\n` +
        `           nvm use 22.15.0\n` +
        `           cd ~/projects/lcnc-workspace/frontend/packages/design-stack\n` +
        `           ./node_modules/.bin/storybook dev -p 6006 --no-open\n` +
        `         Note: 'storybook --version' is broken in this repo (mixed SB 7/9). 'dev' works.`
    );
  }
  if (!res.ok) fail(`${BASE}/index.json returned HTTP ${res.status}`);
  const json = await res.json();
  return json.entries || json.stories || {};
}

/** playwright-core needs an explicit browser; find the newest installed chromium. */
function findChromium() {
  const cache = join(homedir(), 'Library', 'Caches', 'ms-playwright');
  if (!existsSync(cache)) return null;
  const dirs = readdirSync(cache)
    .filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
  const layouts = ['chrome-mac-arm64', 'chrome-mac'];
  const apps = [
    ['Google Chrome for Testing.app', 'Google Chrome for Testing'],
    ['Chromium.app', 'Chromium']
  ];
  for (const d of dirs) {
    for (const l of layouts) {
      for (const [app, bin] of apps) {
        const exe = join(cache, d, l, app, 'Contents', 'MacOS', bin);
        if (existsSync(exe)) return exe;
      }
    }
  }
  return null;
}

/**
 * playwright-core lives in design-stack's node_modules, not the skill's — and this
 * script is imported from the skill directory, so a bare `import` would resolve
 * against the wrong tree. Resolve it from the cwd instead.
 */
async function importPlaywright() {
  // product-agnostic: PLAYWRIGHT_CORE env → local install → cwd / DESIGNSTACK_PATH → any npx cache.
  if (process.env.PLAYWRIGHT_CORE) { try { return await import(pathToFileURL(process.env.PLAYWRIGHT_CORE).href); } catch {} }
  try { return await import('playwright-core'); } catch { /* not next to the script; try other trees */ }
  const bases = [process.cwd(), process.env.DESIGNSTACK_PATH].filter(Boolean);
  try { const npx = join(homedir(), '.npm/_npx'); for (const h of readdirSync(npx)) bases.push(join(npx, h, 'node_modules')); } catch {}
  for (const base of bases) {
    try { const req = createRequire(join(base, 'package.json')); return await import(pathToFileURL(req.resolve('playwright-core')).href); } catch { /* next */ }
    try { const p = join(base, 'playwright-core', 'index.mjs'); if (existsSync(p)) return await import(pathToFileURL(p).href); } catch { /* next */ }
  }
  return null;
}

async function launch() {
  const pw = await importPlaywright();
  if (!pw) {
    fail(
      'Could not resolve playwright-core.\n' +
        '         Run from a tree that has it (your DesignStack checkout ships it), or point at it:\n' +
        '           PLAYWRIGHT_CORE=/abs/path/to/playwright-core/index.mjs node scripts/capture-storybook.mjs …\n' +
        '           # or: DESIGNSTACK_PATH=~/<your-frontend>/packages/design-stack'
    );
  }
  const chromium = pw.chromium ?? pw.default?.chromium;
  if (!chromium) fail('playwright-core loaded but exposes no chromium export.');

  try {
    return await chromium.launch();
  } catch (e1) {
    const exe = findChromium();
    if (!exe) {
      fail(
        `Could not launch chromium (${e1.message.split('\n')[0]}) and found no installed build.\n` +
          `         Install one:  npx playwright install chromium`
      );
    }
    log(`  using chromium at ${exe}`);
    return await chromium.launch({ executablePath: exe });
  }
}

const esc = (s) => String(s).replace(/--+>/g, '--&gt;');

// ---------- dry run ----------
const index = await fetchIndex();
const total = Object.keys(index).length;
log(`\n  Storybook at ${BASE} — ${total} entries indexed`);

const missing = blocks.filter((b) => !index[b.story]);
const present = blocks.filter((b) => index[b.story]);

if (missing.length) {
  log(`\n  ${missing.length} story id(s) in tier-map no longer exist:`);
  for (const b of missing) log(`    tier ${b.tier}  ${b.block.padEnd(20)} ${b.story}`);
} else {
  log(`  all ${blocks.length} tier-map story ids resolve`);
}

if (DRY) {
  log(`\n  dry run only — nothing captured\n`);
  process.exit(missing.length ? 1 : 0);
}
if (!present.length) fail('Nothing left to capture.');

// ---------- capture ----------
const browser = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const storyUrl = (id) => `${BASE}/iframe.html?id=${encodeURIComponent(id)}&viewMode=story`;

async function gotoStory(id) {
  await page.goto(storyUrl(id), { waitUntil: 'load', timeout: 20000 });
  try {
    await page.waitForFunction(
      (sel) => {
        const el = document.querySelector(sel);
        return el && el.children.length > 0;
      },
      DEFAULT_ROOT,
      { timeout: 60000 }
    );
  } catch (e) {
    const stuck = await page
      .locator('.sb-preparing-story, .sb-preparing-docs')
      .count()
      .catch(() => 0);
    if (stuck) {
      throw new Error(
        'Storybook is stuck preparing the story — it could not load the story module. ' +
          'This is almost always missing sibling workspace packages (react-icons, axios, @amplitude/*). ' +
          'Fix with a full install: SKIP_NPMRC_CHECK=1 corepack pnpm install --force'
      );
    }
    throw e;
  }
}

/** Every rule from every stylesheet, once. This is what makes captured blocks render. */
async function grabCss() {
  return page.evaluate(() =>
    [...document.styleSheets]
      .map((s) => {
        try {
          return [...s.cssRules].map((r) => r.cssText).join('\n');
        } catch {
          return ''; // cross-origin sheet, skip
        }
      })
      .filter(Boolean)
      .join('\n')
  );
}

const captured = [];
const failures = [];
let css = '';

for (const b of present) {
  const root = b.root || DEFAULT_ROOT;
  const states = b.states?.length ? b.states : [{ name: 'default' }];

  for (const st of states) {
    const label = `${b.block}/${st.name}`;
    try {
      await gotoStory(b.story); // reload per state so states don't stack
      if (!css) css = await grabCss();

      if (st.do && st.on) {
        const target = page.locator(`${root} ${st.on}`).first();
        await target.waitFor({ state: 'visible', timeout: 10000 });
        if (st.do === 'hover') await target.hover();
        else if (st.do === 'click') await target.click();
        else if (st.do === 'focus') await target.focus();
        else throw new Error(`unknown state action "${st.do}"`);
        await page.waitForTimeout(400);
      }

      // Open menus/popovers portal outside the story root. Take the root plus any
      // portal siblings — NOT the whole body, which drags in Storybook's own chrome.
      const { html, scope } = await page.evaluate((rootSel) => {
        const rootEl = document.querySelector(rootSel);
        const parts = rootEl ? [rootEl.outerHTML] : [];
        const portals = [...document.body.children].filter(
          (el) =>
            el !== rootEl &&
            !el.className?.toString().startsWith('sb-') &&
            el.tagName !== 'SCRIPT' &&
            el.tagName !== 'STYLE' &&
            el.children.length > 0
        );
        for (const p of portals) parts.push(p.outerHTML);
        return {
          html: parts.join('\n'),
          scope: portals.length ? `${rootSel} + ${portals.length} portal(s)` : rootSel
        };
      }, root);

      captured.push({ ...b, state: st.name, html, scope });
      log(`    ok   ${label}`);
    } catch (e) {
      failures.push({ block: b.block, state: st.name, story: b.story, error: e.message });
      log(`    FAIL ${label} — ${e.message.split('\n')[0]}`);
    }
  }
}

await browser.close();

// ---------- assemble ----------
const dsPkg = o.dsPkgPath || (process.env.DESIGNSTACK_PATH && resolve(process.env.DESIGNSTACK_PATH, 'package.json')) ||
  resolve(homedir(), 'projects/lcnc-workspace/frontend/packages/design-stack/package.json');
const dsVersion = existsSync(dsPkg) ? JSON.parse(readFileSync(dsPkg, 'utf8')).version : 'unknown';

const byTier = new Map();
for (const c of captured) {
  if (!byTier.has(c.tier)) byTier.set(c.tier, []);
  byTier.get(c.tier).push(c);
}

const TIER_NAMES = o.tierNames;

let out = `<!-- ${o.sheetTitle} COMPONENT SHEET — generated, do not hand-edit.
     design-system v${dsVersion} · captured from ${BASE}
     Regenerate: node <skill>/scripts/capture-storybook.mjs

     HOW TO USE THIS FILE
     Copy the markup and class names verbatim. Do not restyle, rename or rebuild.
     The stylesheet below is the real compiled one — link or inline it, never write your own.
     If you need a component that is not in this file, say so instead of inventing one.
-->
<style>
${css}
</style>
<style>
  /* Sheet scaffolding only — NOT part of any component. Do not copy these rules. */
  .sheet-block { position: relative; isolation: isolate; transform: translateZ(0);
    margin: 0 0 28px; padding: 44px 16px 16px; border: 1px solid #d1d5db;
    border-radius: 6px; overflow: auto; background: #fff; }
  .sheet-block > .sheet-label { position: absolute; top: 0; left: 0;
    font: 600 11px/1.9 ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: .04em; text-transform: uppercase; color: #374151;
    background: #f3f4f6; border-bottom: 1px solid #d1d5db;
    border-right: 1px solid #d1d5db; border-radius: 6px 0 6px 0; padding: 2px 10px; }
  .sheet-tier { font: 700 13px/1 ui-monospace, monospace; letter-spacing: .08em;
    color: #111827; background: #fde68a; padding: 8px 12px; margin: 32px 0 16px;
    border-radius: 4px; }
  body { margin: 0; padding: 24px; background: #f9fafb; }
</style>
`;

for (const tier of [...byTier.keys()].sort()) {
  out += `\n<!-- ================= TIER ${tier}: ${TIER_NAMES[tier] || ''} ================= -->\n`;
  out += `<div class="sheet-tier">TIER ${tier} — ${TIER_NAMES[tier] || ''}</div>\n`;
  for (const c of byTier.get(tier)) {
    out += `\n<!-- ${c.block.toUpperCase()} / ${c.state}\n     ${esc(c.comment || '')}\n     story: ${c.story} · captured from: ${c.scope}\n     COPY ONLY THE MARKUP INSIDE .sheet-block — the wrapper and label are sheet furniture. -->\n`;
    const minH = Math.max(Number(c.minHeight) || 0, /portal/.test(c.scope) ? 340 : 0);
    const h = minH ? ` style="min-height:${minH}px"` : '';
    out += `<div class="sheet-block"${h}><span class="sheet-label">${esc(c.block)} / ${esc(c.state)}</span>\n`;
    out += c.html + '\n</div>\n';
  }
}

writeFileSync(OUT, out, 'utf8');

// The wireframe scaffolds <link> this instead of each inlining ~160KB of rules.
const CSS_OUT = o.outCss;
writeFileSync(
  CSS_OUT,
  `/* design-system v${dsVersion} compiled stylesheet, captured from ${BASE}.\n` +
    `   Generated — do not hand-edit. Link this from wireframes; never write your own CSS. */\n` +
    css,
  'utf8'
);

const manifest = {
  designStackVersion: dsVersion,
  storybookUrl: BASE,
  storybookEntries: total,
  captured: captured.map((c) => ({ tier: c.tier, block: c.block, state: c.state, story: c.story })),
  missingStoryIds: missing.map((b) => ({ tier: b.tier, block: b.block, story: b.story })),
  failures,
  notCapturedTiers: [3, 4, 5, 6].filter((t) => !byTier.has(t)),
  sheetBytes: Buffer.byteLength(out)
};
writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2), 'utf8');

log(`\n  sheet     ${OUT}  (${(manifest.sheetBytes / 1024).toFixed(0)} KB)`);
log(`  manifest  ${MANIFEST}`);
log(`  captured  ${captured.length} block/state pairs · ${failures.length} failed\n`);
if (failures.length) process.exitCode = 2;

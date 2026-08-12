#!/usr/bin/env node
/**
 * SELF-CHECK — verify the assembled shell renders each screen FAITHFULLY, before it's shared.
 *
 *   node scripts/self-check.mjs --slug <slug>
 *
 * Runs on the RAW working shell (app-shell/multiscreen-shell.html — real data, so it matches prod
 * apples-to-apples). For every screen it:
 *   1) automated structural gates — catches the failures we actually hit:
 *        BLANK (empty/404 panel) · SPINNER (loading-overlay only) · NO_TOPBAR · NO_SIDEBAR
 *        (the product-nav got pruned) · TRUNCATED (content squished to a narrow column).
 *      Any FAIL exits non-zero → the shell is NOT ready to share until fixed.
 *   2) screenshots each panel to self-check/shell/<slug>.png, and — if a prod reference shot exists
 *      at self-check/prod/<slug>.png (captured live during capture) — writes self-check/compare.html
 *      pairing prod|shell per screen for a vision review (layout fidelity a DOM gate can't judge).
 *
 * Fix loop: FAIL/■ mismatch → fix (re-capture the screen, adjust the prune, strip a loading overlay,
 * widen the container), re-assemble, re-run self-check until green. THEN scrub-for-share + share.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { homedir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const slug = process.argv.includes('--slug') ? process.argv[process.argv.indexOf('--slug') + 1] : null;
if (!slug) { console.error('self-check: --slug <slug> required'); process.exit(1); }

const appShell = join(SKILL, 'products', slug, 'app-shell');
const shell = join(appShell, 'multiscreen-shell.html');
if (!existsSync(shell)) { console.error(`self-check: no shell ${shell} — assemble it first`); process.exit(1); }
const screens = JSON.parse(readFileSync(join(appShell, 'screens', 'screens.json'), 'utf8'));
let cfg = {}; try { cfg = JSON.parse(readFileSync(join(SKILL, 'products', slug, 'product.config.json'), 'utf8')); } catch {}
const TOPBAR = cfg.chrome?.topbar || null;

const outDir = join(appShell, 'self-check');
const shotDir = join(outDir, 'shell');
mkdirSync(shotDir, { recursive: true });
const prodDir = join(outDir, 'prod');

// ---- headless browser (reuse the cache-discovery pattern) ----
async function pw() { try { return await import('playwright-core'); } catch {}
  for (const h of readdirSync(join(homedir(), '.npm/_npx'))) { const p = join(homedir(), '.npm/_npx', h, 'node_modules/playwright-core/index.mjs'); if (existsSync(p)) return import(pathToFileURL(p).href); } return null; }
const mod = await pw();
if (!mod) { console.error('self-check: playwright-core not found — cannot render. Install it or set it up.'); process.exit(1); }
const chromium = mod.chromium ?? mod.default?.chromium;
const sys = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch(existsSync(sys) ? { executablePath: sys } : {});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(pathToFileURL(shell).href, { waitUntil: 'load' });
await page.waitForTimeout(400);

const results = [];
for (const s of screens) {
  // show only this panel
  await page.evaluate((slug) => { document.querySelectorAll('.ms-panel').forEach((p) => { p.hidden = p.getAttribute('data-screen') !== slug; }); window.scrollTo(0, 0); }, s.slug);
  await page.waitForTimeout(200);
  const checks = await page.evaluate(({ slug, TOPBAR }) => {
    const panel = document.querySelector('.ms-panel[data-screen="' + slug + '"]');
    const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 1 && r.height > 1 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
    const text = panel ? panel.innerText.replace(/\s+/g, ' ').trim() : '';
    const spinner = !!(panel && panel.querySelector('[class*="spinner"],[class*="loader"],svg[class*="animate-spin"],[class*="animate-spin"],[role="progressbar"]'));
    const topbar = TOPBAR ? !!document.querySelector(TOPBAR) : true;
    const navRects = [...document.querySelectorAll('nav,aside')].filter(vis).map((el) => el.getBoundingClientRect());
    const hasSidebar = navRects.some((r) => r.left < 150 && r.height > 300 && r.width >= 110 && r.width <= 470);
    let contentRight = 0;
    if (panel) for (const el of panel.querySelectorAll('*')) { if (!vis(el)) continue; const r = el.getBoundingClientRect(); if (r.left > 250 && r.width > 120) contentRight = Math.max(contentRight, r.right); }
    return { textLen: text.length, spinner, topbar, hasSidebar, contentRight: Math.round(contentRight) };
  }, { slug: s.slug, TOPBAR });

  const fails = [], warns = [];
  if (checks.textLen < 40) fails.push('BLANK (panel has almost no text — 404/empty)');
  else if (checks.textLen < 160 && checks.spinner) fails.push('SPINNER (loading overlay only — did not render)');
  if (!checks.topbar) fails.push('NO_TOPBAR (chrome top bar missing)');
  if (!checks.hasSidebar) fails.push('NO_SIDEBAR (product-nav sidebar missing — likely pruned)');
  if (checks.contentRight && checks.contentRight < 760) warns.push(`TRUNCATED (content only reaches x=${checks.contentRight} of 1440 — squished)`);

  await page.screenshot({ path: join(shotDir, `${s.slug}.png`) });
  results.push({ slug: s.slug, label: s.label, fails, warns, checks });
}
await browser.close();

// ---- compare.html (prod | shell) if prod refs exist ----
const havePairs = existsSync(prodDir) && readdirSync(prodDir).some((f) => f.endsWith('.png'));
if (havePairs) {
  const rows = results.map((r) => {
    const prod = join('prod', `${r.slug}.png`); const shot = join('shell', `${r.slug}.png`);
    const hasProd = existsSync(join(prodDir, `${r.slug}.png`));
    const badge = r.fails.length ? '#b91c1c' : r.warns.length ? '#b45309' : '#15803d';
    const verdict = r.fails.length ? 'FAIL: ' + r.fails.join('; ') : r.warns.length ? 'WARN: ' + r.warns.join('; ') : 'OK';
    return `<section><h2>${r.label} <span style="color:${badge}">— ${verdict}</span></h2>
<div class="pair"><figure><figcaption>PROD</figcaption>${hasProd ? `<img src="${prod}">` : '<p style="color:#b45309">no prod reference — capture one during capture</p>'}</figure>
<figure><figcaption>SHELL</figcaption><img src="${shot}"></figure></div></section>`;
  }).join('\n');
  writeFileSync(join(outDir, 'compare.html'), `<!DOCTYPE html><meta charset="utf-8"><title>Self-check — ${slug}</title>
<style>body{margin:0;font:14px/1.5 -apple-system,sans-serif;background:#f3f4f6}h1{padding:16px 24px;margin:0;background:#0b1020;color:#fff;font-size:15px}section{padding:16px 24px;border-bottom:1px solid #e5e7eb}h2{font-size:14px;margin:0 0 8px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}figure{margin:0}figcaption{font-size:11px;color:#6b7280;font-weight:600;margin-bottom:4px}img{width:100%;border:1px solid #e5e7eb;border-radius:8px}</style>
<h1>Self-check — ${slug} · review each PROD↔SHELL pair for layout fidelity</h1>${rows}`);
}

// ---- report + gate ----
console.log(`\nself-check: ${slug} — ${results.length} screen(s)\n`);
let failed = 0;
for (const r of results) {
  const mark = r.fails.length ? '✗ FAIL' : r.warns.length ? '▲ WARN' : '✓ ok  ';
  if (r.fails.length) failed++;
  console.log(`  ${mark}  ${r.slug.padEnd(14)} ${[...r.fails, ...r.warns].join(' · ') || `text=${r.checks.textLen} sidebar=${r.checks.hasSidebar} content→${r.checks.contentRight}`}`);
}
console.log(`\n  screenshots -> ${shotDir}` + (havePairs ? `\n  visual compare -> ${join(outDir, 'compare.html')} (open it, review each pair)` : `\n  (no prod references in ${prodDir} — add them during capture for the visual diff)`));
if (failed) { console.error(`\nself-check: ${failed} screen(s) FAILED structural checks — FIX before sharing (do not scrub-for-share yet).`); process.exit(2); }
console.log(`\nself-check: all screens passed structural checks. Review compare.html, then scrub-for-share.`);

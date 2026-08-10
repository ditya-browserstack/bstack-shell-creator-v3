#!/usr/bin/env node
/**
 * Finalize a captured shell so it is a single self-contained file, safe to hand to shell-sync.
 *
 *   node scripts/finalize-shell.mjs <shell.html> [--slug <slug>]
 *
 * Does three things, then hard-stops on PII:
 *   1. Self-contain fonts — remove @font-face rules that fetch from the network (fonts.gstatic.com
 *      etc.) so the file needs no connection; the DS font-family stacks fall back to system fonts.
 *   2. Ensure the SOLUTION BODY content slot exists (from config chrome.contentSlot when --slug given).
 *   3. Run scrub-gate.mjs — exit non-zero (blocking) if any suspected customer data remains.
 *
 * shell-sync requires "one exported HTML file that opens in a browser"; this guarantees that.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const argv = process.argv.slice(2);
const file = argv.find((a) => a.endsWith('.html'));
const slug = argv.includes('--slug') ? argv[argv.indexOf('--slug') + 1] : null;
if (!file) {
  console.error('finalize-shell: pass a shell .html file');
  process.exit(1);
}

let html = readFileSync(file, 'utf8');
const before = html.length;

// 1. strip network @font-face rules (self-contain). Leaves local/system fallbacks intact.
let removed = 0;
html = html.replace(/@font-face\s*\{[^}]*\}/gi, (block) => {
  if (/https?:\/\/(fonts\.gstatic\.com|fonts\.googleapis\.com|[^)]*\.(woff2?|ttf|otf))/i.test(block)) {
    removed++;
    return '/* @font-face removed for self-containment (system-font fallback) */';
  }
  return block;
});

// 2. ensure a content slot exists
let slotOk = /class="[^"]*(main-slot|lca-main-slot)[^"]*"/.test(html) || /SOLUTION BODY/.test(html);
if (slug) {
  try {
    const cfg = JSON.parse(readFileSync(join(SKILL, 'products', slug, 'product.config.json'), 'utf8'));
    const slotClass = (cfg.chrome && cfg.chrome.contentSlot ? cfg.chrome.contentSlot : '.main-slot').replace(/^\./, '');
    if (!new RegExp(`class="[^"]*${slotClass}[^"]*"`).test(html)) {
      console.warn(`finalize-shell: WARNING — no element with contentSlot ".${slotClass}" found; USE mount will have nowhere to inject.`);
      slotOk = false;
    } else slotOk = true;
  } catch {
    /* no config; skip slot check */
  }
}

writeFileSync(file, html, 'utf8');
console.log(`finalize-shell: removed ${removed} network font rule(s); ${html.length - before} byte delta; slot ${slotOk ? 'ok' : 'MISSING'}`);

// 3. scrub gate — blocking
const gate = spawnSync(process.execPath, [join(SKILL, 'scripts', 'scrub-gate.mjs'), file], { stdio: 'inherit' });
if (gate.status !== 0) {
  console.error('finalize-shell: scrub gate failed — fix the flagged data before handing off.');
  process.exit(2);
}
if (!slotOk) process.exit(3);
console.log('finalize-shell: OK — self-contained, scrubbed, slot present.');

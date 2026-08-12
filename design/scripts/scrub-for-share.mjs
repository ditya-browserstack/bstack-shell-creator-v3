#!/usr/bin/env node
/**
 * SHARE-TIME scrub. Capture stays RAW (real data — best for designing locally); this turns the raw
 * working shell into a scrubbed, gated build that is safe to SHARE (Confluence, the .skill bundle,
 * review hand-offs). Run it before anything leaves your machine.
 *
 *   node scripts/scrub-for-share.mjs --slug <slug>
 *
 * Reads the raw working capture:   products/<slug>/app-shell/screens/*.html  (+ chrome.html, screens.json)
 * Writes the shareable build:      products/<slug>/app-shell/share/screens/*.html
 *                                  products/<slug>/app-shell/share/multiscreen-shell.html
 * Then runs scrub-gate on the share build (HARD STOP — exits non-zero if any PII remains).
 *
 * The raw screens/ are the designer's working data and are gitignored; only share/ is committed/
 * bundled/uploaded. This is the single home for the scrub rules — capture no longer scrubs inline.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const slug = process.argv.includes('--slug') ? process.argv[process.argv.indexOf('--slug') + 1] : null;
if (!slug) { console.error('scrub-for-share: --slug <slug> required'); process.exit(1); }

const appShell = join(SKILL, 'products', slug, 'app-shell');
const rawDir = join(appShell, 'screens');
if (!existsSync(rawDir)) { console.error(`no screens dir: ${rawDir} — capture first`); process.exit(1); }
const shareDir = join(appShell, 'share');
const shareScreens = join(shareDir, 'screens');
rmSync(shareDir, { recursive: true, force: true });
mkdirSync(shareScreens, { recursive: true });

// ---- the ONE canonical scrub (was inline in capture; now share-time only) ----
// SAFE hosts kept as-is; everything customer-shaped -> example.com / fake person.
function scrub(html) {
  return html
    // author name in the <span> right after "... by </span>"  (tests-style markup)
    .replace(/((?:updated|created|modified|shared|added|last edited) by\s*<\/span>\s*<span[^>]*>)[^<]{1,80}(<\/span>)/gi, '$1Sample User$2')
    // "by <Name> on <date>"  (suites/builds-style markup). Allow internal capitals (AbdulQadir),
    // apostrophes/dots/hyphens, and 1–4 name tokens — compound names slipped a stricter pattern.
    .replace(/\bby\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}\s+on\b/g, 'by Sample User on')
    // customer URLs + bare hostnames -> example.com; keep browserstack/example/CDNs
    .replace(/https?:\/\/(?!(?:[a-z0-9-]+\.)*(?:browserstack\.com|example\.com))[a-z0-9.-]+[^\s"'<>]*/gi, 'https://example.com')
    .replace(/\b(?!(?:www\.)?(?:browserstack|example|w3|gstatic|googleapis|schema)\.)([a-z0-9-]+(?:\.[a-z0-9-]+){1,3}\.(?:com|co|io|net|org|in|dev|app|ai))\b/gi, 'example.com')
    // standalone emails (real on config pages as VALUES) -> fake; keep already-safe example.*
    .replace(/[a-zA-Z0-9._%+-]+@(?!example\.(?:com|org|net))[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, 'user@example.com')
    // BrowserStack usernames in "created by" columns (firstlast_XXXXXX) -> fake
    .replace(/\b[a-z][a-z0-9]*_[A-Za-z0-9]{6}\b/g, 'teammate_ab12cd');
}

let count = 0;
for (const f of readdirSync(rawDir)) {
  if (!f.endsWith('.html')) continue;
  const src = readFileSync(join(rawDir, f), 'utf8');
  writeFileSync(join(shareScreens, f), f === 'chrome.html' ? scrub(src) : scrub(src));
  count++;
}
// screens.json carries no page data — copy verbatim
if (existsSync(join(rawDir, 'screens.json'))) writeFileSync(join(shareScreens, 'screens.json'), readFileSync(join(rawDir, 'screens.json'), 'utf8'));
console.log(`scrub-for-share: scrubbed ${count} file(s) -> ${shareScreens}`);

// ---- assemble the shareable shell from the scrubbed screens ----
const shareShell = join(shareDir, 'multiscreen-shell.html');
const asm = spawnSync('node', [join(HERE, 'assemble-multiscreen.mjs'), '--slug', slug, '--screens-dir', shareScreens, '--out', shareShell], { stdio: 'inherit' });
if (asm.status !== 0) { console.error('scrub-for-share: assemble failed'); process.exit(asm.status || 1); }

// ---- HARD GATE the share build (never share what fails) ----
const targets = readdirSync(shareScreens).filter((f) => f.endsWith('.html')).map((f) => join(shareScreens, f));
const gate = spawnSync('node', [join(HERE, 'scrub-gate.mjs'), ...targets, shareShell], { stdio: 'inherit' });
if (gate.status !== 0) {
  console.error('\nscrub-for-share: share build FAILED the gate — do NOT share it. Fix the scrub rules above for the offending markup, then re-run.');
  process.exit(2);
}
console.log(`\nscrub-for-share: SHARE BUILD READY (gate clean) -> ${shareShell}`);
console.log('  This share/ build is the only version to commit, bundle, upload, or hand to review.');

#!/usr/bin/env node
/**
 * Draft a shell-sync "screen map" from a captured shell's sidebar nav — so onboarding shell-sync
 * starts from your real nav instead of cold.
 *
 *   node scripts/screen-map-draft.mjs <shell.html> --slug <slug>
 *
 * shell-sync's screen map is one entry per screen: slug / nav (what to click) / gate (state) /
 * verify (text proving you landed). This drafts slug + nav from the sidebar labels and leaves
 * gate/verify as TODO for the operator to confirm — exactly the "Claude drafts, you confirm" flow
 * shell-sync describes. Output goes to products/<slug>/app-shell/screen-map.draft.md.
 *
 * Built to shell-sync's DOCUMENTED format (Confluence). Confirm field names against the shipped
 * shell-sync.zip before relying on it programmatically.
 */
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const argv = process.argv.slice(2);
const file = argv.find((a) => a.endsWith('.html'));
const slug = argv.includes('--slug') ? argv[argv.indexOf('--slug') + 1] : null;
if (!file || !slug) {
  console.error('screen-map-draft: usage: <shell.html> --slug <slug>');
  process.exit(1);
}
const cfg = JSON.parse(readFileSync(join(SKILL, 'products', slug, 'product.config.json'), 'utf8'));
const sidebarSel = (cfg.chrome && cfg.chrome.sidebar) || 'nav';
const activeNav = (cfg.chrome && cfg.chrome.activeNav) || '';

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
function findChromium() {
  const cache = join(homedir(), 'Library', 'Caches', 'ms-playwright');
  try {
    const dirs = readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
    for (const d of dirs) for (const l of ['chrome-mac-arm64', 'chrome-mac']) for (const [a, b] of [['Google Chrome for Testing.app', 'Google Chrome for Testing'], ['Chromium.app', 'Chromium']]) {
      const exe = join(cache, d, l, a, 'Contents/MacOS', b); if (existsSync(exe)) return exe;
    }
  } catch {}
  return null;
}

const kebab = (s) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

const pw = await importPlaywright();
if (!pw) { console.error('screen-map-draft: playwright-core not resolvable (run from design-stack cwd, or install it)'); process.exit(1); }
const chromium = pw.chromium ?? pw.default?.chromium;
const exe = findChromium();
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage();
await page.goto(pathToFileURL(resolve(file)).href, { waitUntil: 'load' });
const labels = await page.evaluate((sel) => {
  const root = document.querySelector(sel) || document;
  const items = [...root.querySelectorAll('a, button, [role=link], li')]
    .map((el) => (el.textContent || '').replace(/\s+/g, ' ').trim())
    .filter((t) => t && t.length <= 30);
  return [...new Set(items)];
}, sidebarSel);
await browser.close();

if (!labels.length) { console.error('screen-map-draft: no sidebar labels found with selector', sidebarSel); process.exit(2); }

// Emit paste-ready entries for shell-sync's `storyboard.SCREENS` (lib/storyboard.py):
//   { slug, title, group, nav:[labels to click], gate:<sc-if state key>, verify:<text> }
let out = `# ${cfg.product} — storyboard.SCREENS draft (for shell-sync)\n\n`;
out += `Auto-drafted from the captured shell's sidebar (${labels.length} nav items).\n`;
out += `Paste into \`lib/storyboard.py\` \`SCREENS\` in your shell-sync install, then **confirm each**:\n`;
out += `\`nav\` (click labels) is pre-filled; you must set \`gate\` (the \`<sc-if>\` state key the screen\n`;
out += `shows behind) and \`verify\` (text that proves you landed). shell-sync's own check catches wrong ones.\n\n`;
out += `> NOTE: shell-sync boards MULTIPLE screens gated by \`<sc-if>\`. This skill's capture is currently a\n`;
out += `> SINGLE surface, so only the active screen truly exists in the shell today; the rest are nav stubs.\n`;
out += `> Capture the other screens (re-run capture-shell.md per screen) to make them real boards.\n\n`;
out += '```python\nSCREENS = [\n';
for (const label of labels) {
  const active = label === activeNav ? '  # ← the captured surface (real today)' : '';
  out += `    {\n`;
  out += `        "slug": "${kebab(label)}",${active}\n`;
  out += `        "title": "${label}",\n`;
  out += `        "group": "Screens",\n`;
  out += `        "nav": ["${label}"],\n`;
  out += `        "gate": "<TODO: sc-if state key>",\n`;
  out += `        "verify": "<TODO: text on this screen>",\n`;
  out += `    },\n`;
}
out += ']\n```\n';

const dest = join(SKILL, 'products', slug, 'app-shell', 'screen-map.draft.md');
writeFileSync(dest, out, 'utf8');
console.log(`screen-map-draft: wrote ${labels.length} entries → ${dest}`);

/**
 * Walk a packed shell and screenshot every screen in the map.
 *
 *   node lib/capture.mjs <base-url> <packed.html> <screens.json> <shots-dir>
 *
 * Tracked deliberately. This lived in runs/ (gitignored) for two runs and had to
 * be re-derived from prose each time, which is how the leaf-click bug below got
 * reintroduced. The capture logic is load-bearing; it belongs in the skill.
 *
 * Uses playwright-core against the system Chrome rather than Playwright MCP: this
 * takes a dozen full-page screenshots, and through the MCP every one of them would
 * land in the agent's context for no benefit. Locate playwright-core with
 *   find ~/.npm/_npx -maxdepth 6 -type d -name playwright-core
 * and override with PLAYWRIGHT_CORE / CHROME_PATH if the defaults miss.
 */
import { readFileSync } from 'node:fs';

const PW = process.env.PLAYWRIGHT_CORE
  || '/Users/harshkothari/.npm/_npx/9833c18b2d85bc59/node_modules/playwright-core/index.mjs';
const CHROME = process.env.CHROME_PATH
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const [baseUrl, packed, screensPath, shotsDir] = process.argv.slice(2);
if (!baseUrl || !packed || !screensPath || !shotsDir) {
  console.error('usage: node lib/capture.mjs <base-url> <packed.html> <screens.json> <shots-dir>');
  process.exit(2);
}

const { chromium } = await import(PW);
const SCREENS = JSON.parse(readFileSync(screensPath, 'utf8'));
const URL = baseUrl.replace(/\/$/, '') + '/' + packed;

const browser = await chromium.launch({ executablePath: CHROME });

/**
 * Click a label, trying the two levels the shell puts handlers on.
 *
 * Sidebar rows carry their handler on the row div, so clicking the leaf span does
 * nothing useful. Inline affordances like the editor's "@" carry it on the leaf
 * span, and clicking an ancestor never reaches a child's listener. A single
 * strategy silently misses one of the two groups.
 */
async function clickLabel(page, label, strategy) {
  const hit = await page.evaluate(([text, mode]) => {
    const leaf = [...document.querySelectorAll('span,div')]
      .filter((e) => e.childElementCount === 0 && e.textContent.trim() === text)
      .pop();
    if (!leaf) return false;
    const target = mode === 'leaf' ? leaf : (leaf.closest('div[style]') || leaf);
    target.click();
    return true;
  }, [label, strategy]);
  if (hit) return true;
  // Buttons wrapping a Material Symbols span read as "addCreate test suite", so
  // exact-text matching fails on them; has-text is substring-based.
  try {
    await page.locator(`button:has-text("${label}")`).first().click({ timeout: 4000 });
    return true;
  } catch {
    return false;
  }
}

async function attempt(screen, strategy) {
  const page = await browser.newPage({ viewport: { width: 1560, height: 1000 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  try {
    await page.goto(URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    for (const label of screen.nav) {
      if (!await clickLabel(page, label, strategy)) return null;
      await page.waitForTimeout(1100);
    }
    // The verify assertion is what stops a mis-click producing a confidently
    // mislabelled card. Skipping a screen is always better than shooting the
    // wrong one.
    const text = await page.evaluate(() => document.body.innerText);
    if (!text.includes(screen.verify)) return null;
    await page.screenshot({ path: `${shotsDir}/${screen.slug}.png`, fullPage: false });
    return { strategy, errors: errors.filter((e) => !/favicon/i.test(e)) };
  } finally {
    await page.close();
  }
}

const results = [];
for (const screen of SCREENS) {
  let won = null;
  for (const strategy of ['ancestor', 'leaf']) {
    won = await attempt(screen, strategy);
    if (won) break;
  }
  results.push({ slug: screen.slug, won });
  const note = won ? won.strategy + (won.errors.length ? `  ERRORS: ${won.errors.length}` : '') : '';
  console.log(`${won ? 'OK  ' : 'MISS'} ${screen.slug.padEnd(26)} ${note}`);
}

await browser.close();

const missed = results.filter((r) => !r.won);
console.log(`\ncaptured ${results.length - missed.length}/${results.length}`);
if (missed.length) {
  console.log('missed: ' + missed.map((r) => r.slug).join(', '));
  console.log('Report these as NEEDS_SCREENSHOT rather than boarding them.');
}
process.exit(0);

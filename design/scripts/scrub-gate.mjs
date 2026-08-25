#!/usr/bin/env node
/**
 * PII scrub gate — fail the build if a captured artifact still holds real customer data.
 *
 *   node scripts/scrub-gate.mjs <file.html> [<file2.html> ...] [--allow host,host]
 *
 * Live-DOM captures (shell-scaffold.html, app-captured sheet blocks) come from a logged-in
 * product and can carry real emails, customer URLs, account/project ids. Scrubbing is a human
 * step; this gate is the safety net that stops an unscrubbed capture reaching git.
 *
 * Exit 0 = clean · exit 2 = suspected PII found (prints offenders). Never a silent pass.
 */
import { readFileSync } from 'node:fs';

const argv = process.argv.slice(2);
const allowIdx = argv.indexOf('--allow');
const extraAllow = allowIdx !== -1 && argv[allowIdx + 1] ? argv[allowIdx + 1].split(',') : [];

// asset/namespace hosts that are never customer data (kills obvious noise)
const ALLOW_HOSTS = ['example.com', 'example.org', 'example.net', 'localhost',
  'w3.org', 'fonts.gstatic.com', 'fonts.googleapis.com', 'schema.org',
  // asset/stock-photo CDNs — never customer data (stock avatars in the DesignStack core sheet,
  // product asset hosts). Their query strings look like data paths, so exempt them explicitly.
  // first-party BrowserStack (any subdomain) + stock-photo CDN are never customer data. The scrub
  // already PRESERVES browserstack.com URLs, so the gate must agree or it flags first-party links.
  'images.unsplash.com', 'browserstack.com', ...extraAllow];
const ALLOW_EMAIL = /@(example\.(com|org|net))$/i;
// a URL path that looks like it carries a specific entity: encoded spaces, or a 4+ digit id
const DATA_PATH = /[?/][^\s"'<>]*(\+|%20|%2B|\d{4,})/;

const RULES = [
  {
    name: 'email',
    re: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    bad: (m) => !ALLOW_EMAIL.test(m)
  },
  {
    name: 'entity-url', // a real host + a path that encodes a specific project/id/name
    re: /https?:\/\/[^\s"'<>]+/gi,
    bad: (m) => !ALLOW_HOSTS.some((h) => m.includes(h)) && DATA_PATH.test(m)
  },
  {
    // record attribution on RAW html (same-run names)
    name: 'attributed-name',
    re: /\b(updated|created|modified|owned|shared|added|last edited)\s+by\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?/gi,
    bad: () => true
  }
];

// Rules that run on TEXT (tags stripped) — catches names split across tags like
// "updated by</span><a>Malvika Chaudhary</a>", which the raw-HTML rules miss.
const FAKE = /Sample User|Example User/i; // known placeholders — not a leak
const TEXT_RULES = [
  { name: 'attributed-name (text)', re: /\b(updated|created|modified|owned|shared|added|last edited)\s+by\s+[A-Z][a-z]+\s+[A-Z][a-z]+/gi, bad: (m) => !FAKE.test(m) },
  { name: 'record-name+date', re: /[A-Z][a-z]+\s+[A-Z][a-z]+\s+on\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/g, bad: (m) => !FAKE.test(m) }
];

let hits = 0;
const targets = argv.filter((a) => a.endsWith && a.endsWith('.html'));
if (!targets.length) {
  console.error('scrub-gate: pass at least one .html file');
  process.exit(1);
}
for (const f of targets) {
  let html;
  try {
    html = readFileSync(f, 'utf8');
  } catch {
    console.error(`scrub-gate: cannot read ${f}`);
    process.exit(1);
  }
  const text = html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');
  for (const [rules, subject] of [[RULES, html], [TEXT_RULES, text]]) {
    for (const rule of rules) {
      const found = new Set();
      let m;
      rule.re.lastIndex = 0;
      while ((m = rule.re.exec(subject))) if (rule.bad(m[0])) found.add(m[0]);
      for (const v of found) {
        console.error(`  PII? [${rule.name}] ${v}   (${f})`);
        hits++;
      }
    }
  }
}
if (hits) {
  console.error(`\nscrub-gate: ${hits} suspected PII string(s) — scrub before committing. ` +
    `Replace with example.com / fake equivalents, or pass --allow <host> if a match is genuinely safe.\n`);
  process.exit(2);
}
console.log(`scrub-gate: clean (${targets.length} file(s))`);

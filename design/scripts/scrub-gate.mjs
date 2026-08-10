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
  'w3.org', 'fonts.gstatic.com', 'fonts.googleapis.com', 'schema.org', ...extraAllow];
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
  }
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
  for (const rule of RULES) {
    const found = new Set();
    let m;
    rule.re.lastIndex = 0;
    while ((m = rule.re.exec(html))) if (rule.bad(m[0])) found.add(m[0]);
    for (const v of found) {
      console.error(`  PII? [${rule.name}] ${v}   (${f})`);
      hits++;
    }
  }
}
if (hits) {
  console.error(`\nscrub-gate: ${hits} suspected PII string(s) — scrub before committing. ` +
    `Replace with example.com / fake equivalents, or pass --allow <host> if a match is genuinely safe.\n`);
  process.exit(2);
}
console.log(`scrub-gate: clean (${targets.length} file(s))`);

#!/usr/bin/env node
/**
 * Emit a ready-to-use shell-sync onboarding JSON from a product's config.
 *
 *   node scripts/shell-sync-onboard.mjs --slug <slug>
 *
 * Maps products/<slug>/product.config.json (its `shellSync` block + liveUrl + the finalized shell)
 * to the exact shape shell-sync's `lib/onboard.py write` validates:
 *   required: slug, product_name, product_url, ticket_prefix, repos[]
 *   optional: shared_repos[], product_signals[], drop_branch_patterns[], shell_source
 * Writes products/<slug>/app-shell/shell-sync-onboard.json — hand that to:
 *   (in the shell-sync install)  python3 lib/onboard.py write <that file>
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILL = resolve(HERE, '..');
const argv = process.argv.slice(2);
const slug = argv.includes('--slug') ? argv[argv.indexOf('--slug') + 1] : null;
if (!slug) { console.error('shell-sync-onboard: usage: --slug <slug>'); process.exit(1); }

const cfg = JSON.parse(readFileSync(join(SKILL, 'products', slug, 'product.config.json'), 'utf8'));
const ss = cfg.shellSync || {};
const shellPath = join(SKILL, 'products', slug, 'app-shell', 'shell-scaffold.html');

const onboard = {
  slug,
  product_name: cfg.product,
  product_url: cfg.liveUrl,
  ticket_prefix: ss.ticketPrefix,
  repos: ss.repos || [],
  shared_repos: ss.sharedRepos || [],
  product_signals: ss.productSignals || [],
  drop_branch_patterns: ss.dropBranchPatterns || ['main'],
  shell_source: shellPath
};

// mirror shell-sync's onboard.py REQUIRED checks so we fail here with a clear message
const missing = [];
if (!onboard.product_name) missing.push('product (product_name)');
if (!onboard.product_url || !String(onboard.product_url).startsWith('http')) missing.push('liveUrl (product_url, must be http…)');
if (!onboard.ticket_prefix) missing.push('shellSync.ticketPrefix');
if (!onboard.repos.length) missing.push('shellSync.repos (at least one owner/name)');
for (const r of [...onboard.repos, ...onboard.shared_repos])
  if (!/^[^/]+\/[^/]+$/.test(r)) missing.push(`repo "${r}" must be owner/name`);
if (onboard.shared_repos.length && !onboard.product_signals.length)
  missing.push('shellSync.productSignals (required when sharedRepos is set — else you harvest another team\'s work)');
if (!existsSync(shellPath)) missing.push(`shell not found at ${shellPath} — run SETUP + finalize-shell first`);

if (missing.length) {
  console.error('shell-sync-onboard: cannot emit a valid onboard JSON — fill these in product.config.json:');
  for (const m of missing) console.error('  - ' + m);
  process.exit(2);
}

const dest = join(SKILL, 'products', slug, 'app-shell', 'shell-sync-onboard.json');
writeFileSync(dest, JSON.stringify(onboard, null, 2) + '\n', 'utf8');
console.log(`shell-sync-onboard: wrote ${dest}`);
console.log('Next (in your shell-sync install):  python3 lib/onboard.py write ' + dest);

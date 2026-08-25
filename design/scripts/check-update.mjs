#!/usr/bin/env node
/**
 * STEP-0 UPDATE CHECK — the "auto-update" mechanism.
 *
 *   node design/scripts/check-update.mjs
 *
 * There is no push daemon; instead the SKILL router runs this at the top of every invocation. It
 * compares the local install to its git origin and, if newer commits exist, prints one line the
 * agent relays to the user with the offer to update. Git-based so it works on private repos over the
 * colleague's existing SSH/GH access — no tokens here.
 *
 * Safe by construction: throttled to once/24h, hard 6s timeout, and FAILS SILENT (exit 0, no output)
 * on anything unexpected — not a git checkout, no origin, offline, detached HEAD. A flaky network
 * must never block the skill.
 *
 * Prints exactly one machine-readable line when an update exists:
 *   UPDATE_AVAILABLE <remoteVersion> (<n> commit(s) behind) :: <changelog headline>
 *   UPDATE_CMD git -C "<root>" pull --ff-only
 * Prints nothing (exit 0) when up to date or when checking isn't possible.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..'); // design/scripts -> skill root
const FORCE = process.argv.includes('--force');
const git = (args, timeout = 6000) => execFileSync('git', ['-C', ROOT, ...args], { timeout, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();

try {
  // must be a git checkout with an upstream, else nothing to compare
  if (git(['rev-parse', '--is-inside-work-tree']) !== 'true') process.exit(0);
  let upstream;
  try { upstream = git(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']); } catch { process.exit(0); }

  // throttle: at most once / 24h (skip with --force). Stamp is gitignored.
  const stamp = join(ROOT, '.last-update-check');
  if (!FORCE && existsSync(stamp)) {
    const ageH = (Date.now() - statSync(stamp).mtimeMs) / 3.6e6;
    if (ageH < 24) process.exit(0);
  }
  try { writeFileSync(stamp, new Date().toISOString()); } catch {}

  git(['fetch', '--quiet', '--no-tags', 'origin']); // may throw offline -> caught below
  const behind = parseInt(git(['rev-list', '--count', `HEAD..${upstream}`]) || '0', 10);
  if (!behind) process.exit(0); // up to date

  let ver = '?'; try { ver = JSON.parse(git(['show', `${upstream}:version.json`])).version || '?'; } catch {}
  let headline = ''; try { headline = (git(['show', `${upstream}:CHANGELOG.md`]).split('\n').find((l) => l.trim() && !l.startsWith('#') && !l.startsWith('Newest')) || '').trim(); } catch {}

  console.log(`UPDATE_AVAILABLE ${ver} (${behind} commit(s) behind) :: ${headline}`);
  console.log(`UPDATE_CMD git -C "${ROOT}" pull --ff-only`);
} catch {
  process.exit(0); // never block the skill on an update check
}

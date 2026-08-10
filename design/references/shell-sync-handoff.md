# Handing the shell to shell-sync (keep it fresh over time)

This skill **builds** the shell; Harsh's `shell-sync` skill **keeps it honest** — weekly it diffs
your shell against what shipped (drop-branch PRs on GitHub), updates it on your yes, manages
git-backed design versions that auto-merge production changes, and pushes the shell into Claude
Design (`/shell-sync storyboard`). shell-sync's stated prerequisite is *"the product needs a Claude
Design shell to exist"* — that shell is this skill's output.

**This skill = producer · shell-sync = maintainer + distributor + Claude-Design bridge.** Verified
against `shell-sync.zip` (Python, stdlib-only, profile-per-product).

## Produce the exact handoff (two generators, real contract)
```bash
cd ~/projects/lcnc-workspace/lcnc-backend/workspace/skills/bs-design-from-tb
# 1. self-contained, scrubbed shell (shell-sync needs one browser-openable HTML file)
node scripts/finalize-shell.mjs     products/<slug>/app-shell/shell-scaffold.html --slug <slug>
# 2. onboarding JSON in the exact shape `lib/onboard.py write` validates
node scripts/shell-sync-onboard.mjs --slug <slug>   # → app-shell/shell-sync-onboard.json
# 3. a paste-ready storyboard.SCREENS draft, pre-filled from the real sidebar
node scripts/screen-map-draft.mjs   products/<slug>/app-shell/shell-scaffold.html --slug <slug>
```

Then, **in the shell-sync install**:
```bash
python3 lib/onboard.py write <abs path>/products/<slug>/app-shell/shell-sync-onboard.json
# point its shell_source at the finalized shell (the JSON already does)
# paste the screen-map.draft.md SCREENS block into lib/storyboard.py, fill gate/verify, confirm
```

## What maps to what (checked against shell-sync's code)
| shell-sync onboard field (`lib/onboard.py` REQUIRED/optional) | Comes from your `product.config.json` |
|---|---|
| `slug`, `product_name`, `product_url` | slug · `product` · `liveUrl` |
| `ticket_prefix` (Jira key, e.g. `LCNC`) | `shellSync.ticketPrefix` |
| `repos[]` (owner/name) | `shellSync.repos` |
| `shared_repos[]` + `product_signals[]` | `shellSync.sharedRepos` + `shellSync.productSignals` |
| `drop_branch_patterns[]` (prod branches) | `shellSync.dropBranchPatterns` |
| `shell_source` (the HTML file) | the finalized `app-shell/shell-scaffold.html` |
| `storyboard.SCREENS` (`{slug,title,group,nav,gate,verify}`) | `screen-map.draft.md` (nav pre-filled; you set gate/verify) |

`shell-sync-onboard.mjs` mirrors onboard.py's own checks (repos must be `owner/name`; `product_signals`
required when `shared_repos` is set; `product_url` must be http), so it fails here with a clear message
instead of failing inside shell-sync.

## The one real structural gap to know
shell-sync boards **multiple screens** hidden behind `<sc-if>` gates in a single Claude Design shell.
This skill currently captures a **single surface** (e.g. LCA's Tests page). So:
- The captured shell is a valid shell-sync input, but only its one screen is "real"; the screen-map
  draft's other entries are nav stubs until you capture those screens too.
- To make a full multi-screen board, re-run `capture-shell.md` for each key screen and combine them
  (gated), or let shell-sync's own live capture fill the rest over time.
This is the honest boundary between "one high-fidelity surface" (this skill's strength) and "a full
gated multi-screen shell" (what shell-sync ultimately wants).

## Division of labour (no overlap)
| Concern | This skill | shell-sync |
|---|---|---|
| First capture of the real shell | ✅ | — (requires one to exist) |
| TB → high-fidelity explorations (switcher) | ✅ | — |
| Weekly diff vs shipped GitHub PRs · auto-merge into versions | — | ✅ |
| Version / publish / share · push into Claude Design (storyboard) | — | ✅ |

# Handing the shell to shell-sync (keep it fresh over time)

This skill **builds** the shell; Harsh's `shell-sync` skill **keeps it honest** — weekly it diffs
your shell against what shipped (drop-branch PRs on GitHub), updates it on your yes, manages
git-backed design versions that auto-merge production changes, and pushes the shell into Claude
Design (`/shell-sync storyboard`). shell-sync's stated prerequisite is *"the product needs a Claude
Design shell to exist"* — that shell is this skill's output.

**This skill = producer · shell-sync = maintainer + distributor + Claude-Design bridge.** Verified
against `shell-sync.zip` (Python, stdlib-only, profile-per-product).

## Produce the exact handoff (one command + the config JSON)
```bash
cd ~/.claude/skills/bstack-shell-creator-v3/design
# 1. onboarding JSON in the exact shape `lib/onboard.py write` validates
node scripts/shell-sync-onboard.mjs --slug <slug>   # → app-shell/shell-sync-onboard.json
# 2. COMPLETE screen-map + screenshots + @dsCard gallery, in one command
node scripts/handoff-to-sync.mjs    --slug <slug>   # → shell-sync-screens.json + shots/ + cards/
```
`handoff-to-sync.mjs` reads the multi-screen capture (`app-shell/screens/`) and:
- derives a **complete** `shell-sync-screens.json` (`{slug,title,group,nav,gate,verify}` for every
  screen, **filled from the capture — no manual paste, no gate/verify TODO**). Top-level screens
  verify on their heading; `detailFor` detail pages get a **panel-unique** verify + a best-effort
  row-click nav, so a missed click is reported as `NEEDS_SCREENSHOT`, never mislabelled.
- runs Harsh's `sync/lib/capture.mjs` **unmodified** against the plain-HTML `multiscreen-shell.html`
  (a tiny local static server + `PLAYWRIGHT_CORE`/`CHROME_PATH`), screenshotting each screen to
  `shots/`, then wraps each PNG into a self-contained `@dsCard` preview in `cards/` that the Claude
  Design pane indexes. `--no-shots` emits just the screen-map if you'd rather run the camera elsewhere.

Then, **in the shell-sync install**, register the product config:
```bash
python3 lib/onboard.py write <abs path>/products/<slug>/app-shell/shell-sync-onboard.json
# shell_source already points at the finalized shell; the screen-map + cards are produced above.
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
Two things that used to be gaps are now closed by the handoff above:
- **Multi-screen** — this skill captures *every* major screen (`capture-multiscreen.md`), not one
  surface, so the screen-map's entries are all real, not stubs.
- **Screenshots + cards** — `handoff-to-sync.mjs` drives shell-sync's own camera on our plain-HTML
  shell and emits the `@dsCard` gallery. No manual paste, no format conversion.

The **remaining** seam is deep-parse only: shell-sync's weekly diff *brain* (`index.py`/`match.py`)
and `storyboard.py`'s component scanner read Claude Design **`x-dc`** shells (`<sc-if>` gated,
computed styles), which our plain-HTML "photo" is not. So the camera and cards work on our shell, but
the automated "which component changed since last drop" reasoning still needs an `x-dc` export. That
boundary is inherent to keeping two shell formats; closing it would mean an `x-dc` emitter (a separate
project), not a bug to paper over here.

## Division of labour (no overlap)
| Concern | This skill | shell-sync |
|---|---|---|
| First capture of the real shell | ✅ | — (requires one to exist) |
| TB → high-fidelity explorations (switcher) | ✅ | — |
| Weekly diff vs shipped GitHub PRs · auto-merge into versions | — | ✅ |
| Version / publish / share · push into Claude Design (storyboard) | — | ✅ |
